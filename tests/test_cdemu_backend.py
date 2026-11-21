"""Tests for CDEmu's system-wide reader and image operations."""
import json
from pathlib import Path

import pytest

from protontricks import cdemu_backend as backend
from protontricks.cdrom import CDROMError


def test_list_readers_including_empty_and_unmounted(monkeypatch, tmp_path):
    mount = tmp_path / "Disc Two"
    mount.mkdir()

    def fake_command(args):
        if args[:2] == ["cdemu", "device-mapping"]:
            return (
                "Device mapping:\nDEV SCSI CD-ROM SCSI generic\n"
                "0 /dev/sr0 /dev/sg1\n1 /dev/sr1 /dev/sg2\n"
            )
        if args[:2] == ["cdemu", "status"]:
            return (
                "Devices status:\nDEV LOADED FILENAME\n"
                "0 True /images/disc two.cue\n1 False\n"
            )
        if args[0] == "findmnt":
            if args[3] == "/dev/sr0":
                return json.dumps({
                    "filesystems": [{"target": str(mount)}]
                })
            raise CDROMError("Not mounted")
        raise AssertionError(args)

    monkeypatch.setattr(backend, "_command", fake_command)
    drives = backend.list_drives()
    assert [(d.slot, d.loaded) for d in drives] == [(0, True), (1, False)]
    assert drives[0].mountpoint == mount
    assert drives[0].image == "/images/disc two.cue"
    assert drives[1].mountpoint is None


def test_load_mount_unmount_eject_sequence(monkeypatch, tmp_path):
    image = tmp_path / "test disc.iso"
    image.write_bytes(b"disc")
    mounted = tmp_path / "mount"
    mounted.mkdir()
    drive = [backend.OpticalDrive(0, Path("/dev/sr0"))]
    calls = []

    def fake_command(args):
        calls.append(args)
        if args[:2] == ["cdemu", "load"]:
            drive[0] = backend.OpticalDrive(
                0, Path("/dev/sr0"), str(image)
            )
        elif args[:2] == ["udisksctl", "mount"]:
            drive[0] = backend.OpticalDrive(
                0, Path("/dev/sr0"), str(image), mounted
            )
        elif args[:2] == ["udisksctl", "unmount"]:
            drive[0] = backend.OpticalDrive(
                0, Path("/dev/sr0"), str(image)
            )
        elif args[:2] == ["cdemu", "unload"]:
            drive[0] = backend.OpticalDrive(0, Path("/dev/sr0"))
        return ""

    monkeypatch.setattr(backend, "list_drives", lambda: drive[:])
    monkeypatch.setattr(backend, "_command", fake_command)
    assert backend.load_image(0, image).mountpoint == mounted
    with pytest.raises(CDROMError, match="not empty"):
        backend.load_image(0, image)
    assert backend.eject_drive(0).loaded is False
    assert [c[:2] for c in calls] == [
        ["cdemu", "load"], ["udisksctl", "mount"],
        ["udisksctl", "unmount"], ["cdemu", "unload"]
    ]


def test_add_and_remove_last_reader(monkeypatch):
    """Any empty last reader can be removed, including pre-existing ones."""
    drives = [
        backend.OpticalDrive(slot, Path("/dev/sr{}".format(slot)))
        for slot in range(3)
    ]
    commands = []

    def fake_command(args):
        commands.append(args)
        if args == ["cdemu", "add-device"]:
            drives.append(backend.OpticalDrive(3, Path("/dev/sr3")))
        elif args == ["cdemu", "remove-device"]:
            drives.pop()
        return ""

    monkeypatch.setattr(backend, "list_drives", lambda: drives[:])
    monkeypatch.setattr(backend, "_command", fake_command)

    assert backend.add_drive().slot == 3
    # Only the last reader can be removed by CDEmu.
    with pytest.raises(CDROMError, match="only remove its last reader"):
        backend.remove_drive(2)
    assert backend.remove_drive(3).slot == 3
    # Reader 2 was not created by Protontricks, but it is empty and last.
    assert backend.remove_drive(2).slot == 2
    assert [drive.slot for drive in drives] == [0, 1]
    assert commands == [
        ["cdemu", "add-device"], ["cdemu", "remove-device"],
        ["cdemu", "remove-device"]
    ]


@pytest.mark.parametrize("slot", [0, 1])
def test_default_readers_cannot_be_removed(monkeypatch, slot):
    drives = [
        backend.OpticalDrive(number, Path("/dev/sr{}".format(number)))
        for number in range(slot + 1)
    ]
    commands = []
    monkeypatch.setattr(backend, "list_drives", lambda: drives[:])
    monkeypatch.setattr(backend, "_command", commands.append)

    assert not backend.is_removable_slot(slot)
    with pytest.raises(CDROMError, match="default readers"):
        backend.remove_drive(slot)
    assert commands == []


def test_cannot_remove_reader_holding_an_image(monkeypatch, tmp_path):
    mount = tmp_path / "mount"
    mount.mkdir()
    commands = []
    monkeypatch.setattr(backend, "_command", commands.append)

    for drive in (
            backend.OpticalDrive(2, Path("/dev/sr2"), "/disc1.iso"),
            backend.OpticalDrive(2, Path("/dev/sr2"), "/disc1.iso", mount)):
        monkeypatch.setattr(backend, "list_drives", lambda: [drive])
        with pytest.raises(CDROMError, match="Eject the disc"):
            backend.remove_drive(2)
    assert commands == []


def test_external_mount_failure_does_not_force_eject(
        monkeypatch, tmp_path):
    mount = tmp_path / "disc"
    mount.mkdir()
    drive = backend.OpticalDrive(
        0, Path("/dev/sr0"), "/images/disc.iso", mount
    )
    seen = []
    monkeypatch.setattr(backend, "list_drives", lambda: [drive])

    def fake_command(args):
        seen.append(args)
        raise CDROMError("Device busy")

    monkeypatch.setattr(backend, "_command", fake_command)
    with pytest.raises(CDROMError, match="busy"):
        backend.eject_drive(0)
    assert seen == [
        ["udisksctl", "unmount", "-b", "/dev/sr0"]
    ]


def test_failed_replace_attempts_to_restore_old_disc(monkeypatch, tmp_path):
    old_file = tmp_path / "old.iso"
    new_file = tmp_path / "bad.iso"
    old_file.write_bytes(b"old")
    new_file.write_bytes(b"bad")
    mount = tmp_path / "mount"
    mount.mkdir()
    drive = [backend.OpticalDrive(
        0, Path("/dev/sr0"), str(old_file), mount
    )]
    calls = []

    def fake_command(args):
        calls.append(args)
        if args[:2] == ["udisksctl", "unmount"]:
            drive[0] = backend.OpticalDrive(
                0, Path("/dev/sr0"), str(old_file)
            )
        elif args[:2] == ["cdemu", "unload"]:
            drive[0] = backend.OpticalDrive(
                0, Path("/dev/sr0")
            )
        elif args[:2] == ["cdemu", "load"]:
            if args[-1] == str(new_file):
                raise CDROMError("Broken disc image")
            drive[0] = backend.OpticalDrive(
                0, Path("/dev/sr0"), str(old_file)
            )
        elif args[:2] == ["udisksctl", "mount"]:
            drive[0] = backend.OpticalDrive(
                0, Path("/dev/sr0"), str(old_file), mount
            )
        return ""

    monkeypatch.setattr(backend, "list_drives", lambda: drive[:])
    monkeypatch.setattr(backend, "_command", fake_command)
    with pytest.raises(CDROMError, match="Broken disc image"):
        backend.load_image(0, new_file, replace=True)
    assert drive[0].image == str(old_file)
    assert drive[0].mountpoint == mount
    assert [c[:2] for c in calls][-2:] == [
        ["cdemu", "load"], ["udisksctl", "mount"]
    ]


def test_missing_reader_status_is_not_treated_as_empty(monkeypatch):
    def fake_command(args):
        if args[:2] == ["cdemu", "device-mapping"]:
            return "DEV SCSI CD-ROM SCSI generic\n0 /dev/sr0 /dev/sg1\n"
        if args[:2] == ["cdemu", "status"]:
            return "DEV LOADED FILENAME\n"
        raise AssertionError(args)

    monkeypatch.setattr(backend, "_command", fake_command)
    with pytest.raises(CDROMError, match="did not report status"):
        backend.list_drives()


def test_mount_drive_handles_desktop_automount_race(monkeypatch, tmp_path):
    mounted = tmp_path / "cd"
    mounted.mkdir()
    device = Path("/dev/sr0")
    drive = [backend.OpticalDrive(0, device, "/discs/disc.cue")]
    calls = []

    def command(args):
        calls.append(args)
        # udisks loses the race, but the desktop has already mounted it.
        drive[0] = backend.OpticalDrive(
            0, device, "/discs/disc.cue", mounted
        )
        raise CDROMError("AlreadyMounted")

    monkeypatch.setattr(backend, "list_drives", lambda: drive[:])
    monkeypatch.setattr(backend, "_command", command)
    assert backend.mount_drive(0).mountpoint == mounted
    assert calls == [["udisksctl", "mount", "-b", "/dev/sr0"]]


def test_mount_drive_retries_during_udisks_probe(monkeypatch, tmp_path):
    mounted = tmp_path / "cd"
    mounted.mkdir()
    device = Path("/dev/sr0")
    drive = [backend.OpticalDrive(0, device, "/discs/disc.cue")]
    attempts = []

    def command(args):
        attempts.append(args)
        if len(attempts) < 3:
            raise CDROMError("No filesystem object yet")
        drive[0] = backend.OpticalDrive(
            0, device, "/discs/disc.cue", mounted
        )
        return ""

    monkeypatch.setattr(backend, "list_drives", lambda: drive[:])
    monkeypatch.setattr(backend, "_command", command)
    monkeypatch.setattr(backend.time, "sleep", lambda seconds: None)
    assert backend.mount_drive(0).mountpoint == mounted
    assert len(attempts) == 3


def test_mount_drive_times_out_instead_of_succeeding(monkeypatch):
    drive = backend.OpticalDrive(
        0, Path("/dev/sr0"), "/discs/disc.cue"
    )
    attempts = []

    monkeypatch.setattr(backend, "list_drives", lambda: [drive])
    monkeypatch.setattr(backend.time, "sleep", lambda seconds: None)

    def command(args):
        attempts.append(args)
        raise CDROMError("Not ready")

    monkeypatch.setattr(backend, "_command", command)
    with pytest.raises(CDROMError, match="Not ready"):
        backend.mount_drive(0)
    assert len(attempts) == 10


def _async_unload_command(drive, image, mount, new_image, pending_polls):
    """Fake CDEmu whose unload completes only after a few status polls."""
    state = {"unloading": 0}
    calls = []

    def list_drives():
        if state["unloading"]:
            state["unloading"] -= 1
            if not state["unloading"]:
                drive[0] = backend.OpticalDrive(0, Path("/dev/sr0"))
        return drive[:]

    def command(args):
        calls.append(args)
        if args[:2] == ["udisksctl", "unmount"]:
            drive[0] = backend.OpticalDrive(0, Path("/dev/sr0"), image)
        elif args[:2] == ["cdemu", "unload"]:
            state["unloading"] = pending_polls
        elif args[:2] == ["cdemu", "load"]:
            if drive[0].loaded:
                raise CDROMError(
                    "cdemu failed: ERROR: Failed to load image: "
                    "net.sf.cdemu.CDEmuDaemon.errorDaemon.AlreadyLoaded: "
                    "Device is already loaded! (36)"
                )
            drive[0] = backend.OpticalDrive(
                0, Path("/dev/sr0"), args[-1]
            )
        elif args[:2] == ["udisksctl", "mount"]:
            drive[0] = backend.OpticalDrive(
                0, Path("/dev/sr0"), drive[0].image, mount
            )
        return ""

    return list_drives, command, calls


def test_eject_waits_for_asynchronous_unload(monkeypatch, tmp_path):
    mount = tmp_path / "mount"
    mount.mkdir()
    drive = [backend.OpticalDrive(0, Path("/dev/sr0"), "/disc1.iso", mount)]
    list_drives, command, _ = _async_unload_command(
        drive, "/disc1.iso", mount, None, pending_polls=4
    )
    sleeps = []
    monkeypatch.setattr(backend, "list_drives", list_drives)
    monkeypatch.setattr(backend, "_command", command)
    monkeypatch.setattr(backend.time, "sleep", sleeps.append)

    assert backend.eject_drive(0).loaded is False
    assert sleeps


def test_eject_times_out_when_reader_stays_loaded(monkeypatch, tmp_path):
    drive = [backend.OpticalDrive(0, Path("/dev/sr0"), "/disc1.iso")]
    monkeypatch.setattr(backend, "list_drives", lambda: drive[:])
    monkeypatch.setattr(backend, "_command", lambda args: "")
    monkeypatch.setattr(backend.time, "sleep", lambda seconds: None)

    with pytest.raises(CDROMError, match="still reports a loaded disc"):
        backend.eject_drive(0)


def test_replace_disc_waits_for_unload_before_loading(
        monkeypatch, tmp_path):
    """Regression: Disc 1 -> Disc 2 failed with CDEmu's AlreadyLoaded."""
    disc1 = tmp_path / "disc1.iso"
    disc2 = tmp_path / "disc2.iso"
    disc1.write_bytes(b"1")
    disc2.write_bytes(b"2")
    mount = tmp_path / "mount"
    mount.mkdir()
    drive = [backend.OpticalDrive(0, Path("/dev/sr0"), str(disc1), mount)]
    list_drives, command, calls = _async_unload_command(
        drive, str(disc1), mount, str(disc2), pending_polls=3
    )
    monkeypatch.setattr(backend, "list_drives", list_drives)
    monkeypatch.setattr(backend, "_command", command)
    monkeypatch.setattr(backend.time, "sleep", lambda seconds: None)

    result = backend.load_image(0, disc2, replace=True)

    assert result.image == str(disc2.resolve())
    assert result.mountpoint == mount
    assert [c[:2] for c in calls] == [
        ["udisksctl", "unmount"], ["cdemu", "unload"],
        ["cdemu", "load"], ["udisksctl", "mount"]
    ]


BUSY_ERROR = (
    "udisksctl failed: Error unmounting /dev/sr0: "
    "GDBus.Error:org.freedesktop.UDisks2.Error.DeviceBusy: "
    "Error unmounting /dev/sr0: target is busy"
)


def test_busy_unmount_raises_device_busy_error(monkeypatch, tmp_path):
    mount = tmp_path / "mount"
    mount.mkdir()
    drive = backend.OpticalDrive(0, Path("/dev/sr0"), "/disc1.iso", mount)

    def command(args):
        raise CDROMError(BUSY_ERROR)

    monkeypatch.setattr(backend, "list_drives", lambda: [drive])
    monkeypatch.setattr(backend, "_command", command)

    with pytest.raises(backend.DeviceBusyError, match="still using"):
        backend.unmount_drive(0)


def test_other_unmount_errors_are_not_reported_as_busy(monkeypatch, tmp_path):
    mount = tmp_path / "mount"
    mount.mkdir()
    drive = backend.OpticalDrive(0, Path("/dev/sr0"), "/disc1.iso", mount)

    def command(args):
        raise CDROMError("udisksctl failed: Not authorized")

    monkeypatch.setattr(backend, "list_drives", lambda: [drive])
    monkeypatch.setattr(backend, "_command", command)

    with pytest.raises(CDROMError) as excinfo:
        backend.unmount_drive(0)
    assert not isinstance(excinfo.value, backend.DeviceBusyError)


def test_busy_replace_leaves_current_disc_untouched(monkeypatch, tmp_path):
    disc1 = tmp_path / "disc1.iso"
    disc2 = tmp_path / "disc2.iso"
    disc1.write_bytes(b"1")
    disc2.write_bytes(b"2")
    mount = tmp_path / "mount"
    mount.mkdir()
    drive = backend.OpticalDrive(0, Path("/dev/sr0"), str(disc1), mount)
    calls = []

    def command(args):
        calls.append(args)
        if args[:2] == ["udisksctl", "unmount"]:
            raise CDROMError(BUSY_ERROR)
        return ""

    monkeypatch.setattr(backend, "list_drives", lambda: [drive])
    monkeypatch.setattr(backend, "_command", command)

    with pytest.raises(backend.DeviceBusyError):
        backend.load_image(0, disc2, replace=True)
    # Nothing was unloaded or loaded: Disc 1 stays usable by the installer.
    assert [c[:2] for c in calls] == [["udisksctl", "unmount"]]


def test_find_empty_drive_skips_busy_and_loaded_readers(monkeypatch):
    drives = [
        backend.OpticalDrive(0, Path("/dev/sr0"), "/disc1.iso"),
        backend.OpticalDrive(1, Path("/dev/sr1"), "/other.iso"),
        backend.OpticalDrive(2, Path("/dev/sr2")),
    ]
    monkeypatch.setattr(backend, "list_drives", lambda: drives[:])

    assert backend.find_empty_drive(exclude_slot=0).slot == 2
    assert backend.find_empty_drive(exclude_slot=2) is None


def test_command_reports_missing_tool(monkeypatch):
    def missing(*args, **kwargs):
        raise FileNotFoundError("cdemu")

    monkeypatch.setattr(backend.subprocess, "run", missing)
    with pytest.raises(CDROMError, match="cdemu-client"):
        backend._command(["cdemu", "status"])


def test_command_reports_failing_tool(monkeypatch):
    from subprocess import CompletedProcess

    def failed(args, **kwargs):
        return CompletedProcess(args, 1, "", "D-Bus disconnected")

    monkeypatch.setattr(backend.subprocess, "run", failed)
    with pytest.raises(CDROMError, match="D-Bus disconnected"):
        backend._command(["cdemu", "status"])


def test_reader_without_kernel_device_reports_vhba(monkeypatch):
    """CDEmu can list a reader whose /dev/sr device is missing."""
    def command(args):
        if args[:2] == ["cdemu", "device-mapping"]:
            return (
                "Device mapping:\nDEV   SCSI CD-ROM     SCSI generic\n"
                "0                                    \n"
            )
        if args[:2] == ["cdemu", "status"]:
            return "Devices' status:\nDEV   LOADED     FILENAME\n0     False\n"
        raise AssertionError(args)

    monkeypatch.setattr(backend, "_command", command)
    with pytest.raises(CDROMError, match="modprobe vhba"):
        backend.list_drives()
