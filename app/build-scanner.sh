#!/bin/bash
# Bouwt een eigen macOS .app met CoreWLAN-scan en Location Services.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$DIR/.." && pwd)"
RUNTIME_DIR="$ROOT/.runtime"
APP="$RUNTIME_DIR/WifiKamermeting.app"
if [[ "$(uname -s)" != Darwin ]]; then echo 'Deze build werkt alleen op macOS.' >&2; exit 1; fi
if ! xcrun --find swiftc >/dev/null 2>&1; then
  echo 'Apple Command Line Tools zijn nodig. Start: xcode-select --install' >&2
  exit 1
fi
mkdir -p "$RUNTIME_DIR" "$APP/Contents/MacOS"
cp "$DIR/Info.plist" "$APP/Contents/Info.plist"
echo 'CoreWLAN-helper compileren (eenmalig)...'
xcrun swiftc -parse-as-library -O "$DIR/WifiScan.swift" -framework CoreWLAN -framework CoreLocation -framework AppKit \
  -o "$APP/Contents/MacOS/WifiKamermeting"
# Geen betaalde Developer-account nodig. Ad-hoc signing kan eenmalig om nieuwe toestemming vragen.
codesign --force --sign - "$APP" >/dev/null
printf 'Klaar: %s\n' "$APP"
