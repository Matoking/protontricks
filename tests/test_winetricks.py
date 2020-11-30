from protontricks.winetricks import get_winetricks_path


class TestGetWinetricksPath:
    def test_get_winetricks_env(self, monkeypatch, tmp_path):
        """
        Use a custom Winetricks executable using an env var
        """
        (tmp_path / "winetricks").touch()

        monkeypatch.setenv(
            "WINETRICKS",
            str(tmp_path / "winetricks")
        )
        assert str(get_winetricks_path()) == str(tmp_path / "winetricks")

    def test_get_winetricks_env_not_found(self, monkeypatch):
        """
        Try using a custom Winetricks with a non-existent path
        """
        monkeypatch.setenv("WINETRICKS", "/invalid/path")
        assert not get_winetricks_path()
