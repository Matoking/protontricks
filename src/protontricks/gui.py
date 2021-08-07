import functools
import itertools
import logging
import os
import shutil
import sys
from pathlib import Path
from subprocess import PIPE, CalledProcessError, run

import pkg_resources

__all__ = ("LocaleError", "select_steam_app_with_gui")

logger = logging.getLogger("protontricks")


class LocaleError(Exception):
    pass


@functools.lru_cache(maxsize=1)
def get_gui_provider():
    """
    Get the GUI provider used to display dialogs.
    Returns either 'yad' or 'zenity', preferring 'yad' if both exist.
    """
    try:
        candidates = ["yad", "zenity"]
        # Allow overriding the GUI provider using an envvar
        if os.environ.get("PROTONTRICKS_GUI", "").lower() in candidates:
            candidates.insert(0, os.environ["PROTONTRICKS_GUI"].lower())

        cmd = next(cmd for cmd in candidates if shutil.which(cmd))
        logger.info("Using '%s' as GUI provider", cmd)

        return cmd
    except StopIteration as exc:
        raise FileNotFoundError(
            "'yad' or 'zenity' was not found. Either executable is required "
            "for Protontricks GUI."
        ) from exc


def _get_appid2icon(steam_apps, steam_path):
    """
    Get icons for Steam apps to show in the app selection dialog.
    Return a {appid: icon_path} dict.
    """
    placeholder_path = Path(
        pkg_resources.resource_filename(
            "protontricks", "data/icon_placeholder.png"
        )
    )

    icon_dir = steam_path / "appcache" / "librarycache"
    existing_names = [path.name for path in icon_dir.glob("*")]

    appid2icon = {}

    for app in steam_apps:
        # Use library icon for Steam apps, fallback to placeholder icon
        # for non-Steam shortcuts and missing icons
        appid2icon[app.appid] = (
            icon_dir / "{}_icon.jpg".format(app.appid)
            if "{}_icon.jpg".format(app.appid) in existing_names
            else placeholder_path
        )

    return appid2icon


def select_steam_app_with_gui(steam_apps, steam_path, title=None):
    """
    Prompt the user to select a Proton-enabled Steam app from
    a dropdown list.

    Return the selected SteamApp
    """
    def _get_yad_args():
        return [
            "yad", "--list", "--no-headers", "--center",
            "--window-icon", "wine",
            # Disabling markup means we won't have to escape special characters
            "--no-markup",
            "--search-column", "2",
            "--print-column", "2",
            "--width", "600", "--height", "400",
            "--text", title,
            "--title", "Protontricks",
            "--column", "Icon:IMG",
            "--column", "Steam app"
        ]

    def _get_zenity_args():
        return [
            "zenity", "--list", "--hide-header",
            "--width", "600",
            "--height", "400",
            "--text", title,
            "--title", "Protontricks",
            "--column", "Steam app"
        ]

    def run_gui(args, input_=None, strip_nonascii=False):
        """
        Run YAD/Zenity with the given args.

        If 'strip_nonascii' is True, strip non-ASCII characters to workaround
        environments that can't handle all characters
        """
        if strip_nonascii:
            # Convert to bytes and back to strings while stripping
            # non-ASCII characters
            args = [
                arg.encode("ascii", "ignore").decode("ascii") for arg in args
            ]
            if input_:
                input_ = input_.encode("ascii", "ignore").decode("ascii")

        if input_:
            input_ = input_.encode("utf-8")

        try:
            return run(
                args, input=input_, check=True, stdout=PIPE, stderr=PIPE,
            )
        except CalledProcessError as exc:
            if exc.returncode == 255:
                # User locale incapable of handling all characters in the
                # command
                raise LocaleError()

            raise

    if not title:
        title = "Select Steam app"

    gui_provider = get_gui_provider()

    if gui_provider == "yad":
        args = _get_yad_args()

        # YAD implementation has icons for app selection
        appid2icon = _get_appid2icon(steam_apps, steam_path=steam_path)

        cmd_input = [
            [
                str(appid2icon[app.appid]),
                "{}: {}".format(app.name, app.appid)
            ]
            for app in steam_apps if app.prefix_path_exists and app.appid
        ]
        # Flatten the list
        cmd_input = list(itertools.chain.from_iterable(cmd_input))
    else:
        args = _get_zenity_args()
        cmd_input = [
            '{}: {}'.format(app.name, app.appid) for app in steam_apps
            if app.prefix_path_exists and app.appid
        ]

    cmd_input = "\n".join(cmd_input)

    try:
        try:
            result = run_gui(args, input_=cmd_input)
        except LocaleError:
            # User has weird locale settings. Log a warning and
            # run the command while stripping non-ASCII characters.
            logger.warning(
                "Your system locale is incapable of displaying all "
                "characters. Some app names may not show up correctly. "
                "Please use an UTF-8 locale to avoid this warning."
            )
            result = run_gui(args, strip_nonascii=True)

        choice = result.stdout
    except CalledProcessError as exc:
        # TODO: Remove this hack once the bug has been fixed upstream
        # Newer versions of zenity have a bug that causes long dropdown choice
        # lists to crash the command with a specific message.
        # Since stdout still prints the correct value, we can safely ignore
        # this error.
        #
        # The error is usually the message
        # 'free(): double free detected in tcache 2', but it can vary
        # depending on the environment. Instead, check if the returncode
        # is -6
        #
        # Related issues:
        # https://github.com/Matoking/protontricks/issues/20
        # https://gitlab.gnome.org/GNOME/zenity/issues/7
        if exc.returncode == -6:
            logger.info("Ignoring zenity crash bug")
            choice = exc.stdout
        elif exc.returncode in (1, 252):
            # YAD returns 252 when dialog is closed by pressing Esc
            # No game was selected
            choice = b""
        else:
            raise RuntimeError("{} returned an error".format(gui_provider))

    if choice in (b"", b" \n"):
        print("No game was selected. Quitting...")
        sys.exit(0)

    appid = str(choice).rsplit(':')[-1]
    appid = ''.join(x for x in appid if x.isdigit())
    appid = int(appid)

    steam_app = next(
        app for app in steam_apps
        if app.appid == appid)
    return steam_app
