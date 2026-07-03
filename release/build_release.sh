#!/bin/bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_NAME="DeskController.app"
DIST_PATH="$REPO_ROOT/dist/$APP_NAME"
SPEC_FILE="$REPO_ROOT/app.spec"
ENTITLEMENTS="$REPO_ROOT/release/entitlements.plist"

VERSION="$(python3 -c "import re,pathlib;print(re.search(r'VERSION:\s*str\s*=\s*\"v?([0-9.]+)\"', pathlib.Path('$REPO_ROOT/desk_controller/constants.py').read_text()).group(1))")"
ZIP_NAME="DeskController-${VERSION}.zip"
ZIP_PATH="$REPO_ROOT/dist/$ZIP_NAME"

: "${SIGN_ID:?Set SIGN_ID to your 'Developer ID Application: ...' identity}"

if [ -n "${NOTARY_PROFILE:-}" ]; then
  NOTARY_ARGS=(--keychain-profile "$NOTARY_PROFILE")
elif [ -n "${APPLE_ID:-}" ] && [ -n "${APPLE_TEAM_ID:-}" ] && [ -n "${APPLE_APP_SPECIFIC_PASSWORD:-}" ]; then
  NOTARY_ARGS=(--apple-id "$APPLE_ID" --team-id "$APPLE_TEAM_ID" --password "$APPLE_APP_SPECIFIC_PASSWORD")
else
  echo "Set NOTARY_PROFILE, or APPLE_ID + APPLE_TEAM_ID + APPLE_APP_SPECIFIC_PASSWORD" >&2
  exit 1
fi

echo "==> Building $APP_NAME (version $VERSION)"
DC_TARGET_ARCH=universal2 pyinstaller --noconfirm "$SPEC_FILE"
[ -d "$DIST_PATH" ] || { echo "Build did not produce $DIST_PATH"; exit 1; }

echo "==> Verifying the bundle is universal (x86_64 + arm64)"
thin_binaries=""
while IFS= read -r -d '' bin; do
  archs="$(lipo -archs "$bin" 2>/dev/null)" || continue  # not a Mach-O file
  case "$archs" in
    *x86_64*arm64*|*arm64*x86_64*) ;;
    *) thin_binaries="${thin_binaries}${bin} (${archs})"$'\n' ;;
  esac
done < <(find "$DIST_PATH" -type f \( -perm +111 -o -name '*.so' -o -name '*.dylib' \) -print0)
if [ -n "$thin_binaries" ]; then
  printf 'Binaries missing an architecture slice:\n%s' "$thin_binaries" >&2
  exit 1
fi

echo "==> Code signing"
codesign --force --deep --options runtime --timestamp \
  --entitlements "$ENTITLEMENTS" \
  --sign "$SIGN_ID" \
  "$DIST_PATH"

echo "==> Verifying signature"
codesign --verify --deep --strict --verbose=2 "$DIST_PATH"

echo "==> Zipping for notarization"
rm -f "$ZIP_PATH"
ditto -c -k --keepParent "$DIST_PATH" "$ZIP_PATH"

echo "==> Submitting to Apple notary service (this can take a few minutes)"
xcrun notarytool submit "$ZIP_PATH" "${NOTARY_ARGS[@]}" --wait

echo "==> Stapling the notarization ticket to the app"
xcrun stapler staple "$DIST_PATH"
xcrun stapler validate "$DIST_PATH"

echo "==> Gatekeeper assessment"
spctl --assess --type execute --verbose=4 "$DIST_PATH" || true

echo "==> Re-zipping the STAPLED app for distribution"
rm -f "$ZIP_PATH"
ditto -c -k --keepParent "$DIST_PATH" "$ZIP_PATH"

echo
echo "Done. Distribution artifact:"
echo "  $ZIP_PATH"
echo
echo "sha256 for the cask:"
shasum -a 256 "$ZIP_PATH"
echo
