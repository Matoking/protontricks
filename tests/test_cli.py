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
        assert command.args[0].endswith(".local/bin/winetricks")
        assert command.args[1] == "winecfg"

        # Correct environment vars were set
        assert command.env["WINE"] == str(
            proton_install_path / "dist" / "bin" / "wine")
        assert command.env["WINETRICKS"] == str(
            home_dir / ".local" / "bin" / "winetricks")
        assert command.env["WINEPREFIX"] == str(steam_app.prefix_path)
        assert command.env["WINELOADER"] == str(
            proton_install_path / "dist" / "bin" / "wine")
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
        assert command.env["WINE"] == str(
            proton_install_path / "dist" / "bin" / "wine")
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

        assert command.env["WINE"] == str(
            Path(custom_proton.install_path) / "dist" / "bin" / "wine"
        )

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
            home_dir / ".steam_new" / "steamapps" / "common"
            / "Proton 4.20" / "dist" / "bin" / "wine"
        )

    def test_run_winetricks_steam_runtime(
            self, cli, steam_app_factory, steam_runtime_dir, default_proton,
            command, home_dir):
        """
        Perform a Protontricks command using Steam Runtime
        """
        proton_install_path = Path(default_proton.install_path)
        steam_app_factory(name="Fake game 1", appid=10)

        cli(["10", "winecfg"], env={"STEAM_RUNTIME": "1"})

        # winecfg was actually run
        assert command.args[0].endswith(".local/bin/winetricks")
        assert command.args[1] == "winecfg"

        assert command.env["LD_LIBRARY_PATH"].strip() == "".join([
            str(proton_install_path / "dist" / "lib"), os.pathsep,
            str(proton_install_path / "dist" / "lib64"), os.pathsep,
            "fake_steam_runtime/lib:fake_steam_runtime/lib64"
        ]).strip()

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


class TestCLIGUI:
    def test_run_gui(
            self, cli, default_proton, steam_app_factory, zenity, command,
            home_dir):
        """
        Start the GUI and fake selecting a game
        """
        steam_app = steam_app_factory(name="Fake game 1", appid=10)
        proton_install_path = Path(default_proton.install_path)

        # Fake the user selecting the game
        zenity.mock_stdout = "Fake game 1: 10"

        cli(["--gui"])

        # 'winetricks --gui' was run for the game selected by user
        assert command.args[0] == str(
            home_dir / ".local" / "bin" / "winetricks")
        assert command.args[1] == "--gui"

        # Correct environment vars were set
        assert command.env["WINE"] == str(
            proton_install_path / "dist" / "bin" / "wine")
        assert command.env["WINETRICKS"] == str(
            home_dir / ".local" / "bin" / "winetricks")
        assert command.env["WINEPREFIX"] == str(steam_app.prefix_path)
        assert command.env["WINELOADER"] == str(
            proton_install_path / "dist" / "bin" / "wine")
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
            self, cli, default_proton, steam_app_factory, zenity, command,
            home_dir):
        """
        Run a shell command for a given game
        """
        steam_app = steam_app_factory(name="Fake game", appid=10)
        proton_install_path = Path(default_proton.install_path)

        cli(["-c", "bash", "10"])

        # The command is just 'bash'
        assert command.args == "bash"

        assert command.kwargs["cwd"] == str(steam_app.install_path)
        assert command.kwargs["shell"] is True

        # Correct environment vars were set
        assert command.env["WINE"] == str(
            proton_install_path / "dist" / "bin" / "wine")
        assert command.env["WINETRICKS"] == str(
            home_dir / ".local" / "bin" / "winetricks")
        assert command.env["WINEPREFIX"] == str(steam_app.prefix_path)
        assert command.env["WINELOADER"] == str(
            proton_install_path / "dist" / "bin" / "wine")
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
