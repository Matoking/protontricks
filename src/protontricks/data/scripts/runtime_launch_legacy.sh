#!/bin/bash
# Helper script created by Protontricks to run Wine binaries using Steam Runtime
export LD_LIBRARY_PATH="$PROTON_LD_LIBRARY_PATH"
exec "$PROTON_DIST_PATH"/bin/@@name@@ "$@"
