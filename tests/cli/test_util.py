import pytest

from protontricks.cli.util import (_delete_log_file, _get_log_file_path,
                                   exit_with_error)


@pytest.fixture(scope="function")
def broken_appmanifest(monkeypatch):
    def _mock_from_appmanifest(*args, **kwargs):
        raise ValueError("Test appmanifest error")

    monkeypatch.setattr(
        "protontricks.steam.SteamApp.from_appmanifest",
        _mock_from_appmanifest
    )


def test_cli_error_handler_uncaught_exception(
        cli, default_proton, steam_app_factory, broken_appmanifest,
        gui_provider):
    """
    Ensure that 'cli_error_handler' correctly catches any uncaught
    exception and includes a stack trace in the error dialog.
    """
    steam_app_factory(name="Fake game", appid=10)

    cli(["--no-term", "-s", "Fake"], expect_exit=True)

    assert gui_provider.args[0] == "yad"
    assert gui_provider.args[1] == "--text-info"

    message = gui_provider.kwargs["input"]

    # 'broken_appmanifest' will induce an error in 'SteamApp.from_appmanifest'
    assert b"Test appmanifest error" in message


@pytest.mark.parametrize("gui_cmd", ["yad", "zenity"])
def test_cli_error_handler_gui_provider_env(
        cli, default_proton, steam_app_factory, monkeypatch,
        broken_appmanifest, gui_provider, gui_cmd):
    """
    Ensure that correct GUI provider is used depending on 'PROTONTRICKS_GUI'
    environment variable
    """
    monkeypatch.setenv("PROTONTRICKS_GUI", gui_cmd)

    steam_app_factory(name="Fake game", appid=10)

    cli(["--no-term", "-s", "Fake"], expect_exit=True)

    message = gui_provider.kwargs["input"]

    assert b"Test appmanifest error" in message

    if gui_cmd == "yad":
        assert gui_provider.args[0] == "yad"
        # YAD has custom button declarations
        assert "--button=OK:1" in gui_provider.args
    elif gui_cmd == "zenity":
        assert gui_provider.args[0] == "zenity"
        # Zenity doesn't have custom button declarations
        assert "--button=OK:1" not in gui_provider.args



def test_exit_with_error_no_log_file(gui_provider):
    """
    Ensure that `exit_with_error` can show the error dialog even if
    the log file goes missing for some reason
    """
    try:
        _get_log_file_path().unlink()
    except FileNotFoundError:
        pass

    with pytest.raises(SystemExit):
        exit_with_error("Test error", desktop=True)

    assert gui_provider.args[0] == "yad"
    assert gui_provider.args[1] == "--text-info"

    message = gui_provider.kwargs["input"]

    assert b"Test error" in message


def test_log_file_cleanup(cli, steam_app_factory, gui_provider):
    """
    Ensure that log file contains the log files generated during the
    CLI call and that it is cleared after running `_delete_log_file`
    """
    steam_app_factory(name="Fake game", appid=10)
    cli(["--no-term", "-s", "Fake"])

    assert "Found Steam directory" in _get_log_file_path().read_text()

    # This is called on shutdown by atexit, but call it here directly
    # since we can't test atexit.
    _delete_log_file()

    assert not _get_log_file_path().is_file()

    # Nothing happens if the file is already missing
    _delete_log_file()
