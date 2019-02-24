import sys
import os
import logging
import subprocess

__all__ = ("run_command",)

logger = logging.getLogger("protontricks")


def run_command(
        steam_path, winetricks_path, proton_app, steam_app, command,
        **kwargs):
    """Run an arbitrary command with the correct environment variables
    for the given Proton app

    The environment variables are set for the duration of the call
    and restored afterwards
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

    os.environ["PATH"] = os.path.join(
        proton_app.install_path, "dist", "bin"
    ) + os.pathsep + os.environ["PATH"]

    # Unset WINEARCH, which might be set for another Wine installation
    os.environ.pop("WINEARCH", "")

    logger.info("Attempting to run sp.call::{command}".format(command=command))

    try:
        subprocess.call(command, **kwargs)
    finally:
        # Restore original env vars
        os.environ.clear()
        os.environ.update(environ_copy)
