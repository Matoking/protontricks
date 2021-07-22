import argparse
import logging
import shlex
import sys
from pathlib import Path
from subprocess import run

from ..gui import select_steam_app_with_gui
from ..steam import find_steam_path, get_steam_apps, get_steam_lib_paths
from .main import main as cli_main
from .util import CustomArgumentParser, enable_logging

logger = logging.getLogger("protontricks")


def exit_with_error(error, display_dialog=False):
    """
    Print or display an error, and then exit.
    """
    if display_dialog:
        run([
            "zenity", "--error", "--width", "400", "--text", error
        ], check=True)
    else:
        print(error)

    sys.exit(-1)


def main(args=None):
    """
    'protontricks-launch' script entrypoint
    """
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
        "--from-desktop", action="store_true",
        help=(
            "Display error messages using error dialogs instead of printing "
            "to stderr."
        )
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Print debug information")
    parser.add_argument(
        "--no-runtime", action="store_true", default=False,
        help="Disable Steam Runtime")
    parser.add_argument(
        "--no-bwrap", action="store_true", default=False,
        help="Disable bwrap containerization when using Steam Runtime"
    )
    parser.add_argument(
        "--appid", type=int, nargs="?", default=None
    )
    parser.add_argument("executable", type=str)
    parser.add_argument("exec_args", nargs=argparse.REMAINDER)

    args = parser.parse_args(args)

    enable_logging(args.verbose)

    try:
        executable_path = Path(args.executable).resolve(strict=True)
    except TypeError:  # Python 3.5
        executable_path = Path(args.executable).resolve()

    # 1. Find Steam path
    steam_path, steam_root = find_steam_path()
    if not steam_path:
        exit_with_error(
            "Steam installation directory could not be found.",
            args.from_desktop
        )

    # 2. Find any Steam library folders
    steam_lib_paths = get_steam_lib_paths(steam_path)

    # 3. Find any Steam apps
    steam_apps = get_steam_apps(
        steam_root=steam_root, steam_path=steam_path,
        steam_lib_paths=steam_lib_paths
    )
    steam_apps = [
        app for app in steam_apps if app.prefix_path_exists and app.appid
    ]

    if not steam_apps:
        exit_with_error(
            "No Proton enabled Steam apps were found. Have you launched one "
            "of the apps at least once?",
            args.from_desktop
        )

    if not args.appid:
        appid = select_steam_app_with_gui(
            steam_apps,
            title="Choose Wine prefix to run {}".format(executable_path.name)
        ).appid
    else:
        appid = args.appid

    # Build the command to pass to the main Protontricks CLI entrypoint
    cli_args = []

    # Ensure each individual argument passed to the EXE is escaped
    exec_args = [shlex.quote(arg) for arg in args.exec_args]

    if args.verbose:
        cli_args += ["--verbose"]

    if args.no_runtime:
        cli_args += ["--no-runtime"]

    if args.no_bwrap:
        cli_args += ["--no-bwrap"]

    inner_args = " ".join(
        ["wine", "'{}'".format(str(executable_path))]
        + exec_args
    )

    cli_args += [
        "-c", inner_args, str(appid)
    ]

    # Launch the main Protontricks CLI entrypoint
    logger.info(
        "Calling `protontricks` with the command: %s", cli_args
    )
    cli_main(cli_args)


if __name__ == "__main__":
    main()
