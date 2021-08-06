import argparse
import atexit
import functools
import logging
import os
import sys
import tempfile
import traceback
from pathlib import Path
from subprocess import run

from ..gui import get_gui_provider


def _get_log_file_path():
    """
    Get the log file path to use for this Protontricks process.
    """
    temp_dir = tempfile.gettempdir()

    return Path(temp_dir) / "protontricks{}.log".format(os.getpid())


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


def enable_logging(info=False, record_to_file=True):
    """
    Enables logging.
    If info is True, print INFO messages in addition to WARNING and ERROR
    messages

    :param bool record_to_file: Whether to log the generated log messages
                                to a temporary file.
                                This is used for the error dialog containing
                                log records.
    """
    level = logging.INFO if info else logging.WARNING

    # Logs printed to stderr will follow the log level
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(level)
    stream_handler.setFormatter(
        logging.Formatter("%(name)s (%(levelname)s): %(message)s")
    )

    logger = logging.getLogger("protontricks")
    logger.setLevel(logging.INFO)
    logger.addHandler(stream_handler)

    if not record_to_file:
        return

    # Record log files to temporary file. This means log messages can be
    # printed at the end of the session in an error dialog.
    # *All* log messages are written into this file whether `--verbose`
    # is enabled or not.
    log_file_path = _get_log_file_path()
    try:
        log_file_path.unlink()
    except FileNotFoundError:
        pass

    file_handler = logging.FileHandler(str(_get_log_file_path()))
    file_handler.setLevel(logging.INFO)
    logger.addHandler(file_handler)

    # Ensure the log file is removed before the process exits
    atexit.register(_delete_log_file)


def exit_with_error(error, desktop=False):
    """
    Exit with an error, either by printing the error to stderr or displaying
    an error dialog.

    :param bool desktop: If enabled, display an error dialog containing
                         the error itself and additional log messages.
    """
    def _get_yad_args():
        return [
            "yad", "--text-info", "--window-icon", "error",
            "--title", "Protontricks", "--width", "600", "--height", "600",
            "--button=OK:1", "--wrap", "--margins", "2", "--center"
        ]

    def _get_zenity_args():
        return [
            "zenity", "--text-info", "--window-icon", "error",
            "--title", "Protontricks", "--width", "600", "--height", "600"
        ]

    if not desktop:
        print(error)
        sys.exit(-1)

    try:
        log_messages = _get_log_file_path().read_text()
    except FileNotFoundError:
        log_messages = "!! LOG FILE NOT FOUND !!"

    # Display an error dialog containing the message
    message = "".join([
        "Protontricks was closed due to the following error:\n\n",
        "{}\n\n".format(error),
        "=============\n\n",
        "Please include this entire error message when making a bug report.\n",
        "Log messages:\n\n",
        "{}".format(log_messages)
    ])

    if get_gui_provider() == "yad":
        args = _get_yad_args()
    else:
        args = _get_zenity_args()

    run(args, input=message.encode("utf-8"), check=False)
    sys.exit(-1)


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
