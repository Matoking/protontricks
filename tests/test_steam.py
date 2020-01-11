import os
import shutil
import time
from pathlib import Path

from protontricks.steam import (SteamApp, find_appid_proton_prefix,
                                find_steam_path, find_steam_proton_app,
                                get_custom_proton_installations,
                                get_steam_apps)

import pytest


class TestSteamApp:
    def test_steam_app_from_appmanifest(self, steam_app_factory, steam_dir):
        """
        Create a SteamApp from an appmanifest file
        """
        steam_app = steam_app_factory(name="Fake game", appid=10)

        appmanifest_path = \
            Path(steam_app.install_path).parent.parent / "appmanifest_10.acf"

        steam_app = SteamApp.from_appmanifest(
            path=str(appmanifest_path),
            steam_lib_paths=[str(steam_dir / "steam" / "steamapps")]
        )

        assert steam_app.name == "Fake game"
        assert steam_app.appid == 10

    def test_steam_app_from_appmanifest_invalid(self, steam_app_factory):
        steam_app = steam_app_factory(name="Fake game", appid=10)

        appmanifest_path = \
            Path(steam_app.install_path).parent.parent / "appmanifest_10.acf"
        appmanifest_path.write_text("invalid")

        # Invalid appmanifest file is ignored
        assert not SteamApp.from_appmanifest(
            path=str(appmanifest_path),
            steam_lib_paths=[]
        )

    def test_steam_app_from_appmanifest_empty(self, steam_app_factory):
        steam_app = steam_app_factory(name="Fake game", appid=10)

        appmanifest_path = \
            Path(steam_app.install_path).parent.parent / "appmanifest_10.acf"
        appmanifest_path.write_text("")

        # Empty appmanifest file is ignored
        assert not SteamApp.from_appmanifest(
            path=str(appmanifest_path),
            steam_lib_paths=[]
        )


class TestFindSteamProtonApp:
    def test_find_steam_specific_app_proton(
            self, steam_app_factory, steam_dir, default_proton,
            proton_factory):
        """
        Set a specific Proton version for a game and check that it is
        detected correctly
        """
        custom_proton = proton_factory(
            name="Proton 6.66", appid=54440, compat_tool_name="proton_6_66"
        )
        steam_app_factory(
            name="Fake game", appid=10,
            compat_tool_name="proton_6_66")

        proton_app = find_steam_proton_app(
            steam_path=str(steam_dir),
            steam_apps=[default_proton, custom_proton],
            appid=10
        )

        # Proton 4.20 is the global default, but Proton 6.66 is the selected
        # version for this game
        assert proton_app.name == "Proton 6.66"


class TestFindAppidProtonPrefix:
    def test_find_appid_proton_prefix_steamapps_case(
            self, steam_app_factory, steam_dir, default_proton,
            steam_library_factory):
        """
        Find the proton prefix directory for a game located inside
        a "SteamApps" directory instead of the default "steamapps".

        Regression test for #33.
        """
        library_dir = steam_library_factory("TestLibrary")
        steam_app_factory(name="Test game", appid=10, library_dir=library_dir)

        os.rename(
            str(library_dir / "steamapps"),
            str(library_dir / "SteamApps")
        )

        path = find_appid_proton_prefix(
            appid=10, steam_lib_paths=[str(steam_dir), str(library_dir)]
        )

        assert path == str(
            library_dir / "SteamApps" / "compatdata" / "10" / "pfx"
        )

    def test_find_appid_proton_prefix_latest_compatdata(
            self, steam_app_factory, steam_library_factory):
        """
        Find the correct Proton prefix directory for a game that has
        three compatdata directories, two of which are old.
        """
        library_dir_a = steam_library_factory("TestLibraryA")
        library_dir_b = steam_library_factory("TestLibraryB")
        library_dir_c = steam_library_factory("TestLibraryC")
        steam_app_factory(
            name="Test game", appid=10, library_dir=library_dir_a
        )

        shutil.copytree(
            str(library_dir_a / "steamapps" / "compatdata"),
            str(library_dir_b / "steamapps" / "compatdata"),
        )
        shutil.copytree(
            str(library_dir_a / "steamapps" / "compatdata"),
            str(library_dir_c / "steamapps" / "compatdata")
        )

        # Give the copy in library B the most recent modification timestamp
        os.utime(
            str(library_dir_a / "steamapps" / "compatdata" / "10" / "pfx.lock"),
            (time.time() - 100, time.time() - 100)
        )
        os.utime(
            str(library_dir_b / "steamapps" / "compatdata" / "10" / "pfx.lock"),
            (time.time() - 25, time.time() - 25)
        )
        os.utime(
            str(library_dir_c / "steamapps" / "compatdata" / "10" / "pfx.lock"),
            (time.time() - 50, time.time() - 50)
        )

        path = find_appid_proton_prefix(
            appid=10,
            steam_lib_paths=[
                str(library_dir_a), str(library_dir_b), str(library_dir_c)
            ]
        )
        assert path == str(
            library_dir_b / "steamapps" / "compatdata" / "10" / "pfx"
        )


class TestFindSteamPath:
    def test_find_steam_path_env(
            self, steam_dir, steam_root, tmp_path, monkeypatch):
        """
        Ensure the Steam directory is found when using STEAM_DIR env var
        and when both runtime and steamapps directories exist inside
        the path
        """
        custom_path = tmp_path / "custom_steam"
        custom_path.mkdir()

        monkeypatch.setenv("STEAM_DIR", str(custom_path))

        os.rename(
            str(steam_dir / "steamapps"),
            str(custom_path / "steamapps")
        )

        # The path isn't valid yet
        assert find_steam_path() == (None, None)

        os.rename(
            str(steam_root / "ubuntu12_32"),
            str(custom_path / "ubuntu12_32")
        )
        assert find_steam_path() == (str(custom_path), str(custom_path))


class TestGetSteamApps:
    def test_get_steam_apps_custom_proton(
            self, default_proton, custom_proton_factory, steam_dir,
            steam_root):
        """
        Create a custom Proton installation and ensure
        'get_steam_apps' can find it
        """
        custom_proton = custom_proton_factory(name="Custom Proton")

        steam_apps = get_steam_apps(
            steam_root=str(steam_root),
            steam_path=str(steam_dir),
            steam_lib_paths=[str(steam_dir)]
        )

        assert len(steam_apps) == 2

        found_custom_proton = next(
            app for app in steam_apps
            if app.name == "Custom Proton"
        )
        assert found_custom_proton.install_path == \
            str(custom_proton.install_path)

    def test_get_steam_apps_in_library_folder(
            self, default_proton, steam_library_factory, steam_app_factory,
            steam_dir, steam_root):
        """
        Create two games, one installed in the Steam installation directory
        and another in a Steam library folder
        """
        library_dir = steam_library_factory(name="GameDrive")
        steam_app_factory(name="Fake game 1", appid=10)
        steam_app_factory(
            name="Fake game 2", appid=20, library_dir=library_dir)

        steam_apps = get_steam_apps(
            steam_root=str(steam_root),
            steam_path=str(steam_dir),
            steam_lib_paths=[str(steam_dir), str(library_dir)]
        )

        # Two games and the default Proton installation should be found
        assert len(steam_apps) == 3
        steam_app_a = next(app for app in steam_apps if app.appid == 10)
        steam_app_b = next(app for app in steam_apps if app.appid == 20)

        assert steam_app_a.install_path == \
            str(steam_dir / "steamapps" / "common" / "Fake game 1")
        assert steam_app_b.install_path == \
            str(library_dir / "steamapps" / "common" / "Fake game 2")

    def test_get_steam_apps_proton_precedence(
            self, custom_proton_factory, home_dir, steam_root, steam_dir,
            monkeypatch):
        """
        Create two Proton apps with the same name but located in
        different paths. Only one will be returned due to precedence
        in the directory paths
        """
        custom_compat_dir = home_dir / "CompatTools"

        monkeypatch.setenv(
            "STEAM_EXTRA_COMPAT_TOOLS_PATHS", str(custom_compat_dir)
        )

        proton_app_a = custom_proton_factory(
            name="Fake Proton", compat_tool_dir=custom_compat_dir
        )

        steam_apps = get_steam_apps(
            steam_root=str(steam_root),
            steam_path=str(steam_dir),
            steam_lib_paths=[str(steam_dir)]
        )
        assert len(steam_apps) == 1
        assert steam_apps[0].install_path == proton_app_a.install_path

        # Create a Proton app with the same name in the default directory;
        # this will override the former Proton app we created
        proton_app_b = custom_proton_factory(name="Fake Proton")

        steam_apps = get_steam_apps(
            steam_root=str(steam_root),
            steam_path=str(steam_dir),
            steam_lib_paths=[str(steam_dir)]
        )
        assert len(steam_apps) == 1
        assert steam_apps[0].install_path == proton_app_b.install_path
