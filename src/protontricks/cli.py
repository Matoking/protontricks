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

from protontricks.steam import (find_current_proton_app, find_steam_path,
                                get_steam_apps, get_steam_lib_paths,
                                get_custom_proton_installations)
from protontricks.winetricks import (get_winetricks_path,
                                     run_winetricks_command)
from protontricks.gui import select_steam_app_with_gui

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
            "Usage:\n"
            "\n"
            "Run winetricks for game with APPID\n"
            "$ protontricks APPID COMMAND\n"
            "\n"
            "Search installed games to find the APPID\n"
            "$ protontricks -s GAME_NAME\n"
            "\n"
            "Launch the Protontricks GUI\n"
            "$ protontricks --gui"
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
        "--gui", action="store_true",
        help="Launch the Protontricks GUI.")
    parser.add_argument("appid", type=int, nargs="?", default=None)
    parser.add_argument("winetricks_command", nargs="*")

    args = parser.parse_args()

    do_search = bool(args.search)
    do_gui = bool(args.gui)
    do_winetricks = bool(args.appid and args.winetricks_command)

    if not do_search and not do_gui and not do_winetricks:
        parser.print_help()
        return

    # Don't allow more than one action
    if sum([do_search, do_gui, do_winetricks]) != 1:
        print("Only one action can be performed at a time.")
        parser.print_help()
        return

    enable_logging(args.verbose)

    # 1. Find Steam path
    steam_path = find_steam_path()

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
    if not os.environ.get("PROTON_VERSION"):
        # If $PROTON_VERSION isn't set, find the currently used Proton
        # installation automatically
        proton_app = find_current_proton_app(
            steam_path=steam_path, steam_apps=steam_apps)
        if not proton_app:
            print(
                "Current Proton installation couldn't be found "
                "automatically and $PROTON_VERSION wasn't set"
            )
            sys.exit(-1)
    else:
        proton_version = os.environ.get("PROTON_VERSION")
        try:
            proton_app = next(
                app for app in steam_apps
                if app.name == proton_version)
        except StopIteration:
            print("Proton installation could not be found!")
            sys.exit(-1)

    # Run the GUI
    if args.gui:
        steam_app = select_steam_app_with_gui(steam_apps=steam_apps)
        run_winetricks_command(
            steam_path=steam_path,
            winetricks_path=winetricks_path,
            proton_app=proton_app,
            steam_app=steam_app,
            command=["--gui"]
        )
        return
    # Perform a search
    elif args.search:
        # Search for games
        search_query = " ".join(args.search)
        matching_apps = [
            app for app in steam_apps
            if not app.is_proton and app.name_contains(search_query)
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

    run_winetricks_command(
        steam_path=steam_path,
        winetricks_path=winetricks_path,
        proton_app=proton_app,
        steam_app=steam_app,
        command=args.winetricks_command)


if __name__ == "__main__":
    main()
