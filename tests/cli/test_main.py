import os
import shutil
from pathlib import Path

import pytest


class TestCLIRun:
    def test_run_winetricks(
            self, cli, steam_app_factory, default_proton, command,
            home_dir):
        """
        Perform a Protontricks command directly for a certain game
        """
        proton_install_path = Path(default_proton.install_path)

        steam_app = steam_app_factory(name="Fake game 1", appid=10)

        cli(["10", "winecfg"], env={"STEAM_RUNTIME": "0"})

        # winecfg was actually run
        assert str(command.args[0]).endswith(".local/bin/winetricks")
        assert command.args[1] == "winecfg"

        # Correct environment vars were set
        assert command.env["PROTON_PATH"] == str(proton_install_path)
        assert command.env["PROTON_DIST_PATH"] == \
            str(proton_install_path / "dist")
        assert command.env["WINETRICKS"] == str(
            home_dir / ".local" / "bin" / "winetricks")
        assert command.env["WINEPREFIX"] == str(steam_app.prefix_path)
        assert command.env["WINELOADER"] == command.env["WINE"]
        assert command.env["WINEDLLPATH"] == "{}{}{}".format(
            str(proton_install_path / "dist" / "lib64" / "wine"),
            os.pathsep,
            str(proton_install_path / "dist" / "lib" / "wine")
        )

    def test_run_winetricks_shortcut(
            self, cli, shortcut_factory, default_proton, command,
            steam_dir):
        """
        Perform a Protontricks command for a non-Steam shortcut
        """
        proton_install_path = Path(default_proton.install_path)
        shortcut_factory(install_dir="fake/path/", name="fakegame.exe")

        cli(["4149337689", "winecfg"])

        # Default Proton is used
        assert command.env["PROTON_PATH"] == str(proton_install_path)
        assert command.env["WINEPREFIX"] == str(
            steam_dir / "steamapps" / "compatdata" / "4149337689" / "pfx")

    def test_run_winetricks_select_proton(
            self, cli, steam_app_factory, default_proton,
            custom_proton_factory, command, home_dir):
        """
        Perform a Protontricks command while selecting a specific
        Proton version using PROTON_VERSION env var
        """
        steam_app_factory(name="Fake game", appid=10)
        custom_proton = custom_proton_factory(name="Custom Proton")
        cli(["10", "winecfg"], env={"PROTON_VERSION": "Custom Proton"})

        assert command.env["PROTON_PATH"] == str(custom_proton.install_path)

    def test_run_winetricks_select_steam(
            self, cli, steam_app_factory, default_proton, command,
            home_dir):
        """
        Perform a Protontricks command while selecting a specific
        Steam installation directory
        """
        steam_app_factory(name="Fake game", appid=10)
        os.rename(
            str(home_dir / ".steam" / "steam"),
            str(home_dir / ".steam_new")
        )
        os.rename(
            str(home_dir / ".steam" / "root" / "ubuntu12_32"),
            str(home_dir / ".steam_new" / "ubuntu12_32")
        )

        cli(
            ["10", "winecfg"],
            env={"STEAM_DIR": str(home_dir / ".steam_new")}
        )

        assert command.env["WINE"] == str(
            home_dir / ".cache" / "protontricks" / "proton"
            / "Proton 4.20" / "bin" / "wine"
        )
        assert command.env["PROTON_PATH"] == str(
            home_dir / ".steam_new" / "steamapps" / "common"
            / "Proton 4.20"
        )

    def test_run_winetricks_steam_runtime_v1(
            self, cli, steam_app_factory, steam_runtime_dir, default_proton,
            command, home_dir):
        """
        Perform a Protontricks command using the older Steam Runtime
        bundled with Steam
        """
        steam_app_factory(name="Fake game 1", appid=10)

        cli(["10", "winecfg"], env={"STEAM_RUNTIME": "1"})

        wine_bin_dir = (
            home_dir / ".cache" / "protontricks" / "proton" / "Proton 4.20"
            / "bin"
        )

        # winecfg was actually run
        assert str(command.args[0]).endswith(".local/bin/winetricks")
        assert command.args[1] == "winecfg"
        assert command.env["PATH"].startswith(str(wine_bin_dir))
        assert (
            "fake_steam_runtime/lib64" in command.env["PROTON_LD_LIBRARY_PATH"]
        )
        assert command.env["WINE"] == str(wine_bin_dir / "wine")
        assert command.env["WINELOADER"] == str(wine_bin_dir / "wine")
        assert command.env["WINESERVER"] == str(wine_bin_dir / "wineserver")

        assert command.env["LEGACY_STEAM_RUNTIME_PATH"] == \
            str(steam_runtime_dir / "steam-runtime")
        assert "STEAM_RUNTIME_PATH" not in command.env

        for name in ("wine", "wineserver"):
            # The helper scripts are created that point towards the real
            # Wine binaries
            path = wine_bin_dir / name
            assert path.is_file()

            content = path.read_text()

            # The script template for legacy Steam Runtime is used
            assert "\"$PROTON_DIST_PATH\"/bin/{}".format(name) in content
            assert "PROTONTRICKS_INSIDE_STEAM_RUNTIME" not in content

    def test_run_winetricks_steam_runtime_v2(
            self, cli, home_dir, steam_app_factory, steam_runtime_dir,
            steam_runtime_soldier, command, proton_factory, caplog):
        """
        Perform a Protontricks command using a newer Steam Runtime that is
        installed as its own application
        """
        proton_app = proton_factory(
            name="Proton 5.13", appid=10, compat_tool_name="proton_513",
            is_default_proton=True, required_tool_app=steam_runtime_soldier
        )
        steam_app_factory(name="Fake game 1", appid=20)

        cli(["20", "winecfg"], env={"STEAM_RUNTIME": "1"})

        wine_bin_dir = (
            home_dir / ".cache" / "protontricks" / "proton" / "Proton 5.13"
            / "bin"
        )

        # winecfg was run
        assert str(command.args[0]).endswith(".local/bin/winetricks")
        assert command.args[1] == "winecfg"
        assert command.env["PATH"].startswith(str(wine_bin_dir))

        # Compared to the traditional Steam Runtime, PROTON_LD_LIBRARY_PATH
        # will be different
        proton_install_path = Path(proton_app.install_path)
        assert command.env["PROTON_LD_LIBRARY_PATH"] == "".join([
            str(proton_install_path / "dist" / "lib"), os.pathsep,
            str(proton_install_path / "dist" / "lib64"), os.pathsep
        ])

        # Environment variables for both legacy and new Steam Runtime exist
        assert command.env["LEGACY_STEAM_RUNTIME_PATH"] == \
            str(steam_runtime_dir / "steam-runtime")
        assert command.env["STEAM_RUNTIME_PATH"] == \
            str(steam_runtime_soldier.install_path)

        # No warning will be created since Steam Runtime Soldier is recognized
        # by Protontricks
        assert len([
            record for record in caplog.records
            if record.levelname == "WARNING"
            and "Steam Runtime not recognized" in record.message
        ]) == 0

        for name in ("wine", "wineserver"):
            # The helper scripts are created that point towards the real
            # Wine binaries
            path = wine_bin_dir / name
            assert path.is_file()

            content = path.read_text()

            # The script template for bwrap-based Steam Runtime is used
            assert "\"$PROTON_DIST_PATH\"/bin/{}".format(name) in content
            assert "PROTONTRICKS_INSIDE_STEAM_RUNTIME" in content

    def test_run_winetricks_steam_runtime_v2_no_bwrap(
            self, cli, home_dir, steam_app_factory, steam_runtime_dir,
            steam_runtime_soldier, command, proton_factory, caplog):
        """
        Perform a Protontricks command using a newer Steam Runtime
        *without* bwrap that is installed as its own application
        """
        proton_app = proton_factory(
            name="Proton 5.13", appid=10, compat_tool_name="proton_513",
            is_default_proton=True, required_tool_app=steam_runtime_soldier
        )
        steam_app_factory(name="Fake game 1", appid=20)

        cli(["--no-bwrap", "20", "winecfg"], env={"STEAM_RUNTIME": "1"})

        wine_bin_dir = (
            home_dir / ".cache" / "protontricks" / "proton" / "Proton 5.13"
            / "bin"
        )

        # winecfg was run
        assert str(command.args[0]).endswith(".local/bin/winetricks")
        assert command.args[1] == "winecfg"
        assert command.env["PATH"].startswith(str(wine_bin_dir))

        # Compared to the traditional Steam Runtime, PROTON_LD_LIBRARY_PATH
        # will be different
        proton_install_path = Path(proton_app.install_path)
        assert command.env["PROTON_LD_LIBRARY_PATH"].startswith("".join([
            str(proton_install_path / "dist" / "lib"), os.pathsep,
            str(proton_install_path / "dist" / "lib64"), os.pathsep
        ]))

        runtime_root = \
            steam_runtime_soldier.install_path / "soldier" / "files"
        assert command.env["PROTON_LD_LIBRARY_PATH"].endswith("".join([
            str(runtime_root / "lib" / "i386-linux-gnu"), os.pathsep,
            str(runtime_root / "lib" / "x86_64-linux-gnu")
        ]))

        # Environment variables for both legacy and new Steam Runtime exist
        assert command.env["LEGACY_STEAM_RUNTIME_PATH"] == \
            str(steam_runtime_dir / "steam-runtime")
        assert command.env["STEAM_RUNTIME_PATH"] == \
            str(steam_runtime_soldier.install_path)

        # No warning will be created since Steam Runtime Soldier is recognized
        # by Protontricks
        assert len([
            record for record in caplog.records
            if record.levelname == "WARNING"
            and "Steam Runtime not recognized" in record.getMessage()
        ]) == 0

        for name in ("wine", "wineserver"):
            # The helper scripts are created that point towards the real
            # Wine binaries
            path = wine_bin_dir / name
            assert path.is_file()

            content = path.read_text()

            # The script template for normal Steam Runtime is used
            assert "\"$PROTON_DIST_PATH\"/bin/{}".format(name) in content
            assert "PROTONTRICKS_INSIDE_STEAM_RUNTIME" not in content

    def test_run_winetricks_game_not_found(
            self, cli, steam_app_factory, default_proton, command):
        """
        Try running a Protontricks command for a non-existing app
        """
        result = cli(["100", "winecfg"], expect_exit=True)

        assert "Steam app with the given app ID could not be found" in result

    def test_run_no_command(self, cli):
        """
        Run only the 'protontricks' command.
        """
        result = cli([])

        # Help will be printed if no specific command is given
        assert result.startswith("usage: ")

    def test_run_multiple_commands(self, cli):
        """
        Try performing multiple commands at once
        """
        result = cli(["--gui", "-s", "game"])

        assert "Only one action can be performed" in result

    def test_run_steam_not_found(self, cli, steam_dir):
        """
        Try performing a command with a missing Steam directory
        """
        shutil.rmtree(str(steam_dir))

        result = cli(["10", "winecfg"], expect_exit=True)

        assert "Steam installation directory could not be found" in result

    def test_run_winetricks_not_found(
            self, cli, default_proton, home_dir, steam_app_factory):
        """
        Try performing a command with missing Winetricks executable
        """
        steam_app_factory(name="Fake game 1", appid=10)
        (home_dir / ".local" / "bin" / "winetricks").unlink()

        result = cli(["10", "winecfg"], expect_exit=True)

        assert "Winetricks isn't installed" in result

    def test_run_winetricks_from_desktop(
            self, cli, default_proton, home_dir, steam_app_factory,
            monkeypatch, gui_provider):
        """
        Try performing a command with missing Winetricks executable.

        Run command using --no-term and ensure error dialog is shown
        with the expected error message
        """
        steam_app_factory(name="Fake game 1", appid=10)
        (home_dir / ".local" / "bin" / "winetricks").unlink()

        cli(["--no-term", "10", "winecfg"], expect_exit=True)

        assert gui_provider.args[0] == "yad"
        assert gui_provider.args[1] == "--text-info"

        message = gui_provider.kwargs["input"]

        assert b"Winetricks isn't installed" in message

        # Also ensure log messages are included in the error message
        assert b"Found Steam directory at" in message
        assert b"Using default Steam Runtime" in message

    def test_run_gui_provider_not_found(self, cli, home_dir, steam_app_factory):
        """
        Try performing a command with missing YAD or Zenity executable
        """
        steam_app_factory(name="Fake game 1", appid=10)
        (home_dir / ".local" / "bin" / "yad").unlink()
        (home_dir / ".local" / "bin" / "zenity").unlink()

        result = cli(["--gui"], expect_exit=True)

        assert "YAD or Zenity is not installed" in result

    def test_run_steam_runtime_not_found(
            self, cli, steam_dir, steam_app_factory):
        """
        Try performing a command with Steam Runtime enabled but no
        available Steam Runtime installation
        """
        steam_app_factory(name="Fake game 1", appid=10)
        result = cli(
            ["10", "winecfg"], env={"STEAM_RUNTIME": "invalid/path"},
            expect_exit=True
        )

        assert "Steam Runtime was enabled but couldn't be found" in result

    def test_run_proton_not_found(self, cli, steam_dir, steam_app_factory):
        steam_app_factory(name="Fake game 1", appid=10)
        result = cli(["10", "winecfg"], expect_exit=True)

        assert "Proton installation could not be found" in result

    def test_run_compat_tool_not_proton(
            self, cli, steam_dir, default_proton, custom_proton_factory,
            steam_app_factory, caplog):
        """
        Try performing a Protontricks command for a Steam app that
        uses a compatibility tool that isn't Proton.

        Regression test for https://github.com/Matoking/protontricks/issues/113
        """
        # Create a compatibility tool that isn't actually Proton
        tool_app = custom_proton_factory(name="Not Proton")
        (tool_app.install_path / "proton").unlink()

        steam_app_factory(
            name="Fake game", appid=10, compat_tool_name="Not Proton"
        )

        result = cli(["10", "winecfg"], expect_exit=True)

        assert "Proton installation could not be found" in result

        record = caplog.records[-1]
        assert (
            "Active compatibility tool was found, but it's not a Proton" in
            record.getMessage()
        )

    def test_run_command_runtime_incomplete(
            self, cli, steam_app_factory, steam_runtime_soldier,
            command, proton_factory, steam_dir):
        """
        Try performing a Protontricks command using a Proton installation that
        is still missing a Steam Runtime installation.

        Regression test for https://github.com/Matoking/protontricks/issues/75
        """
        proton_factory(
            name="Proton 5.13", appid=10, compat_tool_name="proton_513",
            is_default_proton=True, required_tool_app=steam_runtime_soldier
        )
        steam_app_factory(name="Fake game 1", appid=20)

        # Delete the Steam Runtime installation to simulate an incomplete
        # Proton installation that's missing the required Steam Runtime
        shutil.rmtree(str(steam_runtime_soldier.install_path))
        (steam_dir / "steamapps" / "appmanifest_1391110.acf").unlink()

        with pytest.raises(RuntimeError) as exc:
            cli(["20", "winecfg"])

        assert "Proton 5.13 is missing the required Steam Runtime" \
            in str(exc.value)

    def test_flatpak_detected(self, cli, monkeypatch, caplog):
        """
        Try performing a Protontricks command when running inside a Flatpak
        environment and ensure a warning is printed when --no-bwrap is provided
        redundantly
        """
        cli(["--no-bwrap", "-s", "nothing"])

        # No warning is printed since we're not running inside Flatpak
        assert len([
            record for record in caplog.records
            if record.levelname == "WARNING"
        ]) == 0

        # Fake a Flatpak environment
        monkeypatch.setattr(
            "protontricks.cli.main.is_flatpak_sandbox",
            lambda: True
        )

        cli(["--no-bwrap", "-s", "nothing"])

        assert len([
            record for record in caplog.records
            if record.levelname == "WARNING"
        ]) == 1
        record = next(
            record for record in caplog.records
            if record.levelname == "WARNING"
        )

        assert record.levelname == "WARNING"
        assert "--no-bwrap is redundant when running Protontricks" \
            in record.message

    def test_cli_error_handler_uncaught_exception(
            self, cli, default_proton, steam_app_factory, monkeypatch,
            gui_provider):
        """
        Ensure that 'cli_error_handler' correctly catches any uncaught
        exception and includes a stack trace in the error dialog.
        """
        def _mock_from_appmanifest(*args, **kwargs):
            raise ValueError("Test appmanifest error")

        steam_app_factory(name="Fake game", appid=10)

        monkeypatch.setattr(
            "protontricks.steam.SteamApp.from_appmanifest",
            _mock_from_appmanifest
        )

        cli(["--no-term", "-s", "Fake"], expect_exit=True)

        assert gui_provider.args[0] == "yad"
        assert gui_provider.args[1] == "--text-info"

        message = gui_provider.kwargs["input"]

        assert b"Test appmanifest error" in message


class TestCLIGUI:
    def test_run_gui(
            self, cli, default_proton, steam_app_factory, gui_provider, command,
            home_dir):
        """
        Start the GUI and fake selecting a game
        """
        steam_app = steam_app_factory(name="Fake game 1", appid=10)
        proton_install_path = Path(default_proton.install_path)

        # Fake the user selecting the game
        gui_provider.mock_stdout = "Fake game 1: 10"

        cli(["--gui"])

        # 'winetricks --gui' was run for the game selected by user
        assert str(command.args[0]) == \
            str(home_dir / ".local" / "bin" / "winetricks")
        assert command.args[1] == "--gui"

        # Correct environment vars were set
        assert command.env["WINE"] == str(
            home_dir / ".cache" / "protontricks" / "proton" / "Proton 4.20"
            / "bin" / "wine"
        )
        assert command.env["PROTON_PATH"] == str(proton_install_path)
        assert command.env["WINETRICKS"] == str(
            home_dir / ".local" / "bin" / "winetricks")
        assert command.env["WINEPREFIX"] == str(steam_app.prefix_path)
        assert command.env["WINELOADER"] == command.env["WINE"]
        assert command.env["WINEDLLPATH"] == "{}{}{}".format(
            str(proton_install_path / "dist" / "lib64" / "wine"),
            os.pathsep,
            str(proton_install_path / "dist" / "lib" / "wine")
        )

    def test_run_gui_no_games(self, cli, default_proton):
        """
        Try starting the GUI when no games are installed
        """
        result = cli(["--gui"], expect_exit=True)

        assert "Found no games" in result


class TestCLICommand:
    def test_run_command(
            self, cli, default_proton, steam_app_factory, gui_provider, command,
            home_dir):
        """
        Run a shell command for a given game
        """
        steam_app = steam_app_factory(name="Fake game", appid=10)
        proton_install_path = default_proton.install_path

        cli(["-c", "bash", "10"])

        # The command is just 'bash'
        assert command.args == "bash"

        assert command.kwargs["cwd"] == steam_app.install_path
        assert command.kwargs["shell"] is True

        # Correct environment vars were set
        assert command.env["WINE"] == str(
            home_dir / ".cache" / "protontricks" / "proton" / "Proton 4.20"
            / "bin" / "wine"
        )
        assert command.env["PROTON_PATH"] == str(proton_install_path)
        assert command.env["WINETRICKS"] == str(
            home_dir / ".local" / "bin" / "winetricks")
        assert command.env["WINEPREFIX"] == str(steam_app.prefix_path)
        assert command.env["WINELOADER"] == command.env["WINE"]
        assert command.env["WINEDLLPATH"] == "{}{}{}".format(
            str(proton_install_path / "dist" / "lib64" / "wine"),
            os.pathsep,
            str(proton_install_path / "dist" / "lib" / "wine")
        )


class TestCLISearch:
    def test_search_case_insensitive(self, cli, steam_app_factory):
        """
        Do a case-insensitive search
        """
        steam_app_factory(name="FaKe GaMe 1", appid=10)
        steam_app_factory(name="FAKE GAME 2", appid=20)

        # Search is case-insensitive
        stdout = cli(["-s", "game"])

        assert "FaKe GaMe 1 (10)" in stdout
        assert "FAKE GAME 2 (20)" in stdout

    def test_search_pfx_lock_required(self, cli, steam_app_factory):
        """
        Do a search for a game that doesn't have a complete prefix yet
        """
        steam_app = steam_app_factory(name="Fake game", appid=10)

        # Delete the pfx.lock file that signifies that the game has been
        # launched at least once. Protontricks requires that this file
        # exists
        (Path(steam_app.prefix_path).parent / "pfx.lock").unlink()

        stdout = cli(["-s", "game"])

        assert "Found no games" in stdout
        assert "Fake game" not in stdout

    def test_search_multiple_keywords(self, cli, steam_app_factory):
        """
        Do a search for games with multiple subsequent words from the entire
        name
        """
        steam_app_factory(name="Apple banana cinnamon", appid=10)
        steam_app_factory(name="Apple banana", appid=20)

        stdout = cli(["-s", "apple", "banana"])

        # First game is found, second is not
        assert "Apple banana cinnamon (10)" in stdout
        assert "Apple banana (20)" in stdout

        # Having the keywords in one parameter is also valid
        stdout = cli(["-s", "apple banana"])

        assert "Apple banana cinnamon (10)" in stdout
        assert "Apple banana (20)" in stdout

    def test_search_strip_non_ascii(self, cli, steam_app_factory):
        """
        Do a search for a game with various symbols that are ignored
        when doing the search
        """
        steam_app_factory(
            name="Frog™ Simulator®: Year of the 🐸 Edition", appid=10
        )

        # Non-ASCII symbols are not checked for when doing the search
        stdout = cli([
            "-s", "frog", "simulator", "year", "of", "the", "edition"
        ])

        assert "Frog™ Simulator®: Year of the 🐸 Edition (10)" in stdout

    def test_search_multiple_library_folders(
            self, cli, steam_app_factory, steam_library_factory):
        """
        Create three games in three different locations and ensure
        all are found when searched for
        """
        library_dir_a = steam_library_factory("LibraryA")
        library_dir_b = steam_library_factory("LibraryB")

        steam_app_factory(name="Fake game 1", appid=10)
        steam_app_factory(
            name="Fake game 2", appid=20, library_dir=library_dir_a
        )
        steam_app_factory(
            name="Fake game 3", appid=30, library_dir=library_dir_b
        )

        # All three games should be found automatically
        result = cli(["-s", "game"])

        assert "Fake game 1" in result
        assert "Fake game 2" in result
        assert "Fake game 3" in result

    def test_search_shortcut(
            self, cli, shortcut_factory):
        """
        Create two non-Steam shortcut and ensure they can be found
        """
        shortcut_factory(install_dir="fake/path/", name="fakegame.exe")
        shortcut_factory(install_dir="fake/path2/", name="fakegame.exe")

        result = cli(["-v", "-s", "steam"])

        assert "Non-Steam shortcut: fakegame.exe (4149337689)" in result
        assert "Non-Steam shortcut: fakegame.exe (4136117770)" in result


def test_cli_error_help(cli):
    """
    Ensure that the full help message is printed when an incorrect argument
    is provided
    """
    _, stderr = cli(["--nothing"], expect_exit=True, include_stderr=True)

    # Usage message
    assert "[-h] [--verbose]" in stderr
    # Help message
    assert "positional arguments:" in stderr
