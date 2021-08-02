import os
import shutil
import time
from pathlib import Path

import pytest
import vdf

from protontricks.steam import (SteamApp, find_appid_proton_prefix,
                                find_steam_compat_tool_app, find_steam_path,
                                get_custom_compat_tool_installations,
                                get_custom_windows_shortcuts, get_steam_apps,
                                get_steam_lib_paths)


class TestSteamApp:
    def test_steam_app_from_appmanifest(self, steam_app_factory, steam_dir):
        """
        Create a SteamApp from an appmanifest file
        """
        steam_app = steam_app_factory(name="Fake game", appid=10)

        appmanifest_path = \
            Path(steam_app.install_path).parent.parent / "appmanifest_10.acf"

        steam_app = SteamApp.from_appmanifest(
            path=appmanifest_path,
            steam_lib_paths=[steam_dir / "steam" / "steamapps"]
        )

        assert steam_app.name == "Fake game"
        assert steam_app.appid == 10

    @pytest.mark.parametrize(
        "content",
        [
            b"",  # Empty VDF is ignored
            b"corrupted",  # Can't be parsed as VDF
            bytes([255]),  # Can't be decoded as Unicode
        ]
    )
    def test_steam_app_from_appmanifest_invalid(
            self, steam_app_factory, content):
        steam_app = steam_app_factory(name="Fake game", appid=10)

        appmanifest_path = \
            Path(steam_app.install_path).parent.parent / "appmanifest_10.acf"
        appmanifest_path.write_bytes(content)

        # Invalid appmanifest file is ignored
        assert not SteamApp.from_appmanifest(
            path=appmanifest_path,
            steam_lib_paths=[]
        )

    def test_steam_app_from_appmanifest_empty(self, steam_app_factory):
        """
        Try to deserialize an empty appmanifest and check that no SteamApp
        is returned
        """
        steam_app = steam_app_factory(name="Fake game", appid=10)

        appmanifest_path = \
            Path(steam_app.install_path).parent.parent / "appmanifest_10.acf"
        appmanifest_path.write_text("")

        # Empty appmanifest file is ignored
        assert not SteamApp.from_appmanifest(
            path=appmanifest_path,
            steam_lib_paths=[]
        )

    @pytest.mark.parametrize(
        "content",
        [
            b"",  # Empty VDF is ignored
            b"corrupted",  # Can't be parsed as VDF
        ]
    )
    def test_steam_app_from_appmanifest_corrupted_toolmanifest(
            self, steam_runtime_soldier, proton_factory, caplog, content):
        """
        Test trying to a SteamApp manifest from an incomplete
        Proton installation with an empty or corrupted toolmanifest.vdf file
        """
        proton_app = proton_factory(
            name="Proton 5.13", appid=10, compat_tool_name="proton_513",
            required_tool_app=steam_runtime_soldier
        )
        # Empty the "toolmanifest.vdf" file
        (proton_app.install_path / "toolmanifest.vdf").write_bytes(content)

        assert not SteamApp.from_appmanifest(
            path=proton_app.install_path.parent.parent / "appmanifest_10.acf",
            steam_lib_paths=[]
        )

        assert len(caplog.records) == 1
        record = caplog.records[0]

        assert "Tool manifest for Proton 5.13 is empty" in record.message

    def test_steam_app_from_appmanifest_permission_denied(
            self, steam_app_factory, caplog, monkeypatch):
        """
        Test trying to read a SteamApp manifest that the user doesn't
        have read permission for
        """
        def _mock_read_text(self, encoding=None):
            """
            Mock `pathlib.Path.read_text` that mimics a failure due to
            insufficient permissions
            """
            raise PermissionError("Permission denied")

        steam_app = steam_app_factory(name="Fake game", appid=10)

        appmanifest_path = \
            Path(steam_app.install_path).parent.parent / "appmanifest_10.acf"

        monkeypatch.setattr(
            "pathlib.Path.read_text", _mock_read_text
        )

        assert not SteamApp.from_appmanifest(
            path=appmanifest_path, steam_lib_paths=[]
        )

        record = caplog.records[-1]
        assert record.getMessage() == (
            "Skipping appmanifest {} due to insufficient permissions".format(
                str(appmanifest_path)
            )
        )

    def test_steam_app_proton_dist_path(self, default_proton):
        """
        Check that correct path to Proton binarires and libraries is found
        using the `SteamApp.proton_dist_path` property
        """
        # 'dist' exists and is found correctly
        assert str(default_proton.proton_dist_path).endswith(
            "Proton 4.20/dist"
        )

        # Create a copy named 'files'. This will be favored over 'dist'.
        shutil.copytree(
            str(default_proton.install_path / "dist"),
            str(default_proton.install_path / "files")
        )
        assert str(default_proton.proton_dist_path).endswith(
            "Proton 4.20/files"
        )

        # If neither exists, None is returned
        shutil.rmtree(str(default_proton.install_path / "dist"))
        shutil.rmtree(str(default_proton.install_path / "files"))
        assert default_proton.proton_dist_path is None

    def test_steam_app_userconfig_name(self, steam_app_factory):
        """
        Try creating a SteamApp from an older version of the app manifest
        which contains the application name in a different field

        See GitHub issue #103 for details
        """
        steam_app = steam_app_factory(name="Fake game", appid=10)

        appmanifest_path = \
            Path(steam_app.install_path).parent.parent / "appmanifest_10.acf"
        data = vdf.loads(appmanifest_path.read_text())

        # Older installations store the name in `userconfig/name` instead
        del data["AppState"]["name"]
        data["AppState"]["userconfig"] = {
            "name": "Fake game"
        }

        appmanifest_path.write_text(vdf.dumps(data))

        app = SteamApp.from_appmanifest(
            path=appmanifest_path,
            steam_lib_paths=[]
        )

        assert app.name == "Fake game"


class TestFindSteamCompatToolApp:
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

        proton_app = find_steam_compat_tool_app(
            steam_path=steam_dir,
            steam_apps=[default_proton, custom_proton],
            appid=10
        )

        # Proton 4.20 is the global default, but Proton 6.66 is the selected
        # version for this game
        assert proton_app.name == "Proton 6.66"


class TestFindLibraryPaths:
    @pytest.mark.parametrize(
        "new_struct", [False, True], ids=["old struct", "new struct"]
    )
    def test_get_steam_lib_paths(
            self, steam_dir, steam_library_factory, new_struct):
        """
        Find the Steam library folders generated with either the old or new
        structure.
        Older Steam releases only use a field value containing the path
        to the library, while newer releases store a dict with additional
        information besides the library path.
        """
        library_a = steam_library_factory(
            "TestLibrary_A", new_struct=new_struct
        )
        library_b = steam_library_factory(
            "TestLibrary_B", new_struct=new_struct
        )

        lib_paths = get_steam_lib_paths(steam_dir)
        lib_paths.sort(key=lambda path: str(path))

        assert len(lib_paths) == 3
        assert str(lib_paths[0]) == str(steam_dir)
        assert str(lib_paths[1]) == str(library_a)
        assert str(lib_paths[2]) == str(library_b)

    def test_get_steam_lib_paths_corrupted_libraryfolders(
            self, steam_dir, steam_library_factory):
        """
        Try to find the Steam library folders and ensure a corrupted
        libraryfolders.vdf causes an exception to be raised
        """
        steam_library_factory("TestLibrary")

        (steam_dir / "steamapps" / "libraryfolders.vdf").write_text(
            "Corrupted"
        )

        with pytest.raises(ValueError) as exc:
            get_steam_lib_paths(steam_dir)

        assert "Library folder configuration file" in str(exc.value)


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
            appid=10, steam_lib_paths=[steam_dir, library_dir]
        )

        assert path == \
            library_dir / "SteamApps" / "compatdata" / "10" / "pfx"

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
            steam_lib_paths=[library_dir_a, library_dir_b, library_dir_c]
        )
        assert \
            path == library_dir_b / "steamapps" / "compatdata" / "10" / "pfx"


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
        steam_paths = find_steam_path()
        assert str(steam_paths[0]) == str(custom_path)
        assert str(steam_paths[1]) == str(custom_path)


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
            steam_root=steam_root,
            steam_path=steam_dir,
            steam_lib_paths=[steam_dir]
        )

        assert len(steam_apps) == 2

        found_custom_proton = next(
            app for app in steam_apps
            if app.name == "Custom Proton"
        )
        assert str(found_custom_proton.install_path) == \
            str(custom_proton.install_path)

    def test_get_steam_apps_custom_proton_empty_toolmanifest(
            self, custom_proton_factory, steam_runtime_soldier,
            steam_dir, steam_root, caplog):
        """
        Create a custom Proton installation with an empty toolmanifest and
        ensure a warning is printed and the app is ignored
        """
        custom_proton = custom_proton_factory(name="Custom Proton")
        (custom_proton.install_path / "toolmanifest.vdf").write_text("")

        steam_apps = get_steam_apps(
            steam_root=steam_root,
            steam_path=steam_dir,
            steam_lib_paths=[steam_dir]
        )

        # Custom Proton is skipped due to empty tool manifest
        assert not any(
            app for app in steam_apps if app.name == "Custom Proton"
        )

        assert len([
            record for record in caplog.records
            if record.levelname == "WARNING"
        ]) == 1

        record = next(
            record for record in caplog.records
            if record.levelname == "WARNING"
        )

        assert record.getMessage().startswith(
            "Tool manifest for Custom Proton is empty"
        )

    def test_get_steam_apps_custom_proton_corrupted_compatibilitytool(
            self, custom_proton_factory, steam_dir, steam_root, caplog):
        """
        Create a custom Proton installation with a corrupted
        compatibilitytool.vdf and ensure a warning is printed and the app
        is ignored
        """
        custom_proton = custom_proton_factory(name="Custom Proton")
        (custom_proton.install_path / "compatibilitytool.vdf").write_text(
            "corrupted"
        )

        steam_apps = get_steam_apps(
            steam_root=steam_root,
            steam_path=steam_dir,
            steam_lib_paths=[steam_dir]
        )

        # Custom Proton is skipped due to empty tool manifest
        assert not any(
            app for app in steam_apps if app.name == "Custom Proton"
        )

        assert len([
            record for record in caplog.records
            if record.levelname == "WARNING"
        ]) == 1

        record = next(
            record for record in caplog.records
            if record.levelname == "WARNING"
        )

        assert record.getMessage().startswith(
            "Compatibility tool declaration at"
        )

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
            steam_root=steam_root,
            steam_path=steam_dir,
            steam_lib_paths=[steam_dir, library_dir]
        )

        # Two games and the default Proton installation should be found
        assert len(steam_apps) == 3
        steam_app_a = next(app for app in steam_apps if app.appid == 10)
        steam_app_b = next(app for app in steam_apps if app.appid == 20)

        assert str(steam_app_a.install_path) == \
            str(steam_dir / "steamapps" / "common" / "Fake game 1")
        assert str(steam_app_b.install_path) == \
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
            steam_root=steam_root,
            steam_path=steam_dir,
            steam_lib_paths=[steam_dir]
        )
        assert len(steam_apps) == 1
        assert str(steam_apps[0].install_path) == \
            str(proton_app_a.install_path)

        # Create a Proton app with the same name in the default directory;
        # this will override the former Proton app we created
        proton_app_b = custom_proton_factory(name="Fake Proton")

        steam_apps = get_steam_apps(
            steam_root=steam_root,
            steam_path=steam_dir,
            steam_lib_paths=[steam_dir]
        )
        assert len(steam_apps) == 1
        assert str(steam_apps[0].install_path) == \
            str(proton_app_b.install_path)

    def test_get_steam_apps_escape_chars(
            self, steam_app_factory, steam_library_factory,
            steam_root, steam_dir):
        """
        Create a Steam library directory with a name containing the
        character '[' and ensure it is found correctly.

        Regression test for https://github.com/Matoking/protontricks/issues/47
        """
        library_dir = steam_library_factory(name="[HDD-1] SteamLibrary")
        steam_app_factory(name="Test game", appid=10, library_dir=library_dir)

        steam_apps = get_steam_apps(
            steam_root=steam_root,
            steam_path=steam_dir,
            steam_lib_paths=[steam_dir, library_dir]
        )

        assert len(steam_apps) == 1
        assert steam_apps[0].name == "Test game"
        assert str(steam_apps[0].install_path).startswith(str(library_dir))

    def test_get_steam_apps_steamapps_case_warning(
            self, steam_root, steam_dir, caplog):
        """
        Ensure a warning is logged if both 'steamapps' and 'SteamApps'
        directories exist at one of the Steam library directories
        """
        get_steam_apps(
            steam_root=steam_root,
            steam_path=steam_dir,
            steam_lib_paths=[steam_dir]
        )

        # No log was created yet
        assert len([
            record for record in caplog.records
            if record.levelname == "WARNING"
        ]) == 0

        (steam_dir / "SteamApps").mkdir()

        get_steam_apps(
            steam_root=steam_root,
            steam_path=steam_dir,
            steam_lib_paths=[steam_dir]
        )

        # Warning was logged due to two Steam app directories
        log = next(
            record for record in caplog.records
            if record.levelname == "WARNING"
        )
        assert (
            "directories were found at {}".format(str(steam_dir))
            in log.getMessage()
        )

    def test_get_steam_apps_steamapps_case_insensitive_fs(
            self, monkeypatch, steam_root, steam_dir, caplog):
        """
        Ensure that the "'steamapps' and 'SteamApps' both exist" warning
        is not printed if a case-insensitive file system is in use

        Regression test for https://github.com/Matoking/protontricks/issues/112
        """
        def _mock_is_dir(self):
            return self.name in ("steamapps", "SteamApps")

        # Mock the "existence" of both 'steamapps' and 'SteamApps' by
        # monkeypatching pathlib
        monkeypatch.setattr("pathlib.Path.is_dir", _mock_is_dir)

        get_steam_apps(
            steam_root=steam_root,
            steam_path=steam_dir,
            steam_lib_paths=[steam_dir]
        )

        # No warning is printed
        assert len([
            record for record in caplog.records
            if record.levelname == "WARNING"
        ]) == 0


class TestGetWindowsShortcuts:
    def test_get_custom_windows_shortcuts_derive_appid(
            self, steam_dir, shortcut_factory):
        """
        Retrieve custom Windows shortcut. The app ID is derived from the
        executable name since it's not found in shortcuts.vdf.
        """
        shortcut_factory(install_dir="fake/path/", name="fakegame.exe")

        shortcut_apps = get_custom_windows_shortcuts(steam_dir)

        assert len(shortcut_apps) == 1
        assert shortcut_apps[0].name == "Non-Steam shortcut: fakegame.exe"
        assert shortcut_apps[0].appid == 4149337689

    def test_get_custom_windows_shortcuts_read_vdf(
            self, steam_dir, shortcut_factory):
        """
        Retrieve custom Windows shortcut. The app ID is read and derived
        directly from the shortcuts.vdf, which is used on newer Steam versions.
        """
        shortcut_factory(
            install_dir="fake/path/", name="fakegame.exe",
            appid_in_vdf=True
        )

        shortcut_apps = get_custom_windows_shortcuts(steam_dir)

        assert len(shortcut_apps) == 1
        assert shortcut_apps[0].name == "Non-Steam shortcut: fakegame.exe"
        assert shortcut_apps[0].appid == 4149337689
