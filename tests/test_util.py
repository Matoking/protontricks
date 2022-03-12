from pathlib import Path

from protontricks.util import (create_wine_bin_dir,
                               get_running_flatpak_version, lower_dict,
                               run_command, get_inaccessible_paths)


def get_files_in_dir(d):
    return {binary.name for binary in d.iterdir()}


class TestCreateWineBinDir:
    def test_wine_bin_dir_updated(self, home_dir, default_proton):
        """
        Test that the directory containing the helper scripts is kept
        up-to-date with the Proton installation's binaries
        """
        create_wine_bin_dir(default_proton)

        # Check that the Wine binaries exist
        files = get_files_in_dir(
            home_dir / ".cache" / "protontricks" / "proton" / "Proton 4.20"
            / "bin"
        )
        assert set([
            "wine", "wineserver", "wineserver-keepalive", "bwrap-launcher",
            "wineserver-keepalive.bat"
        ]) == files

        # Create a new binary for the Proton installation and delete another
        # one
        proton_bin_path = Path(default_proton.install_path) / "dist" / "bin"

        (proton_bin_path / "winedine").touch()
        (proton_bin_path / "wineserver").unlink()

        # The old scripts will be deleted and regenerated now that the Proton
        # installation's contents changed
        create_wine_bin_dir(default_proton)

        files = get_files_in_dir(
            home_dir / ".cache" / "protontricks" / "proton" / "Proton 4.20"
            / "bin"
        )
        # Scripts are regenerated
        assert set([
            "wine", "winedine", "wineserver-keepalive", "bwrap-launcher",
            "wineserver-keepalive.bat"
        ]) == files


class TestRunCommand:
    def test_user_environment_variables_used(
            self, default_proton, steam_runtime_dir, steam_app_factory,
            home_dir, commands, monkeypatch):
        """
        Test that user-provided environment variables are used even when
        Steam Runtime is enabled
        """
        steam_app = steam_app_factory(name="Fake game", appid=10)

        run_command(
            winetricks_path=Path("/usr/bin/winetricks"),
            proton_app=default_proton,
            steam_app=steam_app,
            command=["echo", "nothing"],
            use_steam_runtime=True,
            legacy_steam_runtime_path=steam_runtime_dir / "steam-runtime"
        )

        # Proxy scripts are used if no environment variables are set by the
        # user
        wine_bin_dir = (
            home_dir / ".cache" / "protontricks" / "proton" / "Proton 4.20"
            / "bin"
        )

        command = commands[-1]
        assert command.args == ["echo", "nothing"]
        assert command.env["WINE"] == str(wine_bin_dir / "wine")
        assert command.env["WINELOADER"] == str(wine_bin_dir / "wine")
        assert command.env["WINESERVER"] == str(wine_bin_dir / "wineserver")

        monkeypatch.setenv("WINE", "/fake/wine")
        monkeypatch.setenv("WINESERVER", "/fake/wineserver")

        run_command(
            winetricks_path=Path("/usr/bin/winetricks"),
            proton_app=default_proton,
            steam_app=steam_app,
            command=["echo", "nothing"],
            use_steam_runtime=True,
            legacy_steam_runtime_path=steam_runtime_dir / "steam-runtime"
        )

        # User provided Wine paths are used even when Steam Runtime is enabled
        command = commands[-1]
        assert command.args == ["echo", "nothing"]
        assert command.env["WINE"] == "/fake/wine"
        assert command.env["WINELOADER"] == "/fake/wine"
        assert command.env["WINESERVER"] == "/fake/wineserver"

    def test_unknown_steam_runtime_detected(
            self, home_dir, proton_factory, runtime_app_factory,
            steam_app_factory, caplog):
        """
        Test that Protontricks will log a warning if it encounters a Steam
        Runtime it does not recognize
        """
        steam_runtime_medic = runtime_app_factory(
            name="Steam Linux Runtime - Medic",
            appid=14242420,
            runtime_dir_name="medic"
        )
        proton_app = proton_factory(
            name="Proton 5.20", appid=100, compat_tool_name="proton_520",
            is_default_proton=True, required_tool_app=steam_runtime_medic
        )
        steam_app = steam_app_factory(name="Fake game", appid=10)

        run_command(
            winetricks_path=Path("/usr/bin/winetricks"),
            proton_app=proton_app,
            steam_app=steam_app,
            command=["echo", "nothing"],
            shell=True,
            use_steam_runtime=True
        )

        # Warning will be logged since Protontricks does not recognize
        # Steam Runtime Medic and can't ensure it's being configured correctly
        warning = next(
            record for record in caplog.records
            if record.levelname == "WARNING"
            and "not recognized" in record.getMessage()
        )
        assert warning.getMessage() == \
            "Current Steam Runtime not recognized by Protontricks."


class TestLowerDict:
    def test_lower_nested_dict(self):
        """
        Turn all keys in a nested dictionary to lowercase using `lower_dict`
        """
        before = {
            "AppState": {
                "Name": "Blah",
                "appid": 123450,
                "userconfig": {
                    "Language": "English"
                }
            }
        }

        after = {
            "appstate": {
                "name": "Blah",
                "appid": 123450,
                "userconfig": {
                    "language": "English"
                }
            }
        }

        assert lower_dict(before) == after


class TestGetRunningFlatpakVersion:
    def test_flatpak_not_active(self):
        """
        Test Flatpak version detection when Flatpak is not active
        """
        assert get_running_flatpak_version() is None

    def test_flatpak_active(self, monkeypatch, tmp_path):
        """
        Test Flatpak version detection when Flatpak is active
        """
        flatpak_info_path = tmp_path / "flatpak-info"

        flatpak_info_path.write_text(
            "[Application]\n"
            "name=fake.flatpak.Protontricks\n"
            "\n"
            "[Instance]\n"
            "flatpak-version=1.12.1"
        )
        monkeypatch.setattr(
            "protontricks.util.FLATPAK_INFO_PATH", str(flatpak_info_path)
        )

        assert get_running_flatpak_version() == (1, 12, 1)


class TestGetInaccessiblePaths:
    def test_flatpak_disabled(self):
        """
        Test that an empty list is returned if Flatpak is not active
        """
        assert get_inaccessible_paths(["/fake", "/fake_2"]) == []

    def test_flatpak_active(self, monkeypatch, tmp_path):
        """
        Test that inaccessible paths are correctly detected when
        Flatpak is active
        """
        flatpak_info_path = tmp_path / "flatpak-info"

        flatpak_info_path.write_text(
            "[Application]\n"
            "name=fake.flatpak.Protontricks\n"
            "\n"
            "[Instance]\n"
            "flatpak-version=1.12.1\n"
            "\n"
            "[Context]\n"
            "filesystems=/mnt/SSD_A;/mnt/SSD_B;xdg-data/Steam;"
        )
        monkeypatch.setattr(
            "protontricks.util.FLATPAK_INFO_PATH", str(flatpak_info_path)
        )

        inaccessible_paths = get_inaccessible_paths([
            "/mnt/SSD_A", "/mnt/SSD_C", "~/.local/share/SteamOld",
            "~/.local/share/Steam"
        ])
        assert len(inaccessible_paths) == 2
        assert str(inaccessible_paths[0]) == "/mnt/SSD_C"
        assert str(inaccessible_paths[1]) == \
            str(Path("~/.local/share/SteamOld").resolve())

    def test_flatpak_home(self, monkeypatch, tmp_path, home_dir):
        """
        Test that 'home' filesystem permission grants permission to the
        home directory
        """
        flatpak_info_path = tmp_path / "flatpak-info"

        flatpak_info_path.write_text(
            "[Application]\n"
            "name=fake.flatpak.Protontricks\n"
            "\n"
            "[Instance]\n"
            "flatpak-version=1.12.1\n"
            "\n"
            "[Context]\n"
            "filesystems=home;"
        )
        monkeypatch.setattr(
            "protontricks.util.FLATPAK_INFO_PATH", str(flatpak_info_path)
        )

        inaccessible_paths = get_inaccessible_paths([
            "/mnt/SSD_A", "/var/fake_path",
            str(home_dir / "fake_path"),
            str(home_dir / ".local/share/FakePath")
        ])

        assert len(inaccessible_paths) == 2
        assert str(inaccessible_paths[0]) == "/mnt/SSD_A"
        assert str(inaccessible_paths[1]) == "/var/fake_path"

    def test_flatpak_host(self, monkeypatch, tmp_path, home_dir):
        """
        Test that 'host' filesystem permission grants permission to the
        whole file system
        """
        flatpak_info_path = tmp_path / "flatpak-info"

        flatpak_info_path.write_text(
            "[Application]\n"
            "name=fake.flatpak.Protontricks\n"
            "\n"
            "[Instance]\n"
            "flatpak-version=1.12.1\n"
            "\n"
            "[Context]\n"
            "filesystems=host;"
        )
        monkeypatch.setattr(
            "protontricks.util.FLATPAK_INFO_PATH", str(flatpak_info_path)
        )

        inaccessible_paths = get_inaccessible_paths([
            "/mnt/SSD_A", "/var/fake_path",
            str(home_dir / "fake_path"),
        ])

        assert len(inaccessible_paths) == 0

    def test_flatpak_unknown_permission(self, monkeypatch, tmp_path, caplog):
        """
        Test that unknown filesystem permissions are ignored
        """
        flatpak_info_path = tmp_path / "flatpak-info"

        flatpak_info_path.write_text(
            "[Application]\n"
            "name=fake.flatpak.Protontricks\n"
            "\n"
            "[Instance]\n"
            "flatpak-version=1.12.1\n"
            "\n"
            "[Context]\n"
            "filesystems=home;unknown-fs;"
        )
        monkeypatch.setattr(
            "protontricks.util.FLATPAK_INFO_PATH", str(flatpak_info_path)
        )

        inaccessible_paths = get_inaccessible_paths([
            "/mnt/SSD",
        ])

        assert len(inaccessible_paths) == 1

        # Unknown filesystem permission is logged
        records = caplog.records

        assert len(records) == 1
        assert records[0].levelname == "WARNING"
        assert "Unknown Flatpak file system permission 'unknown-fs'" \
            in records[0].message
