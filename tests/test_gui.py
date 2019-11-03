import pytest
from protontricks.gui import select_steam_app_with_gui
from protontricks.steam import SteamApp


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
