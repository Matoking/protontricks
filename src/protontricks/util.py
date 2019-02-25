import sys
import os
import logging
import subprocess

__all__ = ("run_command",)

logger = logging.getLogger("protontricks")


def run_command(
        steam_path, winetricks_path, proton_app, steam_app, command,
        steam_runtime_path=None,
        **kwargs):
    """Run an arbitrary command with the correct environment variables
    for the given Proton app

    The environment variables are set for the duration of the call
    and restored afterwards

    If 'steam_runtime_path' is provided, run the command using Steam Runtime
    """
    def get_runtime_library_path(steam_runtime_path, proton_app):
        """
        Get LD_LIBRARY_PATH value to run a command using Steam Runtime
        """
        steam_runtime_paths = subprocess.check_output([
            os.path.join(steam_runtime_path, "run.sh"),
            "--print-steam-runtime-library-paths"
        ])
        steam_runtime_paths = str(steam_runtime_paths, "utf-8")

        # Add Proton installation directory first into LD_LIBRARY_PATH
        # so that libwine.so.1 is picked up correctly (see issue #3)
        return "".join([
            os.path.join(proton_app.install_path, "dist", "lib"), os.pathsep,
            os.path.join(proton_app.install_path, "dist", "lib64"), os.pathsep,
            steam_runtime_paths
        ])

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

    if steam_runtime_path:
        # If we're running this command inside Steam Runtime,
        # set LD_LIBRARY_PATH accordingly
        os.environ["LD_LIBRARY_PATH"] = get_runtime_library_path(
            steam_runtime_path=steam_runtime_path, proton_app=proton_app)

    logger.info("Attempting to run sp.call::{command}".format(command=command))

    try:
        subprocess.call(command, **kwargs)
    finally:
        # Restore original env vars
        os.environ.clear()
        os.environ.update(environ_copy)
