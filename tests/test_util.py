import stat
import textwrap
from pathlib import Path

import pytest

from protontricks.util import (create_wine_bin_dir, is_steam_deck, lower_dict,
                               run_command)


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
            home_dir, command_mock, monkeypatch):
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

        command = command_mock.commands[-1]
        assert command.args == ["echo", "nothing"]
        assert command.env["WINE"] == str(wine_bin_dir / "wine")
        assert command.env["WINELOADER"] == str(wine_bin_dir / "wine")
        assert command.env["WINESERVER"] == str(wine_bin_dir / "wineserver")

        assert command.env["WINE_BIN"] == str(
            default_proton.proton_dist_path / "bin" / "wine"
        )
        assert command.env["WINESERVER_BIN"] == str(
            default_proton.proton_dist_path / "bin" / "wineserver"
        )

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
        command = command_mock.commands[-1]
        assert command.args == ["echo", "nothing"]
        assert command.env["WINE"] == "/fake/wine"
        assert command.env["WINELOADER"] == "/fake/wine"
        assert command.env["WINESERVER"] == "/fake/wineserver"

    @pytest.mark.usefixtures("command_mock")
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

    @pytest.mark.usefixtures("steam_deck")
    def test_locale_fixed_on_steam_deck(
            self, proton_factory, default_proton, steam_app_factory, home_dir,
            command_mock, caplog):
        """
        Test that Protontricks will fix locale settings if nonexistent locale
        settings are detected and Steam Deck is used to run Protontricks
        """
        # Create binary to fake the 'locale' executable
        locale_script_path = home_dir / ".local" / "bin" / "locale"
        locale_script_path.write_text("""#!/bin/sh
            if [ "$1" = "-a" ]; then
                echo 'C'
                echo 'C.UTF-8'
                echo 'en_US'
                echo 'en_US.utf8'
            else
                echo 'LANG=fi_FI.UTF-8'
                echo 'LC_CTYPE=en_US.utf8'
                echo 'LC_TIME=en_US.UTF-8'
                echo 'LC_NUMERIC=D'
            fi
        """)
        locale_script_path.chmod(
            locale_script_path.stat().st_mode | stat.S_IEXEC
        )

        steam_app = steam_app_factory(name="Fake game", appid=10)
        run_command(
            winetricks_path=Path("/usr/bin/winetricks"),
            proton_app=default_proton,
            steam_app=steam_app,
            command=["/bin/env"],
            env={
                # Use same environment variables as in the mocked 'locale'
                # script
                "LANG": "fi_FI.UTF-8",
                "LC_CTYPE": "en_US.utf8",
                "LC_TIME": "en_US.UTF-8",
                "LC_NUMERIC": "D"
            }
        )

        # Warning will be logged to indicate 'LANG' was changed
        warning = next(
            record for record in caplog.records
            if record.levelname == "WARNING"
            and "locale has been reset" in record.getMessage()
        )
        assert warning.getMessage().endswith(
            "for the following categories: LANG, LC_NUMERIC"
        )

        # Ensure the incorrect locale settings were changed for the command
        command = command_mock.commands[-1]
        assert command.env["LANG"] == "en_US.UTF-8"
        # LC_CTYPE was not changed as 'en_US.UTF-8' and 'en_US.utf8'
        # are identical after normalization.
        assert command.env["LC_CTYPE"] == "en_US.utf8"
        assert command.env["LC_TIME"] == "en_US.UTF-8"
        assert command.env["LC_NUMERIC"] == "en_US.UTF-8"

    def test_bwrap_launcher_crash_detected(
            self, default_new_proton, steam_app_factory, command_mock):
        """
        Test that Protontricks will raise an exception if `bwrap-launcher`
        crashes unexpectedly
        """
        steam_app = steam_app_factory(name="Fake game", appid=10)

        # Mock a crashing 'bwrap-launcher'
        command_mock.launcher_working = False

        with pytest.raises(RuntimeError) as exc:
            run_command(
                winetricks_path=Path("/usr/bin/winetricks"),
                proton_app=default_new_proton,
                steam_app=steam_app,
                command=["echo", "nothing"],
                shell=True,
                use_steam_runtime=True
            )

        assert str(exc.value) == "bwrap launcher crashed, returncode: 1"


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


class TestIsSteamDeck:
    def test_not_steam_deck(self):
        """
        Test that non-Steam Deck environment is detected correctly
        """
        assert not is_steam_deck()

    @pytest.mark.usefixtures("steam_deck")
    def test_is_steam_deck(self):
        """
        Test that Steam Deck environment is detected correctly
        """
        assert is_steam_deck()
