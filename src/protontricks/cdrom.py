"""Map a mounted CD/DVD to a Windows drive letter in one Proton prefix.

Only the prefix's dosdevices links (and a backup of the original links)
are changed here; CDEmu device operations live in cdemu_backend.
"""
import json
import os
import re
from pathlib import Path


class CDROMError(Exception):
    """An expected CD-ROM discovery or mapping failure."""


def _paths(prefix, letter):
    if not re.fullmatch(r"[D-Yd-y]", letter):
        raise CDROMError("Choose a drive letter from D: through Y:.")
    prefix = Path(prefix)
    dosdevices = prefix / "dosdevices"
    if not dosdevices.is_dir() or dosdevices.is_symlink():
        raise CDROMError(
            "The selected Proton prefix has no valid dosdevices directory."
        )
    letter = letter.lower()
    links = (dosdevices / (letter + ":"), dosdevices / (letter + "::"))
    state = prefix / ".protontricks-cdrom" / (letter + ".json")
    return links, state


def _targets(links):
    targets = []
    for link in links:
        if link.is_symlink():
            targets.append(os.readlink(link))
        elif os.path.lexists(link):
            raise CDROMError(
                "{} exists but is not a symlink; refusing to overwrite "
                "it.".format(link)
            )
        else:
            targets.append(None)
    return targets


def _set_links(links, targets):
    """Replace symlinks without following them. Roll back if a write fails."""
    old = _targets(links)
    try:
        for link, target in zip(links, targets):
            if target is None:
                if link.is_symlink():
                    link.unlink()
                continue
            temp = link.with_name(link.name + ".protontricks-new")
            if os.path.lexists(temp):
                raise CDROMError(
                    "Temporary mapping already exists: {}".format(temp)
                )
            os.symlink(target, temp)
            try:
                os.replace(temp, link)
            finally:
                if temp.is_symlink():
                    temp.unlink()
    except Exception:
        # Restore the previous mappings, including a previously absent link.
        for link, target in zip(links, old):
            if target is None:
                if link.is_symlink():
                    link.unlink()
            else:
                temp = link.with_name(link.name + ".protontricks-rollback")
                if not os.path.lexists(temp):
                    os.symlink(target, temp)
                    os.replace(temp, link)
        raise


def _save_state(path, state):
    if path.parent.is_symlink():
        raise CDROMError("Refusing to use a symlinked backup directory.")
    path.parent.mkdir(mode=0o700, exist_ok=True)
    if path.is_symlink():
        raise CDROMError("Refusing to overwrite a symlinked CD-ROM backup.")
    temp = path.with_suffix(".tmp")
    if os.path.lexists(temp):
        raise CDROMError(
            "A temporary CD-ROM backup already exists: {}".format(temp)
        )
    try:
        with temp.open("x", encoding="utf-8") as file:
            json.dump(state, file)
            file.write("\n")
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def _load_state(path):
    if path.is_symlink() or path.parent.is_symlink():
        raise CDROMError("Refusing to read a symlinked CD-ROM backup.")
    if not path.exists():
        return None
    try:
        with path.open(encoding="utf-8") as file:
            state = json.load(file)
        original, current = state["original"], state["current"]
        if not all(
            isinstance(pair, list) and len(pair) == 2 and
            all(value is None or isinstance(value, str) for value in pair)
            for pair in (original, current)
        ):
            raise ValueError("Invalid mapping state")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise CDROMError("Invalid CD-ROM backup: {}".format(path)) from exc
    return state


def find_disc_letters(prefix, mountpoints):
    """Return the prefix's drive letters that point to a mounted disc.

    Wine assigns a letter (not always D:) to a disc mounted before the
    installer starts, and the installer then looks for the next disc on
    that same letter. Returns ``{letter: mountpoint}`` sorted by letter.
    """
    wanted = {str(Path(mountpoint)) for mountpoint in mountpoints}
    found = {}
    try:
        links = list((Path(prefix) / "dosdevices").iterdir())
    except OSError:
        return found
    for link in links:
        name = link.name.lower()
        if not (len(name) == 2 and name[1] == ":" and "d" <= name[0] <= "y"):
            continue
        if not link.is_symlink():
            continue
        target = os.readlink(link).rstrip("/")
        if target in wanted:
            found[name[0].upper()] = target
    return dict(sorted(found.items()))


def set_cdrom_mapping(prefix, drive, letter="D"):
    """Point a Windows letter and its raw-device link to a mounted disc.

    The original links are backed up once under .protontricks-cdrom in the
    prefix. Existing symlinks are replaced even if they changed since the
    last mapping: Wine's mount manager itself adds and removes these links
    when optical media is mounted or unmounted. Regular files are never
    overwritten.
    """
    links, path = _paths(prefix, letter)
    if drive.mountpoint is None or not Path(drive.mountpoint).is_dir():
        raise CDROMError("Mount the disc before mapping it.")
    previous = _targets(links)
    state = _load_state(path)
    target = [str(drive.mountpoint), str(drive.device)]
    new_state = {
        "original": state["original"] if state else previous,
        "current": target
    }
    if target == previous:
        return
    _set_links(links, target)
    try:
        _save_state(path, new_state)
    except Exception:
        _set_links(links, previous)
        raise
