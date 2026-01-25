from __future__ import annotations

import logging
import os
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

from ..flatpak import (FLATPAK_BWRAP_COMPATIBLE_VERSION,
                       get_running_flatpak_version)
from ..gui import (prompt_filesystem_access, select_steam_app_with_gui,
                   select_steam_installation)
from ..steam import (SNAP_STEAM_DIRS, SteamApp, find_legacy_steam_runtime_path,
                     find_proton_app, find_steam_installations, get_steam_apps,
                     get_steam_lib_paths)
from ..winetricks import get_winetricks_path
from .util import exit_with_error

logger = logging.getLogger("protontricks")


@dataclass
class BaseCommand:
    """
    Encapsulates a single command-line command that might have different
    prerequisites. For example, we might need to find the Steam installation
    and select a Steam app in it.
    """
    steam_required: ClassVar[bool] = False
    steam_app_required: ClassVar[bool] = False
    steam_apps_required: ClassVar[bool] = False
    steam_runtime_required: ClassVar[bool] = False
    proton_app_required: ClassVar[bool] = False
    winetricks_required: ClassVar[bool] = False
    all_steam_installations_required: ClassVar[bool] = False
    all_steam_apps_required: ClassVar[bool] = False

    cli_args: dict = field(default_factory=dict)
    """Original command-line arguments"""

    no_term: bool | None = None
    """
    Whether no terminal is active and the application was launched from desktop
    """

    steam_path: Path | None = None
    """Contains 'appcache', 'config' and 'steamapps'"""
    steam_root: Path | None = None
    """Steam installation path, contains 'appcache', 'config' and 'steamapps'"""

    steam_lib_paths: list[Path] = field(default_factory=list)
    """List of Steam library paths"""

    steam_apps: list[SteamApp] = field(default_factory=list)
    """List of Steam apps for the Steam installation"""

    winetricks_path: Path | None = None
    """Path to Winetricks executable"""

    legacy_steam_runtime_path: Path | None = None
    """
    Path to legacy, non-container Steam Runtime.

    In most cases, this is *not* used; instead, the Proton installation will
    have a Steam Runtime that is accessible via `SteamApp.tool_app` parameter.
    """
    use_steam_runtime: bool | None = None
    """Whether to use Steam Runtime"""
    use_bwrap: bool | None = None
    """Whether to use bubblewrap-based containerization with newer Steam Runtime"""
    start_background_wineserver: bool | None = None
    """Whether to start background `wineserver`"""

    steam_app: SteamApp | None = None
    """Steam app selected by the user"""
    proton_app: SteamApp | None = None
    """Proton app either configured for the Steam app or overridden manually"""

    def __init__(self, cli_args):
        super().__init__()

        self.cli_args = cli_args

    def exit(self, error: str):
        """
        Shorthand method to print an error or display it in a graphical dialog
        depending on the environment
        """
        exit_with_error(error, self.cli_args.no_term)

    def execute(self):
        """
        Retrieve required resources and run the actual command
        """
        self.populate_required_params()

        self.run()

    def populate_required_params(self):
        """
        Populate required parameters to run this command
        """
        # Check for dependencies and set them accordingly
        # (eg. to select a single Steam app we need to retrieve all apps first)
        if self.steam_runtime_required:
            self.proton_app_required = True

        if self.proton_app_required:
            self.steam_app_required = True

        if self.steam_app_required:
            self.steam_apps_required = True

        if self.steam_apps_required:
            self.steam_required = True

        if self.all_steam_apps_required:
            self.all_steam_installations_required = True

        # Perform the actual detection. User might be prompted
        # if multiple choices exist.
        if self.steam_required:
            self.populate_steam()

            if self.proton_app_required:
                self.populate_steam_runtime()

        self.populate_winetricks(strict=self.winetricks_required)

        if self.steam_apps_required:
            self.populate_steam_apps()

        if self.steam_app_required:
            self.populate_steam_app()

        if self.proton_app_required:
            self.populate_proton_app()

        if self.all_steam_installations_required:
            self.populate_all_steam_installations()

        if self.all_steam_apps_required:
            self.populate_all_steam_apps()

    def populate_steam_runtime(self):
        """
        Populate Steam Runtime
        """
        # Set 'use_bwrap' to opposite of args.no_bwrap if it was provided.
        # If not, keep it as None and determine the correct value to use later
        # once we've determined whether the selected Steam Runtime is a bwrap-based
        # one.
        use_bwrap = (
            not bool(self.cli_args.no_bwrap)
            if self.cli_args.no_bwrap in (True, False) else None
        )
        start_background_wineserver = (
            self.cli_args.background_wineserver
            if self.cli_args.background_wineserver is not None
            else use_bwrap
        )

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

        self.use_bwrap = use_bwrap

        legacy_steam_runtime_path = None
        use_steam_runtime = True

        if os.environ.get("STEAM_RUNTIME", "") != "0" and not self.cli_args.no_runtime:
            legacy_steam_runtime_path = find_legacy_steam_runtime_path(
                steam_root=self.steam_root
            )

            if not legacy_steam_runtime_path:
                self.exit("Steam Runtime was enabled but couldn't be found!")
        else:
            use_steam_runtime = False
            logger.info("Steam Runtime disabled.")

        self.use_steam_runtime = use_steam_runtime
        self.legacy_steam_runtime_path = legacy_steam_runtime_path
        self.use_bwrap = use_bwrap
        self.start_background_wineserver = start_background_wineserver

    def populate_winetricks(self, strict):
        """
        Populate Winetricks

        :param strict: If true, exit if Winetricks cannot be found.
        """
        # Find Winetricks
        winetricks_path = get_winetricks_path()
        if not winetricks_path and strict:
            self.exit(
                "Winetricks isn't installed, please install "
                "winetricks in order to use this command!"
            )

        self.winetricks_path = winetricks_path

    def populate_steam(self):
        """
        Populate the selected Steam installation, prompting the user first
        if multiple options exist
        """
        if not self.steam_path:
            steam_installations = find_steam_installations()
            if not steam_installations:
                self.exit("Steam installation directory could not be found.")

            self.steam_path, self.steam_root = select_steam_installation(
                steam_installations
            )
            if not self.steam_path:
                self.exit("No Steam installation was selected.")

    def populate_steam_apps(self):
        """
        Populate list of Steam apps for selected Steam installation
        """
        # Find any Steam library folders
        steam_lib_paths = get_steam_lib_paths(self.steam_path)

        # Check if Protontricks has access to all the required paths
        prompt_filesystem_access(
            paths=[self.steam_path, self.steam_root] + steam_lib_paths,
            show_dialog=self.cli_args.no_term
        )

        # Find any Steam apps
        self.steam_apps = get_steam_apps(
            steam_root=self.steam_root, steam_path=self.steam_path,
            steam_lib_paths=steam_lib_paths
        )
        self.steam_lib_paths = steam_lib_paths

    def populate_steam_app(self):
        """
        Populate the selected Proton-enabled Steam app
        """
        # If app ID was provided via command-line arguments, retrieve
        # app using it. Otherwise, show a graphical prompt.
        if self.cli_args.appid:
            # App ID provided, retrieve the corresponding app
            steam_appid = int(self.cli_args.appid)
            try:
                self.steam_app = next(
                    app for app in self.steam_apps
                    if app.is_windows_app and app.appid == steam_appid
                )
            except StopIteration:
                self.exit(
                    "Steam app with the given app ID could not be found. "
                    "Is it installed, Proton compatible and have you launched "
                    "it at least once? You can search for the app ID using "
                    "the following command:\n"
                    "$ protontricks -s <GAME NAME>"
                )
        else:
            has_installed_apps = any([
                app for app in self.steam_apps if app.is_windows_app
            ])

            if not has_installed_apps:
                self.exit(
                    "Found no games. You need to launch a game at least once "
                    "before Protontricks can find it."
                )

            # App ID not provided, prompt the user
            try:
                steam_app = select_steam_app_with_gui(
                    steam_apps=self.steam_apps, steam_path=self.steam_path
                )
                self.steam_app = steam_app
            except FileNotFoundError:
                self.exit(
                    "YAD or Zenity is not installed. "
                    "Either executable is required for the Protontricks GUI."
                )

    def populate_proton_app(self):
        """
        Populate the Proton app for the Steam app chosen prior
        """
        proton_app = find_proton_app(
            steam_path=self.steam_path, steam_apps=self.steam_apps,
            appid=self.steam_app.appid
        )

        if not proton_app:
            if os.environ.get("PROTON_VERSION"):
                # Print an error listing accepted values if PROTON_VERSION was
                # set, as the user is trying to use a certain Proton version
                proton_names = sorted(set([
                    app.name for app in self.steam_apps if app.is_proton
                ]))
                self.exit(
                    "Protontricks installation could not be found with given "
                    "$PROTON_VERSION!\n\n"
                    f"Valid values include: {', '.join(proton_names)}"
                )
            else:
                self.exit("Proton installation could not be found!")

        if not proton_app.is_proton_ready:
            self.exit(
                "Proton installation is incomplete. Have you launched a Steam "
                "app using this Proton version at least once to finish the "
                "installation?"
            )

        self.proton_app = proton_app

    def populate_all_steam_installations(self):
        """
        Populate all Steam installations
        """
        # Dict that maps installation type (Flatpak, Snap, native) to list
        # of found Steam installations.
        # In an ideal case each type will only have one installation or none,
        # but do not assume so.
        steam_dirs_by_type = defaultdict(list)

        steam_installations = find_steam_installations()

        for steam_path, steam_root in steam_installations:
            is_flatpak = (
                str(steam_path).endswith(
                    "/com.valvesoftware.Steam/.local/share/Steam"
                )
            )
            is_snap = any(
                str(steam_path).endswith(snap_dir)
                for snap_dir in SNAP_STEAM_DIRS
            )

            if is_flatpak:
                steam_dirs_by_type["Flatpak"].append((steam_path, steam_root))
            elif is_snap:
                steam_dirs_by_type["Snap"].append((steam_path, steam_root))
            else:
                steam_dirs_by_type["Native"].append((steam_path, steam_root))

        if not steam_dirs_by_type:
            self.exit("Found no Steam installations.")

        self.steam_dirs_by_type = steam_dirs_by_type

    def populate_all_steam_apps(self):
        """
        Populate all Steam apps for all found Steam installations
        """
        steam_apps_by_install_type = defaultdict(list)

        for install_type, steam_installations in \
                self.steam_dirs_by_type.items():
            for steam_path, steam_root in steam_installations:
                steam_lib_paths = get_steam_lib_paths(steam_path)
                steam_apps = get_steam_apps(
                    steam_root=steam_root, steam_path=steam_path,
                    steam_lib_paths=steam_lib_paths
                )

                steam_apps_by_install_type[install_type] += steam_apps

        self.steam_apps_by_install_type = steam_apps_by_install_type
