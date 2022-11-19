import argparse
from pathlib import Path
from subprocess import run

import pkg_resources

from .util import CustomArgumentParser


def install_desktop_entries():
    """
    Install the desktop entry files for Protontricks.

    This should only be necessary when using an installation method that does
    not support .desktop files (eg. pip/pipx)

    :returns: Directory containing the installed .desktop files
    """
    applications_dir = Path.home() / ".local" / "share" / "applications"
    applications_dir.mkdir(parents=True, exist_ok=True)

    run([
        "desktop-file-install", "--dir", str(applications_dir),
        pkg_resources.resource_filename(
            "protontricks", "data/share/applications/protontricks.desktop"
        ),
        pkg_resources.resource_filename(
            "protontricks",
            "data/share/applications/protontricks-launch.desktop"
        )
    ], check=True)

    return applications_dir


def cli(args=None):
    main(args)


def main(args=None):
    """
    'protontricks-desktop-install' script entrypoint
    """
    parser = CustomArgumentParser(
        description=(
            "Install Protontricks application shortcuts for the local user\n"
        ),
        formatter_class=argparse.RawTextHelpFormatter
    )

    # This doesn't really do much except accept `--help`
    parser.parse_args(args)

    print("Installing .desktop files for the local user...")
    install_dir = install_desktop_entries()
    print(f"\nDone. Files have been installed under {install_dir}")
    print("The Protontricks shortcut and desktop integration should now work.")


if __name__ == "__main__":
    main()
