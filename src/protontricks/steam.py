import os
import string
import re
import binascii
import struct
import glob
import logging
import vdf

__all__ = (
    "COMMON_STEAM_DIRS", "SteamApp", "find_steam_path",
    "find_steam_proton_app", "find_proton_app", "find_steam_runtime_path",
    "get_steam_lib_paths", "get_steam_apps", "get_custom_proton_installations"
)

COMMON_STEAM_DIRS = [
    os.path.join(os.environ.get("HOME"), ".steam", "steam"),
    os.path.join(os.environ.get("HOME"), ".local", "share", "Steam")
]

logger = logging.getLogger("protontricks")


class SteamApp(object):
    """
    SteamApp represents an installed Steam app
    """
    __slots__ = ("appid", "name", "prefix_path", "install_path")

    def __init__(self, name, install_path, prefix_path=None, appid=None):
        """
        :appid: App's appid
        :name: The app's human-readable name
        :prefix_path: Absolute path to where the app's Wine prefix *might*
                      exist.
        :app_path: Absolute path to app's installation directory
        """
        self.appid = int(appid) if appid else None
        self.name = name
        self.prefix_path = prefix_path
        self.install_path = install_path

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
            os.path.exists(self.prefix_path)
            and os.path.exists(os.path.join(self.prefix_path, "..", "pfx.lock"))
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
        return os.path.exists(os.path.join(self.install_path, "proton"))

    @classmethod
    def from_appmanifest(cls, path):
        """
        Parse appmanifest_X.acf file containing Steam app installation metadata
        and return a SteamApp object
        """
        with open(path, "r") as f:
            try:
                content = f.read()
            except UnicodeDecodeError:
                # This might occur if the appmanifest becomes corrupted
                # eg. due to running a Linux filesystem under Windows
                # In that case just skip it
                logger.warning(
                    "Skipping malformed appmanifest {}".format(path)
                )
                return None

        try:
            vdf_data = vdf.loads(content)
        except SyntaxError:
            logger.warning("Skipping malformed appmanifest {}".format(path))
            return None

        try:
            app_state = vdf_data["AppState"]
        except KeyError:
            # Some appmanifest files may be empty. Ignore those.
            logger.info("Skipping empty appmanifest {}".format(path))
            return None

        appid = int(app_state["appid"])
        name = app_state["name"]
        prefix_path = os.path.join(
            os.path.split(path)[0], "compatdata", str(appid), "pfx")

        install_path = os.path.join(
            os.path.split(path)[0], "common", app_state["installdir"])

        return cls(
            appid=appid, name=name, prefix_path=prefix_path,
            install_path=install_path)


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
        return (
            # 'steamapps' is the usual name under Linux Steam installations
            os.path.isdir(os.path.join(path, "steamapps"))
            # 'SteamApps' name appears in installations imported from Windows
            or os.path.isdir(os.path.join(path, "SteamApps"))
        )

    # as far as @admalledd can tell,
    # this should always be correct for the tools root:
    steam_root = os.path.join(os.path.expanduser("~"), ".steam", "root")

    if not os.path.isdir(os.path.join(steam_root, "ubuntu12_32")):
        # Check that runtime dir exists, if not make root=path and hope
        steam_root = None

    if os.environ.get("STEAM_DIR"):
        steam_path = os.environ.get("STEAM_DIR")
        if has_steamapps_dir(steam_path):
            logger.info(
                "Found a valid Steam installation at {}.".format(steam_path)
            )

            if not steam_root:
                steam_root = steam_path
            return steam_path, steam_root

        logger.error(
            "$STEAM_DIR was provided but didn't point to a valid Steam "
            "installation."
        )

        return None

    for steam_path in COMMON_STEAM_DIRS:
        if has_steamapps_dir(steam_path):
            logger.info(
                "Found Steam directory at {}. You can also define Steam "
                "directory manually using $STEAM_DIR".format(steam_path)
            )
            if not steam_root:
                steam_root = steam_path
            return steam_path, steam_root


def find_steam_runtime_path(steam_root):
    """
    Find the Steam Runtime either using the STEAM_RUNTIME env or
    steam_root
    """
    env_steam_runtime = os.environ.get("STEAM_RUNTIME", "")

    if env_steam_runtime == "0":
        # User has disabled Steam Runtime
        logger.info("STEAM_RUNTIME is 0. Disabling Steam Runtime.")
        return None
    elif os.path.isdir(env_steam_runtime):
        # User has a custom Steam Runtime
        logger.info(
            "Using custom Steam Runtime at %s", env_steam_runtime)
        return env_steam_runtime
    elif env_steam_runtime in ["1", ""]:
        # User has enabled Steam Runtime or doesn't have STEAM_RUNTIME set;
        # default to enabled Steam Runtime in either case
        steam_runtime_path = os.path.join(
            steam_root, "ubuntu12_32", "steam-runtime")

        logger.info(
            "Using default Steam Runtime at %s", steam_runtime_path)
        return steam_runtime_path

    logger.error(
        "Path in STEAM_RUNTIME doesn't point to a valid Steam Runtime!")

    return None


def find_steam_proton_app(steam_path, steam_apps, appid=None):
    """
    Get the current Proton installation used by Steam
    and return a SteamApp object

    If 'appid' is provided, try to find the app-specific Proton installation
    if one is configured
    """
    # 1. Find the name of Proton installation in use
    #    from STEAM_DIR/config/config.vdf
    # 2. If the Proton installation's name can be found directly
    #    in the list of apps we discovered earlier, return that
    # 3. ...or if the name can't be found that way, parse
    #    the file in STEAM_DIR/appcache/appinfo.vdf to find the Proton
    #    installation's App ID
    config_vdf_path = os.path.join(steam_path, "config", "config.vdf")

    with open(config_vdf_path, "r") as f:
        content = f.read()

    vdf_data = vdf.loads(content)
    # ToolMapping seems to be used in older Steam beta releases
    try:
        tool_mapping = (
            vdf_data["InstallConfigStore"]["Software"]["Valve"]["Steam"]
                    ["ToolMapping"]
        )
    except KeyError:
        tool_mapping = {}

    # CompatToolMapping seems to be the name used in newer Steam releases
    # We'll prioritize this if it exists
    try:
        compat_tool_mapping = (
            vdf_data["InstallConfigStore"]["Software"]["Valve"]["Steam"]
                    ["CompatToolMapping"]
        )
    except KeyError:
        compat_tool_mapping = {}

    name = None

    # The name of potential names in order of priority
    potential_names = [
        compat_tool_mapping.get(str(appid), {}).get("name", None),
        compat_tool_mapping.get("0", {}).get("name", None),
        tool_mapping.get(str(appid), {}).get("name", None),
        tool_mapping.get("0", {}).get("name", None)
    ]
    # Get the first name that was valid
    try:
        name = next(name for name in potential_names if name)
    except StopIteration:
        logger.error("No Proton installation found in config.vdf")
        return None

    # We've got the name,
    # now there are two possible ways to find the installation
    # 1. It's a custom Proton installation, and we simply need to find
    #    a SteamApp by its internal name
    # 2. It's a production Proton installation, in which case we need
    #    to parse a binary configuration file to find the App ID

    # Let's try option 1 first
    try:
        app = next(app for app in steam_apps if app.name == name)
        logger.info(
            "Found active custom Proton installation: {}".format(app.name)
        )
        return app
    except StopIteration:
        pass

    # Try option 2:
    # Find the corresponding App ID from <steam_path>/appcache/appinfo.vdf
    appinfo_path = os.path.join(steam_path, "appcache", "appinfo.vdf")

    with open(appinfo_path, "rb") as f:
        appinfo = str(binascii.hexlify(f.read()), "utf-8")

    # In ASCII, the substring we're looking for looks like this
    # ```
    # proton_316_beta..appid.
    # ```
    appid_regex = "({name_ascii}0002617070696400)([a-z0-9]{{8}})".format(
        name_ascii=str(binascii.hexlify(bytes(name, "utf-8")), "utf-8")
    )
    # The second group contains the App ID as a 32-bit integer in little-endian
    proton_appid = re.search(appid_regex, appinfo).group(2)
    proton_appid = struct.unpack("<I", binascii.unhexlify(proton_appid))[0]

    # We've now got the appid. Return the corresponding SteamApp
    try:
        app = next(app for app in steam_apps if app.appid == proton_appid)
        logger.info(
            "Found active Proton installation: {}".format(app.name)
        )
        return app
    except StopIteration:
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
                 "Found requested Proton version: {}".format(proton_app.name)
            )
            return proton_app
        except StopIteration:
            logger.error(
                "$PROTON_VERSION was set but matching Proton installation "
                "could not be found."
            )
            return None

    proton_app = find_steam_proton_app(
        steam_path=steam_path, steam_apps=steam_apps, appid=appid)

    if not proton_app:
        logger.error(
            "Active Proton installation could not be found automatically."
        )

    return proton_app


def get_steam_lib_paths(steam_path):
    """
    Return a list of any Steam directories including any user-added
    Steam library folders
    """
    def parse_library_folders(data):
        """
        Parse the Steam library folders in the VDF file using the given data
        """
        # VDF key & value pairs have the following syntax:
        # \t"<KEY>"\t\t"<VALUE>"
        pattern = re.compile(r'\t"([^"]*)"\t\t"([^"]*)"')

        lines = data.split("\n")

        # Skip the header and the last line
        lines = lines[2:]
        lines = lines[:-2]

        library_folders = []

        for line in lines:  # Skip the header and the last line
            match = pattern.search(line)
            key, value = match.group(1), match.group(2)

            # Keys corresponding to library folders are integers. Other keys
            # we can skip.
            try:
                key = int(key)
            except ValueError:
                continue

            library_folders.append(value)

        logger.info(
            "Found {} Steam library folders".format(len(library_folders))
        )
        return library_folders

    # Try finding Steam library folders using libraryfolders.vdf in Steam root
    if os.path.isdir(os.path.join(steam_path, "steamapps")):
        folders_vdf_path = os.path.join(
            steam_path, "steamapps", "libraryfolders.vdf")
    elif os.path.isdir(os.path.join(steam_path, "SteamApps")):
        folders_vdf_path = os.path.join(
            steam_path, "SteamApps", "libraryfolders.vdf")

    try:
        with open(folders_vdf_path, "r") as f:
            library_folders = parse_library_folders(f.read())
    except OSError:
        # libraryfolders.vdf doesn't exist; maybe no Steam library folders
        # are set?
        library_folders = []

    return [steam_path] + library_folders


def get_custom_proton_installations(steam_root):
    """
    Return a list of custom Proton installations as a list of SteamApp objects
    """
    comp_root = os.path.join(steam_root, "compatibilitytools.d")

    if not os.path.isdir(comp_root):
        return []

    comptool_files = glob.glob(
        os.path.join(comp_root, "*", "compatibilitytool.vdf")
    )
    comptool_files += glob.glob(
        os.path.join(comp_root, "compatibilitytool.vdf")
    )

    custom_proton_apps = []

    for vdf_path in comptool_files:
        with open(vdf_path, "r") as f:
            content = f.read()

        vdf_data = vdf.loads(content)
        internal_name = list(
            vdf_data["compatibilitytools"]["compat_tools"].keys())[0]
        tool_info = vdf_data["compatibilitytools"]["compat_tools"][
            internal_name]

        install_path = tool_info["install_path"]
        from_oslist = tool_info["from_oslist"]
        to_oslist = tool_info["to_oslist"]

        if from_oslist != "windows" or to_oslist != "linux":
            continue

        # Installation path can be relative if the VDF was in
        # 'compatibilitytools.d/'
        # or '.' if the VDF was in 'compatibilitytools.d/TOOL_NAME'
        if install_path == ".":
            install_path = os.path.dirname(vdf_path)
        else:
            install_path = os.path.join(comp_root, install_path)

        custom_proton_apps.append(
            SteamApp(name=internal_name, install_path=install_path)
        )

    return custom_proton_apps


def get_steam_apps(steam_root, steam_lib_dirs):
    """
    Find all the installed Steam apps and return them as a list of SteamApp
    objects
    """
    steam_apps = []

    for path in steam_lib_dirs:
        if os.path.isdir(os.path.join(path, "steamapps")):
            appmanifest_paths = glob.glob(
                os.path.join(path, "steamapps", "appmanifest_*.acf")
            )
        elif os.path.isdir(os.path.join(path, "SteamApps")):
            appmanifest_paths = glob.glob(
                os.path.join(path, "SteamApps", "appmanifest_*.acf")
            )

        for path in appmanifest_paths:
            steam_app = SteamApp.from_appmanifest(path)
            if steam_app:
                steam_apps.append(steam_app)

    # Get the custom Proton installations as well
    steam_apps += get_custom_proton_installations(steam_root=steam_root)

    # Exclude games that haven't been launched yet
    steam_apps = [
        app for app in steam_apps if app.prefix_path_exists or app.is_proton
    ]

    # Sort the apps by their names
    steam_apps.sort(key=lambda app: app.name)

    return steam_apps
