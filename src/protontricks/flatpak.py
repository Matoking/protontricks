import configparser
import logging
import os
import re
import subprocess
from pathlib import Path

__all__ = (
    "FLATPAK_BWRAP_COMPATIBLE_VERSION", "FLATPAK_INFO_PATH",
    "is_flatpak_sandbox", "get_running_flatpak_version",
    "get_inaccessible_paths"
)

logger = logging.getLogger("protontricks")

# Flatpak minimum version required to enable bwrap. In other words, the first
# Flatpak version with the necessary support for sub-sandboxes.
FLATPAK_BWRAP_COMPATIBLE_VERSION = (1, 12, 1)

FLATPAK_INFO_PATH = "/.flatpak-info"


def is_flatpak_sandbox():
    """
    Check if we're running inside a Flatpak sandbox
    """
    return bool(get_running_flatpak_version())


def _get_flatpak_config():
    config = configparser.ConfigParser()

    try:
        config.read_string(Path(FLATPAK_INFO_PATH).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None

    return config


_XDG_PERMISSIONS = {
    "xdg-desktop": "DESKTOP",
    "xdg-documents": "DOCUMENTS",
    "xdg-download": "DOWNLOAD",
    "xdg-music": "MUSIC",
    "xdg-pictures": "PICTURES",
    "xdg-public-share": "PUBLICSHARE",
    "xdg-videos": "VIDEOS",
    "xdg-templates": "TEMPLATES",
}


def _get_xdg_user_dir(permission):
    """
    Get the XDG user directory corresponding to the given "xdg-" prefixed
    Flatpak permission and retrieve its absolute path using the `xdg-user-dir`
    command.
    """
    if permission in _XDG_PERMISSIONS:
        # This will only be called in a Flatpak environment, and we can assume
        # 'xdg-user-dir' always exists in that environment.
        path = subprocess.check_output(
            ["xdg-user-dir", _XDG_PERMISSIONS[permission]]
        )
        path = path.strip()
        path = os.fsdecode(path)
        logger.debug("XDG path for %s is %s", permission, path)
        return Path(path)

    return None


def get_running_flatpak_version():
    """
    Get the running Flatpak version if running inside a Flatpak sandbox,
    or None if Flatpak sandbox isn't active
    """
    config = _get_flatpak_config()

    if config is None:
        return None

    # If this fails it's because the Flatpak version is older than 0.6.10.
    # Since Steam Flatpak requires at least 1.0.0, we can fail here instead
    # of continuing on. It's also extremely unlikely, since even older distros
    # like CentOS 7 ship Flatpak releases newer than 1.0.0.
    version = config["Instance"]["flatpak-version"]

    # Remove non-numeric characters just in case (eg. if a suffix like '-pre'
    # is used).
    version = "".join([ch for ch in version if ch in ("0123456789.")])

    # Convert version number into a tuple
    version = tuple([int(part) for part in version.split(".")])
    return version


def get_inaccessible_paths(paths):
    """
    Check which given paths are inaccessible under Protontricks.

    Inaccessible paths are returned as a list. This has no effect in
    non-Flatpak environments, where an empty list is always returned.
    """
    def _path_is_relative_to(a, b):
        try:
            a.relative_to(b)
            return True
        except ValueError:
            return False

    def _map_path(path):
        if path == "":
            return None

        if path.startswith("xdg-data/"):
            return (
                Path("~/.local/share").expanduser()
                / path.split("xdg-data/")[1]
            )

        if path.startswith("xdg-"):
            path_ = _get_xdg_user_dir(path)

            if path_:
                return path_

        if path == "home":
            return Path.home()

        if path.startswith("/"):
            return Path(path).resolve()

        if path.startswith("~"):
            return Path(path).expanduser()

        logger.warning(
            "Unknown Flatpak file system permission '%s', ignoring.",
            path
        )
        return None

    if not is_flatpak_sandbox():
        return []

    config = _get_flatpak_config()

    try:
        mounted_paths = \
            re.split(r'(?<!\\);', config["Context"]["filesystems"])
    except KeyError:
        logger.warning("Could not find mounted Flatpak filesystems")
        return []

    if "host" in mounted_paths:
        # If 'host' is enabled, Flatpak has full file system access,
        # aside from some Flatpak specific paths that are not relevant
        # for Protontricks or Steam usage.
        return []

    paths = [Path(path).resolve() for path in paths]

    # Resolve the mounted filesystems
    mounted_paths = [_map_path(path) for path in mounted_paths]
    mounted_paths = list(filter(bool, mounted_paths))

    return [
        Path(path) for path in paths
        if not any(
            True for mounted_path in mounted_paths
            if _path_is_relative_to(path, mounted_path)
        )
    ]
