#!/bin/bash
# Helper script created by Protontricks to run Wine binaries using Steam Runtime
set -o errexit

PROTONTRICKS_PROXY_SCRIPT_PATH="@@script_path@@"

BLACKLISTED_ROOT_DIRS=(
    /bin /dev /lib /lib64 /proc /run /sys /var /usr
)

ADDITIONAL_MOUNT_DIRS=(
    /run/media "$PROTON_PATH" "$WINEPREFIX"
)

WINESERVER_ENV_VARS_TO_COPY=(
    WINEESYNC WINEFSYNC
)

if [[ -z "$PROTONTRICKS_FIRST_START" ]]; then
    # Try to detect if wineserver is already running, and if so, copy a few
    # environment variables from it to ensure our own Wine processes
    # are able to run at the same time without any issues.
    # This usually happens when the user is running the Steam app and
    # Protontricks at the same time.
    wineserver_found=false

    # Find the correct Wineserver that's using the same prefix
    while read -r pid; do
        if [[ $(xargs -0 -L1 -a "/proc/${pid}/environ" | grep "^WINEPREFIX=${WINEPREFIX}") ]] &> /dev/null; then
            if [[ "$pid" = "$$" ]]; then
                # Don't mistake this very script for a wineserver instance
                continue
            fi
            wineserver_found=true
            wineserver_pid="$pid"
        fi
    done < <(pgrep wineserver)

    if [[ "$wineserver_found" = true ]]; then
        # wineserver found, retrieve its environment variables
        wineserver_env_vars=$(xargs -0 -L1 -a "/proc/${wineserver_pid}/environ")

        # Copy the required environment variables found in the
        # existing wineserver process
        for env_name in "${WINESERVER_ENV_VARS_TO_COPY[@]}"; do
            env_declr=$(echo "$wineserver_env_vars" | grep "^${env_name}=" || :)
            if [[ -n "$env_declr" ]]; then
                export "${env_declr?}"
            fi
        done
    fi

    # Enable fsync & esync by default
    if [[ -z "$WINEFSYNC" ]]; then
        if [[ -z "$PROTON_NO_FSYNC" || "$PROTON_NO_FSYNC" = "0" ]]; then
            export WINEFSYNC=1
        fi
    fi

    if [[ -z "$WINEESYNC" ]]; then
        if [[ -z "$PROTON_NO_ESYNC" || "$PROTON_NO_ESYNC" = "0" ]]; then
            export WINEESYNC=1
        fi
    fi

    export PROTONTRICKS_FIRST_START=1
fi

# PROTONTRICKS_STEAM_RUNTIME values:
#   bwrap:  Run Wine binaries inside Steam Runtime's bwrap sandbox,
#           modify LD_LIBRARY_PATH to include Proton libraries
#
#   legacy: Modify LD_LIBRARY_PATH to include Steam Runtime *and* Proton
#           libraries. Host library order is adjusted as well.
#
#   off:    Just run the binaries as-is.
if [[ -n "$PROTONTRICKS_INSIDE_STEAM_RUNTIME"
       || "$PROTONTRICKS_STEAM_RUNTIME" = "legacy"
       || "$PROTONTRICKS_STEAM_RUNTIME" = "off"
    ]]; then

    # If either Steam Runtime is enabled, change LD_LIBRARY_PATH
    if [[ "$PROTONTRICKS_STEAM_RUNTIME" = "bwrap" ]]; then
        export LD_LIBRARY_PATH="$LD_LIBRARY_PATH":"$PROTON_LD_LIBRARY_PATH"
    elif [[ "$PROTONTRICKS_STEAM_RUNTIME" = "legacy" ]]; then
        export LD_LIBRARY_PATH="$PROTON_LD_LIBRARY_PATH"
    fi
    exec "$PROTON_DIST_PATH"/bin/@@name@@ "$@" || :
elif [[ "$PROTONTRICKS_STEAM_RUNTIME" = "bwrap" ]]; then
    # Command is being executed outside Steam Runtime and bwrap is enabled.
    # Determine mount point and configure our Wine environment before running
    # bwrap and continuing execution inside the sandbox.

    mount_dirs=()

    # Add any root directories that are not blacklisted
    for dir in /* ; do
        if [[ ! -d "$dir" ]]; then
            continue
        fi
        if [[ " ${BLACKLISTED_ROOT_DIRS[*]} " =~ " $dir " ]]; then
            continue
        fi
        mount_dirs+=("$dir")
    done

    # Add additional mount directories, including the Wine prefix and Proton
    # installation directory
    for dir in "${ADDITIONAL_MOUNT_DIRS[@]}"; do
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
        for mount_dir in "${mount_dirs[@]}"; do
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

    for mount in "${mount_dirs[@]}"; do
        mount_params+=(--filesystem "${mount}")
    done


    exec "$STEAM_RUNTIME_PATH"/run --share-pid --batch \
    "${mount_params[@]}" -- \
    env PROTONTRICKS_INSIDE_STEAM_RUNTIME=1 \
    "$PROTONTRICKS_PROXY_SCRIPT_PATH" "$@"
else
    echo "Unknown PROTONTRICKS_STEAM_RUNTIME value $PROTONTRICKS_STEAM_RUNTIME"
    exit 1
fi

