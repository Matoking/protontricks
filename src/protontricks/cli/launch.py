import argparse
import logging
import shlex
import sys
from pathlib import Path

from ..gui import (prompt_filesystem_access, select_steam_app_with_gui,
                   select_steam_installation)
from ..steam import (find_steam_installations, get_steam_apps,
                     get_steam_lib_paths)
from .main import main as cli_main
from .util import (CustomArgumentParser, cli_error_handler, enable_logging,
                   exit_with_error)

logger = logging.getLogger("protontricks")


def cli(args=None):
    main(args)


@cli_error_handler
def main(args=None):
    """
    'protontricks-launch' script entrypoint
    """
    if args is None:
        args = sys.argv[1:]

    parser = CustomArgumentParser(
        description=(
            "Utility for launching Windows executables using Protontricks\n"
            "\n"
            "Usage:\n"
            "\n"
            "Launch EXECUTABLE and pick the Steam app using a dialog.\n"
            "$ protontricks-launch EXECUTABLE [ARGS]\n"
            "\n"
            "Launch EXECUTABLE for Steam app APPID\n"
            "$ protontricks-launch --appid APPID EXECUTABLE [ARGS]\n"
            "\n"
            "Environment variables:\n"
            "\n"
            "PROTON_VERSION: name of the preferred Proton installation\n"
            "STEAM_DIR: path to custom Steam installation\n"
            "WINETRICKS: path to a custom 'winetricks' executable\n"
            "WINE: path to a custom 'wine' executable\n"
            "WINESERVER: path to a custom 'wineserver' executable\n"
            "STEAM_RUNTIME: 1 = enable Steam Runtime, 0 = disable Steam "
            "Runtime, valid path = custom Steam Runtime path, "
            "empty = enable automatically (default)"
        ),
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "--no-term", action="store_true",
        help=(
            "Program was launched from desktop and no user-visible "
            "terminal is available. Error will be shown in a dialog instead "
            "of being printed."
        )
    )
    parser.add_argument(
        "--verbose", "-v", action="count", default=0,
        help=(
            "Increase log verbosity. Can be supplied twice for "
            "maximum verbosity."
        )
    )
    parser.add_argument(
        "--no-runtime", action="store_true", default=False,
        help="Disable Steam Runtime")
    parser.add_argument(
        "--no-bwrap", action="store_true", default=False,
        help="Disable bwrap containerization when using Steam Runtime"
    )
    parser.add_argument(
        "--background-wineserver",
        dest="background_wineserver",
        action="store_true",
        help=(
            "Launch a background wineserver process to improve Wine command "
            "startup time. Disabled by default, as it can cause problems with "
            "some graphical applications."
        )
    )
    parser.add_argument(
        "--no-background-wineserver",
        dest="background_wineserver",
        action="store_false",
        help=(
            "Do not launch a background wineserver process to improve Wine "
            "command startup time."
        )
    )
    parser.add_argument(
        "--appid", type=int, nargs="?", default=None
    )
    parser.add_argument(
        "--cwd-app",
        dest="cwd_app",
        default=False,
        action="store_true",
        help=(
            "Set the working directory of launched executable to the Steam "
            "app's installation directory."
        )
    )
    parser.add_argument("executable", type=str)
    parser.add_argument("exec_args", nargs=argparse.REMAINDER)
    parser.set_defaults(background_wineserver=False)

    args = parser.parse_args(args)

    # 'cli_error_handler' relies on this to know whether to use error dialog or
    # not
    main.no_term = args.no_term

    # Shorthand function for aborting with error message
    def exit_(error):
        exit_with_error(error, args.no_term)

    enable_logging(args.verbose, record_to_file=args.no_term)

    executable_path = Path(args.executable).resolve(strict=True)

    # 1. Find Steam path
    steam_installations = find_steam_installations()
    if not steam_installations:
        exit_("Steam installation directory could not be found.")

    steam_path, steam_root = select_steam_installation(steam_installations)
    if not steam_path:
        exit_("No Steam installation was selected.")

    # 2. Find any Steam library folders
    steam_lib_paths = get_steam_lib_paths(steam_path)

    # Check if Protontricks has access to all the required paths
    prompt_filesystem_access(
        paths=[steam_path, steam_root] + steam_lib_paths,
        show_dialog=args.no_term
    )

    # 3. Find any Steam apps
    steam_apps = get_steam_apps(
        steam_root=steam_root, steam_path=steam_path,
        steam_lib_paths=steam_lib_paths
    )
    steam_apps = [
        app for app in steam_apps if app.prefix_path_exists and app.appid
    ]

    if not steam_apps:
        exit_(
            "No Proton enabled Steam apps were found. Have you launched one "
            "of the apps at least once?"
        )

    if not args.appid:
        appid = select_steam_app_with_gui(
            steam_apps,
            title=f"Choose Wine prefix to run {executable_path.name}",
            steam_path=steam_path
        ).appid
    else:
        appid = args.appid

    # Build the command to pass to the main Protontricks CLI entrypoint
    cli_args = []

    # Ensure each individual argument passed to the EXE is escaped
    exec_args = [shlex.quote(arg) for arg in args.exec_args]

    if args.verbose:
        cli_args += ["-" + ("v" * args.verbose)]

    if args.no_runtime:
        cli_args += ["--no-runtime"]

    if args.no_bwrap:
        cli_args += ["--no-bwrap"]

    if args.background_wineserver is True:
        cli_args += ["--background-wineserver"]
    elif args.background_wineserver is False:
        cli_args += ["--no-background-wineserver"]

    if args.no_term:
        cli_args += ["--no-term"]

    inner_args = " ".join(
        ["wine", shlex.quote(str(executable_path))]
        + exec_args
    )

    if args.cwd_app:
        cli_args += ["--cwd-app"]

    cli_args += [
        "-c", inner_args, str(appid)
    ]

    # Launch the main Protontricks CLI entrypoint
    logger.info(
        "Calling `protontricks` with the command: %s", cli_args
    )
    cli_main(cli_args, steam_path=steam_path, steam_root=steam_root)


if __name__ == "__main__":
    main()
