#!/bin/bash
# Helper script created by Protontricks to run Wine binaries using Steam Runtime
set -o errexit

WINESERVER_ENV_VARS_TO_COPY=(
    WINEESYNC WINEFSYNC
)

if [[ -z "$PROTONTRICKS_WINESERVER_SEARCH_DONE" ]]; then
    # Try to detect if wineserver is already running, and if so, copy a few
    # environment variables from it to ensure our own Wine processes
    # are able to run at the same time without any issues.
    # This usually happens when the user is running the Steam app and
    # Protontricks at the same time.
    wineserver_found=false

    export PROTONTRICKS_WINESERVER_SEARCH_DONE=1

    # Find the correct Wineserver that's using the same prefix
    while read -r pid; do
        if xargs -0 -L1 -a "/proc/${pid}/environ" | grep "^WINEPREFIX=${WINEPREFIX}" > /dev/null 2>&1; then
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
            env_declr=$(echo "$wineserver_env_vars" | grep "^${env_name}=")
            export "${env_declr?}"
        done
    fi
fi

export LD_LIBRARY_PATH="$PROTON_LD_LIBRARY_PATH"
exec "$PROTON_DIST_PATH"/bin/@@name@@ "$@"
