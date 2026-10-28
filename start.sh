#!/bin/bash
# Centrale launcher voor de Wi-Fi-meting, controle, helper en het dashboard.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$ROOT/app"
DATA_DIR="$ROOT/data"
RUNTIME_DIR="$ROOT/.runtime"

mkdir -p "$DATA_DIR" "$RUNTIME_DIR"

usage() {
  cat <<'HELP'
Wi-Fi Kamermeting

Start zonder argumenten voor het hoofdmenu:
  ./start.sh

Of kies direct een onderdeel:
  ./start.sh meten [opties]       begeleide Wi-Fi-meting
  ./start.sh dashboard [poort]    lokaal dashboard openen
  ./start.sh controle             Wi-Fi en macOS-toestemming testen
  ./start.sh bouwen               lokale CoreWLAN-helper opnieuw bouwen
  ./start.sh help                 deze uitleg tonen

Meetbestanden worden lokaal in data/ opgeslagen.
HELP
}

need_python() {
  if ! command -v python3 >/dev/null 2>&1; then
    echo 'Python 3 is nodig voor dit onderdeel.' >&2
    echo 'Installeer Python 3 en start ./start.sh daarna opnieuw.' >&2
    exit 1
  fi
}

run_measurement() {
  exec "$APP_DIR/wifi-kamermeting.sh" "$@"
}

run_dashboard() {
  local port=${1:-8765}
  need_python
  exec python3 "$APP_DIR/server.py" "$port" --open
}

run_check() {
  exec "$APP_DIR/wifi-kamermeting.sh" --check
}

run_build() {
  "$APP_DIR/build-scanner.sh"
}

if [[ $# -gt 0 ]]; then
  command=$1
  shift
  case "$command" in
    meten|measurement|measure) run_measurement "$@" ;;
    dashboard|server) run_dashboard "$@" ;;
    controle|check) run_check ;;
    bouwen|build) run_build ;;
    help|--help|-h) usage ;;
    --open) run_dashboard "$@" ;; # compatibel met de vorige startopdracht
    ''|*[!0-9]*)
      echo "Onbekend onderdeel: $command" >&2
      usage
      exit 2 ;;
    *) run_dashboard "$command" ;; # compatibel met: ./start.sh 8766
  esac
  exit 0
fi

while :; do
  printf '\n============================================================\n'
  printf 'Wi-Fi Kamermeting\n'
  printf '============================================================\n'
  printf '  [1] Wi-Fi-meting starten of hervatten\n'
  printf '  [2] Dashboard openen\n'
  printf '  [3] Wi-Fi en macOS-toestemming controleren\n'
  printf '  [4] CoreWLAN-helper opnieuw bouwen\n'
  printf '  [5] Uitleg tonen\n'
  printf '  [6] Afsluiten\n'
  printf 'Keuze [1]: '
  IFS= read -r choice || choice=6
  choice=${choice:-1}
  case "$choice" in
    1) run_measurement ;;
    2) run_dashboard ;;
    3) run_check ;;
    4)
      run_build
      printf '\nDe helper is opnieuw gebouwd.\n' ;;
    5)
      usage
      printf '\nUitgebreide uitleg: docs/LEESMIJ.md\n' ;;
    6) printf 'Tot ziens.\n'; exit 0 ;;
    *) printf 'Kies 1, 2, 3, 4, 5 of 6.\n' ;;
  esac
done
