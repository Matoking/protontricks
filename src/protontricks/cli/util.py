import argparse
import atexit
import functools
import logging
import os
import sys
import tempfile
import traceback
import contextlib
from pathlib import Path

from ..gui import show_text_dialog
from ..flatpak import is_flatpak_sandbox
from ..util import is_steam_deck
from .. import __version__


def _get_log_file_path():
    """
    Get the log file path to use for this Protontricks process.
    """
    temp_dir = tempfile.gettempdir()

    pid = os.getpid()
    return Path(temp_dir) / f"protontricks{pid}.log"


def _delete_log_file():
    """
    Delete the log file if one exists.

    This is usually executed before shutdown by registering this function
    using `atexit`
    """
    try:
        _get_log_file_path().unlink()
    except FileNotFoundError:
        pass


def enable_logging(level=0, record_to_file=True):
    """
    Enables logging.

    :param int level: Level of logging. 0 = WARNING, 1 = INFO, 2 = DEBUG.
    :param bool record_to_file: Whether to log the generated log messages
                                to a temporary file.
                                This is used for the error dialog containing
                                log records.
    """
    if level >= 2:
        level = logging.DEBUG
        label = "DEBUG"
    elif level >= 1:
        level = logging.INFO
        label = "INFO"
    else:
        level = logging.WARNING
        label = "WARNING"

    # 'PROTONTRICKS_LOG_LEVEL' env var allows separate Bash scripts
    # to detect when logging is enabled.
    os.environ["PROTONTRICKS_LOG_LEVEL"] = label

    logger = logging.getLogger("protontricks")

    stream_handler_added = any(
        filter(
            lambda hndl: hndl.name == "protontricks-stream", logger.handlers
        )
    )

    if not stream_handler_added:
        # Logs printed to stderr will follow the log level
        stream_handler = logging.StreamHandler()
        stream_handler.name = "protontricks-stream"
        stream_handler.setLevel(level)
        stream_handler.setFormatter(
            logging.Formatter("%(name)s (%(levelname)s): %(message)s")
        )

        logger.setLevel(logging.DEBUG)
        logger.addHandler(stream_handler)

        logger.debug("Stream log handler added")

    if not record_to_file:
        return

    file_handler_added = any(
        filter(lambda hndl: hndl.name == "protontricks-file", logger.handlers)
    )

    if not file_handler_added:
        # Record log files to temporary file. This means log messages can be
        # printed at the end of the session in an error dialog.
        # INFO and WARNING log messages are written into this file whether
        # `--verbose` is enabled or not.
        log_file_path = _get_log_file_path()
        try:
            log_file_path.unlink()
        except FileNotFoundError:
            pass

        file_handler = logging.FileHandler(str(_get_log_file_path()))
        file_handler.name = "protontricks-file"
        file_handler.setLevel(logging.INFO)
        logger.addHandler(file_handler)

        # Ensure the log file is removed before the process exits
        atexit.register(_delete_log_file)

        logger.debug("File log handler added")


def exit_with_error(error, desktop=False):
    """
    Exit with an error, either by printing the error to stderr or displaying
    an error dialog.

    :param bool desktop: If enabled, display an error dialog containing
                         the error itself and additional log messages.
    """
    if not desktop:
        print(error)
        sys.exit(1)

    try:
        log_messages = _get_log_file_path().read_text()
    except FileNotFoundError:
        log_messages = "!! LOG FILE NOT FOUND !!"

    is_flatpak_sandbox_ = None
    with contextlib.suppress(Exception):
        is_flatpak_sandbox_ = is_flatpak_sandbox()

    is_steam_deck_ = None
    with contextlib.suppress(Exception):
        is_steam_deck_ = is_steam_deck()

    # Display an error dialog containing the message
    message = "".join([
        "Protontricks was closed due to the following error:\n\n",
        f"{error}\n\n",
        "=============\n\n",
        "Please include this entire error message when making a bug report.\n",
        "Environment:\n\n",
        f"Protontricks version: {__version__}\n",
        f"Is Flatpak sandbox: {is_flatpak_sandbox_}\n",
        f"Is Steam Deck: {is_steam_deck_}\n\n",
        "Log messages:\n\n",
        f"{log_messages}"
    ])

    show_text_dialog(
        title="Protontricks",
        text=message,
        window_icon=error
    )
    sys.exit(1)


def cli_error_handler(cli_func):
    """
    Decorator for CLI entry points.

    If an unhandled exception is raised and Protontricks was launched from
    desktop, display an error dialog containing the stack trace instead
    of printing to stderr.
    """
    @functools.wraps(cli_func)
    def wrapper(self, *args, **kwargs):
        try:
            wrapper.no_term = False
            return cli_func(self, *args, **kwargs)
        except Exception:  # pylint: disable=broad-except
            if not wrapper.no_term:
                # If we weren't launched from desktop, handle it normally
                raise

            traceback_ = traceback.format_exc()
            exit_with_error(traceback_, desktop=True)

    return wrapper


class CustomArgumentParser(argparse.ArgumentParser):
    """
    Custom argument parser that prints the full help message
    when incorrect parameters are provided
    """
    def error(self, message):
        self.print_help(sys.stderr)
        args = {'prog': self.prog, 'message': message}
        self.exit(2, '%(prog)s: error: %(message)s\n' % args)
