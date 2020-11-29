import logging
import os
import shlex
import shutil
import stat
from pathlib import Path
from subprocess import check_output, run, PIPE

__all__ = ("get_runtime_library_path", "create_wine_bin_dir", "run_command")

logger = logging.getLogger("protontricks")

SUPPORTED_STEAM_RUNTIMES = [
    "Steam Linux Runtime - Soldier"
]


def lower_dict(d):
    """
    Return a copy of the dictionary with all keys converted to lowercase.

    This is mainly used when dealing with Steam VDF files, as those tend to
    have either CamelCase or lowercase keys depending on the version.
    """
    return {k.lower(): v for k, v in d.items()}


def get_host_library_paths():
    """
    Get host library paths to use when creating the LD_LIBRARY_PATH environment
    variable for use with newer Steam Runtime installations
    """
    # The traditional Steam Runtime does the following when running the
    # `run.sh --print-steam-runtime-library-paths` command.
    # Since that command is unavailable with newer Steam Runtime releases,
    # do it ourselves here.
    result = run(
        ["/sbin/ldconfig", "-XNv"],
        encoding="utf-8", check=True, stdout=PIPE, stderr=PIPE
    )
    lines = result.stdout.split("\n")
    paths = [
        line.split(":")[0] for line in lines
        if line.startswith("/") and ":" in line
    ]

    return ":".join(paths)


def get_runtime_library_path(steam_runtime_path, proton_app):
    """
    Get LD_LIBRARY_PATH value to run a command using Steam Runtime
    """
    if proton_app.required_tool_app:
        # bwrap based Steam Runtime is used for Proton installations that
        # use separate Steam runtimes
        # TODO: Try to run the Wine binaries inside an user namespace somehow.
        # Newer Steam Runtime environments may rely on a newer glibc than what
        # is available on the host system, which may cause potential problems
        # otherwise.
        runtime_root = next(
            Path(proton_app.required_tool_app.install_path).glob("*/files/")
        )
        return "".join([
            os.path.join(proton_app.install_path, "dist", "lib"), os.pathsep,
            os.path.join(proton_app.install_path, "dist", "lib64"), os.pathsep,
            get_host_library_paths(), os.pathsep,
            str(runtime_root / "i686-pc-linux-gnu" / "lib"), os.pathsep,
            str(runtime_root / "x86_64-pc-linux-gnu" / "lib"), os.pathsep,
        ])

    # Traditional LD_LIBRARY_PATH based Steam Runtime is used otherwise
    steam_runtime_paths = check_output([
        os.path.join(steam_runtime_path, "run.sh"),
        "--print-steam-runtime-library-paths"
    ])
    steam_runtime_paths = str(steam_runtime_paths, "utf-8")
    # Add Proton installation directory first into LD_LIBRARY_PATH
    # so that libwine.so.1 is picked up correctly (see issue #3)
    return "".join([
        os.path.join(proton_app.install_path, "dist", "lib"), os.pathsep,
        os.path.join(proton_app.install_path, "dist", "lib64"), os.pathsep,
        steam_runtime_paths
    ])


WINE_SCRIPT_TEMPLATE = (
    "#!/bin/bash\n"
    "# Helper script created by Protontricks to run Wine binaries using Steam Runtime\n"
    "export LD_LIBRARY_PATH=\"$PROTON_LD_LIBRARY_PATH\"\n"
    "exec \"$PROTON_PATH\"/dist/bin/{name} \"$@\""
)


def create_wine_bin_dir(proton_app):
    """
    Create a directory with "proxy" executables that load shared libraries
    using Steam Runtime and Proton's own libraries instead of the system
    libraries
    """
    binaries = list((
        Path(proton_app.install_path) / "dist" / "bin"
    ).iterdir())

    # Create the base directory containing files for every Proton installation
    xdg_cache_dir = os.environ.get(
        "XDG_CACHE_HOME", os.path.expanduser("~/.cache")
    )
    base_path = Path(xdg_cache_dir) / "protontricks" / "proton"
    os.makedirs(str(base_path), exist_ok=True)

    # Create a directory to hold the new executables for the specific
    # Proton installation
    bin_path = base_path / proton_app.name / "bin"
    os.makedirs(str(bin_path), exist_ok=True)

    logger.info(
        "Created Steam Runtime Wine binary directory at %s", str(bin_path)
    )

    # Check if the correct binaries exist
    files_already_exist = (
        {binary.name for binary in binaries}
        == {binary.name for binary in bin_path.iterdir()}
    )

    if files_already_exist:
        # The correct files exist and nothing needs to be rewritten
        return bin_path

    # Delete the directory and rewrite the scripts. Some binaries may no
    # longer exist in the Proton installation, so we'll also get rid of
    # scripts that point to non-existing files
    shutil.rmtree(str(bin_path))
    os.makedirs(str(bin_path))

    for binary in binaries:
        content = WINE_SCRIPT_TEMPLATE.format(
            name=shlex.quote(binary.name)
        ).encode("utf-8")

        with open(str(bin_path / binary.name), "wb") as file_:
            file_.write(content)

        script_stat = os.stat(str(bin_path / binary.name))
        # Make the helper script executable
        (bin_path / binary.name).chmod(script_stat.st_mode | stat.S_IEXEC)

    return bin_path


def run_command(
        winetricks_path, proton_app, steam_app, command,
        steam_runtime_path=None,
        **kwargs):
    """Run an arbitrary command with the correct environment variables
    for the given Proton app

    The environment variables are set for the duration of the call
    and restored afterwards

    If 'steam_runtime_path' is provided, run the command using Steam Runtime
    """
    # Make a copy of the environment variables to restore later
    environ_copy = os.environ.copy()

    if not os.environ.get("WINE"):
        logger.info(
            "WINE environment variable is not available. "
            "Setting WINE environment variable to Proton bundled version"
        )
        os.environ["WINE"] = os.path.join(
            proton_app.install_path, "dist", "bin", "wine")

    if not os.environ.get("WINESERVER"):
        logger.info(
            "WINESERVER environment variable is not available. "
            "Setting WINESERVER environment variable to Proton bundled version"
        )
        os.environ["WINESERVER"] = os.path.join(
            proton_app.install_path, "dist", "bin", "wineserver"
        )

    os.environ["WINETRICKS"] = winetricks_path
    os.environ["WINEPREFIX"] = steam_app.prefix_path
    os.environ["WINELOADER"] = os.environ["WINE"]
    os.environ["WINEDLLPATH"] = "".join([
        os.path.join(proton_app.install_path, "dist", "lib64", "wine"),
        os.pathsep,
        os.path.join(proton_app.install_path, "dist", "lib", "wine")
    ])

    os.environ["PATH"] = os.path.join(
        proton_app.install_path, "dist", "bin"
    ) + os.pathsep + os.environ["PATH"]

    # Expose the path to Proton installation. This is mainly used for
    # Wine helper scripts, but other scripts could use it as well.
    os.environ["PROTON_PATH"] = proton_app.install_path

    # Unset WINEARCH, which might be set for another Wine installation
    os.environ.pop("WINEARCH", "")

    wine_bin_dir = None
    if steam_runtime_path:
        if proton_app.required_tool_app:
            runtime_name = proton_app.required_tool_app.name
            logger.info(
                "Using separately installed Steam Runtime: %s",
                runtime_name
            )

            if runtime_name not in SUPPORTED_STEAM_RUNTIMES:
                logger.warning(
                    "Current Steam Runtime not recognized by Protontricks."
                )

        # When Steam Runtime is enabled, create a set of helper scripts
        # that load the underlying Proton Wine executables with Steam Runtime
        # and Proton libraries instead of system libraries
        wine_bin_dir = create_wine_bin_dir(proton_app=proton_app)
        os.environ["PROTON_LD_LIBRARY_PATH"] = \
            get_runtime_library_path(steam_runtime_path, proton_app)
        os.environ["PATH"] = \
            str(wine_bin_dir) + os.pathsep + os.environ["PATH"]
        os.environ["WINE"] = str(wine_bin_dir / "wine")
        os.environ["WINELOADER"] = os.environ["WINE"]
        os.environ["WINESERVER"] = str(wine_bin_dir / "wineserver")

    logger.info("Attempting to run command %s", command)

    try:
        run(command, **kwargs)
    finally:
        # Restore original env vars
        os.environ.clear()
        os.environ.update(environ_copy)
