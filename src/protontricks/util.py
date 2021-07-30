import logging
import os
import shlex
import shutil
import stat

from pathlib import Path
from subprocess import check_output, run, PIPE

__all__ = (
    "SUPPORTED_STEAM_RUNTIMES", "is_flatpak_sandbox", "lower_dict",
    "get_legacy_runtime_library_paths", "get_host_library_paths",
    "RUNTIME_ROOT_GLOB_PATTERNS", "get_runtime_library_paths",
    "WINE_SCRIPT_RUNTIME_V1_TEMPLATE",
    "WINE_SCRIPT_RUNTIME_V2_TEMPLATE",
    "create_wine_bin_dir", "run_command"
)

logger = logging.getLogger("protontricks")

SUPPORTED_STEAM_RUNTIMES = [
    "Steam Linux Runtime - Soldier"
]


def is_flatpak_sandbox():
    """
    Check if we're running inside a Flatpak sandbox
    """
    return Path("/.flatpak-info").exists()


def lower_dict(d):
    """
    Return a copy of the dictionary with all keys recursively converted to
    lowercase.

    This is mainly used when dealing with Steam VDF files, as those tend to
    have either CamelCase or lowercase keys depending on the version.
    """
    def _lower_value(value):
        if not isinstance(value, dict):
            return value

        return {k.lower(): _lower_value(v) for k, v in value.items()}

    return {k.lower(): _lower_value(v) for k, v in d.items()}


def get_legacy_runtime_library_paths(legacy_steam_runtime_path, proton_app):
    """
    Get LD_LIBRARY_PATH value to use when running a command using Steam Runtime
    """
    steam_runtime_paths = check_output([
        str(legacy_steam_runtime_path / "run.sh"),
        "--print-steam-runtime-library-paths"
    ])
    steam_runtime_paths = str(steam_runtime_paths, "utf-8")
    # Add Proton installation directory first into LD_LIBRARY_PATH
    # so that libwine.so.1 is picked up correctly (see issue #3)
    return "".join([
        str(proton_app.proton_dist_path / "lib"), os.pathsep,
        str(proton_app.proton_dist_path / "lib64"), os.pathsep,
        steam_runtime_paths
    ])


def get_host_library_paths():
    """
    Get host library paths to use when creating the LD_LIBRARY_PATH environment
    variable for use with newer Steam Runtime installations when *not*
    using bwrap
    """
    # The traditional Steam Runtime does the following when running the
    # `run.sh --print-steam-runtime-library-paths` command.
    # Since that command is unavailable with newer Steam Runtime releases,
    # do it ourselves here.
    result = run(
        ["/sbin/ldconfig", "-XNv"],
        check=True, stdout=PIPE, stderr=PIPE
    )
    lines = result.stdout.decode("utf-8").split("\n")
    paths = [
        line.split(":")[0] for line in lines
        if line.startswith("/") and ":" in line
    ]

    return ":".join(paths)


RUNTIME_ROOT_GLOB_PATTERNS = (
    "var/*/files/",
    "*/files/"
)


def get_runtime_library_paths(proton_app, use_bwrap=True):
    """
    Get LD_LIBRARY_PATH value to use when running a command using Steam Runtime
    """
    def find_runtime_app_root(runtime_app):
        """
        Find the runtime root (the directory containing the root fileystem
        used for the container) for separately installed Steam Runtime app
        """
        for pattern in RUNTIME_ROOT_GLOB_PATTERNS:
            try:
                return next(
                    runtime_app.install_path.glob(pattern)
                )
            except StopIteration:
                pass

        raise RuntimeError(
            "Could not find Steam Runtime runtime root for {}".format(
                runtime_app.name
            )
        )

    if use_bwrap:
        return "".join([
            str(proton_app.proton_dist_path / "lib"), os.pathsep,
            str(proton_app.proton_dist_path / "lib64"), os.pathsep
        ])

    runtime_root = find_runtime_app_root(proton_app.required_tool_app)
    return "".join([
        str(proton_app.proton_dist_path / "lib"), os.pathsep,
        str(proton_app.proton_dist_path / "lib64"), os.pathsep,
        get_host_library_paths(), os.pathsep,
        str(runtime_root / "lib" / "i386-linux-gnu"), os.pathsep,
        str(runtime_root / "lib" / "x86_64-linux-gnu")
    ])


WINE_SCRIPT_RUNTIME_V1_TEMPLATE = (
    "#!/bin/bash\n"
    "# Helper script created by Protontricks to run Wine binaries using Steam Runtime\n"
    "export LD_LIBRARY_PATH=\"$PROTON_LD_LIBRARY_PATH\"\n"
    "exec \"$PROTON_DIST_PATH\"/bin/{name} \"$@\""
)

WINE_SCRIPT_RUNTIME_V2_TEMPLATE = """#!/bin/bash
# Helper script created by Protontricks to run Wine binaries using Steam Runtime
set -o errexit

PROTONTRICKS_PROXY_SCRIPT_PATH="{script_path}"

BLACKLISTED_ROOT_DIRS=(
    /bin /dev /lib /lib64 /proc /run /sys /var /usr
)

ADDITIONAL_MOUNT_DIRS=(
    /run/media "$PROTON_PATH" "$WINEPREFIX"
)

mount_dirs=()

# Add any root directories that are not blacklisted
for dir in /* ; do
    if [[ ! -d "$dir" ]]; then
        continue
    fi
    if [[ " ${{BLACKLISTED_ROOT_DIRS[*]}} " =~ " $dir " ]]; then
        continue
    fi
    mount_dirs+=("$dir")
done

# Add additional mount directories, including the Wine prefix and Proton
# installation directory
for dir in "${{ADDITIONAL_MOUNT_DIRS[@]}}"; do
    if [[ ! -d "$dir" ]]; then
        continue
    fi

    already_mounted=false
    # Check if the additional mount directory is already covered by one
    # of the existing root directories.
    # Most of the time this is the case, but if the user has placed the Proton
    # installation or prefix inside a blacklisted directory (eg. '/lib'),
    # we'll want to ensure it's mounted even if we're not mounting the entire
    # root directory.
    for mount_dir in "${{mount_dirs[@]}}"; do
        if [[ "$dir" =~ ^$mount_dir ]]; then
            # This directory is already covered by one of the existing mount
            # points
            already_mounted=true
            break
        fi
    done

    if [[ "$already_mounted" = false ]]; then
        mount_dirs+=("$dir")
    fi
done


mount_params=()

for mount in "${{mount_dirs[@]}}"; do
    mount_params+=(--filesystem "${{mount}}")
done

if [[ -n "$PROTONTRICKS_INSIDE_STEAM_RUNTIME" ]]; then
  # Command is being executed inside Steam Runtime
  # LD_LIBRARY_PATH can now be set.
  export LD_LIBRARY_PATH="$LD_LIBRARY_PATH":"$PROTON_LD_LIBRARY_PATH"
  "$PROTON_DIST_PATH"/bin/{name} "$@"
else
  exec "$STEAM_RUNTIME_PATH"/run --share-pid --batch \
  "${{mount_params[@]}}" -- \
  env PROTONTRICKS_INSIDE_STEAM_RUNTIME=1 \
  "$PROTONTRICKS_PROXY_SCRIPT_PATH" "$@"
fi
"""


def create_wine_bin_dir(proton_app, use_bwrap=True):
    """
    Create a directory with "proxy" executables that load shared libraries
    using Steam Runtime and Proton's own libraries instead of the system
    libraries
    """
    # If the Proton installation uses a newer version of Steam Runtime,
    # use a different template for the scripts
    bin_template = (
        WINE_SCRIPT_RUNTIME_V2_TEMPLATE
        if proton_app.required_tool_app and use_bwrap
        else WINE_SCRIPT_RUNTIME_V1_TEMPLATE
    )

    binaries = list((proton_app.proton_dist_path / "bin").iterdir())

    # Create the base directory containing files for every Proton installation
    xdg_cache_dir = os.environ.get(
        "XDG_CACHE_HOME", os.path.expanduser("~/.cache")
    )
    base_path = Path(xdg_cache_dir) / "protontricks" / "proton"
    os.makedirs(str(base_path), exist_ok=True)

    # Create a directory to hold the new executables for the specific
    # Proton installation
    bin_path = base_path / proton_app.name / "bin"
    bin_path.mkdir(parents=True, exist_ok=True)

    logger.info(
        "Created Steam Runtime Wine binary directory at %s", str(bin_path)
    )

    # Delete the directory and rewrite the scripts. Some binaries may no
    # longer exist in the Proton installation, so we'll also get rid of
    # scripts that point to non-existing files
    shutil.rmtree(str(bin_path))
    bin_path.mkdir(parents=True)

    for binary in binaries:
        proxy_script_path = bin_path / binary.name

        content = bin_template.format(
            name=shlex.quote(binary.name),
            script_path=str(proxy_script_path)
        ).encode("utf-8")

        proxy_script_path.write_bytes(content)

        script_stat = proxy_script_path.stat()
        # Make the helper script executable
        proxy_script_path.chmod(script_stat.st_mode | stat.S_IEXEC)

    return bin_path


def run_command(
        winetricks_path, proton_app, steam_app, command,
        use_steam_runtime=False,
        legacy_steam_runtime_path=None,
        use_bwrap=True,
        **kwargs):
    """Run an arbitrary command with the correct environment variables
    for the given Proton app

    The environment variables are set for the duration of the call
    and restored afterwards

    If 'use_steam_runtime' is True, run the command using Steam Runtime
    using either 'legacy_steam_runtime_path' or the Proton app's specific
    Steam Runtime installation, depending on which one is required.

    If 'use_bwrap' is True, run newer Steam Runtime installations using
    bwrap based containerization.
    """
    # Check for incomplete Steam Runtime installation
    runtime_install_incomplete = \
        proton_app.required_tool_appid and not proton_app.required_tool_app

    if use_steam_runtime and runtime_install_incomplete:
        raise RuntimeError(
            "{} is missing the required Steam Runtime. You may need to launch "
            "a Steam app using this Proton version to finish the "
            "installation.".format(proton_app.name)
        )

    # Make a copy of the environment variables to restore later
    environ_copy = os.environ.copy()

    user_provided_wine = os.environ.get("WINE", False)
    user_provided_wineserver = os.environ.get("WINESERVER", False)

    if not user_provided_wine:
        logger.info(
            "WINE environment variable is not available. "
            "Setting WINE environment variable to Proton bundled version"
        )
        os.environ["WINE"] = \
            str(proton_app.proton_dist_path / "bin" / "wine")

    if not user_provided_wineserver:
        logger.info(
            "WINESERVER environment variable is not available. "
            "Setting WINESERVER environment variable to Proton bundled version"
        )
        os.environ["WINESERVER"] = \
            str(proton_app.proton_dist_path / "bin" / "wineserver")

    os.environ["WINETRICKS"] = str(winetricks_path)
    os.environ["WINEPREFIX"] = str(steam_app.prefix_path)
    os.environ["WINELOADER"] = os.environ["WINE"]
    os.environ["WINEDLLPATH"] = "".join([
        str(proton_app.proton_dist_path / "lib64" / "wine"),
        os.pathsep,
        str(proton_app.proton_dist_path / "lib" / "wine")
    ])

    os.environ["PATH"] = "".join([
        str(proton_app.proton_dist_path / "bin"), os.pathsep,
        os.environ["PATH"]
    ])

    # Expose the path to Proton installation. This is mainly used for
    # Wine helper scripts, but other scripts could use it as well.
    os.environ["PROTON_PATH"] = str(proton_app.install_path)
    os.environ["PROTON_DIST_PATH"] = str(proton_app.proton_dist_path)

    # Unset WINEARCH, which might be set for another Wine installation
    os.environ.pop("WINEARCH", "")

    wine_bin_dir = None
    if use_steam_runtime:
        if proton_app.required_tool_app:
            os.environ["STEAM_RUNTIME_PATH"] = \
                str(proton_app.required_tool_app.install_path)
            os.environ["PROTON_LD_LIBRARY_PATH"] = \
                get_runtime_library_paths(proton_app, use_bwrap=use_bwrap)

            runtime_name = proton_app.required_tool_app.name
            logger.info(
                "Using separately installed Steam Runtime: %s",
                runtime_name
            )

            if use_bwrap:
                logger.info(
                    "Running Steam Runtime using bwrap containerization.\n"
                    "If any problems arise, please try running the command "
                    "again using the `--no-bwrap` flag and make an issue "
                    "report if the problem only occurs when bwrap is in use."
                )

            if runtime_name not in SUPPORTED_STEAM_RUNTIMES:
                logger.warning(
                    "Current Steam Runtime not recognized by Protontricks."
                )
        else:
            # Legacy Steam Runtime requires a different LD_LIBRARY_PATH
            os.environ["PROTON_LD_LIBRARY_PATH"] = \
                get_legacy_runtime_library_paths(
                    legacy_steam_runtime_path, proton_app
                )

        # When Steam Runtime is enabled, create a set of helper scripts
        # that load the underlying Proton Wine executables with Steam Runtime
        # and Proton libraries instead of system libraries
        wine_bin_dir = create_wine_bin_dir(
            proton_app=proton_app, use_bwrap=use_bwrap
        )
        os.environ["LEGACY_STEAM_RUNTIME_PATH"] = \
            str(legacy_steam_runtime_path)

        os.environ["PATH"] = "".join([
            str(wine_bin_dir), os.pathsep, os.environ["PATH"]
        ])

        if not user_provided_wine:
            os.environ["WINE"] = str(wine_bin_dir / "wine")
            os.environ["WINELOADER"] = os.environ["WINE"]

        if not user_provided_wineserver:
            os.environ["WINESERVER"] = str(wine_bin_dir / "wineserver")

    logger.info("Attempting to run command %s", command)

    try:
        run(command, **kwargs)
    finally:
        # Restore original env vars
        os.environ.clear()
        os.environ.update(environ_copy)

