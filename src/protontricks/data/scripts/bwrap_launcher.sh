#!/bin/bash
# Helper script
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

log_info "Following directories will be mounted inside container: ${mount_dirs[*]}"
log_info "Using temporary directory: $PROTONTRICKS_TEMP_PATH"

exec "$STEAM_RUNTIME_PATH"/run --share-pid --launcher \
"${mount_params[@]}" -- \
--bus-name="com.github.Matoking.protontricks.App${STEAM_APPID}_${PROTONTRICKS_SESSION_ID}"
