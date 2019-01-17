import logging
import os
import shutil
import subprocess
import sys

__all__ = (
    "get_winetricks_path", "run_winetricks_command"
)

logger = logging.getLogger("protontricks")


def get_winetricks_path():
    """
    Return to the path to 'winetricks' executable or return None if not found
    """
    if os.environ.get('WINETRICKS') is None:
        logger.info(
            "WINETRICKS environment variable is not available. "
            "Searching from $PATH.")
        winetricks_path = shutil.which("winetricks")
        if winetricks_path:
            return winetricks_path
        else:
            return None
            raise RuntimeError(
                "Winetricks isn't installed, please install "
                "winetricks in order to use this script!"
            )
    else:
        logger.info(
            "[INFO] Winetricks path is set to {}".format(
                os.environ.get('WINETRICKS')
            )
        )
        if not os.path.exists(os.environ.get('WINETRICKS')):
            raise RuntimeError(
                "The WINETRICKS path is invalid, please make sure "
                "Winetricks is installed in that path!"
            )

        return os.environ.get("WINETRICKS")


def run_winetricks_command(
        steam_path, winetricks_path, proton_app, steam_app, command):
    """Run a Winetricks command inside the Wine prefix for the selected
    Proton-enabled Steam app.

    The environment variables are changed for the duration of the
    call and restored afterwards.
    """
    # Make a copy of the environment variables to restore later
    environ_copy = os.environ.copy()

    if not os.environ.get("WINE"):
        logger.info(
            "WINE environment variable is not available. "
            "Setting WINE environment variable to Proton bundled version"
        )
        os.environ["WINE"] = os.path.join(
            proton_app.install_path, "dist", "bin", "wine")

    if not os.environ.get("WINESERVER"):
        logger.info(
            "WINESERVER environment variable is not available. "
            "Setting WINESERVER environment variable to Proton bundled version"
        )
        os.environ["WINESERVER"] = os.path.join(
            proton_app.install_path, "dist", "bin", "wineserver"
        )

    os.environ["WINETRICKS"] = winetricks_path
    os.environ["WINEPREFIX"] = steam_app.prefix_path

    # Unset WINEARCH, which might be set for another Wine installation
    os.environ.pop("WINEARCH", "")

    try:
        subprocess.call([winetricks_path] + command)
    finally:
        # Restore original env vars
        os.environ.clear()
        os.environ.update(environ_copy)
