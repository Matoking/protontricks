import argparse
import logging
import sys

logger = logging.getLogger("protontricks")


def enable_logging(info=False):
    """
    Enables logging.
    If info is True, print INFO messages in addition to WARNING and ERROR
    messages
    """
    level = logging.INFO if info else logging.WARNING
    logging.basicConfig(
        stream=sys.stderr, level=level,
        format="%(name)s (%(levelname)s): %(message)s")


class CustomArgumentParser(argparse.ArgumentParser):
    """
    Custom argument parser that prints the full help message
    when incorrect parameters are provided
    """
    def error(self, message):
        self.print_help(sys.stderr)
        args = {'prog': self.prog, 'message': message}
        self.exit(2, '%(prog)s: error: %(message)s\n' % args)
