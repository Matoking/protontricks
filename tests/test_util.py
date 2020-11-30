from pathlib import Path

from protontricks.util import create_wine_bin_dir, run_command


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
        assert set(["wine", "wineserver"]) == files

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
        assert set(["wine", "winedine"]) == files


class TestRunCommand:
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
            steam_runtime_path=steam_runtime_medic.install_path
        )

        # Warning will be logged since Protontricks does not recognize
        # Steam Runtime Medic and can't ensure it's being configured correctly
        warning = next(
            record for record in caplog.records
            if record.levelname == "WARNING"
        )
        assert warning.getMessage() == \
            "Current Steam Runtime not recognized by Protontricks."
