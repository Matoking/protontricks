import locale
import logging
import os
import shlex
import shutil
import stat
import tempfile
from pathlib import Path
from subprocess import DEVNULL, PIPE, Popen, TimeoutExpired, check_output, run

import pkg_resources

__all__ = (
    "SUPPORTED_STEAM_RUNTIMES", "OS_RELEASE_PATHS", "lower_dict",
    "is_steam_deck", "get_legacy_runtime_library_paths",
    "get_host_library_paths", "RUNTIME_ROOT_GLOB_PATTERNS",
    "get_runtime_library_paths", "WINE_SCRIPT_TEMPLATE",
    "get_cache_dir", "create_wine_bin_dir", "run_command"
)

logger = logging.getLogger("protontricks")

SUPPORTED_STEAM_RUNTIMES = [
    # Old names
    "Steam Linux Runtime - Soldier",
    "Steam Linux Runtime - Sniper",

    # New names
    "Steam Linux Runtime 2.0 (soldier)",
    "Steam Linux Runtime 3.0 (sniper)"
]

OS_RELEASE_PATHS = [
    "/run/host/os-release",  # The host file if we're inside a Flatpak sandbox
    "/etc/os-release"
]


def lower_dict(d):
    """
    Return a copy of the dictionary with all keys recursively converted to
    lowercase.

    This is mainly used when dealing with Steam VDF files, as those tend to
    have either CamelCase or lowercase keys depending on the version.
    """
    def _lower_value(value):
        if not isinstance(value, dict):
            return value

        return {k.lower(): _lower_value(v) for k, v in value.items()}

    return {k.lower(): _lower_value(v) for k, v in d.items()}


def is_steam_deck():
    """
    Check if we're running on a Steam Deck
    """
    for path in OS_RELEASE_PATHS:
        try:
            lines = Path(path).read_text("utf-8").split("\n")
        except FileNotFoundError:
            continue

        if "ID=steamos" in lines and "VARIANT_ID=steamdeck" in lines:
            logger.info("The current device is a Steam Deck")
            return True

    return False


def get_legacy_runtime_library_paths(legacy_steam_runtime_path, proton_app):
    """
    Get LD_LIBRARY_PATH value to use when running a command using Steam Runtime
    """
    steam_runtime_paths = check_output([
        str(legacy_steam_runtime_path / "run.sh"),
        "--print-steam-runtime-library-paths"
    ])
    steam_runtime_paths = str(steam_runtime_paths, "utf-8")
    # Add Proton installation directory first into LD_LIBRARY_PATH
    # so that libwine.so.1 is picked up correctly (see issue #3)
    return "".join([
        str(proton_app.proton_dist_path / "lib"), os.pathsep,
        str(proton_app.proton_dist_path / "lib64"), os.pathsep,
        steam_runtime_paths
    ])


def get_host_library_paths():
    """
    Get host library paths to use when creating the LD_LIBRARY_PATH environment
    variable for use with newer Steam Runtime installations when *not*
    using bwrap
    """
    # The traditional Steam Runtime does the following when running the
    # `run.sh --print-steam-runtime-library-paths` command.
    # Since that command is unavailable with newer Steam Runtime releases,
    # do it ourselves here.
    result = run(
        ["/sbin/ldconfig", "-XNv"],
        check=True, stdout=PIPE, stderr=PIPE
    )
    lines = result.stdout.decode("utf-8").split("\n")
    paths = [
        line.split(":")[0] for line in lines
        if line.startswith("/") and ":" in line
    ]

    return ":".join(paths)


RUNTIME_ROOT_GLOB_PATTERNS = (
    "var/*/files/",
    "*/files/"
)


def get_runtime_library_paths(proton_app, use_bwrap=True):
    """
    Get LD_LIBRARY_PATH value to use when running a command using Steam Runtime
    """
    def find_runtime_app_root(runtime_app):
        """
        Find the runtime root (the directory containing the root fileystem
        used for the container) for separately installed Steam Runtime app
        """
        for pattern in RUNTIME_ROOT_GLOB_PATTERNS:
            try:
                return next(
                    runtime_app.install_path.glob(pattern)
                )
            except StopIteration:
                pass

        raise RuntimeError(
            f"Could not find Steam Runtime runtime root for {runtime_app.name}"
        )

    if use_bwrap:
        return "".join([
            str(proton_app.proton_dist_path / "lib"), os.pathsep,
            str(proton_app.proton_dist_path / "lib64"), os.pathsep
        ])

    runtime_root = find_runtime_app_root(proton_app.required_tool_app)
    return "".join([
        str(proton_app.proton_dist_path / "lib"), os.pathsep,
        str(proton_app.proton_dist_path / "lib64"), os.pathsep,
        get_host_library_paths(), os.pathsep,
        str(runtime_root / "lib" / "i386-linux-gnu"), os.pathsep,
        str(runtime_root / "lib" / "x86_64-linux-gnu")
    ])


WINE_SCRIPT_TEMPLATE = Path(
    pkg_resources.resource_filename(
        "protontricks", "data/scripts/wine_launch.sh"
    )
).read_text(encoding="utf-8")
WINESERVER_KEEPALIVE_SH_SCRIPT = Path(
    pkg_resources.resource_filename(
        "protontricks", "data/scripts/wineserver_keepalive.sh"
    )
).read_text(encoding="utf-8")
WINESERVER_KEEPALIVE_BATCH_SCRIPT = Path(
    pkg_resources.resource_filename(
        "protontricks", "data/scripts/wineserver_keepalive.bat"
    )
).read_text(encoding="utf-8")
BWRAP_LAUNCHER_SH_SCRIPT = Path(
    pkg_resources.resource_filename(
        "protontricks", "data/scripts/bwrap_launcher.sh"
    )
).read_text(encoding="utf-8")


def get_cache_dir():
    """
    Get Protontricks' cache directory, creating it first if it does not
    exist
    """
    xdg_cache_dir = os.environ.get(
        "XDG_CACHE_HOME", os.path.expanduser("~/.cache")
    )
    base_path = Path(xdg_cache_dir) / "protontricks"
    os.makedirs(str(base_path), exist_ok=True)

    return base_path


def create_wine_bin_dir(proton_app, use_bwrap=True):
    """
    Create a directory with "proxy" executables that load shared libraries
    using Steam Runtime and Proton's own libraries instead of the system
    libraries
    """
    binaries = list((proton_app.proton_dist_path / "bin").iterdir())

    # Create the base directory containing files for every Proton installation
    base_path = get_cache_dir() / "proton"
    os.makedirs(str(base_path), exist_ok=True)

    # Create a directory to hold the new executables for the specific
    # Proton installation
    bin_path = base_path / proton_app.name / "bin"
    bin_path.mkdir(parents=True, exist_ok=True)

    logger.info(
        "Created Steam Runtime Wine binary directory at %s", str(bin_path)
    )

    # Delete the directory and rewrite the scripts. Some binaries may no
    # longer exist in the Proton installation, so we'll also get rid of
    # scripts that point to non-existing files
    shutil.rmtree(str(bin_path))
    bin_path.mkdir(parents=True)

    for binary in binaries:
        proxy_script_path = bin_path / binary.name

        content = WINE_SCRIPT_TEMPLATE.replace(
            "@@name@@", shlex.quote(binary.name),
        )
        content = content.replace(
            "@@script_path@@", str(proxy_script_path)
        )

        proxy_script_path.write_text(content, encoding="utf-8")

        script_stat = proxy_script_path.stat()
        # Make the helper script executable
        proxy_script_path.chmod(script_stat.st_mode | stat.S_IEXEC)

    # Create the wineserver keepalive batch script
    (bin_path / "wineserver-keepalive.bat").write_text(
        WINESERVER_KEEPALIVE_BATCH_SCRIPT
    )
    keepalive_shell_script = bin_path / "wineserver-keepalive"
    keepalive_shell_script.write_text(
        WINESERVER_KEEPALIVE_SH_SCRIPT.replace(
            "@@keepalive_bat_path@@",
            str(bin_path / "wineserver-keepalive.bat")
        )
    )
    keepalive_shell_script.chmod(
        keepalive_shell_script.stat().st_mode | stat.S_IEXEC
    )
    launcher_script = bin_path / "bwrap-launcher"
    launcher_script.write_text(BWRAP_LAUNCHER_SH_SCRIPT)
    launcher_script.chmod(launcher_script.stat().st_mode | stat.S_IEXEC)

    return bin_path


def _get_fixed_locale_env():
    """Return a dictionary of fixed locale environment variables if Steam Deck
    is in use and some of the selected locales haven't actually been generated
    by the system.

    If the locale settings require no changes, an empty dict will be returned
    instead.
    """
    # We can assume the 'en_US.UTF-8' locale always exists on Steam Deck, but
    # we can't assume the same about other distros. Therefore, only attempt
    # fixing the locale when running on a Steam Deck.
    if not is_steam_deck():
        return {}

    supported_locales = run(
        ["locale", "-a"], check=True, stdout=PIPE, stderr=DEVNULL
    ).stdout.decode("utf-8").splitlines()
    supported_locales = [
        locale.normalize(locale_) for locale_
        in supported_locales
    ]

    locale_output = run(
        ["locale"], check=True, stdout=PIPE, stderr=DEVNULL
    ).stdout.decode("utf-8").splitlines()
    locale_output = [value.split("=") for value in locale_output]
    locale_settings = {
        value[0]: value[1].strip('"') for value in locale_output
    }

    fixed_env = {}

    # Check if any of the locales don't actually exist
    for category, locale_ in locale_settings.items():
        if locale_.strip() == "":
            continue

        # Normalize the locale name
        locale_ = locale.normalize(locale_)
        if locale_ not in supported_locales:
            # Locale does not exist
            fixed_env[category] = "en_US.UTF-8"

    if fixed_env:
        logger.warning(
            "Found locale categories configured with missing locales. "
            "The locale has been reset to 'en_US.UTF-8' for the "
            "following categories: %s",
            ", ".join(fixed_env.keys())
        )

    return fixed_env


def _start_process(args, wait=False, **kwargs):
    """Start a new process and return a Popen instance
    """
    process = Popen(args=args, **kwargs)

    if wait:
        process.wait()

    return process


def run_command(
        winetricks_path, proton_app, steam_app, command,
        use_steam_runtime=False,
        legacy_steam_runtime_path=None,
        use_bwrap=None,
        start_wineserver=None,
        env=None,
        **kwargs):
    """Run an arbitrary command with the correct environment variables
    for the given Proton app

    The environment variables are set for the duration of the call
    and restored afterwards

    If 'use_steam_runtime' is True, run the command using Steam Runtime
    using either 'legacy_steam_runtime_path' or the Proton app's specific
    Steam Runtime installation, depending on which one is required.

    If 'use_bwrap' is True, run newer Steam Runtime installations using
    bwrap based containerization. If None, determine whether bwrap is available
    and use it if so.

    If 'start_wineserver' is True, launch a background wineserver and keep it
    alive for the duration of the Protontricks call. If None, launch background
    wineserver if bwrap can be enabled.

    :returns: Return code of the executed command
    """
    # Check for incomplete Steam Runtime installation
    runtime_install_incomplete = \
        proton_app.required_tool_appid and not proton_app.required_tool_app

    if use_steam_runtime and runtime_install_incomplete:
        raise RuntimeError(
            f"{proton_app.name} is missing the required Steam Runtime. "
            "You may need to launch a Steam app using this Proton version "
            "to finish the installation."
        )

    # Make a copy of the environment variables to use for the subprocesses.
    # Include any additional environment variables if provided.
    if env is None:
        env = {}

    wine_environ = os.environ.copy()
    wine_environ.update(env)

    user_provided_wine = os.environ.get("WINE", False)
    user_provided_wineserver = os.environ.get("WINESERVER", False)

    wine_environ["WINETRICKS"] = str(winetricks_path)
    wine_environ["WINEPREFIX"] = str(steam_app.prefix_path)
    wine_environ["WINEDLLPATH"] = "".join([
        str(proton_app.proton_dist_path / "lib64" / "wine"),
        os.pathsep,
        str(proton_app.proton_dist_path / "lib" / "wine")
    ])

    wine_environ["PATH"] = "".join([
        str(proton_app.proton_dist_path / "bin"), os.pathsep,
        wine_environ["PATH"]
    ])

    # Expose the path to Proton installation. This is mainly used for
    # Wine helper scripts, but other scripts could use it as well.
    wine_environ["PROTON_PATH"] = str(proton_app.install_path)
    wine_environ["PROTON_DIST_PATH"] = str(proton_app.proton_dist_path)

    wine_environ["STEAM_APP_PATH"] = str(steam_app.install_path)
    wine_environ["STEAM_APPID"] = str(steam_app.appid)

    # Unset WINEARCH, which might be set for another Wine installation
    wine_environ.pop("WINEARCH", "")

    # Fix the locale for Steam Deck, if necessary
    wine_environ.update(_get_fixed_locale_env())

    wine_bin_dir = None
    wine_environ["PROTONTRICKS_STEAM_RUNTIME"] = "off"
    if use_steam_runtime:
        if use_bwrap is None:
            use_bwrap = bool(proton_app.required_tool_app)
            logger.info("Using 'bwrap = %s' as default value", use_bwrap)

        if start_wineserver is None:
            start_wineserver = use_bwrap
            logger.info(
                "Using 'background-wineserver = %s' as default value",
                start_wineserver
            )

        if proton_app.required_tool_app:
            wine_environ["STEAM_RUNTIME_PATH"] = \
                str(proton_app.required_tool_app.install_path)
            wine_environ["PROTON_LD_LIBRARY_PATH"] = \
                get_runtime_library_paths(proton_app, use_bwrap=use_bwrap)

            runtime_name = proton_app.required_tool_app.name
            logger.info(
                "Using separately installed Steam Runtime: %s",
                runtime_name
            )

            if use_bwrap:
                wine_environ["PROTONTRICKS_STEAM_RUNTIME"] = "bwrap"
                logger.info(
                    "Running Steam Runtime using bwrap containerization.\n"
                    "If any problems arise, please try running the command "
                    "again using the `--no-bwrap` flag and make an issue "
                    "report if the problem only occurs when bwrap is in use."
                )
            else:
                wine_environ["PROTONTRICKS_STEAM_RUNTIME"] = "legacy"

            if runtime_name not in SUPPORTED_STEAM_RUNTIMES:
                logger.warning(
                    "Current Steam Runtime not recognized by Protontricks."
                )
        else:
            # Legacy Steam Runtime requires a different LD_LIBRARY_PATH
            # that is produced by a script.
            wine_environ["PROTONTRICKS_STEAM_RUNTIME"] = "legacy"
            wine_environ["PROTON_LD_LIBRARY_PATH"] = \
                get_legacy_runtime_library_paths(
                    legacy_steam_runtime_path, proton_app
                )

            # bwrap is not available, so ensure it is not launched even if the
            # user configured it so
            use_bwrap = False

    # Configure the environment to use launch scripts that take care of
    # configuring the environment and Wine before launching the underlying
    # Wine binaries.
    wine_bin_dir = create_wine_bin_dir(proton_app)
    wine_environ["LEGACY_STEAM_RUNTIME_PATH"] = str(legacy_steam_runtime_path)
    wine_environ["PATH"] = os.pathsep.join(
        [str(wine_bin_dir), wine_environ["PATH"]]
    )

    if not user_provided_wine:
        logger.info(
            "WINE environment variable is not available. "
            "Setting WINE environment variable to Proton bundled version."
        )
        wine_environ["WINE"] = str(wine_bin_dir / "wine")
        wine_environ["WINE_BIN"] = str(
            proton_app.proton_dist_path / "bin" / "wine"
        )

    wine_environ["WINELOADER"] = wine_environ["WINE"]

    if not user_provided_wineserver:
        logger.info(
            "WINESERVER environment variable is not available. "
            "Setting WINESERVER environment variable to Proton bundled version"
        )
        wine_environ["WINESERVER"] = str(wine_bin_dir / "wineserver")
        wine_environ["WINESERVER_BIN"] = str(
            proton_app.proton_dist_path / "bin" / "wineserver"
        )

    temp_dir = Path(tempfile.mkdtemp(prefix="protontricks-"))
    wine_environ["PROTONTRICKS_TEMP_PATH"] = str(temp_dir)
    wine_environ["PROTONTRICKS_SESSION_ID"] = temp_dir.name.split("-")[1]

    if start_wineserver:
        wine_environ["PROTONTRICKS_BACKGROUND_WINESERVER"] = "1"

    launcher_process = None
    keepalive_process = None
    try:
        if use_bwrap:
            logger.info(
                "Starting bwrap launcher process: %s",
                str(wine_bin_dir / "bwrap-launcher")
            )

            # TODO: Waiting for launcher to start can be simplified once
            # ValveSoftware/steam-runtime#593 has been fixed and stdout can
            # be used instead.
            launcher_read_fd, launcher_write_fd = os.pipe2(os.O_CLOEXEC)
            launcher_process = _start_process(
                [str(wine_bin_dir / "bwrap-launcher"), str(launcher_write_fd)],
                wait=False,
                pass_fds=[launcher_write_fd],
                env=wine_environ
            )

            # The Steam Runtime launcher service will write to the given
            # file descriptor and then close it to indicate the launcher is
            # ready or about to exit (i.e. due to wrong CLI parameters).
            os.close(launcher_write_fd)
            with open(launcher_read_fd, "rb") as reader:
                reader.read()

            # Check if the launcher actually started up and is still running.
            try:
                launcher_process.wait(timeout=0.1)
                # Launcher process crashed, bail out
                raise RuntimeError(
                    f"bwrap launcher crashed, "
                    f"returncode: {launcher_process.returncode}"
                )
            except TimeoutExpired:
                # Launcher is running as expected
                pass

            logger.info("bwrap launcher started")

        if start_wineserver:
            logger.info(
                "Starting wineserver keepalive process: %s",
                str(wine_bin_dir / "wineserver-keepalive")
            )
            keepalive_process = _start_process(
                str(wine_bin_dir / "wineserver-keepalive"),
                wait=False,
                env=wine_environ,
                stdout=DEVNULL,
            )

        logger.info("Attempting to run command %s", command)

        kwargs = kwargs.copy()
        kwargs["env"] = wine_environ

        process = _start_process(
            command, wait=True, **kwargs
        )
        return process.returncode
    finally:
        shutil.rmtree(str(temp_dir), ignore_errors=True)

        if keepalive_process:
            logger.info(
                "Terminating wineserver keepalive process %d",
                keepalive_process.pid
            )
            keepalive_process.terminate()

        if launcher_process:
            logger.info(
                "Terminating launcher process %d",
                launcher_process.pid
            )
            launcher_process.terminate()
            launcher_process.wait()
            logger.info("Launcher process terminated")
