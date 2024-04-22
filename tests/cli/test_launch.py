import pytest


@pytest.fixture(scope="function", autouse=True)
def home_cwd(home_dir, monkeypatch):
    """
    Set the current working directory to the user's home directory and add
    an executable named "test.exe"
    """
    monkeypatch.chdir(str(home_dir))

    (home_dir / "test.exe").write_text("")


class TestCLIRun:
    def test_run_executable(
            self, steam_app_factory, default_proton,
            command_mock, gui_provider, launch_cli):
        """
        Run an EXE file by selecting using the GUI
        """
        steam_app = steam_app_factory("Fake game", appid=10)

        # Fake the user selecting the game
        gui_provider.mock_stdout = "Fake game: 10"

        launch_cli(["test.exe"])

        # 'test.exe' was executed
        command = command_mock.commands[-1]
        assert command.args.startswith("wine ")
        assert command.args.endswith("/test.exe")

        assert command.env["WINEPREFIX"] == str(steam_app.prefix_path)

    def test_run_executable_appid(
            self, default_proton, steam_app_factory, command_mock, launch_cli):
        """
        Run an EXE file directly for a chosen game
        """
        steam_app = steam_app_factory(name="Fake game 1", appid=10)

        launch_cli(["--appid", "10", "test.exe"])

        # 'test.exe' was executed
        command = command_mock.commands[-1]
        assert command.args.startswith("wine ")
        assert command.args.endswith("/test.exe")

        assert command.env["WINEPREFIX"] == str(steam_app.prefix_path)

    def test_run_executable_no_selection(
            self, default_proton, steam_app_factory, gui_provider,
            launch_cli):
        """
        Try running an EXE file but don't pick a Steam app
        """
        steam_app_factory("Fake game", appid=10)

        # Fake the user closing the form
        gui_provider.mock_stdout = ""

        result = launch_cli(["test.exe"], expect_returncode=1)

        assert "No game was selected." in result

    def test_run_executable_no_apps(self, launch_cli):
        """
        Try running an EXE file when no Proton enabled Steam apps are installed
        or ready
        """
        result = launch_cli(["test.exe"], expect_returncode=1)

        assert "No Proton enabled Steam apps were found" in result

    def test_run_executable_no_apps_from_desktop(
            self, launch_cli, gui_provider):
        """
        Try running an EXE file when no Proton enabled Steam apps are installed
        or ready, and ensure an error dialog is opened using `gui_provider`.
        """
        launch_cli(["--no-term", "test.exe"], expect_returncode=1)

        assert gui_provider.args[0] == "yad"
        assert gui_provider.args[1] == "--text-info"

        message = gui_provider.kwargs["input"]

        assert b"No Proton enabled Steam apps were found." in message

        # Also ensure log messages are included in the error message
        assert b"Found Steam directory at" in message

    def test_run_executable_passthrough_arguments(
            self, default_proton, steam_app_factory, caplog,
            steam_dir, launch_cli, monkeypatch):
        """
        Try running an EXE file and apply all arguments; those should
        also be passed to the main entrypoint
        """
        cli_args = []
        cli_kwargs = {}

        def _set_launch_args(*args, **kwargs):
            cli_args.extend(*args)
            cli_kwargs.update(kwargs)

        monkeypatch.setattr(
            "protontricks.cli.launch.cli_main",
            _set_launch_args
        )

        steam_app_factory(name="Fake game", appid=10)

        launch_cli([
            "--verbose", "--no-bwrap", "--no-runtime", "--no-term",
            "--cwd-app", "--appid", "10", "test.exe"
        ])

        # CLI flags are passed through to the main CLI entrypoint
        assert cli_args[0:7] == [
            "-v", "--no-runtime", "--no-bwrap",
            "--no-background-wineserver", "--no-term", "--cwd-app", "-c"
        ]
        assert cli_args[7].startswith("wine ")
        assert cli_args[7].endswith("test.exe")
        assert cli_args[8] == "10"

        # Steam installation was provided to the main entrypoint
        assert str(cli_kwargs["steam_path"]) == str(steam_dir)

    @pytest.mark.parametrize("argument", [
        None,
        "--background-wineserver",
        "--no-background-wineserver"
    ])
    def test_run_executable_passthrough_background_wineserver(
            self, launch_cli, monkeypatch, steam_app_factory,
            argument):
        """
        Try running an EXE file and apply given wineserver argument.
        If the argument is set, it should also be passed to the main
        entrypoint.
        """
        cli_args = []

        def _set_launch_args(*args, **kwargs):
            cli_args.extend(*args)

        monkeypatch.setattr(
            "protontricks.cli.launch.cli_main",
            _set_launch_args
        )

        steam_app_factory(name="Fake game", appid=10)

        extra_args = [argument] if argument else []
        launch_cli(extra_args + ["--appid", "10", "test.exe"])

        if argument:
            # Ensure the corresponding argument was passd to the main CLI
            # entrypoint
            assert argument in cli_args
        else:
            assert "--no-background-wineserver" in cli_args

    def test_cli_error_handler_uncaught_exception(
            self, launch_cli, default_proton, steam_app_factory, monkeypatch,
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

        launch_cli(
            ["--no-term", "--appid", "10", "test.exe"], expect_returncode=1
        )

        assert gui_provider.args[0] == "yad"
        assert gui_provider.args[1] == "--text-info"

        message = gui_provider.kwargs["input"]

        assert b"Test appmanifest error" in message

    @pytest.mark.usefixtures(
        "flatpak_sandbox", "default_proton", "command_mock"
    )
    def test_run_filesystem_permission_missing(
            self, launch_cli, steam_library_factory, steam_app_factory,
            caplog):
        """
        Try performing a launch command in a Flatpak sandbox where the user
        hasn't provided adequate fileystem permissions. Ensure warning is
        printed.
        """
        steam_app_factory(name="Fake game 1", appid=10)
        path = steam_library_factory(name="GameDrive")

        launch_cli(["--appid", "10", "test.exe"])

        record = next(
            record for record in caplog.records
            if "grant access to the required directories" in record.message
        )
        assert record.levelname == "WARNING"
        assert str(path) in record.message

    @pytest.mark.usefixtures(
        "flatpak_sandbox", "steam_dir", "flatpak_steam_dir"
    )
    def test_steam_installation_not_selected(self, launch_cli, gui_provider):
        """
        Test that not selecting a Steam installation results in the correct
        exit message
        """
        # Mock the user choosing the Flatpak installation.
        # Only the index is actually checked in the actual function.
        gui_provider.mock_stdout = ""
        gui_provider.mock_returncode = 1

        result = launch_cli(["test.exe"], expect_returncode=1)

        assert "No Steam installation was selected" in result
