from subprocess import CalledProcessError

from protontricks.gui import select_steam_app_with_gui

import pytest
from conftest import MockResult


@pytest.fixture(scope="function")
def broken_zenity(gui_provider, monkeypatch):
    """
    Mock a broken Zenity executable that prints an error as described in
    the following GitHub issue:
    https://github.com/Matoking/protontricks/issues/20
    """
    def mock_subprocess_run(args, **kwargs):
        gui_provider.args = args

        raise CalledProcessError(
            returncode=-6,
            cmd=args,
            output=gui_provider.mock_stdout,
            stderr=b"free(): double free detected in tcache 2\n"
        )

    monkeypatch.setattr(
        "protontricks.gui.run",
        mock_subprocess_run
    )

    yield gui_provider


@pytest.fixture(scope="function")
def locale_error_zenity(gui_provider, monkeypatch):
    """
    Mock a Zenity executable returning a 255 error due to a locale issue
    on first run and working normally on second run
    """
    def mock_subprocess_run(args, **kwargs):
        if not gui_provider.args:
            gui_provider.args = args
            raise CalledProcessError(
                returncode=255,
                cmd=args,
                output="",
                stderr=(
                    b"This option is not available. "
                    b"Please see --help for all possible usages."
                )
            )

        return MockResult(stdout=gui_provider.mock_stdout.encode("utf-8"))

    monkeypatch.setattr(
        "protontricks.gui.run",
        mock_subprocess_run
    )
    monkeypatch.setenv("PROTONTRICKS_GUI", "zenity")

    yield gui_provider


class TestSelectApp:
    def test_select_game(self, gui_provider, steam_app_factory, steam_dir):
        """
        Select a game using the GUI
        """
        steam_apps = [
            steam_app_factory(name="Fake game 1", appid=10),
            steam_app_factory(name="Fake game 2", appid=20)
        ]

        # Fake user selecting 'Fake game 2'
        gui_provider.mock_stdout = "Fake game 2: 20"
        steam_app = select_steam_app_with_gui(
            steam_apps=steam_apps, steam_path=steam_dir
        )

        assert steam_app == steam_apps[1]

        input_ = gui_provider.kwargs["input"]

        # Check that choices were displayed
        assert b"Fake game 1: 10\n" in input_
        assert b"Fake game 2: 20" in input_

    def test_select_game_icons(
            self, gui_provider, steam_app_factory, steam_dir):
        """
        Select a game using the GUI. Ensure that icons are used in the dialog
        whenever available.
        """
        steam_apps = [
            steam_app_factory(name="Fake game 1", appid=10),
            steam_app_factory(name="Fake game 2", appid=20),
            steam_app_factory(name="Fake game 3", appid=30),
        ]

        # Create icons for game 1 and 3
        (steam_dir / "appcache" / "librarycache" / "10_icon.jpg").touch()
        (steam_dir / "appcache" / "librarycache" / "30_icon.jpg").touch()

        gui_provider.mock_stdout = "Fake game 2: 20"
        select_steam_app_with_gui(steam_apps=steam_apps, steam_path=steam_dir)

        input_ = gui_provider.kwargs["input"]

        assert b"librarycache/10_icon.jpg\nFake game 1" in input_
        assert b"icon_placeholder.png\nFake game 2" in input_
        assert b"librarycache/30_icon.jpg\nFake game 3" in input_

    def test_select_game_no_choice(
            self, gui_provider, steam_app_factory, steam_dir):
        """
        Try choosing a game but make no choice
        """
        steam_apps = [steam_app_factory(name="Fake game 1", appid=10)]

        # Fake user doesn't select any game
        gui_provider.mock_stdout = ""

        with pytest.raises(SystemExit) as exc:
            select_steam_app_with_gui(
                steam_apps=steam_apps, steam_path=steam_dir
            )

        assert exc.value.code == 0

    def test_select_game_broken_zenity(
            self, broken_zenity, monkeypatch, steam_app_factory, steam_dir):
        """
        Try choosing a game with a broken Zenity executable that
        prints a specific error message that Protontricks knows how to ignore
        """
        monkeypatch.setenv("PROTONTRICKS_GUI", "zenity")

        steam_apps = [
            steam_app_factory(name="Fake game 1", appid=10),
            steam_app_factory(name="Fake game 2", appid=20)
        ]

        # Fake user selecting 'Fake game 2'
        broken_zenity.mock_stdout = "Fake game 2: 20"
        steam_app = select_steam_app_with_gui(
            steam_apps=steam_apps, steam_path=steam_dir)

        assert steam_app == steam_apps[1]

    def test_select_game_locale_error(
            self, locale_error_zenity, steam_app_factory, steam_dir, caplog):
        """
        Try choosing a game with an environment that can't handle non-ASCII
        characters
        """
        steam_apps = [
            steam_app_factory(name="Fäke game 1", appid=10),
            steam_app_factory(name="Fäke game 2", appid=20)
        ]

        # Fake user selecting 'Fäke game 2'. The non-ASCII character 'ä'
        # is stripped since Zenity wouldn't be able to display the character.
        locale_error_zenity.mock_stdout = "Fke game 2: 20"
        steam_app = select_steam_app_with_gui(
            steam_apps=steam_apps, steam_path=steam_dir
        )

        assert steam_app == steam_apps[1]
        assert (
            "Your system locale is incapable of displaying all characters"
            in caplog.records[0].message
        )

    @pytest.mark.parametrize("gui_cmd", ["yad", "zenity"])
    def test_select_game_gui_provider_env(
            self, gui_provider, steam_app_factory, monkeypatch, gui_cmd,
            steam_dir):
        """
        Test that the correct GUI provider is selected based on the
        `PROTONTRICKS_GUI` environment variable
        """
        monkeypatch.setenv("PROTONTRICKS_GUI", gui_cmd)

        steam_apps = [
            steam_app_factory(name="Fake game 1", appid=10),
            steam_app_factory(name="Fake game 2", appid=20)
        ]

        gui_provider.mock_stdout = "Fake game 2: 20"
        select_steam_app_with_gui(
            steam_apps=steam_apps, steam_path=steam_dir
        )

        # The flags should differ slightly depending on which provider is in
        # use
        if gui_cmd == "yad":
            assert gui_provider.args[0] == "yad"
            assert gui_provider.args[2] == "--no-headers"
        elif gui_cmd == "zenity":
            assert gui_provider.args[0] == "zenity"
            assert gui_provider.args[2] == "--hide-header"
