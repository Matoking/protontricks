def test_run_desktop_install(home_dir, command, desktop_install_cli):
    """
    Ensure that `desktop-file-install` is called properly
    """
    # `protontricks-desktop-install` takes no arguments
    desktop_install_cli([])

    assert command.args[0:3] == [
        "desktop-file-install",
        "--dir",
        str(home_dir / ".local" / "share" / "applications")
    ]
    assert command.args[3].endswith("/protontricks.desktop")
    assert command.args[4].endswith("/protontricks-launch.desktop")
