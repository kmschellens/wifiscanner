#!/usr/bin/env python3
"""Beheert de voorbereiding en de rustige terminalflow van Wi-Fi Kamermeting."""
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
import webbrowser

try:
    from . import server
except ImportError:
    import server

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / 'app'
RUNTIME = ROOT / '.runtime'
SCANNER = RUNTIME / 'WifiKamermeting.app' / 'Contents' / 'MacOS' / 'WifiKamermeting'
SOURCES = [APP_DIR / name for name in ('WifiScan.swift', 'Info.plist', 'build-scanner.sh')]
LOCAL_HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def choose(prompt, choices, default):
    while True:
        try:
            answer = input(f'{prompt} [{default}]: ').strip() or default
        except EOFError:
            return None
        if answer in choices:
            return answer
        print('Kies ' + ', '.join(choices[:-1]) + ' of ' + choices[-1] + '.')


def scanner_needs_build():
    if not SCANNER.is_file() or not os.access(SCANNER, os.X_OK):
        return True
    built = SCANNER.stat().st_mtime_ns
    return any(source.stat().st_mtime_ns > built for source in SOURCES)


def prepare_scanner(force=False):
    if platform.system() != 'Darwin':
        print('Meten is beschikbaar op een Mac. Je kunt hier wel resultaten bekijken.')
        return False
    if not force and not scanner_needs_build():
        return True
    print('De Wi-Fi-scanner wordt voorbereid. Dit hoeft alleen bij de eerste start of een update.', flush=True)
    RUNTIME.mkdir(parents=True, exist_ok=True)
    log_path = RUNTIME / 'build.log'
    with log_path.open('w', encoding='utf-8') as log:
        result = subprocess.run(['bash', str(APP_DIR / 'build-scanner.sh')], stdout=log, stderr=log)
    if result.returncode:
        print('De scanner is nog niet klaar. Resultaten bekijken kan wel.')
        print('Controleer of Apple Command Line Tools zijn geïnstalleerd: xcode-select --install')
        print('Via Meer opties kun je de voorbereiding opnieuw proberen.')
        return False
    print('De Wi-Fi-scanner is klaar.')
    return True


def matching_server(port):
    try:
        with LOCAL_HTTP.open(f'http://127.0.0.1:{port}/api/health', timeout=0.5) as response:
            health = json.load(response)
        if not isinstance(health, dict):
            return False
        return (health.get('app') == 'wifi-kamermeting'
                and health.get('instance') == server.INSTANCE
                and health.get('protocol') == server.PROTOCOL)
    except (OSError, ValueError, urllib.error.URLError):
        return False


class ResultsServer:
    """Een eigen server opruimen; een server van een ander venster met rust laten."""
    def __init__(self):
        self.httpd = None
        self.thread = None
        self.port = None

    @property
    def url(self):
        return f'http://127.0.0.1:{self.port}'

    def start(self, preferred=8765):
        if self.httpd is not None and self.thread.is_alive():
            return
        if self.port is not None and matching_server(self.port):
            return
        if matching_server(preferred):
            self.port = preferred
            return
        try:
            self.httpd = server.create_server(preferred)
        except OSError as error:
            import errno
            if error.errno != errno.EADDRINUSE:
                raise
            self.httpd = server.create_server(0)
        self.port = self.httpd.server_port
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        if self.httpd is not None:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.thread.join(timeout=2)
            self.httpd = None

    def open(self, dataset=None):
        self.start()
        url = self.url
        if dataset:
            url += '?meting=' + urllib.parse.quote(dataset)
        if not webbrowser.open(url):
            print(f'Open in je browser: {url}')
        print('Je resultaten staan in de browser. Nieuwe metingen verschijnen daar vanzelf.')
        print('Ga hier in Terminal verder om kamers te meten.')


def run_measurement(results, args=(), check=False):
    if not prepare_scanner():
        return
    results.start()
    environment = dict(os.environ, WIFI_APP_MANAGED='1', WIFI_SCANNER_READY='1',
                       WIFI_DASHBOARD_URL=results.url)
    if check:
        args = ['--check']
    command = ['bash', str(APP_DIR / 'wifi-kamermeting.sh'), *args]
    status = subprocess.run(command, env=environment).returncode
    if status not in (0, 130):
        print('\nDe meetronde is gestopt. Eerder opgeslagen kamers zijn bewaard.')


def more_options(results):
    while True:
        print('\nMeer opties\n')
        print('  1  Wi-Fi en locatietoegang controleren')
        print('  2  Scanner opnieuw voorbereiden')
        print('  3  Uitleg')
        print('  4  Terug')
        choice = choose('Keuze', ['1', '2', '3', '4'], '4')
        if choice == '1':
            run_measurement(results, check=True)
        elif choice == '2':
            prepare_scanner(force=True)
        elif choice == '3':
            print('\nMeten doe je hier in Terminal: loop met je Mac naar elke kamer.')
            print('De browser toont je opgeslagen resultaten en werkt vanzelf bij.')
            print('Laat dit venster open terwijl je de resultaten bekijkt.')
            print('Bij Stoppen wordt de lokale resultatenserver gesloten.')
            print('Je metingen blijven bewaard en kun je later hervatten.')
            print('Uitgebreide uitleg: docs/LEESMIJ.md')
        else:
            return


def usage():
    print('Wi-Fi Kamermeting\n')
    print('  ./start.sh                         start de app')
    print('  ./start.sh meten [opties]          start direct een meetronde')
    print('  ./start.sh meten --resume naam.json')
    print('  ./start.sh meten --scans 6 --interval 3')
    print('  ./start.sh dashboard [poort]       open je resultaten')
    print('  ./start.sh controle                controleer de Wi-Fi-scanner')
    print('\nDe app bereidt de scanner en de resultatenserver automatisch voor.')


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    action = args.pop(0) if args else ''
    if action in ('help', '--help', '-h'):
        usage()
        return 0
    if action in ('meten', 'measure', 'measurement') and any(arg in ('--help', '-h') for arg in args):
        return subprocess.run(['bash', str(APP_DIR / 'wifi-kamermeting.sh'), '--help']).returncode
    aliases = {'measure': 'meten', 'measurement': 'meten', 'server': 'dashboard',
               '--open': 'dashboard', 'check': 'controle', 'build': 'bouwen'}
    action = aliases.get(action, action)
    if action.isdigit():
        args.insert(0, action)
        action = 'dashboard'
    if action not in ('', 'meten', 'dashboard', 'controle', 'bouwen'):
        print(f'Onbekende opdracht: {action}', file=sys.stderr)
        usage()
        return 2
    port = 8765
    if action == 'dashboard':
        args = [arg for arg in args if arg != '--open']
        if len(args) > 1 or (args and not args[0].isdigit()):
            print('Gebruik: ./start.sh dashboard [poort]', file=sys.stderr)
            return 2
        port = int(args[0]) if args else port
        if not 1024 <= port <= 65535:
            print('Gebruik een poortnummer tussen 1024 en 65535.', file=sys.stderr)
            return 2
    for directory in (ROOT / 'data', RUNTIME):
        directory.mkdir(parents=True, exist_ok=True)
    results = ResultsServer()
    print('\nWi-Fi Kamermeting\n', flush=True)
    try:
        results.start(port)
        if action not in ('bouwen',):
            prepare_scanner()
        print('\nMeten doe je hier in Terminal.')
        print('Resultaten bekijk je in je browser; die worden automatisch bijgewerkt.')
        print('Alles blijft lokaal. Laat dit venster open zolang je de app gebruikt.')
        default = '1'
        if action == 'meten':
            run_measurement(results, args)
            default = '2'
        elif action == 'controle':
            run_measurement(results, check=True)
        elif action == 'bouwen':
            prepare_scanner(force=True)
        elif action == 'dashboard':
            results.open()
            default = '2'
        while True:
            print('\nWat wil je doen?\n')
            print('  1  Kamers meten')
            print('  2  Resultaten bekijken')
            print('  3  Meer opties')
            print('  4  Stoppen')
            choice = choose('Keuze', ['1', '2', '3', '4'], default)
            if choice == '1':
                run_measurement(results)
                default = '2'
            elif choice == '2':
                results.open()
            elif choice == '3':
                more_options(results)
            else:
                break
    except KeyboardInterrupt:
        print('\n')
    except OSError as error:
        print(f'De app kon niet worden gestart: {error}', file=sys.stderr)
        return 1
    finally:
        results.close()
    print('De app is gesloten. Je metingen zijn bewaard.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
