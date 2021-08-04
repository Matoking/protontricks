import pytest

from protontricks.cli.util import (_delete_log_file, _get_log_file_path,
                                   exit_with_error)


def test_cli_error_handler_uncaught_exception(
        cli, default_proton, steam_app_factory, monkeypatch, zenity):
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

    assert zenity.args[0] == "zenity"
    assert zenity.args[1] == "--text-info"

    message = zenity.kwargs["input"]

    assert b"Test appmanifest error" in message


def test_exit_with_error_no_log_file(zenity):
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

    assert zenity.args[0] == "zenity"
    assert zenity.args[1] == "--text-info"

    message = zenity.kwargs["input"]

    assert b"Test error" in message


def test_log_file_cleanup(cli, steam_app_factory, zenity):
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
