# _____         _           _       _     _
# |  _  |___ ___| |_ ___ ___| |_ ___|_|___| |_ ___
# |   __|  _| . |  _| . |   |  _|  _| |  _| '_|_ -|
# |__|  |_| |___|_| |___|_|_|_| |_| |_|___|_,_|___|
# A simple wrapper that makes it slightly painless to use winetricks with
# Proton prefixes
#
# Script licensed under the GPLv3!

import argparse
import logging
import os
import sys

from .. import __version__
from ..flatpak import (FLATPAK_BWRAP_COMPATIBLE_VERSION,
                       get_running_flatpak_version)
from ..gui import (prompt_filesystem_access, select_steam_app_with_gui,
                   select_steam_installation)
from ..steam import (find_legacy_steam_runtime_path, find_proton_app,
                     find_steam_installations, get_steam_apps,
                     get_steam_lib_paths)
from ..util import run_command
from ..winetricks import get_winetricks_path
from .util import (CustomArgumentParser, cli_error_handler, enable_logging,
                   exit_with_error)

logger = logging.getLogger("protontricks")


def cli(args=None):
    main(args)


@cli_error_handler
def main(args=None, steam_path=None, steam_root=None):
    """
    'protontricks' script entrypoint
    """
    def _find_proton_app_or_exit(steam_path, steam_apps, appid):
        """
        Attempt to find a Proton app. Fail with an appropriate CLI error
        message if one cannot be found.
        """
        proton_app = find_proton_app(
            steam_path=steam_path, steam_apps=steam_apps, appid=appid
        )

        if not proton_app:
            if os.environ.get("PROTON_VERSION"):
                # Print an error listing accepted values if PROTON_VERSION was
                # set, as the user is trying to use a certain Proton version
                proton_names = sorted(set([
                    app.name for app in steam_apps if app.is_proton
                ]))
                exit_(
                    "Protontricks installation could not be found with given "
                    "$PROTON_VERSION!\n\n"
                    f"Valid values include: {', '.join(proton_names)}"
                )
            else:
                exit_("Proton installation could not be found!")

        if not proton_app.is_proton_ready:
            exit_(
                "Proton installation is incomplete. Have you launched a Steam "
                "app using this Proton version at least once to finish the "
                "installation?"
            )

        return proton_app

    if args is None:
        args = sys.argv[1:]

    parser = CustomArgumentParser(
        description=(
            "Wrapper for running Winetricks commands for "
            "Steam Play/Proton games.\n"
            "\n"
            "Usage:\n"
            "\n"
            "Run winetricks for game with APPID. "
            "COMMAND is passed directly to winetricks as-is. "
            "Any options specific to Protontricks need to be provided "
            "*before* APPID.\n"
            "$ protontricks APPID COMMAND\n"
            "\n"
            "Search installed games to find the APPID\n"
            "$ protontricks -s GAME_NAME\n"
            "\n"
            "List all installed games\n"
            "$ protontricks -l\n"
            "\n"
            "Use Protontricks GUI to select the game\n"
            "$ protontricks --gui\n"
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
            "empty = enable automatically (default)\n"
            "PROTONTRICKS_GUI: GUI provider to use, accepts either 'yad' "
            "or 'zenity'\n"
            "\n"
            "Environment variables set automatically by Protontricks:\n"
            "STEAM_APP_PATH: path to the current game's installation directory\n"
            "STEAM_APPID: app ID of the current game\n"
            "PROTON_PATH: path to the currently used Proton installation"
        ),
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "--verbose", "-v", action="count", default=0,
        help=(
            "Increase log verbosity. Can be supplied twice for "
            "maximum verbosity."
        )
    )
    parser.add_argument(
        "--no-term", action="store_true",
        help=(
            "Program was launched from desktop. This is used automatically "
            "when lauching Protontricks from desktop and no user-visible "
            "terminal is available."
        )
    )
    parser.add_argument(
        "-s", "--search", type=str, dest="search", nargs="+",
        required=False, help="Search for game(s) with the given name")
    parser.add_argument(
        "-l", "--list", action="store_true", dest="list", default=False,
        help="List all apps"
    )
    parser.add_argument(
        "-c", "--command", type=str, dest="command",
        required=False,
        help="Run a command with Wine-related environment variables set. "
             "The command is passed to the shell as-is without being escaped.")
    parser.add_argument(
        "--gui", action="store_true",
        help="Launch the Protontricks GUI.")
    parser.add_argument(
        "--no-runtime", action="store_true", default=False,
        help="Disable Steam Runtime")
    parser.add_argument(
        "--no-bwrap", action="store_true", default=None,
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
        "--cwd-app",
        dest="cwd_app",
        default=False,
        action="store_true",
        help=(
            "Set the working directory of launched command to the Steam app's "
            "installation directory."
        )
    )
    parser.set_defaults(background_wineserver=False)

    parser.add_argument("appid", type=int, nargs="?", default=None)
    parser.add_argument("winetricks_command", nargs=argparse.REMAINDER)
    parser.add_argument(
        "-V", "--version", action="version",
        version=f"%(prog)s ({__version__})"
    )

    if len(args) == 0:
        # No arguments were provided, default to GUI
        args = ["--gui"]

    args = parser.parse_args(args)

    # 'cli_error_handler' relies on this to know whether to use error dialog or
    # not
    main.no_term = args.no_term

    # Shorthand function for aborting with error message
    def exit_(error):
        exit_with_error(error, args.no_term)

    do_command = bool(args.command)
    do_list_apps = bool(args.search) or bool(args.list)
    do_gui = bool(args.gui)
    do_winetricks = bool(args.appid and args.winetricks_command)

    # Set 'use_bwrap' to opposite of args.no_bwrap if it was provided.
    # If not, keep it as None and determine the correct value to use later
    # once we've determined whether the selected Steam Runtime is a bwrap-based
    # one.
    use_bwrap = (
        not bool(args.no_bwrap) if args.no_bwrap in (True, False) else None
    )
    start_background_wineserver = (
        args.background_wineserver
        if args.background_wineserver is not None
        else use_bwrap
    )

    if not do_command and not do_list_apps and not do_gui and not do_winetricks:
        parser.print_help()
        return

    # Don't allow more than one action
    if sum([do_list_apps, do_gui, do_winetricks, do_command]) != 1:
        print("Only one action can be performed at a time.")
        parser.print_help()
        return

    enable_logging(args.verbose, record_to_file=args.no_term)

    flatpak_version = get_running_flatpak_version()
    if flatpak_version:
        logger.info(
            "Running inside Flatpak sandbox, version %s.",
            ".".join(map(str, flatpak_version))
        )
        if flatpak_version < FLATPAK_BWRAP_COMPATIBLE_VERSION:
            logger.warning(
                "Flatpak version is too old (<1.12.1) to support "
                "sub-sandboxes. Disabling bwrap. --no-bwrap will be ignored."
            )
            use_bwrap = False

    # 1. Find Steam path
    # We can skip the Steam installation detection if the CLI entrypoint
    # has already been provided the path as a keyword argument.
    # This is the case when this entrypoint is being called by
    # 'protontricks-launch'. This prevents us from asking the user for
    # the Steam installation twice.
    if not steam_path:
        steam_installations = find_steam_installations()
        if not steam_installations:
            exit_("Steam installation directory could not be found.")

        steam_path, steam_root = select_steam_installation(steam_installations)
        if not steam_path:
            exit_("No Steam installation was selected.")

    # 2. Find the pre-installed legacy Steam Runtime if enabled
    legacy_steam_runtime_path = None
    use_steam_runtime = True

    if os.environ.get("STEAM_RUNTIME", "") != "0" and not args.no_runtime:
        legacy_steam_runtime_path = find_legacy_steam_runtime_path(
            steam_root=steam_root
        )

        if not legacy_steam_runtime_path:
            exit_("Steam Runtime was enabled but couldn't be found!")
    else:
        use_steam_runtime = False
        logger.info("Steam Runtime disabled.")

    # 3. Find Winetricks
    winetricks_path = get_winetricks_path()
    if not winetricks_path:
        exit_(
            "Winetricks isn't installed, please install "
            "winetricks in order to use this script!"
        )

    # 4. Find any Steam library folders
    steam_lib_paths = get_steam_lib_paths(steam_path)

    # Check if Protontricks has access to all the required paths
    prompt_filesystem_access(
        paths=[steam_path, steam_root] + steam_lib_paths,
        show_dialog=args.no_term
    )

    # 5. Find any Steam apps
    steam_apps = get_steam_apps(
        steam_root=steam_root, steam_path=steam_path,
        steam_lib_paths=steam_lib_paths
    )

    # It's too early to find Proton here,
    # as it cannot be found if no globally active Proton version is set.
    # Having no Proton at this point is no problem as:
    # 1. not all commands require Proton (search)
    # 2. a specific steam-app will be chosen in GUI mode,
    #    which might use a different proton version than the one found here

    # Run the GUI
    if args.gui:
        has_installed_apps = any([
            app for app in steam_apps if app.is_windows_app
        ])

        if not has_installed_apps:
            exit_("Found no games. You need to launch a game at least once "
                  "before Protontricks can find it.")

        try:
            steam_app = select_steam_app_with_gui(
                steam_apps=steam_apps, steam_path=steam_path
            )
        except FileNotFoundError:
            exit_(
                "YAD or Zenity is not installed. Either executable is required for the "
                "Protontricks GUI."
            )

        cwd = str(steam_app.install_path) if args.cwd_app else None

        # 6. Find Proton version of selected app
        proton_app = _find_proton_app_or_exit(
            steam_path=steam_path, steam_apps=steam_apps, appid=steam_app.appid
        )

        run_command(
            winetricks_path=winetricks_path,
            proton_app=proton_app,
            steam_app=steam_app,
            use_steam_runtime=use_steam_runtime,
            legacy_steam_runtime_path=legacy_steam_runtime_path,
            command=[str(winetricks_path), "--gui"],
            use_bwrap=use_bwrap,
            start_wineserver=start_background_wineserver,
            cwd=cwd
        )

        return
    # List apps (either all or using a search)
    elif do_list_apps:
        if args.list:
            matching_apps = [
                app for app in steam_apps if app.is_windows_app
            ]
        else:
            # Search for games
            search_query = " ".join(args.search)
            matching_apps = [
                app for app in steam_apps
                if app.is_windows_app and app.name_contains(search_query)
            ]

        if matching_apps:
            matching_games = "\n".join([
                f"{app.name} ({app.appid})" for app in matching_apps
            ])
            print(
                f"Found the following games:"
                f"\n{matching_games}\n"
            )
            print(
                "To run Protontricks for the chosen game, run:\n"
                "$ protontricks APPID COMMAND"
            )
        else:
            print("Found no games.")

        print(
            "\n"
            "NOTE: A game must be launched at least once before Protontricks "
            "can find the game."
        )
        return

    # 6. Find globally active Proton version now
    proton_app = _find_proton_app_or_exit(
        steam_path=steam_path, steam_apps=steam_apps, appid=args.appid)

    # If neither search or GUI are set, do a normal Winetricks command
    # Find game by appid
    steam_appid = int(args.appid)
    try:
        steam_app = next(
            app for app in steam_apps
            if app.is_windows_app and app.appid == steam_appid
        )
    except StopIteration:
        exit_(
            "Steam app with the given app ID could not be found. "
            "Is it installed, Proton compatible and have you launched it at "
            "least once? You can search for the app ID using the following "
            "command:\n"
            "$ protontricks -s <GAME NAME>"
        )

    cwd = str(steam_app.install_path) if args.cwd_app else None

    if args.winetricks_command:
        returncode = run_command(
            winetricks_path=winetricks_path,
            proton_app=proton_app,
            steam_app=steam_app,
            use_steam_runtime=use_steam_runtime,
            legacy_steam_runtime_path=legacy_steam_runtime_path,
            use_bwrap=use_bwrap,
            start_wineserver=start_background_wineserver,
            command=[str(winetricks_path)] + args.winetricks_command,
            cwd=cwd
        )
    elif args.command:
        returncode = run_command(
            winetricks_path=winetricks_path,
            proton_app=proton_app,
            steam_app=steam_app,
            command=args.command,
            use_steam_runtime=use_steam_runtime,
            legacy_steam_runtime_path=legacy_steam_runtime_path,
            use_bwrap=use_bwrap,
            start_wineserver=start_background_wineserver,
            # Pass the command directly into the shell *without*
            # escaping it
            shell=True,
            cwd=cwd,
        )

    logger.info("Command returned %d", returncode)

    sys.exit(returncode)


if __name__ == "__main__":
    main()
