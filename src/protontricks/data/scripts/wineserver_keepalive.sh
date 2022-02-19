#!/bin/bash
# A simple keepalive script that will ensure a wineserver process is kept alive
# for the duration of the Protontricks session.
# This is accomplished by launching a simple Windows batch script that will
# run until it is prompted to close itself at the end of the Protontricks
# session.
set -o errexit

function cleanup () {
    # Remove the 'keepalive' file in the temp directory. This will prompt
    # the Wine process to stop execution.
    rm "$keepalive_dir/keepalive"
    if [[ -n "$keepalive_dir" && -d "$keepalive_dir" ]]; then
        rm -rf "$keepalive_dir"
    fi
}

temp_dir="${TMPDIR:-/tmp}"
keepalive_dir="$temp_dir/protontricks-keepalive-$PROTONTRICKS_SESSION_ID"
mkdir "$keepalive_dir"
touch "$keepalive_dir/keepalive"

trap cleanup EXIT HUP INT QUIT ABRT

cd "$keepalive_dir" || exit 1

while [[ -f "$keepalive_dir/keepalive" ]]; do
    wine cmd.exe /c "@@keepalive_bat_path@@" &>/dev/null
    if [[ -f "$keepalive_dir/keepalive" ]]; then
        # If 'keepalive' still exists, someone called 'wineserver -w'.
        # To prevent that command from stalling indefinitely, we need to
        # shut down this process temporarily until the waiting command
        # has terminated.
        wineserver_finished=false
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
    fi
done
