import subprocess
import sys

__all__ = ("select_steam_app_with_gui","select_windows_executable_with_gui",)


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
        choice = subprocess.check_output([
            'zenity', '--forms', '--text=Steam Game Library',
            '--title=Choose Game', '--add-combo', 'Pick a library game',
            '--combo-values', combo_values
        ])
        appid = str(choice).rsplit(':')[-1]
        appid = ''.join(x for x in appid if x.isdigit())
        appid = int(appid)

        steam_app = next(
            app for app in steam_apps
            if app.appid == appid)
        return steam_app
    except subprocess.CalledProcessError:
        raise RuntimeError("Zenity returned an error or cancel was clicked")
    except OSError:
        raise RuntimeError("Zenity was not found")

def select_windows_executable_with_gui():
    """
    Prompt the user to select a windows executable to be run with Proton
    in a SteamApp's environment.
    
    Return the path to the selected executable
    """
    try:
        return subprocess.check_output([
            'zenity', '--file-selection', '--title=Choose Windows Executable',
            '--file-filter=*.exe', '--file-filter=*'
        ])
    except subprocess.CalledProcessError:
        raise RuntimeError("Zenity returned an error or cancel was clicked")
    except OSError:
        raise RuntimeError("Zenity was not found")
