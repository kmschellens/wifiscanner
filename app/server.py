#!/usr/bin/env python3
"""Lokale, alleen-lezen resultatenserver. Alleen Python-standaardbibliotheek."""
import argparse
import hashlib
import http.server
import json
from pathlib import Path
import sys
import threading
import urllib.parse
import webbrowser

BASE = Path(__file__).resolve().parent
ROOT = BASE.parent
DATA_DIR = ROOT / 'data'
PROTOCOL = 2
INSTANCE = hashlib.sha256(str(ROOT).encode()).hexdigest()[:20]


class Handler(http.server.BaseHTTPRequestHandler):
    def send_bytes(self, raw, content_type):
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(raw)

    def send_json(self, value):
        self.send_bytes(json.dumps(value, ensure_ascii=False).encode(), 'application/json; charset=utf-8')

    def do_GET(self):
        path = urllib.parse.unquote(urllib.parse.urlsplit(self.path).path)
        if path == '/api/health':
            self.send_json({'app': 'wifi-kamermeting', 'protocol': PROTOCOL, 'instance': INSTANCE})
        elif path in ('/api/datasets', '/api/catalog'):
            files = sorted(
                (p for p in DATA_DIR.glob('*.json') if p.is_file() and not p.is_symlink()),
                key=lambda p: p.name.casefold(),
            )
            if path == '/api/datasets':
                self.send_json([p.name for p in files])
            else:
                catalog = []
                for file in files:
                    try:
                        stat = file.stat()
                        catalog.append({'name': file.name, 'revision': f'{stat.st_mtime_ns}-{stat.st_size}'})
                    except FileNotFoundError:
                        continue
                self.send_json(catalog)
        elif path in ('/', '/index.html'):
            self.send_bytes((BASE / 'index.html').read_bytes(), 'text/html; charset=utf-8')
        elif path == '/favicon.ico':
            self.send_response(204)
            self.end_headers()
        elif path.count('/') == 1 and path.lower().endswith('.json'):
            file = DATA_DIR / path[1:]
            if file.is_symlink() or file.resolve().parent != DATA_DIR.resolve() or not file.is_file():
                self.send_error(404, 'Meetbestand niet gevonden')
                return
            try:
                self.send_bytes(file.read_bytes(), 'application/json; charset=utf-8')
            except FileNotFoundError:
                self.send_error(404, 'Meetbestand niet gevonden')
        else:
            self.send_error(404, 'Pagina niet gevonden')

    def log_message(self, *_args):
        # De terminal blijft beschikbaar voor meten; geen netwerklog tussen de vragen.
        pass


def create_server(port=8765):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return http.server.ThreadingHTTPServer(('127.0.0.1', port), Handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('port', nargs='?', type=int, default=8765)
    parser.add_argument('--open', action='store_true')
    args = parser.parse_args()
    if args.port != 0 and not 1024 <= args.port <= 65535:
        parser.error('Gebruik een poortnummer tussen 1024 en 65535.')
    with create_server(args.port) as server:
        url = f'http://127.0.0.1:{server.server_port}'
        print(f'Resultaten: {url}', flush=True)
        if args.open:
            threading.Timer(0.25, webbrowser.open, args=(url,)).start()
        server.serve_forever()


if __name__ == '__main__':
    try:
        main()
    except OSError as error:
        sys.exit(f'Resultaten konden niet worden geopend: {error}')
    except KeyboardInterrupt:
        pass
