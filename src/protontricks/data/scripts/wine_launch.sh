#!/bin/bash
# Helper script created by Protontricks to run Wine binaries using Steam Runtime
set -o errexit

function log_debug () {
    if [[ "$PROTONTRICKS_LOG_LEVEL" != "DEBUG" ]]; then
        return
    fi
}

function log_info () {
    if [[ "$PROTONTRICKS_LOG_LEVEL" = "WARNING" ]]; then
        return
    fi

    log "$@"
}

function log_warning () {
    if [[ "$PROTONTRICKS_LOG_LEVEL" = "INFO" || "$PROTONTRICKS_LOG_LEVEL" = "WARNING" ]]; then
        return
    fi

    log "$@"
}

function log () {
    >&2 echo "protontricks - $(basename "$0") $$: $*"
}

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

if [[ -n "$PROTONTRICKS_BACKGROUND_WINESERVER"
       && "$0" = "@@script_path@@"
    ]]; then
    # Check if we're calling 'wineserver -w' when background wineserver is
    # enabled.
    # If so, prompt our keepalive wineserver to restart itself by creating
    # a 'restart' file inside the temporary directory
    if [[ "$(basename "$0")" = "wineserver"
        && "$1" = "-w"
        ]]; then
        log_info "Touching '$PROTONTRICKS_TEMP_PATH/restart' to restart wineserver."
        touch "$PROTONTRICKS_TEMP_PATH/restart"
    fi
fi

if [[ -z "$PROTONTRICKS_FIRST_START" ]]; then
    if [[ "$PROTONTRICKS_STEAM_RUNTIME" = "bwrap" ]]; then
        # Check if the launch script is named 'pressure-vessel-launch' or
        # 'steam-runtime-launch-client'. The latter name is newer and used
        # since steam-runtime-tools v0.20220420.0
        launch_script=""
        script_names=('pressure-vessel-launch' 'steam-runtime-launch-client')
        for name in "${script_names[@]}"; do
            if [[ -f "$STEAM_RUNTIME_PATH/pressure-vessel/bin/$name" ]]; then
                launch_script="$STEAM_RUNTIME_PATH/pressure-vessel/bin/$name"
                log_info "Found Steam Runtime launch client at $launch_script"
            fi
        done

        if [[ "$launch_script" = "" ]]; then
            echo "Launch script could not be found, aborting..."
            exit 1
        fi

        export STEAM_RUNTIME_LAUNCH_SCRIPT="$launch_script"
    fi

    # Try to detect if wineserver is already running, and if so, copy a few
    # environment variables from it to ensure our own Wine processes
    # are able to run at the same time without any issues.
    # This usually happens when the user is running the Steam app and
    # Protontricks at the same time.
    wineserver_found=false

    log_info "Checking for running wineserver instance"

    # Find the correct Wineserver that's using the same prefix
    while read -r pid; do
        if [[ $(xargs -0 -L1 -a "/proc/${pid}/environ" | grep "^WINEPREFIX=${WINEPREFIX}") ]] &> /dev/null; then
            if [[ "$pid" = "$$" ]]; then
                # Don't mistake this very script for a wineserver instance
                continue
            fi
            wineserver_found=true
            wineserver_pid="$pid"

            log_info "Found running wineserver instance with PID ${wineserver_pid}"
        fi
    done < <(pgrep "wineserver$")

    if [[ "$wineserver_found" = true ]]; then
        # wineserver found, retrieve its environment variables.
        # wineserver might disappear from under our foot especially if we're
        # in the middle of running a lot of Wine commands in succession,
        # so don't assume the wineserver still exists.
        wineserver_env_vars=$(xargs -0 -L1 -a "/proc/${wineserver_pid}/environ" 2> /dev/null || echo "")

        # Copy the required environment variables found in the
        # existing wineserver process
        for env_name in "${WINESERVER_ENV_VARS_TO_COPY[@]}"; do
            env_declr=$(echo "$wineserver_env_vars" | grep "^${env_name}=" || :)
            if [[ -n "$env_declr" ]]; then
                log_info "Copying env var from running wineserver: ${env_declr}"
                export "${env_declr?}"
            fi
        done
    fi

    # Enable fsync & esync by default
    if [[ "$wineserver_found" = false ]]; then
        if [[ -z "$WINEFSYNC" ]]; then
            if [[ -z "$PROTON_NO_FSYNC" || "$PROTON_NO_FSYNC" = "0" ]]; then
                log_info "Setting default env: WINEFSYNC=1"
                export WINEFSYNC=1
            fi
        fi

        if [[ -z "$WINEESYNC" ]]; then
            if [[ -z "$PROTON_NO_ESYNC" || "$PROTON_NO_ESYNC" = "0" ]]; then
                log_info "Setting default env: WINEESYNC=1"
                export WINEESYNC=1
            fi
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

    if [[ -n "$PROTONTRICKS_INSIDE_STEAM_RUNTIME" ]]; then
        log_info "Starting Wine process inside the container"
    else
        log_info "Starting Wine process directly, Steam runtime: $PROTONTRICKS_STEAM_RUNTIME"
    fi

    # If either Steam Runtime is enabled, change LD_LIBRARY_PATH
    if [[ "$PROTONTRICKS_STEAM_RUNTIME" = "bwrap" ]]; then
        export LD_LIBRARY_PATH="$LD_LIBRARY_PATH":"$PROTON_LD_LIBRARY_PATH"
        log_info "Appending to LD_LIBRARY_PATH: $PROTON_LD_LIBRARY_PATH"
    elif [[ "$PROTONTRICKS_STEAM_RUNTIME" = "legacy" ]]; then
        export LD_LIBRARY_PATH="$PROTON_LD_LIBRARY_PATH"
        log_info "LD_LIBRARY_PATH set to $LD_LIBRARY_PATH"
    fi
    exec "$PROTON_DIST_PATH"/bin/@@name@@ "$@" || :
elif [[ "$PROTONTRICKS_STEAM_RUNTIME" = "bwrap" ]]; then
    # Command is being executed outside Steam Runtime and bwrap is enabled.
    # Use "pressure-vessel-launch" to launch it in the existing container.

    log_info "Starting Wine process using 'pressure-vessel-launch'"

    # It would be nicer to use the PID here, but that would break multiple
    # simultaneous Protontricks sessions inside Flatpak, which doesn't seem to
    # expose the unique host PID.
    bus_name="com.github.Matoking.protontricks.App${STEAM_APPID}_${PROTONTRICKS_SESSION_ID}"

    # Pass all environment variables to 'steam-runtime-launch-client' except
    # for problematic variables that should be determined by the launch command
    # instead.
    env_params=()
    for env_name in $(compgen -e); do
        # Skip vars that should be set by 'steam-runtime-launch-client' instead
        if [[ "$env_name" = "XAUTHORITY"
              || "$env_name" = "DISPLAY"
              || "$env_name" = "WAYLAND_DISPLAY" ]]; then
            continue
        fi

        env_params+=(--pass-env "${env_name}")
    done

    exec "$STEAM_RUNTIME_LAUNCH_SCRIPT" \
    --share-pids --bus-name="$bus_name" \
    --directory "$PWD" \
    --env=PROTONTRICKS_INSIDE_STEAM_RUNTIME=1 \
    "${env_params[@]}" -- "$PROTONTRICKS_PROXY_SCRIPT_PATH" "$@"
else
    echo "Unknown PROTONTRICKS_STEAM_RUNTIME value $PROTONTRICKS_STEAM_RUNTIME"
    exit 1
fi

