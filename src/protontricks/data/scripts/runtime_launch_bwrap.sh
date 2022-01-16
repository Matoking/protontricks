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

if [[ -n "$PROTONTRICKS_INSIDE_STEAM_RUNTIME" ]]; then
  # Command is being executed inside Steam Runtime
  # LD_LIBRARY_PATH can now be set.
  export LD_LIBRARY_PATH="$LD_LIBRARY_PATH":"$PROTON_LD_LIBRARY_PATH"
  "$PROTON_DIST_PATH"/bin/@@name@@ "$@"
else
  exec "$STEAM_RUNTIME_PATH"/run --share-pid --batch \
  "${mount_params[@]}" -- \
  env PROTONTRICKS_INSIDE_STEAM_RUNTIME=1 \
  "$PROTONTRICKS_PROXY_SCRIPT_PATH" "$@"
fi

