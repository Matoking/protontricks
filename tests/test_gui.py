import pytest
from subprocess import CalledProcessError
from protontricks.gui import select_steam_app_with_gui
from protontricks.steam import SteamApp


@pytest.fixture(scope="function")
def broken_zenity(zenity, monkeypatch):
    """
    Mock a broken Zenity executable that prints an error as described in
    the following GitHub issue:
    https://github.com/Matoking/protontricks/issues/20
    """
    def mock_subprocess_run(args, **kwargs):
        zenity.args = args

        raise CalledProcessError(
            returncode=-6,
            cmd=args,
            output=zenity.mock_stdout,
            stderr=b"free(): double free detected in tcache 2\n"
        )

    monkeypatch.setattr(
        "protontricks.gui.run",
        mock_subprocess_run
    )

    yield zenity


class TestSelectApp:
    def test_select_game(self, zenity, steam_app_factory):
        """
        Select a game using the GUI
        """
        steam_apps = [
            steam_app_factory(name="Fake game 1", appid=10),
            steam_app_factory(name="Fake game 2", appid=20)
        ]

        # Fake user selecting 'Fake game 2'
        zenity.mock_stdout = "Fake game 2: 20"
        steam_app = select_steam_app_with_gui(steam_apps=steam_apps)

        assert steam_app == steam_apps[1]

    def test_select_game_no_choice(self, zenity, steam_app_factory):
        """
        Try choosing a game but make no choice
        """
        steam_apps = [steam_app_factory(name="Fake game 1", appid=10)]

        # Fake user doesn't select any game
        zenity.mock_stdout = ""

        with pytest.raises(SystemExit) as exc:
            select_steam_app_with_gui(steam_apps=steam_apps)

        assert exc.value.code == 0

    def test_select_game_broken_zenity(self, broken_zenity, steam_app_factory):
        """
        Try choosing a game with a broken Zenity executable that
        prints a specific error message that Protontricks knows how to ignore
        """
        steam_apps = [
            steam_app_factory(name="Fake game 1", appid=10),
            steam_app_factory(name="Fake game 2", appid=20)
        ]

        # Fake user selecting 'Fake game 2'
        broken_zenity.mock_stdout = "Fake game 2: 20"
        steam_app = select_steam_app_with_gui(steam_apps=steam_apps)

        assert steam_app == steam_apps[1]

