#!/bin/bash

set -euo pipefail

EXE="${1:?Usage: pin_sdk.sh <executable> [minos] [sdk]}"
MINOS="${2:-11.0}"
SDK="${3:-26.0}"

[ -f "$EXE" ] || { echo "pin_sdk: not a file: $EXE" >&2; exit 1; }
archs="$(lipo -archs "$EXE" 2>/dev/null)" || { echo "pin_sdk: not a Mach-O: $EXE" >&2; exit 1; }

echo "==> Pinning $(basename "$EXE") to macOS $MINOS / SDK $SDK on: $archs"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

set -- $archs
if [ "$#" -eq 1 ]; then
  # Thin binary
  vtool -set-build-version macos "$MINOS" "$SDK" -replace -output "$TMP/out" "$EXE"
else
  # Fat binary
  slices=()
  for arch in "$@"; do
    lipo "$EXE" -thin "$arch" -output "$TMP/$arch"
    vtool -set-build-version macos "$MINOS" "$SDK" -replace -output "$TMP/$arch.stamped" "$TMP/$arch"
    slices+=("$TMP/$arch.stamped")
  done
  lipo -create "${slices[@]}" -output "$TMP/out"
fi

cat "$TMP/out" > "$EXE"
codesign --force --sign - "$EXE"

echo "==> Result:"
for a in $archs; do
  printf '    %s: ' "$a"
  vtool -arch "$a" -show-build "$EXE" 2>/dev/null | awk '/cmd |sdk/{printf "%s ", $2} END{print ""}'
done
