from pathlib import Path
import contextlib
import shutil
from subprocess import CalledProcessError

import pytest
from conftest import MockResult
from PIL import Image

from protontricks.gui import (prompt_filesystem_access,
                              select_steam_app_with_gui,
                              select_steam_installation)
from protontricks.cdemu_backend import OpticalDrive
from protontricks.steam import SteamApp


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
        # Capture the retry's input so the locale regression test can
        # verify that list rows are forwarded on the second invocation.
        gui_provider.kwargs = kwargs
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
        steam_app_factory(name="Fake game 1", appid=10)
        steam_app_factory(name="Fake game 2", appid=20)
        steam_app_factory(name="Fake game 3", appid=30)

        # Create icons for game 1 and 3
        # Old location for 10
        Image.new("RGB", (32, 32)).save(
            steam_dir / "appcache" / "librarycache" / "10_icon.jpg"
        )

        # New location for 30
        (steam_dir / "appcache" / "librarycache" / "30").mkdir()
        Image.new("RGB", (32, 32)).save(
            steam_dir / "appcache" / "librarycache" / "30"
            / "ffffffffffffffffffffffffffffffffffffffff.jpg"
        )

        # Read Steam apps using `SteamApp.from_appmanifest` to ensure
        # icon paths are detected correctly
        steam_apps = [
            SteamApp.from_appmanifest(
                steam_dir / "steamapps" / f"appmanifest_{appid}.acf",
                steam_path=steam_dir,
                steam_lib_paths=[steam_dir]
            )
            for appid in (10, 20, 30)
        ]

        gui_provider.mock_stdout = "Fake game 2: 20"
        select_steam_app_with_gui(steam_apps=steam_apps, steam_path=steam_dir)

        input_ = gui_provider.kwargs["input"]

        assert b"librarycache/10_icon.jpg\nFake game 1" in input_
        assert b"icon_placeholder.png\nFake game 2" in input_
        assert b"librarycache/30/ffffffffffffffffffffffffffffffffffffffff.jpg\nFake game 3" \
            in input_

    def test_select_game_icons_ensure_resize(
            self, gui_provider, steam_app_factory, steam_dir, home_dir):
        """
        Select a game using the GUI. Ensure custom icons with sizes other than
        32x32 are resized.
        """
        steam_apps = [
            steam_app_factory(name="Fake game 1", appid=10)
        ]

        Image.new("RGB", (64, 64)).save(
            steam_dir / "appcache" / "librarycache" / "10_icon.jpg"
        )

        gui_provider.mock_stdout = "Fake game 1: 10"
        select_steam_app_with_gui(steam_apps=steam_apps, steam_path=steam_dir)

        # Resized icon should have been created with the correct size and used
        resized_icon_path = \
            home_dir / ".cache" / "protontricks" / "app_icons" / "10.jpg"
        assert resized_icon_path.is_file()
        with Image.open(resized_icon_path) as img:
            assert img.size == (32, 32)

        input_ = gui_provider.kwargs["input"]

        assert f"{resized_icon_path}\nFake game 1".encode("utf-8") in input_

        # Any existing icon should be overwritten if it already exists
        resized_icon_path.write_bytes(b"not valid")
        select_steam_app_with_gui(steam_apps=steam_apps, steam_path=steam_dir)

        with Image.open(resized_icon_path) as img:
            assert img.size == (32, 32)

    def test_select_game_unidentifiable_icon_skipped(
            self, gui_provider, steam_app_factory, steam_dir, home_dir, caplog):
        """
        Select a game using the GUI. Ensure a custom icon that's not
        identifiable by Pillow is skipped.
        """
        steam_apps = [
            steam_app_factory(name="Fake game 1", appid=10)
        ]

        icon_path = steam_dir / "appcache" / "librarycache" / "10_icon.jpg"
        icon_path.write_bytes(b"")

        gui_provider.mock_stdout = "Fake game 1: 10"
        selected_app = select_steam_app_with_gui(
            steam_apps=steam_apps, steam_path=steam_dir
        )

        # Warning about icon was logged, but the app was selected successfully
        record = caplog.records[-1]
        assert record.message.startswith(f"Could not resize {icon_path}")

        assert selected_app.appid == 10

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

        assert exc.value.code == 1

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
            in caplog.records[-1].message
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


class TestSelectSteamInstallation:
    @pytest.mark.usefixtures("flatpak_sandbox")
    @pytest.mark.parametrize("gui_cmd", ["yad", "zenity"])
    def test_select_steam_gui_provider_env(
            self, gui_provider, monkeypatch, gui_cmd, steam_dir,
            flatpak_steam_dir):
        """
        Test that the correct GUI provider is selected based on the
        `PROTONTRICKS_GUI` environment variable
        """
        monkeypatch.setenv("PROTONTRICKS_GUI", gui_cmd)

        gui_provider.mock_stdout = "1: Flatpak - /foo/bar"
        select_steam_installation([
            (steam_dir, steam_dir),
            (flatpak_steam_dir, flatpak_steam_dir)
        ])

        # The flags should differ slightly depending on which provider is in
        # use
        if gui_cmd == "yad":
            assert gui_provider.args[0] == "yad"
            assert gui_provider.args[2] == "--no-headers"
        elif gui_cmd == "zenity":
            assert gui_provider.args[0] == "zenity"
            assert gui_provider.args[2] == "--hide-header"

    @pytest.mark.parametrize(
        "path,label",
        [
            (".steam", "Native"),
            (".local/share/Steam", "Native"),
            (".var/app/com.valvesoftware.Steam/.local/share/Steam", "Flatpak"),
            ("snap/steam/common/.local/share/Steam", "Snap")
        ]
    )
    def test_correct_labels_detected(
            self, gui_provider, steam_dir, home_dir, path, label):
        """
        Test that the Steam installation selection dialog uses the correct
        label for each Steam installation depending on its type
        """
        steam_new_dir = home_dir / path
        with contextlib.suppress(FileExistsError):
            # First test cases try copying against existing dirs, this can be
            # ignored
            shutil.copytree(steam_dir, steam_new_dir)

        select_steam_installation([
            (steam_new_dir, steam_new_dir),
            # Use an additional nonsense path; there need to be at least
            # two paths or user won't be prompted as there is no need
            ("/mock-steam", "/mock-steam")
        ])

        prompt_input = gui_provider.kwargs["input"].decode("utf-8")

        assert f"{label} - {steam_new_dir}" in prompt_input


@pytest.mark.usefixtures("flatpak_sandbox")
class TestPromptFilesystemAccess:
    def test_prompt_without_desktop(self, home_dir, caplog):
        """
        Test that calling 'prompt_filesystem_access' without showing the dialog
        only generates a warning
        """
        prompt_filesystem_access(
            [home_dir / "fake_path", "/mnt/fake_SSD", "/mnt/fake_SSD_2"],
            show_dialog=False
        )

        assert len(caplog.records) == 1

        record = caplog.records[0]

        assert record.levelname == "WARNING"
        assert "Protontricks does not appear to have access" in record.message

        assert "--filesystem=/mnt/fake_SSD" in record.message
        assert "--filesystem=/mnt/fake_SSD_2" in record.message
        assert str(home_dir / "fake_path") not in record.message

    def test_prompt_home_dir(self, home_dir, tmp_path, caplog):
        """
        Test that calling 'prompt_filesystem_access' with a path
        in the home directory will result in the command using a tilde slash
        as the shorthand instead
        """
        flatpak_info_path = tmp_path / "flatpak-info"

        flatpak_info_path.write_text(
            "[Application]\n"
            "name=fake.flatpak.Protontricks\n"
            "\n"
            "[Instance]\n"
            "flatpak-version=1.12.1\n"
            "\n"
            "[Context]\n"
            "filesystems=/mnt/SSD_A"
        )
        prompt_filesystem_access(
            [home_dir / "fake_path", "/mnt/SSD_A"],
            show_dialog=False
        )

        assert len(caplog.records) == 1

        record = caplog.records[0]

        assert record.levelname == "WARNING"
        assert "Protontricks does not appear to have access" in record.message

        assert "--filesystem='~/fake_path'" in record.message
        assert "/mnt/SSD_A" not in record.message

    def test_prompt_with_desktop_no_dialog(self, home_dir, gui_provider):
        """
        Test that calling 'prompt_filesystem_access' with 'show_dialog'
        displays a dialog
        """
        prompt_filesystem_access(
            [home_dir / "fake_path", "/mnt/fake_SSD", "/mnt/fake_SSD_2"],
            show_dialog=True
        )

        input_ = gui_provider.kwargs["input"].decode("utf-8")

        assert str(home_dir / "fake_path") not in input_
        assert "--filesystem=/mnt/fake_SSD" in input_
        assert "--filesystem=/mnt/fake_SSD_2" in input_

    def test_prompt_with_desktop_dialog(self, home_dir, gui_provider):
        """
        Test that calling 'prompt_filesystem_access' with 'show_dialog'
        displays a dialog
        """
        # Mock the user closing the dialog without ignoring the messages
        gui_provider.returncode = 1

        prompt_filesystem_access(
            [home_dir / "fake_path", "/mnt/fake_SSD", "/mnt/fake_SSD_2"],
            show_dialog=True
        )

        input_ = gui_provider.kwargs["input"].decode("utf-8")

        # Dialog was displayed
        assert "/mnt/fake_SSD" in input_
        assert "/mnt/fake_SSD_2" in input_

        # Mock the user selecting "Ignore, don't ask again"
        gui_provider.returncode = 0
        gui_provider.kwargs["input"] = None

        prompt_filesystem_access(
            [home_dir / "fake_path", "/mnt/fake_SSD", "/mnt/fake_SSD_2"],
            show_dialog=True
        )

        # Dialog is still displayed, but it won't be the next time
        input_ = gui_provider.kwargs["input"].decode("utf-8")
        assert "/mnt/fake_SSD" in input_
        assert "/mnt/fake_SSD_2" in input_

        gui_provider.kwargs["input"] = None

        prompt_filesystem_access(
            [home_dir / "fake_path", "/mnt/fake_SSD", "/mnt/fake_SSD_2"],
            show_dialog=True
        )

        # Dialog is not shown, since the user has opted to ignore the warning
        # for the current paths
        assert not gui_provider.kwargs["input"]

        # A new path makes the warning reappear
        prompt_filesystem_access(
            [
                home_dir / "fake_path",
                "/mnt/fake_SSD",
                "/mnt/fake_SSD_2",
                "/mnt/fake_SSD_3"
            ],
            show_dialog=True
        )

        input_ = gui_provider.kwargs["input"].decode("utf-8")
        assert "/mnt/fake_SSD " not in input_
        assert "/mnt/fake_SSD_2" not in input_
        assert "/mnt/fake_SSD_3" in input_


class TestCDROMGUI:
    def test_action_selection(self, gui_provider, home_dir):
        from protontricks.gui import select_gui_action

        cdemu = home_dir / ".local" / "bin" / "cdemu"
        cdemu.touch()
        cdemu.chmod(0o744)
        gui_provider.mock_stdout = "Manage CD/DVD drives (CDEmu)|\n"
        assert select_gui_action() == "cdrom"
        assert "--separator" in gui_provider.args
        assert gui_provider.args[
            gui_provider.args.index("--separator") + 1
        ] == ""
        assert "--print-column" in gui_provider.args

        gui_provider.mock_stdout = "Run Winetricks|\n"
        assert select_gui_action() == "winetricks"

        gui_provider.mock_stdout = ""
        assert select_gui_action() is None

    def test_no_cdemu_keeps_legacy_winetricks_flow(self, gui_provider):
        from protontricks.gui import select_gui_action

        assert select_gui_action() == "winetricks"
        assert not getattr(gui_provider, "args", None)

    def test_list_selection_zenity(self, gui_provider, monkeypatch):
        from protontricks.gui import _choose_from_list, get_gui_provider

        monkeypatch.setenv("PROTONTRICKS_GUI", "zenity")
        get_gui_provider.cache_clear()
        gui_provider.mock_stdout = "D:\n"
        assert _choose_from_list("Title", "Prompt", ["D:", "E:"]) == "D:"
        assert "--separator" not in gui_provider.args

    def test_invalid_drive_letter_displays_error(
            self, monkeypatch, tmp_path):
        from protontricks.gui import manage_cdrom_drives_gui

        errors = []
        monkeypatch.setattr(
            "protontricks.gui._choose_from_list",
            lambda *args: "invalid"
        )
        monkeypatch.setattr(
            "protontricks.gui._cdrom_error_dialog",
            lambda message: errors.append(str(message))
        )
        manage_cdrom_drives_gui(tmp_path, "Example")
        assert len(errors) == 1
        assert "Invalid Windows drive letter" in errors[0]

    def test_action_dialog_failure_is_handled(
            self, monkeypatch, tmp_path):
        from protontricks.gui import manage_cdrom_drives_gui

        calls = [0]
        errors = []

        def select(*args):
            calls[0] += 1
            if calls[0] == 1:
                return "D:"
            raise RuntimeError("YAD failed")

        monkeypatch.setattr(
            "protontricks.gui._choose_from_list", select
        )
        monkeypatch.setattr(
            "protontricks.gui.list_drives", lambda: []
        )
        monkeypatch.setattr(
            "protontricks.gui._cdrom_error_dialog",
            lambda message: errors.append(str(message))
        )

        manage_cdrom_drives_gui(tmp_path, "Example")
        assert errors == ["YAD failed"]

    def test_gui_locale_fallback_preserves_list_rows(
            self, locale_error_zenity):
        from protontricks.gui import _choose_from_list

        locale_error_zenity.mock_stdout = "D:"
        result = _choose_from_list(
            "CD/DVD Manager - unicode é",
            "Select unit",
            ["D:", "E:"]
        )
        assert result == "D:"
        assert locale_error_zenity.kwargs["input"] == b"D:\nE:"

    def test_load_image_and_assign_to_selected_prefix(
            self, monkeypatch, tmp_path):
        from protontricks.cdemu_backend import OpticalDrive
        from protontricks.gui import (
            _drive_label, manage_cdrom_drives_gui
        )
        prefix = tmp_path / "pfx"
        (prefix / "dosdevices").mkdir(parents=True)
        mounted = tmp_path / "Disc 2"
        mounted.mkdir()
        cue = tmp_path / "Disc 2.cue"
        cue.touch()
        drive = OpticalDrive(1, Path("/dev/sr1"), str(cue), mounted)
        responses = iter([
            "D:", _drive_label(drive), "Load or replace disc image", None
        ])
        actions = []
        monkeypatch.setattr(
            "protontricks.gui._choose_from_list",
            lambda *args: next(responses)
        )
        monkeypatch.setattr(
            "protontricks.gui.list_drives",
            lambda: [drive]
        )
        monkeypatch.setattr(
            "protontricks.gui._select_disc_image", lambda: cue
        )
        monkeypatch.setattr(
            "protontricks.gui._confirm_cdrom_action",
            lambda *args: True
        )
        monkeypatch.setattr(
            "protontricks.gui.load_image",
            lambda slot, image, replace: actions.append(
                ("load", slot, image, replace)
            ) or drive
        )
        monkeypatch.setattr(
            "protontricks.gui.set_cdrom_mapping",
            lambda path, selected, letter: actions.append(
                ("map", path, selected.slot, letter)
            )
        )

        manage_cdrom_drives_gui(prefix, "Fake game")
        assert actions == [
            ("load", 1, cue, True),
            ("map", prefix, 1, "D")
        ]

    def test_add_and_remove_reader_actions(self, monkeypatch, tmp_path):
        from protontricks.cdemu_backend import OpticalDrive
        from protontricks.gui import manage_cdrom_drives_gui

        prefix = tmp_path / "pfx"
        (prefix / "dosdevices").mkdir(parents=True)
        drives = [
            OpticalDrive(0, Path("/dev/sr0")),
            OpticalDrive(1, Path("/dev/sr1")),
        ]
        choices = iter([
            "D:", "Add virtual reader",
            "Remove last virtual reader (reader 2)", None
        ])
        calls = []

        monkeypatch.setattr(
            "protontricks.gui._choose_from_list",
            lambda *args: next(choices)
        )
        monkeypatch.setattr(
            "protontricks.gui.list_drives", lambda: list(drives)
        )
        monkeypatch.setattr(
            "protontricks.gui._confirm_cdrom_action",
            lambda *args: True
        )

        def add_reader():
            drive = OpticalDrive(2, Path("/dev/sr2"))
            drives.append(drive)
            calls.append(("add",))
            return drive

        def remove_reader(slot):
            calls.append(("remove", slot))
            drives.pop()
            return slot

        monkeypatch.setattr("protontricks.gui.add_drive", add_reader)
        monkeypatch.setattr("protontricks.gui.remove_drive", remove_reader)
        manage_cdrom_drives_gui(prefix, "Fake game")
        assert calls == [("add",), ("remove", 2)]

    def test_remove_reader_with_image_asks_to_eject_first(
            self, monkeypatch, tmp_path):
        from protontricks.cdemu_backend import OpticalDrive
        from protontricks.gui import manage_cdrom_drives_gui

        prefix = tmp_path / "pfx"
        (prefix / "dosdevices").mkdir(parents=True)
        drives = [
            OpticalDrive(0, Path("/dev/sr0")),
            OpticalDrive(1, Path("/dev/sr1")),
            OpticalDrive(2, Path("/dev/sr2"), "/disc2.iso", tmp_path),
        ]
        choices = iter([
            "D:", "Remove last virtual reader (reader 2)", None
        ])
        calls = []

        monkeypatch.setattr(
            "protontricks.gui._choose_from_list",
            lambda *args: next(choices)
        )
        monkeypatch.setattr(
            "protontricks.gui.list_drives", lambda: list(drives)
        )
        monkeypatch.setattr(
            "protontricks.gui._confirm_cdrom_action",
            lambda *args: calls.append(("confirm",)) or True
        )
        monkeypatch.setattr(
            "protontricks.gui.remove_drive",
            lambda slot: calls.append(("remove", slot))
        )
        monkeypatch.setattr(
            "protontricks.gui._cdrom_error_dialog",
            lambda message: calls.append(("error", str(message)))
        )
        manage_cdrom_drives_gui(prefix, "Fake game")

        assert len(calls) == 1
        assert calls[0][0] == "error"
        assert "Eject the disc" in calls[0][1]

    def test_disc_image_picker_cancel(self, gui_provider):
        from protontricks.gui import _select_disc_image

        gui_provider.returncode = 1
        assert _select_disc_image() is None


class TestCDROMBusyDiscFallback:
    """Disc swaps while the installer started from Disc 1 is running."""

    def _setup(self, monkeypatch, tmp_path, drives, answers=None):
        from protontricks.cdemu_backend import DeviceBusyError
        from protontricks.gui import _drive_label

        prefix = tmp_path / "pfx"
        (prefix / "dosdevices").mkdir(parents=True)
        disc2 = tmp_path / "Disc 2.iso"
        disc2.touch()
        responses = iter([
            "D:", _drive_label(drives[0]),
            "Load or replace disc image", None
        ])
        calls = []
        answers = iter(answers) if answers is not None else None

        def confirm(message):
            calls.append(("confirm", message))
            return next(answers) if answers is not None else True

        def load_image(slot, image, replace=False):
            calls.append(("load", slot, image, replace))
            if slot == 0:
                raise DeviceBusyError("Reader 0 is busy")
            return OpticalDrive(
                slot, Path("/dev/sr{}".format(slot)), str(image),
                tmp_path
            )

        def add_drive():
            drive = OpticalDrive(len(drives), Path(
                "/dev/sr{}".format(len(drives))
            ))
            drives.append(drive)
            calls.append(("add",))
            return drive

        monkeypatch.setattr(
            "protontricks.gui._choose_from_list",
            lambda *args: next(responses)
        )
        monkeypatch.setattr(
            "protontricks.gui.list_drives", lambda: list(drives)
        )
        monkeypatch.setattr(
            "protontricks.gui.find_empty_drive",
            lambda exclude_slot=None: next(
                (d for d in drives
                 if not d.loaded and d.slot != exclude_slot), None
            )
        )
        monkeypatch.setattr(
            "protontricks.gui._select_disc_image", lambda: disc2
        )
        monkeypatch.setattr(
            "protontricks.gui._confirm_cdrom_action", confirm
        )
        monkeypatch.setattr("protontricks.gui.load_image", load_image)
        monkeypatch.setattr("protontricks.gui.add_drive", add_drive)
        monkeypatch.setattr(
            "protontricks.gui.set_cdrom_mapping",
            lambda path, drive, letter: calls.append(
                ("map", drive.slot, letter)
            )
        )
        monkeypatch.setattr(
            "protontricks.gui._cdrom_error_dialog",
            lambda message: calls.append(("error", str(message)))
        )
        return prefix, disc2, calls

    def test_busy_disc_is_loaded_into_empty_reader(
            self, monkeypatch, tmp_path):
        from protontricks.gui import manage_cdrom_drives_gui

        drives = [
            OpticalDrive(0, Path("/dev/sr0"), "/disc1.iso", tmp_path),
            OpticalDrive(1, Path("/dev/sr1")),
        ]
        prefix, disc2, calls = self._setup(monkeypatch, tmp_path, drives)
        manage_cdrom_drives_gui(prefix, "Fake game")

        actions = [call for call in calls if call[0] != "confirm"]
        assert actions == [
            ("load", 0, disc2, True),
            ("load", 1, disc2, False),
            ("map", 1, "D")
        ]
        assert "empty reader 1" in calls[-3][1]

    def test_busy_disc_without_spare_reader_adds_one(
            self, monkeypatch, tmp_path):
        from protontricks.gui import manage_cdrom_drives_gui

        drives = [
            OpticalDrive(0, Path("/dev/sr0"), "/disc1.iso", tmp_path),
        ]
        prefix, disc2, calls = self._setup(monkeypatch, tmp_path, drives)
        manage_cdrom_drives_gui(prefix, "Fake game")

        actions = [call for call in calls if call[0] != "confirm"]
        assert actions == [
            ("load", 0, disc2, True),
            ("add",),
            ("load", 1, disc2, False),
            ("map", 1, "D")
        ]

    def test_busy_disc_fallback_can_be_cancelled(
            self, monkeypatch, tmp_path):
        from protontricks.gui import manage_cdrom_drives_gui

        drives = [
            OpticalDrive(0, Path("/dev/sr0"), "/disc1.iso", tmp_path),
            OpticalDrive(1, Path("/dev/sr1")),
        ]
        # Accept replacing Disc 1, then decline the second-reader fallback.
        prefix, disc2, calls = self._setup(
            monkeypatch, tmp_path, drives, answers=[True, False]
        )
        manage_cdrom_drives_gui(prefix, "Fake game")

        actions = [call for call in calls if call[0] != "confirm"]
        assert actions == [("load", 0, disc2, True)]


class TestCDROMMinimalMenus:
    """The manager only offers what is needed to swap discs."""

    def _run(self, monkeypatch, tmp_path, drive, choices):
        from protontricks.gui import manage_cdrom_drives_gui

        prefix = tmp_path / "pfx"
        (prefix / "dosdevices").mkdir(parents=True)
        menus = []
        calls = []
        choices = iter(choices)

        def choose(title, prompt, rows):
            menus.append(list(rows))
            return next(choices)

        monkeypatch.setattr("protontricks.gui._choose_from_list", choose)
        monkeypatch.setattr("protontricks.gui.list_drives", lambda: [drive])
        monkeypatch.setattr(
            "protontricks.gui.mount_drive",
            lambda slot: calls.append(("mount", slot)) or OpticalDrive(
                slot, drive.device, drive.image, tmp_path
            )
        )
        monkeypatch.setattr(
            "protontricks.gui.set_cdrom_mapping",
            lambda path, selected, letter: calls.append(
                ("map", selected.slot, letter)
            )
        )
        monkeypatch.setattr(
            "protontricks.gui._cdrom_error_dialog",
            lambda message: calls.append(("error", str(message)))
        )
        manage_cdrom_drives_gui(prefix, "Fake game")
        return menus, calls

    def test_menus_only_offer_disc_swap_actions(self, monkeypatch, tmp_path):
        from protontricks.gui import _drive_label

        drive = OpticalDrive(0, Path("/dev/sr0"))
        menus, _ = self._run(
            monkeypatch, tmp_path, drive,
            ["E:", _drive_label(drive), "Back", None]
        )
        # Reader 0 is a protected default reader: no remove entry.
        assert menus[1] == [_drive_label(drive), "Add virtual reader"]
        assert menus[2] == [
            "Load or replace disc image", "Eject disc", "Map disc to E:",
            "Back"
        ]

    def test_map_mounts_a_loaded_disc_first(self, monkeypatch, tmp_path):
        from protontricks.gui import _drive_label

        drive = OpticalDrive(1, Path("/dev/sr1"), "/disc2.iso")
        _, calls = self._run(
            monkeypatch, tmp_path, drive,
            ["D:", _drive_label(drive), "Map disc to D:", None]
        )
        assert calls == [("mount", 1), ("map", 1, "D")]

    def test_remove_entry_is_offered_for_reader_2(
            self, monkeypatch, tmp_path):
        from protontricks.gui import _drive_label

        drive = OpticalDrive(2, Path("/dev/sr2"))
        menus, _ = self._run(
            monkeypatch, tmp_path, drive, ["D:", None]
        )
        assert menus[1] == [
            _drive_label(drive), "Add virtual reader",
            "Remove last virtual reader (reader 2)"
        ]


class TestCDROMDriveLetterDetection:
    """Installers started from a mounted disc use the letter Wine gave it."""

    def test_letter_assigned_by_wine_is_listed_first(
            self, monkeypatch, tmp_path):
        from protontricks.gui import _drive_letter_choices

        disc1 = tmp_path / "VOLUME_1"
        disc1.mkdir()
        prefix = tmp_path / "pfx"
        (prefix / "dosdevices").mkdir(parents=True)
        (prefix / "dosdevices" / "k:").symlink_to(str(disc1))
        monkeypatch.setattr(
            "protontricks.gui.list_drives",
            lambda: [OpticalDrive(0, Path("/dev/sr0"), "/d1.cue", disc1)]
        )

        prompt, rows = _drive_letter_choices(prefix, "Fake game")
        assert rows[0] == "K: - VOLUME_1 (disc already mapped by Wine)"
        assert "K:" not in rows[1:]
        assert len(rows) == 22
        assert "choose K:" in prompt

    def test_detected_letter_row_selects_that_letter(
            self, monkeypatch, tmp_path):
        from protontricks.gui import _drive_label, manage_cdrom_drives_gui

        prefix = tmp_path / "pfx"
        (prefix / "dosdevices").mkdir(parents=True)
        drive = OpticalDrive(0, Path("/dev/sr0"))
        menus = []
        choices = iter([
            "K: - VOLUME_1 (disc already mapped by Wine)",
            _drive_label(drive), "Back", None
        ])

        def choose(title, prompt, rows):
            menus.append(rows)
            return next(choices)

        monkeypatch.setattr("protontricks.gui._choose_from_list", choose)
        monkeypatch.setattr("protontricks.gui.list_drives", lambda: [drive])
        manage_cdrom_drives_gui(prefix, "Fake game")
        assert "Map disc to K:" in menus[2]

    def test_letter_prompt_without_cdemu(self, monkeypatch, tmp_path):
        from protontricks.cdrom import CDROMError
        from protontricks.gui import _drive_letter_choices

        def missing():
            raise CDROMError("cdemu is not installed")

        monkeypatch.setattr("protontricks.gui.list_drives", missing)
        prompt, rows = _drive_letter_choices(tmp_path, "Fake game")
        assert rows[0] == "D:" and rows[-1] == "Y:"
        assert prompt == "Choose the Windows drive letter for Fake game"
