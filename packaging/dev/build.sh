#!/bin/bash
# Local development build.

set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/build_common.sh"

dc_build            # native architecture
dc_pin_sdk
dc_sign -           # ad-hoc signature

echo
echo "Done. Local build:"
echo "  $DIST_PATH"
echo
echo "Ad-hoc signed for local use only; not universal2 and not notarized."
