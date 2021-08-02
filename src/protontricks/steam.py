import functools
import logging
import os
import string
import struct
import zlib
from pathlib import Path

import vdf

from .util import lower_dict

__all__ = (
    "COMMON_STEAM_DIRS", "SteamApp", "find_steam_path",
    "find_legacy_steam_runtime_path", "get_appinfo_sections",
    "get_tool_appid", "find_steam_compat_tool_app", "find_appid_proton_prefix",
    "find_proton_app", "get_steam_lib_paths", "get_compat_tool_dirs",
    "get_custom_compat_tool_installations_in_dir", "get_custom_compat_tool_installations",
    "find_current_steamid3", "get_appid_from_shortcut",
    "get_custom_windows_shortcuts", "get_steam_apps"
)

COMMON_STEAM_DIRS = [
    ".steam/steam",
    ".local/share/Steam"
]

logger = logging.getLogger("protontricks")


class SteamApp(object):
    """
    SteamApp represents an installed Steam app or whatever is close enough to
    one (eg. a custom Proton installation or a Windows shortcut with its own
    Proton prefix)
    """
    __slots__ = (
        "appid", "name", "prefix_path", "install_path", "required_tool_appid",
        "required_tool_app"
    )

    def __init__(
            self, name, install_path, prefix_path=None, appid=None,
            required_tool_appid=None):
        """
        :appid: App's appid
        :name: The app's human-readable name
        :prefix_path: Absolute path to where the app's Wine prefix *might*
                      exist.
        :app_path: Absolute path to app's installation directory
        :required_tool_appid: App ID required to run this application.
                              Usually corresponds to a Steam Runtime for
                              Proton installations.
        """
        self.appid = int(appid) if appid else None
        self.required_tool_appid = \
            int(required_tool_appid) if required_tool_appid else None

        self.name = name

        if prefix_path:
            self.prefix_path = Path(prefix_path)
        else:
            self.prefix_path = None

        self.install_path = Path(install_path)

        # Reference to another SteamApp will be added later if necessary,
        # once we have the full list of Steam apps
        self.required_tool_app = None

    @property
    def prefix_path_exists(self):
        """
        Returns True if the app has a Wine prefix directory that has been
        launched at least once
        """
        if not self.prefix_path:
            return False

        # 'pfx' directory is incomplete until the game has been launched
        # once, so check for 'pfx.lock' as well
        return (
            self.prefix_path.is_dir()
            and (self.prefix_path.parent / "pfx.lock").is_file()
        )

    def name_contains(self, s):
        """
        Returns True if the name contains the given substring.
        Both strings are normalized for easier searching before comparison.
        """
        def normalize_str(s):
            """
            Normalize the string to make it easier for human to
            perform a search by removing all symbols
            except ASCII digits and letters and turning it into lowercase
            """
            printable = set(string.printable) - set(string.punctuation)
            s = "".join([c for c in s if c in printable])
            s = s.lower()
            s = s.replace(" ", "")
            return s

        return normalize_str(s) in normalize_str(self.name)

    @property
    def is_proton(self):
        """
        Return True if this app is a Proton installation
        """
        # If the installation directory contains a file named "proton",
        # it's a Proton installation
        return (self.install_path / "proton").is_file()

    @property
    def is_tool(self):
        """
        Return True if this app is a tool rather an app.

        This is true for Proton and Steam Runtime installations.
        """
        return (self.install_path / "toolmanifest.vdf").is_file()

    @property
    def proton_dist_path(self):
        """
        Return path to the directory containing Proton binaries and libraries.
        None is returned if this app isn't a Proton installation or either
        directory doesn't exist.

        The directory is named either 'dist' or 'files'.

        'dist' is used by older Proton releases, and it is extracted from a
        separate 'proton_dist.tar' archive during first launch.
        'files' is used by newer Proton releases, and it already exists
        after the Steam app has been installed, requiring no first launch.
        """
        if not self.is_proton:
            return None

        try:
            # Prioritize 'files' directory if it exists.
            # If both directories exist, 'dist' is likely a leftover that
            # wasn't removed by Steam.
            return next(
                (self.install_path / name) for name in ("files", "dist")
                if (self.install_path / name).is_dir()
            )
        except StopIteration:
            return None

    @classmethod
    def from_appmanifest(cls, path, steam_lib_paths):
        """
        Parse appmanifest_X.acf file containing Steam app installation metadata
        and return a SteamApp object
        """
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            # This might occur if the appmanifest becomes corrupted
            # eg. due to running a Linux filesystem under Windows
            # In that case just skip it
            logger.warning(
                "Skipping malformed appmanifest %s", path
            )
            return None
        except PermissionError:
            # Skip the appmanifest if we can't read it.
            # Steam also seems to ignore unreadable app manifests, so do the
            # same here.
            logger.warning(
                "Skipping appmanifest %s due to insufficient permissions",
                path
            )
            return None

        try:
            vdf_data = lower_dict(vdf.loads(content))
        except SyntaxError:
            logger.warning("Skipping malformed appmanifest %s", path)
            return None

        try:
            app_state = vdf_data["appstate"]
        except KeyError:
            # Some appmanifest files may be empty. Ignore those.
            logger.info("Skipping empty appmanifest %s", path)
            return None

        # The app ID field can be named 'appID' or 'appid'.
        # 'appid' is more common, but certain appmanifest
        # files (created by old Steam clients?) also use 'appID'.
        #
        # Use case-insensitive field names to deal with these.
        app_state = lower_dict(app_state)
        appid = int(app_state["appid"])

        try:
            name = app_state["name"]
        except KeyError:
            # Older app installations also use `userconfig/name`
            name = app_state["userconfig"]["name"]

        # Proton prefix may exist on a different library
        prefix_path = find_appid_proton_prefix(
            appid=appid, steam_lib_paths=steam_lib_paths
        )

        install_path = Path(path).parent / "common" / app_state["installdir"]

        # Check if the app requires another app. This is the case with
        # newer versions of Proton, which use Steam Runtimes installed as
        # normal Steam apps
        try:
            required_tool_appid = _get_required_tool_appid(install_path)
        except (ValueError, SyntaxError):
            logger.warning(
                "Tool manifest for %s is empty or corrupted. You may need to "
                "reinstall the application.",
                name
            )
            return None

        return cls(
            appid=appid, name=name, prefix_path=prefix_path,
            install_path=install_path, required_tool_appid=required_tool_appid
        )


def _get_required_tool_appid(path):
    """
    Get the required tool app ID for the Proton installation at the given path

    :raises ValueError: Tool manifest is empty
    :raises SyntaxError: Tool manifest is corrupted
    """
    tool_manifest_path = path / "toolmanifest.vdf"
    try:
        tool_manifest_content = tool_manifest_path.read_text()

        if tool_manifest_content == "":
            raise ValueError("Tool manifest is empty")

        tool_manifest = lower_dict(vdf.loads(tool_manifest_content))

        return tool_manifest["manifest"].get("require_tool_appid", None)
    except FileNotFoundError:
        return None


def find_steam_path():
    """
    Try to discover default Steam dir using common locations and return the
    first one that matches

    Return (steam_path, steam_root), where steam_path points to
    "~/.steam/steam" (contains "appcache", "config" and "steamapps")
    and "~/.steam/root" (contains "ubuntu12_32" and "compatibilitytools.d")
    """
    def has_steamapps_dir(path):
        """
        Return True if the path either has a 'steamapps' or a 'SteamApps'
        subdirectory, False otherwise
        """
        # 'steamapps' is the usual name under Linux Steam installations
        # 'SteamApps' name appears in installations imported from Windows
        return (path / "steamapps").is_dir() or (path / "SteamApps").is_dir()

    def has_runtime_dir(path):
        return (path / "ubuntu12_32").is_dir()

    # as far as @admalledd can tell,
    # this should always be correct for the tools root:
    steam_root = Path.home() / ".steam" / "root"

    if not (steam_root / "ubuntu12_32").is_dir():
        # Check that runtime dir exists, if not make root=path and hope
        steam_root = None

    if os.environ.get("STEAM_DIR"):
        steam_path = Path(os.environ.get("STEAM_DIR"))
        if has_steamapps_dir(steam_path) and has_runtime_dir(steam_path):
            logger.info(
                "Found a valid Steam installation at %s.", steam_path
            )

            return steam_path, steam_path

        logger.error(
            "$STEAM_DIR was provided but didn't point to a valid Steam "
            "installation."
        )

        return None, None

    for steam_path in COMMON_STEAM_DIRS:
        # The common Steam directories are found inside the home directory
        steam_path = Path.home() / steam_path
        if has_steamapps_dir(steam_path):
            logger.info(
                "Found Steam directory at %s. You can also define Steam "
                "directory manually using $STEAM_DIR",
                steam_path
            )
            if not steam_root:
                steam_root = steam_path
            return steam_path, steam_root

    return None, None


def find_legacy_steam_runtime_path(steam_root):
    """
    Find the legacy Steam Runtime either using the STEAM_RUNTIME env or
    steam_root
    """
    env_steam_runtime = os.environ.get("STEAM_RUNTIME", "")

    if env_steam_runtime == "0":
        # User has disabled Steam Runtime
        logger.info("STEAM_RUNTIME is 0. Disabling Steam Runtime.")
        return None
    elif env_steam_runtime and Path(env_steam_runtime).is_dir():
        # User has a custom Steam Runtime
        logger.info(
            "Using custom Steam Runtime at %s", env_steam_runtime)
        return Path(env_steam_runtime)
    elif env_steam_runtime in ["1", ""]:
        # User has enabled Steam Runtime or doesn't have STEAM_RUNTIME set;
        # default to enabled Steam Runtime in either case
        steam_runtime_path = steam_root / "ubuntu12_32" / "steam-runtime"

        logger.info(
            "Using default Steam Runtime at %s", str(steam_runtime_path))
        return steam_runtime_path

    logger.error(
        "Path in STEAM_RUNTIME doesn't point to a valid Steam Runtime!")

    return None


APPINFO_STRUCT_HEADER = "<4sL"
APPINFO_STRUCT_SECTION = "<LLLLQ20sL"


def get_appinfo_sections(path):
    """
    Parse an appinfo.vdf file and return all the deserialized binary VDF
    objects inside it
    """
    # appinfo.vdf is not actually a (binary) VDF file, but a binary file
    # containing multiple binary VDF sections.
    # File structure based on comment from vdf developer:
    # https://github.com/ValvePython/vdf/issues/13#issuecomment-321700244
    data = path.read_bytes()
    i = 0

    # Parse the header
    header_size = struct.calcsize(APPINFO_STRUCT_HEADER)
    magic, universe = struct.unpack(
        APPINFO_STRUCT_HEADER, data[0:header_size]
    )

    i += header_size

    if magic != b"'DV\x07":
        raise SyntaxError("Invalid file magic number")

    sections = []

    section_size = struct.calcsize(APPINFO_STRUCT_SECTION)
    while True:
        # We don't need any of the fields besides 'entry_size',
        # which is used to determine the length of the variable-length VDF
        # field.
        # Still, here they are for posterity's sake.
        (appid, entry_size, infostate, last_updated, access_token,
         sha_hash, change_number) = struct.unpack(
            APPINFO_STRUCT_SECTION, data[i:i+section_size])
        vdf_section_size = entry_size - 40

        i += section_size

        vdf_d = vdf.binary_loads(data[i:i+vdf_section_size])
        vdf_d = lower_dict(vdf_d)
        sections.append(vdf_d)

        i += vdf_section_size

        if i == len(data) - 4:
            return sections


def get_tool_appid(compat_tool_name, appinfo_path):
    """
    Get the App ID for compatibility tool by the compat tool name
    used in STEAM_DIR/config/config.vdf
    """
    # Parse all the individual VDF sections in appinfo.vdf to a list
    vdf_sections = get_appinfo_sections(appinfo_path)

    for section in vdf_sections:
        if not section.get("appinfo", {}).get("extended", {}).get(
                "compat_tools", None):
            continue

        compat_tools = section["appinfo"]["extended"]["compat_tools"]

        for default_name, entry in compat_tools.items():
            # A single compatibility tool may have multiple valid names
            # eg. "proton_316" and "proton_316_beta"
            aliases = [default_name]

            # Each compat tool entry can also contain an 'aliases' field
            # with a different compat tool name
            if "aliases" in entry:
                # All of the appinfo.vdf files encountered so far
                # only have a single string inside the "aliases" field,
                # but let's assume the field could be a list of strings
                # as well
                if isinstance(entry["aliases"], str):
                    aliases.append(entry["aliases"])
                elif isinstance(entry["aliases"], list):
                    aliases += entry["aliases"]
                else:
                    raise TypeError(
                        "Unexpected type {} for 'fields' in "
                        "appinfo.vdf".format(type(aliases))
                    )

            if compat_tool_name in aliases:
                return entry["appid"]

    logger.error("Could not find the Steam Play manifest in appinfo.vdf")

    return None


def find_steam_compat_tool_app(steam_path, steam_apps, appid=None):
    """
    Get the current compatibility tool used by Steam and
    return a SteamApp object

    If 'appid' is provided, try to find the app-specific compatibility tool
    if one is configured

    The compatibility tool *may* not be a Proton installation. This can be
    checked using `SteamApp.is_proton`.
    """
    # 1. Find the name of compatibility tool in use
    #    from STEAM_DIR/config/config.vdf
    # 2. If the compatibility tool's name can be found directly
    #    in the list of apps we discovered earlier, return that
    # 3. ...or if the name can't be found that way, parse
    #    the file in STEAM_DIR/appcache/appinfo.vdf to find the compatibility
    #    tool's App ID
    config_vdf_path = steam_path / "config" / "config.vdf"
    content = config_vdf_path.read_text()

    vdf_data = lower_dict(vdf.loads(content))
    # ToolMapping seems to be used in older Steam beta releases
    try:
        tool_mapping = (
            vdf_data["installconfigstore"]["software"]["valve"]["steam"]
                    ["toolmapping"]
        )
    except KeyError:
        tool_mapping = {}

    # CompatToolMapping seems to be the name used in newer Steam releases
    # We'll prioritize this if it exists
    try:
        compat_tool_mapping = (
            vdf_data["installconfigstore"]["software"]["valve"]["steam"]
                    ["compattoolmapping"]
        )
    except KeyError:
        compat_tool_mapping = {}

    compat_tool_name = None

    # The name of potential names in order of priority
    potential_names = [
        compat_tool_mapping.get(str(appid), {}).get("name", None),
        compat_tool_mapping.get("0", {}).get("name", None),
        tool_mapping.get(str(appid), {}).get("name", None),
        tool_mapping.get("0", {}).get("name", None)
    ]
    # Get the first name that was valid
    try:
        compat_tool_name = next(name for name in potential_names if name)
    except StopIteration:
        logger.error(
            "No compatibility tool found in config.vdf. "
            "Have you enabled Steam Play for all titles under Steam settings?"
        )
        return None

    # We've got the name from config.vdf,
    # now there are two possible ways to find the installation
    # 1. It's a custom compatibility tool, and we simply need to find
    #    a SteamApp by its internal name
    # 2. It's a production Proton installation, in which case we need
    #    to parse a binary configuration file to find the App ID

    # Let's try option 1 first
    try:
        app = next(app for app in steam_apps if app.name == compat_tool_name)
        logger.info(
            "Found active custom compatibility tool: %s", app.name
        )
        return app
    except StopIteration:
        pass

    # Try option 2:
    # Find the corresponding App ID from <steam_path>/appcache/appinfo.vdf
    appinfo_path = steam_path / "appcache" / "appinfo.vdf"
    tool_appid = get_tool_appid(compat_tool_name, appinfo_path)

    if not tool_appid:
        logger.error(
            "Could not find compatibility tool's App ID from appinfo.vdf"
        )
        return None

    # We've now got the appid. Return the corresponding SteamApp
    try:
        app = next(app for app in steam_apps if app.appid == tool_appid)
        logger.info(
            "Found active compatibility tool: %s", app.name
        )
        return app
    except StopIteration:
        return None


def find_appid_proton_prefix(appid, steam_lib_paths):
    """
    Find the Proton prefix for the app by its App ID

    Proton prefix and the game installation itself can exist on different
    Steam libraries, making a search necessary
    """
    def get_prefix_modify_time(prefix_path):
        """
        Get the prefix modification time for sorting purposes.
        The newest modification time corresponds to the most recently
        used Proton prefix
        """
        try:
            # 'pfx.lock' is modified on game launch
            return (prefix_path.parent / "pfx.lock").stat().st_mtime
        except FileNotFoundError:
            return 0

    candidates = []

    for path in steam_lib_paths:
        # 'steamapps' portion of the path can also be 'SteamApps'
        for steamapps_part in ("steamapps", "SteamApps"):
            prefix_path = \
                path / steamapps_part / "compatdata" / str(appid) / "pfx"
            if prefix_path.is_dir():
                candidates.append(prefix_path)

    if len(candidates) > 1:
        # If we have more than one possible prefix path, use the one
        # with the most recent modification date
        logger.info(
            "Multiple compatdata directories found for app %s", appid
        )
        candidates.sort(key=get_prefix_modify_time)
        candidates.reverse()

    if candidates:
        return candidates[0]

    return None


def find_proton_app(steam_path, steam_apps, appid=None):
    """
    Find the Proton app, using either $PROTON_VERSION or the one
    currently configured in Steam

    If 'appid' is provided, use it to find the app-specific Proton installation
    if one is configured
    """
    if os.environ.get("PROTON_VERSION"):
        proton_version = os.environ.get("PROTON_VERSION")
        try:
            proton_app = next(
                app for app in steam_apps if app.name == proton_version)
            logger.info(
                "Found requested Proton version: %s", proton_app.name
            )
            return proton_app
        except StopIteration:
            logger.error(
                "$PROTON_VERSION was set but matching Proton installation "
                "could not be found."
            )
            return None

    tool_app = find_steam_compat_tool_app(
        steam_path=steam_path, steam_apps=steam_apps, appid=appid)

    if not tool_app:
        logger.error(
            "Active Proton installation could not be found automatically."
        )
        return None

    # Check that it's actually a Proton app; Protontricks doesn't handle
    # other compatibility tools.
    if not tool_app.is_proton:
        logger.error(
            "Active compatibility tool was found, but it's not a Proton "
            "installation supported by Protontricks."
        )
        return None

    logger.info("Active compatibility tool is a Proton installation")

    return tool_app


def get_steam_lib_paths(steam_path):
    """
    Return a list of any Steam directories including any user-added
    Steam library folders
    """
    def parse_library_folders(data):
        """
        Parse the Steam library folders in the VDF file using the given data
        """
        vdf_data = lower_dict(vdf.loads(data))
        # Library folders have integer field names in ascending order
        library_entries = [
            value for key, value in vdf_data["libraryfolders"].items()
            if key.isdigit()
        ]
        library_folders = []

        for value in library_entries:
            if isinstance(value, dict):
                # Library data is stored in a dict in newer Steam releases
                library_folders.append(Path(value["path"]))
            else:
                # Older releases just store the library path as a string
                # and nothing else
                library_folders.append(Path(value))

        logger.info(
            "Found %d Steam library folders", len(library_folders)
        )
        return library_folders

    # Try finding Steam library folders using libraryfolders.vdf in Steam root
    if (steam_path / "steamapps").is_dir():
        folders_vdf_path = steam_path / "steamapps" / "libraryfolders.vdf"
    elif (steam_path / "SteamApps").is_dir():
        folders_vdf_path = steam_path / "SteamApps" / "libraryfolders.vdf"

    try:
        library_folders = parse_library_folders(folders_vdf_path.read_text())
    except OSError:
        # libraryfolders.vdf doesn't exist; maybe no Steam library folders
        # are set?
        library_folders = []
    except SyntaxError as exc:
        raise ValueError(
            "Library folder configuration file {} is corrupted".format(
                folders_vdf_path
            )
        ) from exc

    return [steam_path] + library_folders


def get_compat_tool_dirs(steam_root):
    """
    Return a list of compatibility tool directories in order from
    directories with lowest precedence
    """
    # The path list is ordered by priority, starting from Proton apps
    # with the lowest precedence ('/usr/share/steam/compatibilitytools.d')
    paths = [
        Path("/usr/share/steam/compatibilitytools.d"),
        Path("/usr/local/share/steam/compatibilitytools.d"),
    ]
    extra_ct_paths_env = os.getenv("STEAM_EXTRA_COMPAT_TOOLS_PATHS")
    if extra_ct_paths_env:
        paths += [Path(path) for path in extra_ct_paths_env.split(os.pathsep)]
    paths += [steam_root / "compatibilitytools.d"]

    return paths


def get_custom_compat_tool_installations_in_dir(compat_tool_dir):
    """
    Return a list of custom compatibility tools in the given directory
    as a list of SteamApp objects
    """
    if not compat_tool_dir.is_dir():
        return []

    comptool_files = list(compat_tool_dir.glob("*/compatibilitytool.vdf"))
    comptool_files += list(compat_tool_dir.glob("compatibilitytool.vdf"))

    custom_tool_apps = []

    for vdf_path in comptool_files:
        content = vdf_path.read_text()

        try:
            vdf_data = vdf.loads(content)
        except SyntaxError:
            logger.warning(
                "Compatibility tool declaration at %s is corrupted. You may "
                "need to reinstall the application.",
                vdf_path
            )
            continue

        # Traverse to 'compatibilitytools/compat_tools' in a case-insensitive
        # way. This is done because we can't turn all keys recursively to
        # lowercase from the get-go; the app name is stored as a key.
        compat_tools = {k.lower(): v for k, v in vdf_data.items()}
        compat_tools = compat_tools["compatibilitytools"]
        compat_tools = {
            k.lower(): v for k, v in compat_tools.items()
        }
        compat_tools = compat_tools["compat_tools"]
        internal_name = list(compat_tools.keys())[0]
        tool_info = compat_tools[internal_name]

        # We can now convert the remainder into lowercase
        tool_info = lower_dict(tool_info)

        install_path_name = tool_info["install_path"]
        from_oslist = tool_info["from_oslist"]
        to_oslist = tool_info["to_oslist"]

        if from_oslist != "windows" or to_oslist != "linux":
            continue

        # Installation path can be relative if the VDF was in
        # 'compatibilitytools.d/'
        # or '.' if the VDF was in 'compatibilitytools.d/TOOL_NAME'
        if install_path_name == ".":
            install_path = vdf_path.parent
        else:
            install_path = compat_tool_dir / install_path_name

        # Check if the app requires another app. This is the case with
        # newer versions of Proton, which use Steam Runtimes installed as
        # normal Steam apps
        try:
            required_tool_appid = _get_required_tool_appid(install_path)
        except (ValueError, SyntaxError):
            logger.warning(
                "Tool manifest for %s is empty or corrupted. You may need to "
                "reinstall the application.",
                install_path.name
            )
            continue

        custom_tool_apps.append(
            SteamApp(
                name=internal_name, install_path=install_path,
                required_tool_appid=required_tool_appid
            )
        )

    return custom_tool_apps


def get_custom_compat_tool_installations(steam_root):
    """
    Get a list of all custom compatibility tools as a list of SteamApp objects
    """
    custom_tool_apps = {}
    for dir_ in get_compat_tool_dirs(steam_root=steam_root):
        for tool_app in get_custom_compat_tool_installations_in_dir(dir_):
            # If another tool app exists with the same name, it will
            # be replaced with an installation that has higher precedence
            # here
            custom_tool_apps[tool_app.name] = tool_app

    # Return the list of tool apps as a list
    custom_tool_apps = list(custom_tool_apps.values())

    return custom_tool_apps


def find_current_steamid3(steam_path):
    """
    Find the SteamID3 of the currently logged in Steam user
    """
    def to_steamid3(steamid64):
        """Convert a SteamID64 into the SteamID3 format"""
        return int(steamid64) & 0xffffffff

    loginusers_path = steam_path / "config" / "loginusers.vdf"
    try:
        content = loginusers_path.read_text()
        vdf_data = lower_dict(vdf.loads(content))
    except IOError:
        logger.warning(
            "Couldn't determine the currently logged-in Steam user. Custom "
            "shortcuts won't be detected."
        )
        return None

    user_datas = [
        (user_id, lower_dict(user_data))
        for user_id, user_data in vdf_data["users"].items()
    ]
    users = [
        {
            "steamid3": to_steamid3(user_id),
            "account_name": user_data["accountname"],
            "timestamp": user_data.get("timestamp", 0)
        }
        for user_id, user_data in user_datas
    ]

    # Return the user with the highest timestamp, as that's likely to be the
    # currently logged-in user
    if users:
        user = max(users, key=lambda u: u["timestamp"])
        logger.info(
            "Currently logged-in Steam user: %s", user["account_name"]
        )
        return user["steamid3"]

    return None


def get_appid_from_shortcut(target, name):
    """
    Get the identifier used for the Proton prefix from a shortcut's
    target and name
    """
    # First, calculate the screenshot ID Steam uses for shortcuts
    data = b"".join([
        target.encode("utf-8"),
        name.encode("utf-8")
    ])
    result = zlib.crc32(data) & 0xffffffff
    result = result | 0x80000000
    result = (result << 32) | 0x02000000

    # Derive the prefix ID from the screenshot ID
    return result >> 32


def get_custom_windows_shortcuts(steam_path):
    """
    Get a list of custom shortcuts for Windows applications as a list
    of SteamApp objects
    """
    # Get the Steam ID3 for the currently logged-in user
    steamid3 = find_current_steamid3(steam_path)

    shortcuts_path = \
        steam_path / "userdata" / str(steamid3) / "config" / "shortcuts.vdf"

    try:
        content = shortcuts_path.read_bytes()
        vdf_data = lower_dict(vdf.binary_loads(content))
    except IOError:
        logger.info(
            "Couldn't find custom shortcuts. Maybe none have been created yet?"
        )
        return []

    steam_apps = []

    for shortcut_id, shortcut_data in vdf_data["shortcuts"].items():
        # The "exe" field can also be "Exe". Account for this by making
        # all field names lowercase
        shortcut_data = lower_dict(shortcut_data)
        shortcut_id = int(shortcut_id)

        if "appid" in shortcut_data:
            appid = shortcut_data["appid"] & 0xffffffff
        else:
            appid = get_appid_from_shortcut(
                target=shortcut_data["exe"], name=shortcut_data["appname"]
            )

        prefix_path = \
            steam_path / "steamapps" / "compatdata" / str(appid) / "pfx"
        install_path = Path(shortcut_data["startdir"].strip('"'))

        if not prefix_path.is_dir():
            continue

        steam_apps.append(
            SteamApp(
                appid=appid,
                name="Non-Steam shortcut: {}".format(shortcut_data["appname"]),
                prefix_path=prefix_path, install_path=install_path
            )
        )

    logger.info(
        "Found %d Steam shortcuts running using Steam compatibility tools",
        len(steam_apps)
    )

    return steam_apps


def _link_tool_apps(steam_apps):
    """
    Check which Steam apps require other Steam apps and add the corresponding
    references
    """
    appid2steam_app = {steam_app.appid: steam_app for steam_app in steam_apps}

    for steam_app in steam_apps:
        if steam_app.required_tool_appid:
            steam_app.required_tool_app = \
                appid2steam_app.get(steam_app.required_tool_appid)


def get_steam_apps(steam_root, steam_path, steam_lib_paths):
    """
    Find all the installed Steam apps and return them as a list of SteamApp
    objects
    """
    steam_apps = []

    for path in steam_lib_paths:
        appmanifest_paths = []
        is_lowercase = (path / "steamapps").is_dir()
        is_mixedcase = (path / "SteamApps").is_dir()

        if is_lowercase:
            appmanifest_paths = path.glob("steamapps/appmanifest_*.acf")
        elif is_mixedcase:
            appmanifest_paths = path.glob("SteamApps/appmanifest_*.acf")

        if is_lowercase and is_mixedcase:
            # 'steamapps' and 'SteamApps' may both map to the same
            # directory if the file system is case-insensitive.
            # Check that we're actually dealing with more than one directory
            # before printing a warning.
            is_case_sensitive_fs = sum(
                1 for path in path.glob("*")
                if path.name.lower() == "steamapps"
            ) >= 2

            if is_case_sensitive_fs:
                # Log a warning if both 'steamapps' and 'SteamApps' directories
                # exist, as both Protontricks and Steam client have problems
                # dealing with it (see issue #51)
                logger.warning(
                    "Both 'steamapps' and 'SteamApps' directories were found "
                    "at %s. 'SteamApps' directory should be removed to "
                    "prevent issues with app and Proton discovery.",
                    str(path)
                )

        for manifest_path in appmanifest_paths:
            steam_app = SteamApp.from_appmanifest(
                manifest_path, steam_lib_paths=steam_lib_paths
            )
            if steam_app:
                steam_apps.append(steam_app)

    # Get the custom compatibility tools and non-Steam shortcuts as well
    steam_apps += get_custom_compat_tool_installations(steam_root=steam_root)
    steam_apps += get_custom_windows_shortcuts(steam_path=steam_path)

    # Exclude games that haven't been launched yet
    steam_apps = [
        app for app in steam_apps
        if app.prefix_path_exists or app.is_proton or app.is_tool
    ]

    # Populate the `SteamApp.required_tool_app` parameter for Steam apps
    # which rely on other Steam apps
    _link_tool_apps(steam_apps)

    # Sort the apps by their names
    steam_apps.sort(key=lambda app: app.name)

    return steam_apps
