import logging
import subprocess
import sys

__all__ = ("select_steam_app_with_gui",)

logger = logging.getLogger("protontricks")


def select_steam_app_with_gui(steam_apps):
    """
    Prompt the user to select a Proton-enabled Steam app from
    a dropdown list.

    Return the selected SteamApp
    """
    combo_values = "|".join([
        '{}: {}'.format(app.name, app.appid) for app in steam_apps
        if app.prefix_path_exists and app.appid
    ])

    try:
        result = subprocess.run([
            'zenity', '--forms', '--text=Steam Game Library',
            '--title=Choose Game', '--add-combo', 'Pick a library game',
            '--combo-values', combo_values
        ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        choice = result.stdout
    except subprocess.CalledProcessError as exc:
        # TODO: Remove this hack once the bug has been fixed upstream
        # Newer versions of zenity have a bug that causes long dropdown choice
        # lists to crash the command with a specific message.
        # Since stdout still prints the correct value, we can safely ignore
        # this error.
        #
        # Related issues:
        # https://github.com/Matoking/protontricks/issues/20
        # https://gitlab.gnome.org/GNOME/zenity/issues/7
        is_zenity_bug = (
            exc.returncode == -6 and
            exc.stderr == b'free(): double free detected in tcache 2\n'
        )

        if is_zenity_bug:
            logger.info("Ignoring zenity crash bug")
            choice = exc.stdout
        else:
            raise RuntimeError("Zenity returned an error")
    except OSError:
        raise RuntimeError("Zenity was not found")

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
