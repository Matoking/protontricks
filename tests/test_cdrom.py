"""Unit tests for per-prefix CD/DVD drive mappings."""
import os
from pathlib import Path

import pytest

from protontricks.cdemu_backend import OpticalDrive
from protontricks.cdrom import (
    CDROMError, find_disc_letters, set_cdrom_mapping
)


def CDEmuDrive(slot, device, mountpoint, image="/disc.iso"):
    """Build a mounted reader as returned by cdemu_backend.list_drives()."""
    return OpticalDrive(slot, device, image, mountpoint)


def has_backup(prefix, letter="d"):
    return (prefix / ".protontricks-cdrom" / (letter + ".json")).exists()


@pytest.fixture
def prefix(tmp_path):
    path = tmp_path / "compatdata" / "100" / "pfx"
    (path / "dosdevices").mkdir(parents=True)
    return path


def test_switch_mapping_and_keep_original_backup(prefix, tmp_path):
    dos = prefix / "dosdevices"
    (dos / "d:").symlink_to("/old/cdrom")
    (dos / "d::").symlink_to("/dev/sr0")
    disc2 = tmp_path / "disc2"
    disc3 = tmp_path / "disc3"
    disc2.mkdir()
    disc3.mkdir()

    set_cdrom_mapping(
        prefix, CDEmuDrive(1, Path("/dev/sr1"), disc2), "D"
    )
    assert os.readlink(dos / "d:") == str(disc2)
    assert os.readlink(dos / "d::") == "/dev/sr1"
    assert has_backup(prefix)

    set_cdrom_mapping(
        prefix, CDEmuDrive(2, Path("/dev/sr2"), disc3), "D"
    )
    assert os.readlink(dos / "d:") == str(disc3)
    assert os.readlink(dos / "d::") == "/dev/sr2"
    # The very first (original) links stay in the backup.
    backup = (prefix / ".protontricks-cdrom" / "d.json").read_text()
    assert "/old/cdrom" in backup and "/dev/sr0" in backup


def test_mapping_requires_a_mounted_disc(prefix):
    with pytest.raises(CDROMError, match="Mount the disc"):
        set_cdrom_mapping(
            prefix, OpticalDrive(0, Path("/dev/sr0"), "/disc.iso")
        )


def test_refuse_to_overwrite_regular_file(prefix, tmp_path):
    (prefix / "dosdevices" / "d:").write_text("keep")
    mounted = tmp_path / "disc"
    mounted.mkdir()
    with pytest.raises(CDROMError, match="not a symlink"):
        set_cdrom_mapping(
            prefix, CDEmuDrive(0, Path("/dev/sr0"), mounted)
        )
    assert (prefix / "dosdevices" / "d:").read_text() == "keep"


def test_relink_after_wine_changes_or_removes_links(prefix, tmp_path):
    """Wine's mount manager drops d: when a disc is unmounted."""
    disc1 = tmp_path / "disc1"
    disc2 = tmp_path / "disc2"
    disc1.mkdir()
    disc2.mkdir()
    dos = prefix / "dosdevices"
    (dos / "d:").symlink_to(str(disc1))
    (dos / "d::").symlink_to("/dev/sr0")
    set_cdrom_mapping(prefix, CDEmuDrive(1, Path("/dev/sr1"), disc2))
    (dos / "d:").unlink()

    set_cdrom_mapping(prefix, CDEmuDrive(1, Path("/dev/sr1"), disc2))
    assert os.readlink(dos / "d:") == str(disc2)
    assert os.readlink(dos / "d::") == "/dev/sr1"
    # The backup still holds the links found before the first mapping.
    backup = (prefix / ".protontricks-cdrom" / "d.json").read_text()
    assert str(disc1) in backup and "/dev/sr0" in backup


def test_mapping_is_per_prefix(prefix, tmp_path):
    other = tmp_path / "compatdata" / "200" / "pfx"
    (other / "dosdevices").mkdir(parents=True)
    mounted = tmp_path / "disc"
    mounted.mkdir()
    set_cdrom_mapping(prefix, CDEmuDrive(0, Path("/dev/sr0"), mounted))
    assert not (other / "dosdevices" / "d:").is_symlink()


def test_invalid_drive_letter(prefix, tmp_path):
    mounted = tmp_path / "disc"
    mounted.mkdir()
    with pytest.raises(CDROMError, match="drive letter"):
        set_cdrom_mapping(
            prefix, CDEmuDrive(0, Path("/dev/sr0"), mounted), "C"
        )


def test_mapping_rollback_if_second_symlink_fails(
        prefix, monkeypatch, tmp_path):
    from protontricks import cdrom

    dosdevices = prefix / "dosdevices"
    (dosdevices / "d:").symlink_to("/old/mount")
    (dosdevices / "d::").symlink_to("/dev/sr0")
    mounted = tmp_path / "disc2"
    mounted.mkdir()

    original_symlink = cdrom.os.symlink

    def fail_on_raw_device(target, destination, *args, **kwargs):
        if str(destination).endswith("d::.protontricks-new"):
            raise OSError("simulated write failure")
        return original_symlink(target, destination, *args, **kwargs)

    monkeypatch.setattr(cdrom.os, "symlink", fail_on_raw_device)
    with pytest.raises(OSError, match="simulated write failure"):
        set_cdrom_mapping(
            prefix, CDEmuDrive(1, Path("/dev/sr1"), mounted)
        )
    assert os.readlink(dosdevices / "d:") == "/old/mount"
    assert os.readlink(dosdevices / "d::") == "/dev/sr0"
    assert not has_backup(prefix)


def test_stale_temp_backup_reports_path_and_restores_links(
        prefix, tmp_path):
    temporary = prefix / ".protontricks-cdrom" / "d.tmp"
    temporary.parent.mkdir()
    temporary.write_text("stale")
    mounted = tmp_path / "disc"
    mounted.mkdir()
    with pytest.raises(CDROMError) as excinfo:
        set_cdrom_mapping(
            prefix, CDEmuDrive(1, Path("/dev/sr1"), mounted)
        )
    assert str(temporary) in str(excinfo.value)
    assert not (prefix / "dosdevices" / "d:").is_symlink()
    assert not (prefix / "dosdevices" / "d::").is_symlink()
    assert temporary.read_text() == "stale"


def test_find_disc_letters_assigned_by_wine(prefix, tmp_path):
    disc1 = tmp_path / "disc1"
    disc1.mkdir()
    dos = prefix / "dosdevices"
    (dos / "c:").symlink_to("../drive_c")
    (dos / "k:").symlink_to(str(disc1))
    (dos / "d::").symlink_to("/dev/sr1")
    (dos / "z:").symlink_to("/")

    assert find_disc_letters(prefix, [disc1]) == {"K": str(disc1)}
    assert find_disc_letters(prefix, []) == {}
    assert find_disc_letters(tmp_path / "missing", [disc1]) == {}
