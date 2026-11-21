"""Optional CDEmu device operations for Protontricks's per-game CD/DVD GUI.

CDEmu readers are global. Only the drive-letter mapping is game-specific.
No commands run through a shell and no privileged/forced unmounts are used.
"""
import json
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from .cdrom import CDROMError


@dataclass(frozen=True)
class OpticalDrive:
    slot: int
    device: Path
    image: str = ""
    mountpoint: Path = None

    @property
    def loaded(self):
        return bool(self.image)


def _command(args):
    """Run a command without a shell and return its standard output."""
    try:
        result = subprocess.run(
            args, capture_output=True, text=True, check=False
        )
    except FileNotFoundError as exc:
        raise CDROMError(
            "{} is not installed. The CD/DVD manager needs cdemu-client, "
            "udisks2 (udisksctl) and findmnt.".format(args[0])
        ) from exc
    if result.returncode:
        raise CDROMError(
            "{} failed: {}".format(args[0], result.stderr.strip())
        )
    return result.stdout


def list_drives():
    """List all CDEmu devices, including empty and unmounted readers."""
    mapping = _command(["cdemu", "device-mapping"])
    status = _command(["cdemu", "status"])
    image_by_slot = {}
    for line in status.splitlines():
        match = re.match(r"^\s*(\d+)\s+(True|False)\s*(.*)$", line)
        if match:
            image = match.group(3).strip()
            if match.group(2) == "True" and not image:
                raise CDROMError(
                    "CDEmu reports a loaded reader without an image path."
                )
            image_by_slot[int(match.group(1))] = (
                image if match.group(2) == "True" else ""
            )

    result = []
    mapped = set()
    for line in mapping.splitlines():
        match = re.match(r"^\s*(\d+)\s+(/dev/\S+)\s+", line)
        if not match:
            continue
        slot = int(match.group(1))
        mapped.add(slot)
        if slot not in image_by_slot:
            raise CDROMError(
                "CDEmu did not report status for reader {}.".format(slot)
            )
        device = Path(match.group(2))
        mountpoint = None
        try:
            data = json.loads(_command([
                "findmnt", "--json", "--source", str(device),
                "--output", "TARGET"
            ]))
            filesystems = data.get("filesystems") or []
            if filesystems and filesystems[0].get("target"):
                candidate = Path(filesystems[0]["target"])
                if candidate.is_dir():
                    mountpoint = candidate
        except (CDROMError, ValueError, KeyError, TypeError):
            # A reader can be empty, or its loaded disc may not be mounted.
            pass
        result.append(OpticalDrive(
            slot, device, image_by_slot.get(slot, ""), mountpoint
        ))
    unmapped = sorted(set(image_by_slot) - mapped)
    if unmapped:
        # CDEmu still lists the reader, but the kernel side is missing.
        raise CDROMError(
            "CDEmu reader {} has no /dev/sr device. The vhba kernel module "
            "is probably not loaded: run \"sudo modprobe vhba\", then "
            "\"killall cdemu-daemon\", and reopen the manager.".format(
                ", ".join(str(slot) for slot in unmapped)
            )
        )
    return sorted(result, key=lambda d: d.slot)


def _selected_drive(slot):
    drive = next((d for d in list_drives() if d.slot == slot), None)
    if drive is None:
        raise CDROMError(
            "CDEmu reader {} no longer exists.".format(slot)
        )
    return drive


def mount_drive(slot):
    """Wait for optical media probing and tolerate desktop automount races."""
    drive = _selected_drive(slot)
    if not drive.loaded:
        raise CDROMError("Load an image into reader {} first.".format(slot))
    if drive.mountpoint is not None:
        return drive

    last_error = None
    for attempt in range(10):
        drive = _selected_drive(slot)
        if drive.mountpoint is not None:
            return drive
        try:
            _command(["udisksctl", "mount", "-b", str(drive.device)])
        except CDROMError as exc:
            # udisks may not have probed the newly inserted image yet,
            # or a desktop automounter may mount it between the checks.
            last_error = exc
        drive = _selected_drive(slot)
        if drive.mountpoint is not None:
            return drive
        if attempt < 9:
            time.sleep(0.3)

    message = "CDEmu reader {} did not become mounted.".format(slot)
    if last_error is not None:
        message += " Last mount attempt: {}".format(last_error)
    raise CDROMError(message)


class DeviceBusyError(CDROMError):
    """A disc filesystem is in use and cannot be unmounted normally."""


# udisks reports a busy filesystem with this D-Bus error name; the kernel
# message is kept as a fallback for older udisks versions.
_BUSY_MARKERS = ("UDisks2.Error.DeviceBusy", "target is busy")


def find_empty_drive(exclude_slot=None):
    """Return the first empty CDEmu reader, optionally skipping one slot."""
    return next(
        (
            drive for drive in list_drives()
            if not drive.loaded and drive.slot != exclude_slot
        ),
        None
    )


def unmount_drive(slot):
    """Unmount a reader's filesystem regularly; never force or lazy-unmount.

    :raises DeviceBusyError: if a running program still uses the disc,
                             for example an installer started from it
    """
    drive = _selected_drive(slot)
    if drive.mountpoint is not None:
        try:
            _command(["udisksctl", "unmount", "-b", str(drive.device)])
        except CDROMError as exc:
            if any(marker in str(exc) for marker in _BUSY_MARKERS):
                raise DeviceBusyError(
                    "Reader {} cannot be unmounted because a running "
                    "program is still using its disc (usually the "
                    "installer started from it). Load the next disc into "
                    "another reader instead, or close that program "
                    "first.".format(slot)
                ) from exc
            raise
        drive = _selected_drive(slot)
        if drive.mountpoint is not None:
            raise CDROMError("The filesystem is still mounted.")
    return drive


# "cdemu unload" only emulates pressing the drive's eject button: it returns
# before the kernel has released the medium, and loading another image while
# the reader is still loaded fails with CDEmu's "AlreadyLoaded" error.
UNLOAD_POLL_ATTEMPTS = 40
UNLOAD_POLL_INTERVAL = 0.25


def _wait_until_unloaded(slot):
    """Wait until CDEmu reports the reader as empty after an unload."""
    for attempt in range(UNLOAD_POLL_ATTEMPTS):
        drive = _selected_drive(slot)
        if not drive.loaded:
            return drive
        if attempt < UNLOAD_POLL_ATTEMPTS - 1:
            time.sleep(UNLOAD_POLL_INTERVAL)
    raise CDROMError(
        "CDEmu reader {} still reports a loaded disc after the unload "
        "request. The system may still be releasing it, or a running "
        "program may be locking the drive. Try again in a few seconds, "
        "or load the next disc into another reader.".format(slot)
    )


def eject_drive(slot):
    """Unmount and unload a reader, waiting until the unload completes."""
    drive = unmount_drive(slot)
    if drive.loaded:
        _command(["cdemu", "unload", str(slot)])
        return _wait_until_unloaded(slot)
    return drive


def load_image(slot, image_path, replace=False):
    """Load an image and mount it. Replacement is explicit, never forced.

    A failed replacement load attempts to restore the previously loaded disc.
    If a new image loads but cannot mount, it remains loaded for a retry.
    """
    path = Path(image_path).expanduser()
    if not path.is_file():
        raise CDROMError("Image file does not exist: {}".format(path))
    path = path.resolve()
    old = _selected_drive(slot)
    if old.loaded and not replace:
        raise CDROMError(
            "Reader {} is not empty; eject it first.".format(slot)
        )
    if old.loaded:
        eject_drive(slot)
    try:
        _command(["cdemu", "load", str(slot), str(path)])
    except CDROMError:
        if old.loaded and Path(old.image).is_file():
            try:
                _command(["cdemu", "load", str(slot), old.image])
                if old.mountpoint is not None:
                    mount_drive(slot)
            except CDROMError:
                pass
        raise
    return mount_drive(slot)


# Readers 0 and 1 are CDEmu's default devices and are never removed, so
# CDEmu keeps working normally when Protontricks is not in use.
PROTECTED_READER_SLOTS = frozenset({0, 1})


def is_removable_slot(slot):
    """Return True if the manager may remove the given reader slot."""
    return slot not in PROTECTED_READER_SLOTS


def add_drive():
    """Create a system-wide CDEmu reader and return it."""
    before = {drive.slot for drive in list_drives()}
    _command(["cdemu", "add-device"])
    new = []
    for attempt in range(5):
        new = [drive for drive in list_drives() if drive.slot not in before]
        if len(new) == 1:
            break
        time.sleep(0.2)
    if len(new) != 1:
        raise CDROMError(
            "CDEmu add-device completed, but the new reader could not be "
            "identified. Reopen the manager before adding another reader."
        )
    return new[0]


def remove_drive(slot):
    """Remove the last CDEmu reader, but only while it holds no image.

    "cdemu remove-device" always removes the LAST reader, so any other
    slot is refused. Readers 0 and 1 are protected and never removed.
    Readers with a loaded or mounted image must be ejected first.
    """
    if not is_removable_slot(slot):
        raise CDROMError(
            "Readers 0 and 1 are CDEmu's default readers and cannot be "
            "removed."
        )
    drives = list_drives()
    if not drives or drives[-1].slot != slot:
        raise CDROMError(
            "CDEmu can only remove its last reader (reader {}).".format(
                drives[-1].slot if drives else "-"
            )
        )
    drive = drives[-1]
    if drive.loaded or drive.mountpoint is not None:
        raise CDROMError(
            "Reader {} still holds a disc image. Eject the disc before "
            "removing the reader.".format(slot)
        )
    _command(["cdemu", "remove-device"])
    return drive
