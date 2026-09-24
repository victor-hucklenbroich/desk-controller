#!/bin/bash
# Shared build steps for the DeskController app bundle.
#
# Sourced by packaging/dev/build.sh and packaging/release/build.sh; not meant to
# be run directly. Both wrappers run the same core process (build -> pin SDK ->
# sign); the release wrapper adds the distribution-only steps (universal2,
# notarization, stapling, zipping). Callers must `set -euo pipefail` first.

DC_PACKAGING_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DC_REPO_ROOT="$(cd "$DC_PACKAGING_DIR/.." && pwd)"

APP_NAME="DeskController.app"
DIST_PATH="$DC_REPO_ROOT/dist/$APP_NAME"
SPEC_FILE="$DC_REPO_ROOT/app.spec"
ENTITLEMENTS="$DC_PACKAGING_DIR/entitlements.plist"

# Prefer the dedicated universal2 build venv's tools when it is present.
DC_VENV="${DC_VENV:-$DC_REPO_ROOT/.venv-build}"
if [ -x "$DC_VENV/bin/pyinstaller" ]; then
  PATH="$DC_VENV/bin:$PATH"
fi

dc_app_version() {
  python3 -c "import re,pathlib;print(re.search(r'VERSION:\s*str\s*=\s*\"v?([0-9.]+)\"', pathlib.Path('$DC_REPO_ROOT/desk_controller/constants.py').read_text()).group(1))"
}

# Release-only: fail early if the interpreter can't produce a universal2 bundle.
dc_require_universal2_toolchain() {
  local platform
  platform="$(python3 -c 'import sysconfig; print(sysconfig.get_platform())')"
  case "$platform" in
    *universal2*) ;;
    *)
      echo "The build interpreter is '$platform', not universal2:" >&2
      echo "  $(command -v python3)" >&2
      echo "Create the universal2 build venv first (see README)." >&2
      exit 1
      ;;
  esac

  if python3 -c 'import sys, yaml; sys.exit(0 if yaml.__with_libyaml__ else 1)'; then
    echo "PyYAML in $(command -v python3) was installed with the libyaml extension," >&2
    echo "which is single-arch and breaks the universal2 build. Reinstall it as pure Python:" >&2
    echo "  PYYAML_FORCE_LIBYAML=0 pip install --no-binary PyYAML --force-reinstall --no-cache-dir --no-deps PyYAML" >&2
    exit 1
  fi
}

# Build the .app bundle. Pass "universal2" to force a fat binary; anything else
# (or nothing) builds for the current interpreter's native architecture.
dc_build() {
  local target_arch="${1:-}"
  echo "==> Building $APP_NAME (${target_arch:-native}) with $(command -v python3)"
  DC_TARGET_ARCH="$target_arch" pyinstaller --noconfirm "$SPEC_FILE"
  [ -d "$DIST_PATH" ] || { echo "Build did not produce $DIST_PATH" >&2; exit 1; }
}

# Release-only: confirm every Mach-O in the bundle carries both arch slices.
dc_verify_universal() {
  echo "==> Verifying the bundle is universal (x86_64 + arm64)"
  local thin_binaries="" bin archs
  while IFS= read -r -d '' bin; do
    archs="$(xcrun lipo -archs "$bin" 2>/dev/null)" || continue  # not a Mach-O file
    case "$archs" in
      *x86_64*arm64*|*arm64*x86_64*) ;;
      *) thin_binaries="${thin_binaries}${bin} (${archs})"$'\n' ;;
    esac
  done < <(find "$DIST_PATH" -type f \( -perm +111 -o -name '*.so' -o -name '*.dylib' \) -print0)
  if [ -n "$thin_binaries" ]; then
    printf 'Binaries missing an architecture slice:\n%s' "$thin_binaries" >&2
    exit 1
  fi
}

# Pin the linked SDK so the app's AppKit appearance matches a release build.
dc_pin_sdk() {
  echo "==> Pinning the executable's linked SDK for a deterministic appearance"
  "$DC_PACKAGING_DIR/pin_sdk.sh" "$DIST_PATH/Contents/MacOS/DeskController"
}

# Code-sign the whole bundle with the hardened runtime and our entitlements.
# Pass a Developer ID identity for a release, or "-" for an ad-hoc dev signature
# (a secure timestamp is only meaningful for a real identity).
dc_sign() {
  local sign_id="${1:?dc_sign needs a signing identity ('-' for ad-hoc)}"
  local timestamp_arg="--timestamp"
  [ "$sign_id" = "-" ] && timestamp_arg="--timestamp=none"

  echo "==> Code signing ($sign_id)"
  codesign --force --deep --options runtime "$timestamp_arg" \
    --entitlements "$ENTITLEMENTS" \
    --sign "$sign_id" \
    "$DIST_PATH"

  echo "==> Verifying signature"
  codesign --verify --deep --strict --verbose=2 "$DIST_PATH"
}

# Release-only: resolve a Developer ID Application identity into SIGN_ID.
dc_resolve_developer_id() {
  if [ -z "${SIGN_ID:-}" ]; then
    SIGN_ID="$(security find-identity -v -p codesigning \
      | awk -F'"' '/Developer ID Application/{print $2; exit}')" || true
  fi
  : "${SIGN_ID:?No 'Developer ID Application' identity found; set SIGN_ID explicitly}"
}

# Release-only: resolve notarytool credentials from the environment into
# DC_NOTARY_ARGS.
dc_resolve_notary_args() {
  if [ -n "${NOTARY_PROFILE:-}" ]; then
    DC_NOTARY_ARGS=(--keychain-profile "$NOTARY_PROFILE")
  elif [ -n "${APPLE_ID:-}" ] && [ -n "${APPLE_TEAM_ID:-}" ] && [ -n "${APPLE_APP_SPECIFIC_PASSWORD:-}" ]; then
    DC_NOTARY_ARGS=(--apple-id "$APPLE_ID" --team-id "$APPLE_TEAM_ID" --password "$APPLE_APP_SPECIFIC_PASSWORD")
  else
    echo "Set NOTARY_PROFILE, or APPLE_ID + APPLE_TEAM_ID + APPLE_APP_SPECIFIC_PASSWORD" >&2
    echo "(or use packaging/dev/build.sh for an unnotarized local build)" >&2
    exit 1
  fi
}

dc_zip() {
  local zip_path="${1:?dc_zip needs a destination path}"
  echo "==> Zipping"
  rm -f "$zip_path"
  ditto -c -k --keepParent "$DIST_PATH" "$zip_path"
}

# Release-only: notarize the zip and staple the ticket onto the bundle.
dc_notarize() {
  local zip_path="${1:?dc_notarize needs the submitted zip path}"
  echo "==> Submitting to Apple notary service (this can take a few minutes)"
  xcrun notarytool submit "$zip_path" "${DC_NOTARY_ARGS[@]}" --wait

  echo "==> Stapling the notarization ticket to the app"
  xcrun stapler staple "$DIST_PATH"
  xcrun stapler validate "$DIST_PATH"
}

dc_gatekeeper() {
  echo "==> Gatekeeper assessment"
  spctl --assess --type execute --verbose=4 "$DIST_PATH" || true
}
