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
import sys

from .. import __version__
from ..util import run_command
from .command import BaseCommand
from .util import CustomArgumentParser, cli_error_handler, enable_logging

logger = logging.getLogger("protontricks")


def cli(args=None):
    main(args)


@cli_error_handler
def main(args=None, steam_path=None, steam_root=None):
    """
    'protontricks' script entrypoint
    """
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

    do_command = bool(args.command)
    do_list_apps = bool(args.search) or bool(args.list)
    do_gui = bool(args.gui)
    do_winetricks = bool(args.appid and args.winetricks_command)

    if not do_command and not do_list_apps and not do_gui and not do_winetricks:
        parser.print_help()
        return

    # Don't allow more than one action
    if sum([do_list_apps, do_gui, do_winetricks, do_command]) != 1:
        print("Only one action can be performed at a time.")
        parser.print_help()
        return

    enable_logging(args.verbose, record_to_file=args.no_term)

    # Run the GUI
    if do_gui:
        RunWinetricksGUICommand(args).execute()
    # List apps (either all or using a search)
    elif do_list_apps:
        ListAppsCommand(args).execute()
    elif do_winetricks:
        RunWinetricksCommand(args).execute()
    elif do_command:
        RunCustomCommand(args).execute()


class RunWinetricksCommand(BaseCommand):
    steam_app_required = True
    proton_app_required = True
    winetricks_required = True

    def run(self):
        cwd = (
            str(self.steam_app.install_path)
            if self.cli_args.cwd_app else None
        )

        returncode = run_command(
            winetricks_path=self.winetricks_path,
            proton_app=self.proton_app,
            steam_app=self.steam_app,
            use_steam_runtime=self.use_steam_runtime,
            legacy_steam_runtime_path=self.legacy_steam_runtime_path,
            use_bwrap=self.use_bwrap,
            start_wineserver=self.start_background_wineserver,
            command=[str(self.winetricks_path)] + self.cli_args.winetricks_command,
            cwd=cwd
        )

        sys.exit(returncode)


class RunWinetricksGUICommand(BaseCommand):
    steam_app_required = True
    proton_app_required = True
    winetricks_required = True

    def run(self):
        cwd = \
            str(self.steam_app.install_path) if self.cli_args.cwd_app else None

        run_command(
            winetricks_path=self.winetricks_path,
            proton_app=self.proton_app,
            steam_app=self.steam_app,
            use_steam_runtime=self.use_steam_runtime,
            legacy_steam_runtime_path=self.legacy_steam_runtime_path,
            command=[str(self.winetricks_path), "--gui"],
            use_bwrap=self.use_bwrap,
            start_wineserver=self.start_background_wineserver,
            cwd=cwd
        )


class RunCustomCommand(BaseCommand):
    steam_app_required = True
    proton_app_required = True

    def run(self):
        cwd = (
            str(self.steam_app.install_path) if self.cli_args.cwd_app else None
        )

        returncode = run_command(
            winetricks_path=self.winetricks_path,
            proton_app=self.proton_app,
            steam_app=self.steam_app,
            command=self.cli_args.command,
            use_steam_runtime=self.use_steam_runtime,
            legacy_steam_runtime_path=self.legacy_steam_runtime_path,
            use_bwrap=self.use_bwrap,
            start_wineserver=self.start_background_wineserver,
            # Pass the command directly into the shell *without*
            # escaping it
            shell=True,
            cwd=cwd
        )

        sys.exit(returncode)


class ListAppsCommand(BaseCommand):
    steam_apps_required = True

    def run(self):
        if self.cli_args.list:
            matching_apps = [
                app for app in self.steam_apps if app.is_windows_app
            ]
        else:
            # Search for games
            search_query = " ".join(self.cli_args.search)
            matching_apps = [
                app for app in self.steam_apps
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


if __name__ == "__main__":
    main()
