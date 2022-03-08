#!/bin/bash
# A simple keepalive script that will ensure a wineserver process is kept alive
# for the duration of the Protontricks session.
# This is accomplished by launching a simple Windows batch script that will
# run until it is prompted to close itself at the end of the Protontricks
# session.
set -o errexit

function log_info () {
    if [[ "$PROTONTRICKS_LOG_LEVEL" != "INFO" ]]; then
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

function cleanup () {
    # Remove the 'keepalive' file in the temp directory. This will prompt
    # the Wine process to stop execution.
    rm "$PROTONTRICKS_TEMP_PATH/keepalive" &>/dev/null || true
    log_info "Cleanup finished, goodbye!"
}

touch "$PROTONTRICKS_TEMP_PATH/keepalive"

trap cleanup EXIT HUP INT QUIT ABRT

cd "$PROTONTRICKS_TEMP_PATH" || exit 1

while [[ -f "$PROTONTRICKS_TEMP_PATH/keepalive" ]]; do
    log_info "Starting wineserver-keepalive process..."

    wine cmd.exe /c "@@keepalive_bat_path@@" &>/dev/null
    if [[ -f "$PROTONTRICKS_TEMP_PATH/keepalive" ]]; then
        # If 'keepalive' still exists, someone called 'wineserver -w'.
        # To prevent that command from stalling indefinitely, we need to
        # shut down this process temporarily until the waiting command
        # has terminated.
        wineserver_finished=false

        log_info "'wineserver -w' was called, waiting until all processes are finished..."

        while [[ "$wineserver_finished" = false ]]; do
            wineserver_finished=true
            while read -r pid; do
                if [[ "$pid" = "$$" ]]; then
                    continue
                fi

                if [[ $(pgrep -a "$pid" | grep -v -E '\/wineserver -w$') ]] &> /dev/null; then
                    # Skip commands that do *not* end with 'wineserver -w'
                    continue
                fi

                if [[ $(xargs -0 -L1 -a "/proc/${pid}/environ" | grep "^WINEPREFIX=${WINEPREFIX}") ]] &> /dev/null; then
                    wineserver_finished=false
                fi
            done < <(pgrep wineserver)
            sleep 0.25
        done

        log_info "All wineserver processes finished, restarting keepalive process..."
    fi
done
