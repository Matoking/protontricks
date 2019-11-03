from pathlib import Path


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
