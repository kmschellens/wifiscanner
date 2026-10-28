#!/bin/bash
# macOS: starten vanaf iedere locatie, zonder extra Python-packages.
set -eu
DIR="$(cd "$(dirname "$0")" && pwd)"
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is nodig om automatisch JSON-bestanden uit deze map te tonen."
  echo "Installeer Python 3, of open index.html direct en selecteer de JSON-bestanden handmatig."
  exit 1
fi
if [[ $# -eq 0 ]]; then
  set -- 8765
elif [[ "$1" == '--open' ]]; then
  set -- 8765 --open
fi
exec python3 "$DIR/server.py" "$@"
