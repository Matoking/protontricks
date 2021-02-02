import logging
import sys
from subprocess import run, PIPE, CalledProcessError

__all__ = ("select_steam_app_with_gui",)

logger = logging.getLogger("protontricks")


class LocaleError(Exception):
    pass


def select_steam_app_with_gui(steam_apps):
    """
    Prompt the user to select a Proton-enabled Steam app from
    a dropdown list.

    Return the selected SteamApp
    """
    def run_zenity(args, strip_nonascii=False):
        """
        Run Zenity with the given args.

        If 'strip_nonascii' is True, strip non-ASCII characters to workaround
        environments that can't handle all characters
        """
        if strip_nonascii:
            # Convert to bytes and back to strings while stripping
            # non-ASCII characters
            args = [
                arg.encode("ascii", "ignore").decode("ascii") for arg in args
            ]

        try:
            return run(args, check=True, stdout=PIPE, stderr=PIPE)
        except CalledProcessError as exc:
            if exc.returncode == 255:
                # User locale incapable of handling all characters in the
                # command
                raise LocaleError()

            raise

    combo_values = "|".join([
        '{}: {}'.format(app.name, app.appid) for app in steam_apps
        if app.prefix_path_exists and app.appid
    ])
    args = [
        "zenity", "--forms", "--text=Steam Game Library",
        "--title=Choose Game", "--add-combo", "Pick a library game",
        "--combo-values", combo_values
    ]

    try:
        try:
            result = run_zenity(args)
        except LocaleError:
            # User has weird locale settings. Log a warning and
            # run the command while stripping non-ASCII characters.
            logger.warning(
                "Your system locale is incapable of displaying all "
                "characters. Some app names may not show up correctly. "
                "Please use an UTF-8 locale to avoid this warning."
            )
            result = run_zenity(args, strip_nonascii=True)

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
        elif exc.returncode == 1:
            # No game was selected
            choice = b""
        else:
            raise RuntimeError("Zenity returned an error")

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
