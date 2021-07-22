import pytest


@pytest.fixture(scope="function", autouse=True)
def home_cwd(home_dir, monkeypatch):
    """
    Set the current working directory to the user's home directory and add
    an executable named "test.exe"
    """
    monkeypatch.setattr("os.getcwd", lambda: str(home_dir))

    (home_dir / "test.exe").write_text("")


class TestCLIRun:
    def test_run_executable(
            self, steam_app_factory, default_proton,
            command, zenity, launch_cli):
        """
        Run an EXE file by selecting using the GUI
        """
        steam_app = steam_app_factory("Fake game", appid=10)

        # Fake the user selecting the game
        zenity.mock_stdout = "Fake game: 10"

        launch_cli(["test.exe"])

        # 'test.exe' was executed
        assert command.args.startswith("wine ")
        assert command.args.endswith("/test.exe'")

        assert command.env["WINEPREFIX"] == str(steam_app.prefix_path)

    def test_run_executable_appid(
            self, default_proton, steam_app_factory, command, launch_cli):
        """
        Run an EXE file directly for a chosen game
        """
        steam_app = steam_app_factory(name="Fake game 1", appid=10)

        launch_cli(["--appid", "10", "test.exe"])

        # 'test.exe' was executed
        assert command.args.startswith("wine ")
        assert command.args.endswith("/test.exe'")

        assert command.env["WINEPREFIX"] == str(steam_app.prefix_path)

    def test_run_executable_no_selection(
            self, default_proton, steam_app_factory, zenity,
            launch_cli):
        """
        Try running an EXE file but don't pick a Steam app
        """
        steam_app_factory("Fake game", appid=10)

        # Fake the user closing the form
        zenity.mock_stdout = ""

        result = launch_cli(["test.exe"], expect_exit=True)

        assert "No game was selected." in result

    def test_run_executable_no_apps(self, launch_cli):
        """
        Try running an EXE file when no Proton enabled Steam apps are installed or
        ready
        """
        result = launch_cli(["test.exe"], expect_exit=True)

        assert "No Proton enabled Steam apps were found" in result

    def test_run_executable_no_apps_from_desktop(self, launch_cli, monkeypatch):
        """
        Try running an EXE file when no Proton enabled Steam apps are installed
        or ready, and ensure an error dialog is opened using `zenity`.
        """
        result = []
        monkeypatch.setattr(
            "protontricks.cli.launch.run",
            lambda *args, **_: result.extend(*args)
        )

        launch_cli(["--from-desktop", "test.exe"], expect_exit=True)

        assert result[0] == "zenity"
        assert result[-2] == "--text"
        assert result[-1].startswith("No Proton enabled Steam apps were found.")

    def test_run_executable_passthrough_arguments(
            self, default_proton, steam_app_factory, caplog,
            launch_cli, monkeypatch):
        """
        Try running an EXE file and apply all arguments; those should
        also be passed to the main entrypoint
        """
        cli_args = []

        monkeypatch.setattr(
            "protontricks.cli.launch.cli_main",
            cli_args.extend
        )

        steam_app_factory(name="Fake game", appid=10)

        launch_cli([
            "--verbose", "--no-bwrap", "--no-runtime", "--appid", "10",
            "test.exe"
        ])

        # CLI flags are passed through to the main CLI entrypoint
        assert cli_args[0:4] == [
            "--verbose", "--no-runtime", "--no-bwrap", "-c"
        ]
        assert cli_args[4].startswith("wine ")
        assert cli_args[4].endswith("test.exe'")
        assert cli_args[5] == "10"
