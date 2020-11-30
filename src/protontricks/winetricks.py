import logging
import os
import shutil
from pathlib import Path

__all__ = ("get_winetricks_path",)

logger = logging.getLogger("protontricks")


def get_winetricks_path():
    """
    Return to the path to 'winetricks' executable or return None if not found
    """
    if os.environ.get('WINETRICKS'):
        path = Path(os.environ["WINETRICKS"])
        logger.info(
            "Winetricks path is set to %s", str(path)
        )
        if not path.is_file():
            logger.error(
                "The WINETRICKS path is invalid, please make sure "
                "Winetricks is installed in that path!"
            )
            return None

        return path

    logger.info(
        "WINETRICKS environment variable is not available. "
        "Searching from $PATH.")
    winetricks_path = shutil.which("winetricks")

    if winetricks_path:
        return Path(winetricks_path)

    logger.error(
        "'winetricks' executable could not be found automatically."
    )
    return None
