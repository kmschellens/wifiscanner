#!/bin/bash
# Begeleide Wi-Fi multi-AP-meting voor macOS (compatibel met Bash 3.2).
# De terminalapp gebruikt een lokaal gecompileerde Swift CoreWLAN-helper.
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$DIR/.." && pwd)"
DATA_DIR="$ROOT/data"
RUNTIME_DIR="$ROOT/.runtime"
APP="$RUNTIME_DIR/WifiKamermeting.app"
DATASET=''
RESUME_FILE=''
RESUMING=0
SCANS=4
INTERVAL=2
MODE='run'
WIFI_INTERFACE=''
EXPECTED_SSID=''
PREVIOUS_ROOM=''
ROOM_COUNT=0
RAW=''
SCAN_PID=''

help() {
  cat <<'HELP'
Wi-Fi kamermeting voor alle accesspoints met hetzelfde SSID.

Normaal gebruik:
  ./start.sh

De begeleide terminalflow controleert eerst je Mac, toont daarna de instellingen
en leidt je met genummerde keuzes langs accesspoints en kamers.

Extra opties:
  ./start.sh meten [--scans 4] [--interval 2] [uitvoer.json]
  ./start.sh meten --resume bestaand-bestand.json
  ./start.sh controle

  --scans N       1 t/m 12 scans per kamer
  --interval N    0 t/m 30 seconden pauze tussen scans
  --resume PAD    ga verder in een bestaand meetbestand
  --check         controleer alleen CoreWLAN en macOS-toestemming
  --help          toon deze uitleg

Eenmalig zijn Apple Command Line Tools en locatietoegang voor
WifiKamermeting nodig. De meetgegevens blijven lokaal op deze Mac.
HELP
}

step() {
  printf '\n============================================================\n'
  printf 'Stap %s van 4 · %s\n' "$1" "$2"
  printf '============================================================\n'
}

error_with_help() {
  printf '\nNiet gelukt: %s\n' "$1" >&2
  printf 'Oplossing: %s\n' "$2" >&2
}

valid_scan_count() {
  [[ "$1" =~ ^([1-9]|1[0-2])$ ]]
}

valid_interval() {
  [[ "$1" =~ ^([0-9]|[12][0-9]|30)(\.[0-9]+)?$ ]]
}

estimate_seconds() {
  awk -v count="$1" -v pause="$2" 'BEGIN {
    printf "%.0f", (count * 2) + ((count - 1) * pause)
  }'
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --help|-h) help; exit 0 ;;
    --check) MODE='check'; shift ;;
    --resume)
      [[ $# -ge 2 ]] || { echo '--resume heeft een bestandsnaam nodig' >&2; exit 2; }
      RESUME_FILE=$2
      shift 2 ;;
    --scans)
      [[ $# -ge 2 ]] || { echo '--scans heeft een getal nodig' >&2; exit 2; }
      SCANS=$2
      shift 2 ;;
    --interval)
      [[ $# -ge 2 ]] || { echo '--interval heeft een getal nodig' >&2; exit 2; }
      INTERVAL=$2
      shift 2 ;;
    -*) echo "Onbekende optie: $1" >&2; help; exit 2 ;;
    *)
      [[ -z "$DATASET" ]] || { echo 'Eén uitvoerbestand toegestaan.' >&2; exit 2; }
      DATASET=$1
      shift ;;
  esac
done

[[ -z "$RESUME_FILE" || -z "$DATASET" ]] || {
  echo 'Gebruik óf --resume óf een nieuw uitvoerbestand, niet allebei.' >&2
  exit 2
}
valid_scan_count "$SCANS" || { echo '--scans moet 1 t/m 12 zijn' >&2; exit 2; }
valid_interval "$INTERVAL" || { echo '--interval moet 0 t/m 30 seconden zijn' >&2; exit 2; }

shortcut() {
  command -v shortcuts >/dev/null 2>&1 || return 0
  shortcuts run "$1" 2>/dev/null | awk 'NF { sub(/\r$/, ""); print; exit }' || true
}

bssid() {
  local value=$1
  if [[ "$value" =~ ^([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}$ ]]; then
    printf '%s' "$value" | tr '[:upper:]' '[:lower:]'
  fi
}

cleanup() {
  if [[ -n "$SCAN_PID" ]] && kill -0 "$SCAN_PID" 2>/dev/null; then
    kill "$SCAN_PID" 2>/dev/null || true
  fi
  [[ -z "$RAW" || ! -e "$RAW" ]] || rm -f "$RAW"
}
trap cleanup EXIT

run_scan() {
  local scan_count=${1:-$SCANS}
  local scan_interval=${2:-$INTERVAL}
  local estimate start_time elapsed
  estimate=$(estimate_seconds "$scan_count" "$scan_interval")
  RAW=$(mktemp "${TMPDIR:-/tmp}/wifi-corewlan.XXXXXX.json") || return 1
  # Start via LaunchServices: dit is nodig voor CoreWLAN SSID/BSSID-rechten.
  # Het app-proces schrijft zijn JSON rechtstreeks naar RAW.
  rm -f "$RAW"
  printf '\nMeetserie gestart: %s scan(s), %ss pauze, meestal minstens %ss.\n' \
    "$scan_count" "$scan_interval" "$estimate"
  open -W -n -a "$APP" --args --ssid "$EXPECTED_SSID" --interface "$WIFI_INTERFACE" \
    --count "$scan_count" --interval "$scan_interval" --output "$RAW" &
  SCAN_PID=$!
  start_time=$(date '+%s')
  while kill -0 "$SCAN_PID" 2>/dev/null; do
    elapsed=$(( $(date '+%s') - start_time ))
    printf '\r  Bezig · %ss verstreken · %s scan(s) gepland' "$elapsed" "$scan_count"
    sleep 1
  done
  printf '\r%-78s\r' ' '
  if wait "$SCAN_PID"; then
    SCAN_PID=''
  else
    SCAN_PID=''
    error_with_help 'de Wi-Fi-helper kon niet worden gestart.' \
      'Controleer Systeeminstellingen → Privacy en beveiliging → Locatievoorzieningen → WifiKamermeting.'
    return 1
  fi
  if [[ ! -s "$RAW" ]]; then
    error_with_help 'CoreWLAN gaf geen meetgegevens terug.' \
      'Geef WifiKamermeting locatietoegang en voer ./start.sh controle uit.'
    return 1
  fi
  if ! python3 -m json.tool "$RAW" >/dev/null 2>&1; then
    error_with_help 'CoreWLAN gaf ongeldige gegevens terug.' \
      'Voer ./start.sh controle uit en probeer daarna opnieuw.'
    return 1
  fi
  elapsed=$(( $(date '+%s') - start_time ))
  printf 'Meetserie afgerond in %ss.\n' "$elapsed"
}

identify_accesspoint() {
  printf '\nGa vlak bij het accesspoint staan en blijf daar tijdens de korte scan.\n'
  printf 'Druk Enter als je klaarstaat, of typ 2 om terug te gaan: '
  IFS= read -r answer || return 1
  [[ "$answer" != 2 ]] || return 0
  if ! run_scan 2 1; then
    echo 'Het accesspoint is niet benoemd. Je kunt het straks opnieuw proberen.'
    cleanup; RAW=''
    return 1
  fi
  if ! python3 "$DIR/dataset.py" identify "$DATASET" "$RAW"; then
    error_with_help 'de naam kon niet worden opgeslagen.' 'Probeer dezelfde identificatiescan opnieuw.'
    cleanup; RAW=''
    return 1
  fi
  cleanup; RAW=''
}

accesspoint_round() {
  printf '\nTijdens deze ronde geef je fysieke accesspoints herkenbare namen.\n'
  printf 'Verschillende radio’s van hetzelfde apparaat kun je samen selecteren.\n'
  while :; do
    printf '\n  [1] Accesspoint op deze plek identificeren\n'
    printf '  [2] Klaar met accesspoints\n'
    printf 'Keuze [1]: '
    IFS= read -r action || break
    action=${action:-1}
    case "$action" in
      1) identify_accesspoint || true ;;
      2) break ;;
      *) echo 'Kies 1 of 2.' ;;
    esac
  done
}

choose_existing_session() {
  local latest path answer
  if [[ -n "$RESUME_FILE" ]]; then
    return 0
  fi
  if [[ -n "$DATASET" ]]; then
    return 0
  fi

  shopt -s nullglob
  local datasets=("$DATA_DIR"/wifi-meting-*.json)
  shopt -u nullglob
  [[ ${#datasets[@]} -gt 0 ]] || return 0
  latest=${datasets[${#datasets[@]}-1]}

  printf '\nEr staat al een eerdere meetronde in deze map.\n'
  printf '  [1] Nieuwe meetronde starten\n'
  printf '  [2] Laatste meetronde hervatten (%s)\n' "$(basename "$latest")"
  printf '  [3] Een ander meetbestand hervatten\n'
  printf 'Keuze [1]: '
  IFS= read -r answer || exit 1
  answer=${answer:-1}
  case "$answer" in
    1) ;;
    2) RESUME_FILE=$latest ;;
    3)
      printf 'Pad naar het bestaande JSON-bestand: '
      IFS= read -r path || exit 1
      if [[ "$path" != /* ]]; then
        if [[ -f "$DATA_DIR/$path" ]]; then path="$DATA_DIR/$path"; else path="$PWD/$path"; fi
      fi
      RESUME_FILE=$path ;;
    *) echo 'Ongeldige keuze; er wordt een nieuwe meetronde gestart.' ;;
  esac
}

load_resume_session() {
  if [[ "$RESUME_FILE" != /* ]]; then
    if [[ -f "$DATA_DIR/$RESUME_FILE" ]]; then
      RESUME_FILE="$DATA_DIR/$RESUME_FILE"
    else
      RESUME_FILE="$PWD/$RESUME_FILE"
    fi
  fi
  if [[ ! -f "$RESUME_FILE" ]]; then
    error_with_help "het meetbestand bestaat niet: $RESUME_FILE" \
      'Controleer het pad achter --resume.'
    exit 1
  fi
  if ! python3 "$DIR/dataset.py" field "$RESUME_FILE" verwacht_ssid >/dev/null; then
    error_with_help 'het gekozen bestand is geen hervatbaar meetbestand.' \
      'Kies een JSON-bestand dat door deze applicatie is gemaakt.'
    exit 1
  fi
  DATASET=$RESUME_FILE
  EXPECTED_SSID=$(python3 "$DIR/dataset.py" field "$DATASET" verwacht_ssid)
  SCANS=$(python3 "$DIR/dataset.py" field "$DATASET" scans_per_kamer)
  INTERVAL=$(python3 "$DIR/dataset.py" field "$DATASET" interval_tussen_scans_seconden)
  ROOM_COUNT=$(python3 "$DIR/dataset.py" field "$DATASET" aantal_metingen)
  PREVIOUS_ROOM=$(python3 "$DIR/dataset.py" field "$DATASET" laatste_kamer)
  RESUMING=1
}

choose_ssid() {
  local detected=$1 answer
  if [[ -n "$detected" ]]; then
    while :; do
      printf '\nWelk netwerk wil je meten?\n'
      printf '  [1] Huidig netwerk: %s\n' "$detected"
      printf '  [2] Een ander SSID invoeren\n'
      printf '  [3] Stoppen\n'
      printf 'Keuze [1]: '
      IFS= read -r answer || exit 1
      answer=${answer:-1}
      case "$answer" in
        1) EXPECTED_SSID=$detected; break ;;
        2)
          printf 'SSID: '
          IFS= read -r EXPECTED_SSID || exit 1
          [[ -n "$EXPECTED_SSID" ]] && break
          echo 'Een SSID mag niet leeg zijn.' ;;
        3) echo 'Geen meting gestart.'; exit 0 ;;
        *) echo 'Kies 1, 2 of 3.' ;;
      esac
    done
  else
    printf '\nHet huidige SSID kon niet automatisch worden gelezen.\n'
    printf 'SSID dat je wilt meten: '
    IFS= read -r EXPECTED_SSID || exit 1
  fi
  [[ -n "$EXPECTED_SSID" ]] || { echo 'Een SSID is verplicht.' >&2; exit 1; }
}

edit_scan_settings() {
  local answer
  while :; do
    printf 'Aantal scans per kamer [%s]: ' "$SCANS"
    IFS= read -r answer || exit 1
    answer=${answer:-$SCANS}
    if valid_scan_count "$answer"; then SCANS=$answer; break; fi
    echo 'Voer een geheel getal van 1 t/m 12 in.'
  done
  while :; do
    printf 'Pauze tussen scans in seconden [%s]: ' "$INTERVAL"
    IFS= read -r answer || exit 1
    answer=${answer:-$INTERVAL}
    if valid_interval "$answer"; then INTERVAL=$answer; break; fi
    echo 'Voer een getal van 0 t/m 30 in.'
  done
}

confirm_new_session() {
  local answer estimate
  while :; do
    estimate=$(estimate_seconds "$SCANS" "$INTERVAL")
    printf '\nInstellingen\n'
    printf '  Netwerk: %s\n' "$EXPECTED_SSID"
    printf '  Scans per kamer: %s\n' "$SCANS"
    printf '  Pauze tussen scans: %ss\n' "$INTERVAL"
    printf '  Geschatte minimumduur per kamer: %ss\n' "$estimate"
    printf '\n  [1] Doorgaan met deze instellingen\n'
    printf '  [2] Scaninstellingen aanpassen\n'
    printf '  [3] Stoppen\n'
    printf 'Keuze [1]: '
    IFS= read -r answer || exit 1
    answer=${answer:-1}
    case "$answer" in
      1) break ;;
      2) edit_scan_settings ;;
      3) echo 'Geen meting gestart.'; exit 0 ;;
      *) echo 'Kies 1, 2 of 3.' ;;
    esac
  done
}

measure_room() {
  local room=$1 begin end ssid_before ssid_after ap_before ap_after
  begin=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
  ssid_before=$(shortcut 'WiFi-SSID')
  ap_before=$(bssid "$(shortcut 'WiFi-BSSID')")
  printf '\nKamer “%s” wordt gemeten. Blijf op dezelfde plek staan.\n' "$room"
  if ! run_scan; then
    echo 'Deze kamer is niet opgeslagen. Kies opnieuw om het nogmaals te proberen.'
    cleanup; RAW=''
    return 1
  fi
  ssid_after=$(shortcut 'WiFi-SSID')
  ap_after=$(bssid "$(shortcut 'WiFi-BSSID')")
  end=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
  if ! python3 "$DIR/dataset.py" add "$DATASET" "$RAW" "$room" "$begin" "$end" \
    "$ssid_before" "$ssid_after" "$ap_before" "$ap_after"; then
    error_with_help 'de kamer kon niet in het meetbestand worden opgeslagen.' \
      'Controleer of het bestand schrijfbaar is en probeer de kamer opnieuw.'
    cleanup; RAW=''
    return 1
  fi
  PREVIOUS_ROOM=$room
  ROOM_COUNT=$((ROOM_COUNT + 1))
  cleanup; RAW=''
}

room_round() {
  local answer room
  while :; do
    printf '\nKamermetingen opgeslagen: %s\n' "$ROOM_COUNT"
    printf '  [1] Nieuwe kamer meten\n'
    if [[ -n "$PREVIOUS_ROOM" ]]; then
      printf '  [2] Vorige kamer opnieuw meten (%s)\n' "$PREVIOUS_ROOM"
    else
      printf '  [2] Vorige kamer opnieuw meten (nog niet beschikbaar)\n'
    fi
    printf '  [3] Accesspoint identificeren of benoemen\n'
    printf '  [4] Meetronde afronden\n'
    printf 'Keuze [1]: '
    IFS= read -r answer || answer=4
    answer=${answer:-1}
    case "$answer" in
      1)
        printf 'Naam van de kamer: '
        IFS= read -r room || continue
        if [[ -z "$room" ]]; then
          echo 'Vul een kamernaam in.'
          continue
        fi
        measure_room "$room" || true ;;
      2)
        if [[ -z "$PREVIOUS_ROOM" ]]; then
          echo 'Er is nog geen vorige kamer om opnieuw te meten.'
        else
          measure_room "$PREVIOUS_ROOM" || true
        fi ;;
      3) identify_accesspoint || true ;;
      4) break ;;
      *) echo 'Kies 1, 2, 3 of 4.' ;;
    esac
  done
}

printf '\nWi-Fi Kamermeting\n'
printf 'Begeleide lokale meting · je meetgegevens verlaten deze Mac niet.\n'

mkdir -p "$DATA_DIR" "$RUNTIME_DIR"

step 1 'Mac en Wi-Fi controleren'
if [[ "$(uname -s)" != 'Darwin' ]]; then
  error_with_help 'deze meting werkt alleen op macOS.' 'Start het programma op de Mac waarmee je wilt meten.'
  exit 1
fi
command -v python3 >/dev/null 2>&1 || {
  error_with_help 'Python 3 ontbreekt.' 'Installeer Python 3 en start het programma opnieuw.'
  exit 1
}
command -v networksetup >/dev/null 2>&1 || {
  error_with_help 'het macOS-programma networksetup ontbreekt.' 'Controleer je macOS-installatie.'
  exit 1
}
WIFI_INTERFACE=$(networksetup -listallhardwareports | awk '
  /^Hardware Port: (Wi-Fi|AirPort)$/ { if (getline > 0 && $1 == "Device:") { print $2; exit } }
')
[[ -n "$WIFI_INTERFACE" ]] || {
  error_with_help 'er is geen Wi-Fi-interface gevonden.' 'Schakel Wi-Fi in en start het programma opnieuw.'
  exit 1
}

if [[ ! -x "$APP/Contents/MacOS/WifiKamermeting" \
   || "$DIR/WifiScan.swift" -nt "$APP/Contents/MacOS/WifiKamermeting" \
   || "$DIR/Info.plist" -nt "$APP/Contents/MacOS/WifiKamermeting" ]]; then
  printf 'De lokale Wi-Fi-helper wordt eenmalig gebouwd.\n'
  "$DIR/build-scanner.sh"
fi

ssid_from_shortcut=$(shortcut 'WiFi-SSID')
associated_ap=$(bssid "$(shortcut 'WiFi-BSSID')")
printf '✓ Python 3 gevonden\n'
printf '✓ Wi-Fi-interface: %s\n' "$WIFI_INTERFACE"
printf '✓ Verbonden SSID: %s\n' "${ssid_from_shortcut:-niet leesbaar}"
printf '✓ Verbonden accesspoint: %s\n' "${associated_ap:-niet leesbaar}"

if [[ "$MODE" == check ]]; then
  EXPECTED_SSID=$ssid_from_shortcut
  if [[ -z "$EXPECTED_SSID" ]]; then
    printf '\nSSID voor de testscan: '
    IFS= read -r EXPECTED_SSID || exit 1
  fi
  [[ -n "$EXPECTED_SSID" ]] || { echo 'Een SSID is verplicht.' >&2; exit 1; }
  run_scan 1 "$INTERVAL" || exit 1
  python3 - "$RAW" <<'PY'
import json, sys
v = json.load(open(sys.argv[1], encoding='utf-8'))
print('\nResultaat systeemcontrole')
print('  Toegang locatiediensten:', v.get('location_authorisatie', 'onbekend'))
for s in v.get('scans', []):
    print('  Verbonden:', s.get('verbonden_bssid'), '| RSSI:', s.get('verbonden_rssi_dbm'))
    for ap in s.get('aps', []):
        print('    AP:', ap['bssid'], 'RSSI:', ap['rssi_dbm'], 'dBm | kanaal:', ap.get('kanaal'))
    if not s.get('aps'):
        print('    Geen AP’s met leesbare BSSID gevonden.')
for w in v.get('waarschuwingen', []):
    print('  LET OP:', w)
PY
  exit 0
fi

choose_existing_session
if [[ -n "$RESUME_FILE" ]]; then
  load_resume_session
fi

step 2 'Meetronde instellen'
if [[ "$RESUMING" -eq 1 ]]; then
  printf 'Bestaande meetronde geladen.\n'
  printf '  Bestand: %s\n' "$(basename "$DATASET")"
  printf '  Netwerk: %s\n' "$EXPECTED_SSID"
  printf '  Eerder opgeslagen kamermetingen: %s\n' "$ROOM_COUNT"
  printf '  Instellingen: %s scans, %ss pauze\n' "$SCANS" "$INTERVAL"
  if [[ -n "$ssid_from_shortcut" && "$ssid_from_shortcut" != "$EXPECTED_SSID" ]]; then
    printf '\nLET OP: je Mac is nu verbonden met “%s”, niet met “%s”.\n' \
      "$ssid_from_shortcut" "$EXPECTED_SSID"
  fi
  printf '\n  [1] Deze meetronde hervatten\n'
  printf '  [2] Stoppen\n'
  printf 'Keuze [1]: '
  IFS= read -r answer || exit 1
  answer=${answer:-1}
  [[ "$answer" == 1 ]] || { echo 'Geen meting gestart.'; exit 0; }
else
  choose_ssid "$ssid_from_shortcut"
  confirm_new_session
  if [[ -n "$DATASET" && "$DATASET" != /* ]]; then
    case "$DATASET" in
      */*) DATASET="$PWD/$DATASET" ;;
      *) DATASET="$DATA_DIR/$DATASET" ;;
    esac
  fi
  DATASET=${DATASET:-"$DATA_DIR/wifi-meting-$(date '+%Y%m%d-%H%M%S').json"}
  if [[ -e "$DATASET" ]]; then
    error_with_help "het uitvoerbestand bestaat al: $DATASET" \
      'Gebruik --resume om verder te gaan, of kies een andere bestandsnaam.'
    exit 1
  fi
  python3 "$DIR/dataset.py" init "$DATASET" "$EXPECTED_SSID" "$WIFI_INTERFACE" "$SCANS" "$INTERVAL"
  printf '\nNieuwe meetronde aangemaakt: %s\n' "$(basename "$DATASET")"
fi

step 3 'Accesspoints voorbereiden'
printf 'Je kunt accesspoints nu herkenbare namen geven, of dit later doen.\n'
printf '  [1] Meteen kamers gaan meten\n'
printf '  [2] Eerst accesspoints identificeren\n'
printf 'Keuze [1]: '
IFS= read -r identify_answer || identify_answer=1
identify_answer=${identify_answer:-1}
case "$identify_answer" in
  2) accesspoint_round ;;
  1) ;;
  *) echo 'Ongeldige keuze; de accesspointronde wordt overgeslagen.' ;;
esac

step 4 'Kamers meten'
printf 'Kies steeds een actie. Na iedere geslaagde kamer wordt het JSON-bestand direct opgeslagen.\n'
room_round

python3 "$DIR/dataset.py" summary "$DATASET"
printf '\nWat wil je nu doen?\n'
printf '  [1] Dashboard openen\n'
printf '  [2] Afsluiten\n'
printf 'Keuze [1]: '
IFS= read -r finish_answer || finish_answer=2
finish_answer=${finish_answer:-1}
if [[ "$finish_answer" == 1 ]]; then
  printf '\nHet dashboard wordt in je browser geopend.\n'
  printf 'Laat dit terminalvenster open; stop de dashboardserver later met Ctrl+C.\n\n'
  exec "$ROOT/start.sh" dashboard
fi
printf '\nKlaar. Je meting staat in:\n%s\n' "$DATASET"
