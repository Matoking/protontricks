import functools
import importlib.resources
import itertools
import json
import logging
import os
import shlex
import shutil
import sys
from pathlib import Path
from subprocess import PIPE, CalledProcessError, run

from PIL import Image

from .cdrom import CDROMError, find_disc_letters, set_cdrom_mapping
from .cdemu_backend import (
    DeviceBusyError, add_drive, eject_drive, find_empty_drive,
    is_removable_slot, list_drives, load_image, mount_drive, remove_drive
)
from .config import get_config
from .flatpak import get_inaccessible_paths
from .steam import SNAP_STEAM_DIRS
from .util import get_cache_dir

APP_ICON_SIZE = (32, 32)


__all__ = (
    "LocaleError", "get_gui_provider", "select_steam_app_with_gui",
    "select_steam_installation", "show_text_dialog",
    "prompt_filesystem_access", "select_gui_action", "manage_cdrom_drives_gui"
)

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


def _get_appid2icon(steam_apps):
    """
    Get icons for Steam apps to show in the app selection dialog.
    Return a {appid: icon_path} dict.
    """
    protontricks_icon_dir = get_cache_dir() / "app_icons"
    protontricks_icon_dir.mkdir(exist_ok=True)

    # Write the placeholder from Python package into a more persistent
    # cache directory
    with importlib.resources.path(
            "protontricks.data.data", "icon_placeholder.png") as path:
        placeholder_path = protontricks_icon_dir / "icon_placeholder.png"
        placeholder_path.write_bytes(path.read_bytes())

    appid2icon = {}

    for app in steam_apps:
        # Use library icon for Steam apps, fallback to placeholder icon
        # for non-Steam shortcuts and missing icons
        icon_cache_path = protontricks_icon_dir / f"{app.appid}.jpg"

        # What path to actually use for the app selector icon
        final_icon_path = placeholder_path

        if app.icon_path:
            # Resize icons that have a non-standard size to ensure they can be
            # displayed consistently in the app selector
            try:
                with Image.open(app.icon_path) as img:
                    # Icon exists, so use the current icon instead of the
                    # default placeholder.
                    final_icon_path = app.icon_path

                    resize_icon = img.size != APP_ICON_SIZE

                    # Resize icons that have a non-standard size to ensure they can
                    # be displayed consistently in the app selector
                    if resize_icon:
                        logger.info(
                            "App icon %s has unusual size, resizing",
                            app.icon_path
                        )
                        resized_img = img.resize(APP_ICON_SIZE).convert("RGB")
                        resized_img.save(icon_cache_path)
                        final_icon_path = icon_cache_path
            except FileNotFoundError:
                # Icon does not exist, the placeholder will be used
                pass
            except Exception:
                # Multitude of reasons can cause image parsing or resizing
                # to fail. Instead of trying to catch everything, log the error
                # and move on.
                logger.warning(
                    "Could not resize %s, ignoring",
                    app.icon_path,
                    exc_info=True
                )

        appid2icon[app.appid] = final_icon_path

    return appid2icon


def _run_gui(args, input_=None, strip_nonascii=False):
    """
    Run YAD/Zenity with the given args.

    If 'strip_nonascii' is True, strip non-ASCII characters to workaround
    environments that can't handle all characters
    """
    if isinstance(input_, bytes):
        input_ = input_.decode("utf-8", errors="replace")

    if strip_nonascii:
        # Strip non-ASCII text on systems with incompatible locales.
        args = [
            arg.encode("ascii", "ignore").decode("ascii") for arg in args
        ]
        if input_:
            input_ = input_.encode("ascii", "ignore").decode("ascii")

    if input_ is not None:
        input_ = input_.encode("utf-8")

    try:
        return run(
            args, input=input_, check=True, stdout=PIPE, stderr=PIPE,
        )
    except CalledProcessError as exc:
        if exc.returncode == 255 and not strip_nonascii:
            # User has weird locale settings. Log a warning and
            # rerun the command while stripping non-ASCII characters.
            logger.warning(
                "Your system locale is incapable of displaying all "
                "characters. Some app names may not show up correctly. "
                "Please use an UTF-8 locale to avoid this warning."
            )
            return _run_gui(
                args, input_=input_, strip_nonascii=True
            )

        raise

def show_text_dialog(
        title,
        text,
        window_icon,
        cancel_label=None,
        add_cancel_button=False,
        ok_label=None,
        width=600,
        height=600):
    """
    Show a text dialog to the user

    :returns: True if user clicked OK, False otherwise
    """
    if not ok_label:
        ok_label = "OK"

    if not cancel_label:
        cancel_label = "Cancel"

    def _get_yad_args():
        args = [
            "yad", "--text-info", "--window-icon", window_icon,
            "--title", title, "--width", str(width), "--height", str(height),
            f"--button={ok_label}:0", "--wrap",
            "--margins", "2", "--center"
        ]

        if add_cancel_button:
            args += [f"--button={cancel_label}:1"]

        return args

    def _get_zenity_args():
        args = [
            "zenity", "--text-info", "--window-icon", window_icon,
            "--title", title, "--width", str(width), "--height",
            str(height), "--cancel-label", cancel_label, "--ok-label", ok_label
        ]

        return args

    gui_provider = get_gui_provider()
    if gui_provider == "yad":
        args = _get_yad_args()
    else:
        args = _get_zenity_args()

    process = run(args, input=text.encode("utf-8"), check=False)

    return process.returncode == 0


def select_steam_installation(steam_installations):
    """
    Prompt the user to select a Steam installation if more than one
    installation is available

    Return the selected (steam_path, steam_root) installation, or None
    if the user picked nothing
    """
    def _get_yad_args():
        return [
            "yad", "--list", "--no-headers", "--center",
            "--window-icon", "wine",
            # Disabling markup means we won't have to escape special characters
            "--no-markup",
            "--width", "600", "--height", "400",
            "--text", "Select Steam installation",
            "--title", "Protontricks",
            "--column", "Path"
        ]

    def _get_zenity_args():
        return [
            "zenity", "--list", "--hide-header",
            "--width", "600",
            "--height", "400",
            "--text", "Select Steam installation",
            "--title", "Protontricks",
            "--column", "Path"
        ]

    if len(steam_installations) == 1:
        return steam_installations[0]

    gui_provider = get_gui_provider()

    cmd_input = []

    for i, installation in enumerate(steam_installations):
        steam_path, steam_root = installation

        is_flatpak = (
            str(steam_path).endswith(
                "/com.valvesoftware.Steam/.local/share/Steam"
            )
        )
        is_snap = any(
            str(steam_path).endswith(snap_dir)
            for snap_dir in SNAP_STEAM_DIRS
        )

        if is_flatpak:
            install_type = "Flatpak"
        elif is_snap:
            install_type = "Snap"
        else:
            install_type = "Native"

        cmd_input.append(f"{i+1}: {install_type} - {steam_path}")

    cmd_input = "\n".join(cmd_input)

    if gui_provider == "yad":
        args = _get_yad_args()
    elif gui_provider == "zenity":
        args = _get_zenity_args()

    try:
        result = _run_gui(args, input_=cmd_input)
        choice = result.stdout
    except CalledProcessError as exc:
        if exc.returncode in (1, 252):
            # YAD returns 252 when dialog is closed by pressing Esc
            # No installation was selected
            choice = b""
        else:
            raise RuntimeError(
                f"{gui_provider} returned an error. Stderr: {exc.stderr}"
            )

    if choice in (b"", b" \n"):
        return None, None

    choice = choice.decode("utf-8").split(":")[0]
    choice = int(choice) - 1

    return steam_installations[choice]


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

    if not title:
        title = "Select Steam app"

    gui_provider = get_gui_provider()

    if gui_provider == "yad":
        args = _get_yad_args()

        # YAD implementation has icons for app selection
        appid2icon = _get_appid2icon(steam_apps)

        cmd_input = [
            [
                str(appid2icon[app.appid]),
                f"{app.name}: {app.appid}"
            ]
            for app in steam_apps if app.is_windows_app
        ]
        # Flatten the list
        cmd_input = list(itertools.chain.from_iterable(cmd_input))
    else:
        args = _get_zenity_args()
        cmd_input = [
            f'{app.name}: {app.appid}' for app in steam_apps
            if app.is_windows_app
        ]

    cmd_input = "\n".join(cmd_input)

    try:
        result = _run_gui(args, input_=cmd_input)
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
            raise RuntimeError(
                f"{gui_provider} returned an error. Stderr: {exc.stderr}"
            )

    if choice in (b"", b" \n"):
        print("No game was selected. Quitting...")
        sys.exit(1)

    appid = str(choice).rsplit(':')[-1]
    appid = ''.join(x for x in appid if x.isdigit())
    appid = int(appid)

    steam_app = next(
        app for app in steam_apps
        if app.appid == appid)
    return steam_app


def prompt_filesystem_access(paths, show_dialog=False):
    """
    Check whether Protontricks has access to the provided file system paths
    and prompt the user to grant access if necessary.

    :param show_dialog: Show a dialog. If disabled, just print the message
                        instead.
    """
    def _map_path(path):
        """
        Map path to a path to be added into the `flatpak override` command.
        This means adding a tilde slash if the path is inside the home
        directory.
        """
        home_dir = str(Path.home())
        path = str(path)

        if path.startswith(home_dir):
            path = f"~/{path[len(home_dir)+1:]}"

        return path

    config = get_config()

    inaccessible_paths = get_inaccessible_paths(paths)
    inaccessible_paths = set(map(str, inaccessible_paths))

    logger.debug(
        "Following inaccessible paths were found: %s", inaccessible_paths
    )

    # Check what paths the user has ignored previously
    ignored_paths = set(
        json.loads(config.get("Dialog", "DismissedPaths", "[]"))
    )

    logger.debug("Following paths have been ignored: %s", ignored_paths)

    # Remaining paths that are inaccessible and that haven't been dismissed
    # by the user
    remaining_paths = inaccessible_paths - ignored_paths

    if not remaining_paths:
        return None

    cmd_filesystem = " ".join([
        "--filesystem={}".format(shlex.quote(_map_path(path)))
        for path in remaining_paths
    ])

    # TODO: Showing a text dialog and asking user to manually run the command
    # is very janky. Replace this with a proper permission prompt when
    # Flatpak supports it.
    message = (
        "Protontricks does not appear to have access to the following "
        "directories:\n"
        f" {' '.join(remaining_paths)}\n"
        "\n"
        "To fix this problem, grant access to the required directories by "
        "copying the following command and running it in a terminal:\n"
        "\n"
        f"flatpak override --user {cmd_filesystem} "
        "com.github.Matoking.protontricks\n"
        "\n"
        "You will need to restart Protontricks for the settings to take "
        "effect."
    )

    if show_dialog:
        ignore = show_text_dialog(
            title="Protontricks",
            text=message,
            window_icon="wine",
            cancel_label="Close",
            ok_label="Ignore, don't ask again",
            add_cancel_button=True
        )

        if ignore:
            # If user clicked "Don't ask again", store the paths to ensure the
            # user isn't prompted again for these directories
            ignored_paths |= inaccessible_paths

            config.set(
                "Dialog", "DismissedPaths", json.dumps(list(ignored_paths))
            )

    logger.warning(message)


def _choose_from_list(title, prompt, rows):
    """Present a single-column selection dialog with YAD or Zenity."""
    provider = get_gui_provider()
    args = [
        provider, "--list", "--width", "650", "--height", "380",
        "--title", title, "--text", prompt, "--column", "Option"
    ]
    if provider == "yad":
        args += [
            "--no-headers", "--no-markup", "--center",
            "--print-column", "1", "--separator", ""
        ]
    else:
        args += ["--hide-header"]
    try:
        result = _run_gui(args, input_="\n".join(rows))
    except CalledProcessError as exc:
        if exc.returncode in (1, 252):
            return None
        raise RuntimeError(
            "{} returned an error: {}".format(provider, exc.stderr)
        ) from exc
    value = result.stdout.decode("utf-8").strip()
    # Older YAD builds may retain the default trailing separator.
    if provider == "yad" and value.endswith("|"):
        value = value[:-1]
    return value or None


def select_gui_action():
    """Keep the original Winetricks flow when CDEmu is unavailable."""
    if shutil.which("cdemu") is None:
        return "winetricks"
    selection = _choose_from_list(
        "Protontricks", "Choose an action for the selected game",
        ["Run Winetricks", "Manage CD/DVD drives (CDEmu)"]
    )
    if selection == "Run Winetricks":
        return "winetricks"
    if selection == "Manage CD/DVD drives (CDEmu)":
        return "cdrom"
    return None


def _select_disc_image():
    """Choose an image supported by CDEmu, without restricting all files."""
    provider = get_gui_provider()
    filters = [
        "Disc images | *.iso *.ISO *.cue *.CUE *.mds *.MDS "
        "*.ccd *.CCD *.nrg *.NRG",
        "All files | *"
    ]
    if provider == "yad":
        args = [
            "yad", "--file", "--title", "Select a CD/DVD image",
            "--window-icon", "wine", "--width", "740", "--height", "480"
        ]
    else:
        args = [
            "zenity", "--file-selection", "--title", "Select a CD/DVD image",
            "--window-icon", "wine"
        ]
    for pattern in filters:
        args += ["--file-filter", pattern]
    try:
        result = _run_gui(args)
    except CalledProcessError as exc:
        if exc.returncode in (1, 252):
            return None
        raise RuntimeError(
            "The CD/DVD image picker failed: {}".format(exc.stderr)
        ) from exc
    filename = result.stdout.decode("utf-8").strip()
    return Path(filename) if filename else None


def _confirm_cdrom_action(message):
    return show_text_dialog(
        title="Confirm CDEmu operation",
        text=message,
        window_icon="wine",
        add_cancel_button=True,
        ok_label="Continue",
        cancel_label="Cancel",
        width=540,
        height=280
    )


def _cdrom_error_dialog(message):
    show_text_dialog(
        "Protontricks CD/DVD Manager", str(message), "wine",
        width=560, height=260
    )


def _drive_label(drive):
    if not drive.loaded:
        state = "Empty"
    elif drive.mountpoint is None:
        state = "Loaded (not mounted)"
    else:
        state = "Mounted at {}".format(drive.mountpoint)
    image = Path(drive.image).name if drive.image else "No image"
    return "Reader {} | {} | {} | {}".format(
        drive.slot, drive.device, image, state
    )


def _load_into_spare_reader(prefix, busy_slot, image_path, letter):
    """Load an image into another reader when the current one is busy.

    Return the mounted drive, or None if the user cancelled.
    """
    spare = find_empty_drive(exclude_slot=busy_slot)
    busy_message = (
        "Reader {} is still in use by a running program (usually the "
        "installer started from that disc), so it cannot be ejected "
        "safely. It will stay mounted until that program exits; you can "
        "eject it afterwards.\n\n".format(busy_slot)
    )
    if spare is None:
        if not _confirm_cdrom_action(
            busy_message + "No empty reader is available. Add a new "
            "system-wide CDEmu reader, load {} there and map {}: to "
            "it?".format(Path(image_path).name, letter)
        ):
            return None
        spare = add_drive()
    elif not _confirm_cdrom_action(
        busy_message + "Load {} into empty reader {} instead and map {}: "
        "to it?".format(Path(image_path).name, spare.slot, letter)
    ):
        return None

    return load_image(spare.slot, image_path)


def _drive_letter_choices(prefix, game_name):
    """Build the drive letter prompt, listing letters Wine gave a disc first.

    An installer started from a disc mounted outside Protontricks runs from
    the letter Wine assigned to that disc (for example K:), and it asks for
    the next disc on that same letter.
    """
    try:
        mounted = [
            drive.mountpoint for drive in list_drives()
            if drive.mountpoint is not None
        ]
    except CDROMError:
        mounted = []
    detected = find_disc_letters(prefix, mounted)
    rows = [
        "{}: - {} (disc already mapped by Wine)".format(
            letter, Path(target).name
        )
        for letter, target in detected.items()
    ]
    rows += [
        "{}:".format(chr(number)) for number in range(ord("D"), ord("Z"))
        if chr(number) not in detected
    ]
    prompt = "Choose the Windows drive letter for " + game_name
    if detected:
        prompt += (
            ".\nAn installer started from a mounted disc looks for the next "
            "disc on the letter Wine gave it: choose " +
            ", ".join("{}:".format(letter) for letter in detected) + "."
        )
    return prompt, rows


def manage_cdrom_drives_gui(prefix, game_name):
    """Swap CD/DVD images for one game's Proton prefix with CDEmu.

    The menus are intentionally minimal: add or remove a virtual reader,
    load (or replace) an image, eject it, and map a disc to the selected
    Windows drive letter. Images and readers are system-wide; only the
    dosdevices links (and their backup) are stored in the selected prefix.
    """
    try:
        selected_letter = _choose_from_list(
            "Protontricks CD/DVD Manager",
            *_drive_letter_choices(prefix, game_name)
        )
        if selected_letter is None:
            return
        letter = selected_letter.split(":")[0].strip()
        if len(letter) != 1 or not ("D" <= letter <= "Y"):
            raise CDROMError("Invalid Windows drive letter.")
    except (CDROMError, OSError, RuntimeError, ValueError) as exc:
        _cdrom_error_dialog(exc)
        return

    while True:
        try:
            drives = list_drives()
        except (CDROMError, OSError) as exc:
            _cdrom_error_dialog(exc)
            return

        actions = {}
        for drive in drives:
            actions[_drive_label(drive)] = ("reader", drive.slot)
        actions["Add virtual reader"] = ("add", None)
        # "cdemu remove-device" can only remove the last reader, and the
        # default readers 0 and 1 are never offered for removal.
        if drives and is_removable_slot(drives[-1].slot):
            actions["Remove last virtual reader (reader {})".format(
                drives[-1].slot
            )] = ("remove", drives[-1].slot)

        try:
            selection = _choose_from_list(
                "Protontricks CD/DVD Manager - " + game_name,
                "Select a reader to load, eject or map a disc to "
                "{}:.".format(letter),
                list(actions)
            )
        except (CDROMError, OSError, RuntimeError, ValueError) as exc:
            _cdrom_error_dialog(exc)
            return
        if selection is None:
            return
        if selection not in actions:
            _cdrom_error_dialog("Invalid reader/action selection.")
            continue
        operation, slot = actions[selection]

        try:
            if operation == "add":
                if _confirm_cdrom_action(
                    "Add a CDEmu virtual reader? This changes the system-"
                    "wide CDEmu device list, not only this Proton game."
                ):
                    add_drive()
                continue

            if operation == "remove":
                last = next(
                    (item for item in list_drives() if item.slot == slot),
                    None
                )
                if last is not None and (
                        last.loaded or last.mountpoint is not None):
                    raise CDROMError(
                        "Reader {} still holds a disc image. Eject the "
                        "disc before removing the reader.".format(slot)
                    )
                if _confirm_cdrom_action(
                    "Remove virtual reader {}? This changes the "
                    "system-wide CDEmu device list, not only this "
                    "Proton game.".format(slot)
                ):
                    remove_drive(slot)
                continue

            drive = next(
                (item for item in list_drives() if item.slot == slot), None
            )
            if drive is None:
                raise CDROMError("Reader no longer exists.")

            map_option = "Map disc to {}:".format(letter)
            options = [
                "Load or replace disc image",
                "Eject disc",
                map_option,
                "Back"
            ]
            choice = _choose_from_list(
                "CD/DVD reader {} - {}".format(slot, game_name),
                _drive_label(drive) + "\n"
                "Loading an image also maps it to {}:.".format(letter),
                options
            )
            if choice is None or choice == "Back":
                continue

            if choice == "Load or replace disc image":
                image_path = _select_disc_image()
                if image_path is None:
                    continue
                current = next(
                    (item for item in list_drives() if item.slot == slot), None
                )
                if current is None:
                    raise CDROMError("Reader no longer exists.")
                if current.loaded and not _confirm_cdrom_action(
                    "Replacing the loaded disc will unmount and eject "
                    "the current image from reader {}. This reader is "
                    "shared across applications. Continue?".format(slot)
                ):
                    continue
                try:
                    drive = load_image(
                        slot, image_path, replace=bool(current.loaded)
                    )
                except DeviceBusyError:
                    # The running installer keeps the current disc busy:
                    # use another reader instead of forcing an unmount.
                    drive = _load_into_spare_reader(
                        prefix, slot, image_path, letter
                    )
                    if drive is None:
                        continue
                set_cdrom_mapping(prefix, drive, letter)
            elif choice == map_option:
                # Mount a loaded but unmounted disc first, so mapping works
                # without a separate mount step.
                drive = mount_drive(slot)
                set_cdrom_mapping(prefix, drive, letter)
            elif choice == "Eject disc":
                if _confirm_cdrom_action(
                    "Unmount and eject reader {}? This affects the "
                    "shared CDEmu device; the Wine mapping may temporarily "
                    "point to an unmounted disc.".format(slot)
                ):
                    eject_drive(slot)
        except (CDROMError, OSError, RuntimeError, ValueError) as exc:
            _cdrom_error_dialog(exc)
