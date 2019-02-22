#!/usr/bin/env python3
# _____         _           _       _     _
# |  _  |___ ___| |_ ___ ___| |_ ___|_|___| |_ ___
# |   __|  _| . |  _| . |   |  _|  _| |  _| '_|_ -|
# |__|  |_| |___|_| |___|_|_|_| |_| |_|___|_,_|___|
# A simple wrapper that makes it slightly painless to use winetricks with
# Proton prefixes
#
# Script licensed under the GPLv3!

import sys
import argparse
import shutil
import subprocess
import os
import logging

from . import __version__
from .steam import (find_proton_app, find_steam_path,
                                get_steam_apps, get_steam_lib_paths,
                                get_custom_proton_installations)
from .winetricks import get_winetricks_path
from .gui import select_steam_app_with_gui
from .util import run_command

logger = logging.getLogger("protontricks")


def enable_logging(info=False):
    """
    Enables logging.
    If info is True, print INFO messages in addition to WARNING and ERROR
    messages
    """
    level = logging.INFO if info else logging.WARNING
    logging.basicConfig(
        stream=sys.stderr, level=level,
        format="%(name)s (%(levelname)s): %(message)s")


def main():
    """
    'protontricks' script entrypoint
    """
    parser = argparse.ArgumentParser(
        description=(
            "Wrapper for running Winetricks commands for "
            "Steam Play/Proton games.\n"
            "\n"
            "Usage:\n"
            "\n"
            "Run winetricks for game with APPID\n"
            "$ protontricks APPID COMMAND\n"
            "\n"
            "Search installed games to find the APPID\n"
            "$ protontricks -s GAME_NAME\n"
            "\n"
            "Launch the Protontricks GUI\n"
            "$ protontricks --gui\n"
            "\n"
            "Environment variables:\n"
            "\n"
            "PROTON_VERSION: name of the preferred Proton installation\n"
            "STEAM_DIR: path to custom Steam installation\n"
            "WINETRICKS: path to a custom 'winetricks' executable\n"
            "WINE: path to a custom 'wine' executable\n"
            "WINESERVER: path to a custom 'wineserver' executable"
        ),
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Print debug information")
    parser.add_argument(
        "-s", "--search", type=str, dest="search", nargs="+",
        required=False, help="Search for game(s) with the given name")
    parser.add_argument(
        "-c", "--command", type=str, dest="command",
        required=False,
        help="Run a command in the game's installation directory with "
             "Wine-related environment variables set. "
             "The command is passed to the shell as-is without being escaped.")
    parser.add_argument(
        "--gui", action="store_true",
        help="Launch the Protontricks GUI.")
    parser.add_argument(
        "--runtime", action="store_true", default=False,
        help="Run protontricks using Steam Runtime")
    parser.add_argument("appid", type=int, nargs="?", default=None)
    parser.add_argument("winetricks_command", nargs=argparse.REMAINDER)
    parser.add_argument(
        "-V", "--version", action="version",
        version="%(prog)s ({})".format(__version__)
    )

    args = parser.parse_args()

    do_command = bool(args.command)
    do_search = bool(args.search)
    do_gui = bool(args.gui)
    do_winetricks = bool(args.appid and args.winetricks_command)

    if not do_command and not do_search and not do_gui and not do_winetricks:
        parser.print_help()
        return

    # Don't allow more than one action
    if sum([do_search, do_gui, do_winetricks, do_command]) != 1:
        print("Only one action can be performed at a time.")
        parser.print_help()
        return

    enable_logging(args.verbose)

    # 1. Find Steam path
    steam_path = find_steam_path()
    if not steam_path:
        print(
            "Steam installation directory could not be found."
        )
        sys.exit(-1)

    # 2. Find Winetricks
    winetricks_path = get_winetricks_path()
    if not winetricks_path:
        print(
            "Winetricks isn't installed, please install "
            "winetricks in order to use this script!"
        )
        sys.exit(-1)

    # 3. Find any Steam library folders
    steam_lib_paths = get_steam_lib_paths(steam_path)

    # 4. Find any Steam apps
    steam_apps = get_steam_apps(steam_path, steam_lib_paths)

    # 5. Find active Proton version
    proton_app = find_proton_app(
        steam_path=steam_path, steam_apps=steam_apps, appid=args.appid)

    if not proton_app:
        print("Proton installation could not be found!")
        sys.exit(-1)

    # Run the GUI
    if args.gui:
        if args.runtime:
            runtime_cmd = [
                os.path.join(
                    steam_path, "ubuntu12_32", "steam-runtime", "run.sh")
            ]
        else:
            runtime_cmd = []

        steam_app = select_steam_app_with_gui(steam_apps=steam_apps)
        run_command(
            steam_path=steam_path,
            winetricks_path=winetricks_path,
            proton_app=proton_app,
            steam_app=steam_app,
            command=runtime_cmd + [winetricks_path, "--gui"]
        )
        return
    # Perform a search
    elif args.search:
        # Search for games
        search_query = " ".join(args.search)
        matching_apps = [
            app for app in steam_apps
            if app.prefix_path_exists and app.name_contains(search_query)
        ]

        if matching_apps:
            matching_games = "\n".join([
                "{} ({})".format(app.name, app.appid)
                for app in matching_apps
            ])
            print(
                "Found the following games:"
                "\n{}\n".format(matching_games)
            )
            print(
                "To run protontricks for the chosen game, run:\n"
                "$ protontricks APPID COMMAND"
            )
        else:
            print("Found no games.")

        print(
            "\n"
            "NOTE: A game must be launched at least once before protontricks "
            "can find the game."
        )
        return

    # If neither search or GUI are set, do a normal Winetricks command
    # Find game by appid
    steam_appid = int(args.appid)
    try:
        steam_app = next(
            app for app in steam_apps
            if not app.is_proton and app.appid == steam_appid
            and app.prefix_path_exists)
    except StopIteration:
        print(
            "Steam app with the given app ID could not be found. "
            "Is it installed, Proton compatible and have you launched it at "
            "least once? You can search for the app ID using the following "
            "command:\n"
            "$ protontricks -s <GAME NAME>"
        )
        sys.exit(-1)


    if args.winetricks_command:
        if args.runtime:
            runtime_cmd = [
                os.path.join(
                    steam_path, "ubuntu12_32", "steam-runtime", "run.sh")
            ]
        else:
            runtime_cmd = []

        run_command(
            steam_path=steam_path,
            winetricks_path=winetricks_path,
            proton_app=proton_app,
            steam_app=steam_app,
            command=runtime_cmd + [winetricks_path] + args.winetricks_command)
    elif args.command:
        if args.runtime:
            runtime_cmd = "'{}' ".format(
                os.path.join(
                    steam_path, "ubuntu12_32", "steam-runtime", "run.sh"
                )
            )
        else:
            runtime_cmd = ""

        run_command(
            steam_path=steam_path,
            winetricks_path=winetricks_path,
            proton_app=proton_app,
            steam_app=steam_app,
            command=runtime_cmd + args.command,
            # Pass the command directly into the shell *without*
            # escaping it
            cwd=steam_app.install_path,
            shell=True)


if __name__ == "__main__":
    main()
