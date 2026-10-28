#!/bin/bash
# Eén startpunt; de app verzorgt voorbereiding, metingen en resultaten.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
if ! command -v python3 >/dev/null 2>&1; then
  printf 'Voor Wi-Fi Kamermeting is Python 3 nodig.\nInstalleer Python 3 en open ./start.sh opnieuw.\n' >&2
  exit 1
fi
exec python3 "$ROOT/app/launcher.py" "$@"
