import logging
import os
import shutil
import subprocess
import sys

from .util import run_command

__all__ = ("get_winetricks_path",)

logger = logging.getLogger("protontricks")


def get_winetricks_path():
    """
    Return to the path to 'winetricks' executable or return None if not found
    """
    if os.environ.get('WINETRICKS'):
        logger.info(
            "Winetricks path is set to %s", os.environ.get('WINETRICKS')
        )
        if not os.path.exists(os.environ.get('WINETRICKS')):
            logger.error(
                "The WINETRICKS path is invalid, please make sure "
                "Winetricks is installed in that path!"
            )
            return None

        return os.environ.get("WINETRICKS")

    logger.info(
        "WINETRICKS environment variable is not available. "
        "Searching from $PATH.")
    winetricks_path = shutil.which("winetricks")

    if winetricks_path:
        return winetricks_path

    logger.error(
        "'winetricks' executable could not be found automatically."
    )
    return None
