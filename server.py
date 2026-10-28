#!/usr/bin/env python3
"""Lokaal dashboardserver voor Wi-Fi kamermetingen. Geen externe modules."""
import http.server
import json
import os
from pathlib import Path
import sys
import threading
import webbrowser

BASE = Path(__file__).resolve().parent


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(BASE), **kwargs)

    def do_GET(self):
        if self.path.split('?', 1)[0] == '/api/datasets':
            names = sorted(
                (p.name for p in BASE.iterdir() if p.is_file() and p.suffix.lower() == '.json'),
                key=str.casefold,
            )
            raw = json.dumps(names, ensure_ascii=False).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(raw)
            return
        super().do_GET()

    def end_headers(self):
        if self.path.split('?', 1)[0].lower().endswith('.json'):
            self.send_header('Cache-Control', 'no-store')
        super().end_headers()


if __name__ == '__main__':
    arguments = sys.argv[1:]
    open_browser = '--open' in arguments
    arguments = [argument for argument in arguments if argument != '--open']
    if len(arguments) > 1:
        sys.exit('Gebruik: ./start.sh [poort] [--open]')
    try:
        port = int(arguments[0]) if arguments else 8765
    except ValueError:
        sys.exit('Gebruik: ./start.sh [poort] [--open]')
    if not (1024 <= port <= 65535):
        sys.exit('Gebruik een poortnummer tussen 1024 en 65535.')
    try:
        with http.server.ThreadingHTTPServer(('127.0.0.1', port), Handler) as server:
            url = f'http://127.0.0.1:{port}'
            print(f'Wi-Fi dashboard: {url}', flush=True)
            print(f'Map met JSON-bestanden: {BASE}', flush=True)
            print('Stop met Ctrl+C. Er is geen internetverbinding nodig.', flush=True)
            if open_browser:
                threading.Timer(0.25, webbrowser.open, args=(url,)).start()
            server.serve_forever()
    except OSError as e:
        sys.exit(f'Kan server niet starten: {e}. Probeer een andere poort, bv. ./start.sh 8766')
    except KeyboardInterrupt:
        print('\nServer gestopt.')
