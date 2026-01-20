import argparse
import logging
import shlex
import sys
from pathlib import Path

from .command import BaseCommand
from .main import main as cli_main
from .util import CustomArgumentParser, cli_error_handler, enable_logging

logger = logging.getLogger("protontricks")


def cli(args=None):
    main(args)


@cli_error_handler
def main(args=None):
    """
    'protontricks-launch' script entrypoint
    """
    if args is None:
        args = sys.argv[1:]

    parser = CustomArgumentParser(
        description=(
            "Utility for launching Windows executables using Protontricks\n"
            "\n"
            "Usage:\n"
            "\n"
            "Launch EXECUTABLE and pick the Steam app using a dialog.\n"
            "$ protontricks-launch EXECUTABLE [ARGS]\n"
            "\n"
            "Launch EXECUTABLE for Steam app APPID\n"
            "$ protontricks-launch --appid APPID EXECUTABLE [ARGS]\n"
            "\n"
            "Environment variables:\n"
            "\n"
            "PROTON_VERSION: name of the preferred Proton installation\n"
            "STEAM_DIR: path to custom Steam installation\n"
            "WINETRICKS: path to a custom 'winetricks' executable\n"
            "WINE: path to a custom 'wine' executable\n"
            "WINESERVER: path to a custom 'wineserver' executable\n"
            "STEAM_RUNTIME: 1 = enable Steam Runtime, 0 = disable Steam "
            "Runtime, valid path = custom Steam Runtime path, "
            "empty = enable automatically (default)"
        ),
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "--appid", type=int, nargs="?", default=None
    )
    parser.add_argument("executable", type=str)
    parser.add_argument("exec_args", nargs=argparse.REMAINDER)

    args = parser.parse_args(args)

    # 'cli_error_handler' relies on this to know whether to use error dialog or
    # not
    main.no_term = args.no_term

    enable_logging(args.verbose, record_to_file=args.no_term)

    RunExecutableCommand(args).execute()


class RunExecutableCommand(BaseCommand):
    steam_app_required = True

    def run(self):
        # Build the command to pass to the main Protontricks CLI entrypoint
        cli_args = []

        executable_path = Path(self.cli_args.executable).resolve(strict=True)

        # Ensure each individual argument passed to the EXE is escaped
        exec_args = [shlex.quote(arg) for arg in self.cli_args.exec_args]

        if self.cli_args.verbose:
            cli_args += ["-" + ("v" * self.cli_args.verbose)]

        if self.cli_args.no_runtime:
            cli_args += ["--no-runtime"]

        if self.cli_args.no_bwrap:
            cli_args += ["--no-bwrap"]

        if self.cli_args.background_wineserver is True:
            cli_args += ["--background-wineserver"]
        elif self.cli_args.background_wineserver is False:
            cli_args += ["--no-background-wineserver"]

        if self.cli_args.no_term:
            cli_args += ["--no-term"]

        inner_args = " ".join(
            ["wine", shlex.quote(str(executable_path))]
            + exec_args
        )

        if self.cli_args.cwd_app:
            cli_args += ["--cwd-app"]

        cli_args += [
            "-c", inner_args, str(self.steam_app.appid)
        ]

        # Launch the main Protontricks CLI entrypoint
        logger.info(
            "Calling `protontricks` with the command: %s", cli_args
        )

        cli_main(
            cli_args, steam_path=self.steam_path, steam_root=self.steam_root
        )


if __name__ == "__main__":
    main()
