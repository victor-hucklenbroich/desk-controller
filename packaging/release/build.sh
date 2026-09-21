#!/bin/bash
# Distribution build.

set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/build_common.sh"

VERSION="$(dc_app_version)"
ZIP_PATH="$DC_REPO_ROOT/dist/DeskController-${VERSION}.zip"

# Fail before the long build if the toolchain or credentials are missing.
dc_require_universal2_toolchain
dc_resolve_developer_id
dc_resolve_notary_args

echo "==> Releasing DeskController $VERSION"
dc_build universal2
dc_verify_universal
dc_pin_sdk
dc_sign "$SIGN_ID"
dc_zip "$ZIP_PATH"
dc_notarize "$ZIP_PATH"
dc_gatekeeper

echo "==> Re-zipping the stapled app for distribution"
dc_zip "$ZIP_PATH"

echo
echo "Done. Distribution artifact:"
echo "  $ZIP_PATH"
echo
echo "sha256 for the cask:"
shasum -a 256 "$ZIP_PATH"
echo
