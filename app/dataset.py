#!/usr/bin/env python3
"""JSON-opslag en samenvatting per BSSID. Alleen Python-standaardbibliotheek."""
import collections
import datetime
import json
import os
from pathlib import Path
import sys
import tempfile


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def normal_bssid(v):
    if not isinstance(v, str):
        return None
    p = v.strip().lower().split(':')
    if len(p) == 6 and all(len(s) == 2 and all(c in '0123456789abcdef' for c in s) for s in p):
        return ':'.join(p)
    return None


def integer_rssi(v):
    if isinstance(v, bool) or not isinstance(v, int):
        return None
    return v if -110 <= v <= -1 else None


def one_decimal(values):
    return round(sum(values) / len(values), 1) if values else None


def atomic_write(path, data):
    path = Path(path).resolve()
    tmp = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent, prefix=path.name + '.', suffix='.tmp', delete=False) as f:
            tmp = f.name
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write('\n')
        os.replace(tmp, path)
    finally:
        if tmp and os.path.exists(tmp):
            os.unlink(tmp)


def init_file(path, ssid, interface, n, interval):
    if not ssid:
        raise ValueError('SSID mag niet leeg zijn')
    if os.path.exists(path):
        raise FileExistsError(f'Bestand bestaat al: {path}')
    atomic_write(path, {
        'schema_versie': 3,
        'gestart_op_utc': utc(),
        'verwacht_ssid': ssid,
        'wifi_interface': interface,
        'scans_per_kamer': n,
        'interval_tussen_scans_seconden': interval,
        'accesspoint_namen': {},
        'opmerkingen': '',
        'metingen': []
    })


def accesspoint_names(data):
    names = data.get('accesspoint_namen', {})
    if not isinstance(names, dict):
        return {}
    result = {}
    for raw_bssid, raw_name in names.items():
        bssid = normal_bssid(raw_bssid)
        name = raw_name.strip() if isinstance(raw_name, str) else ''
        if bssid and name:
            result[bssid] = name
    return result


def load_dataset(path):
    """Lees en valideer precies de velden die de begeleide terminalflow nodig heeft."""
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError('het meetbestand bevat geen JSON-object')
    if not isinstance(data.get('verwacht_ssid'), str) or not data['verwacht_ssid']:
        raise ValueError('het meetbestand bevat geen geldig verwacht_ssid')
    if not isinstance(data.get('metingen'), list):
        raise ValueError('het meetbestand bevat geen geldige lijst metingen')
    scans = data.get('scans_per_kamer')
    if isinstance(scans, bool) or not isinstance(scans, int) or not 1 <= scans <= 12:
        raise ValueError('scans_per_kamer moet een geheel getal van 1 t/m 12 zijn')
    interval = data.get('interval_tussen_scans_seconden')
    if isinstance(interval, bool) or not isinstance(interval, (int, float)) or not 0 <= interval <= 30:
        raise ValueError('interval_tussen_scans_seconden moet tussen 0 en 30 liggen')
    return data


def dataset_field(path, name):
    data = load_dataset(path)
    fields = {
        'verwacht_ssid': data['verwacht_ssid'],
        'scans_per_kamer': data['scans_per_kamer'],
        'interval_tussen_scans_seconden': data['interval_tussen_scans_seconden'],
        'aantal_metingen': len(data['metingen']),
        'laatste_kamer': data['metingen'][-1].get('kamer', '') if data['metingen'] else '',
    }
    if name not in fields:
        raise ValueError(f'onbekend veld: {name}')
    value = fields[name]
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    print(value)


def dataset_summary(path):
    data = load_dataset(path)
    if os.environ.get('WIFI_APP_MANAGED') == '1':
        measurements = [m for m in data['metingen'] if isinstance(m, dict)]
        rooms = {str(m.get('kamer', '')).strip().casefold() for m in measurements}
        print(f'\nMeetronde bewaard: {len(rooms)} kamer(s), {len(measurements)} meting(en).')
        if any(m.get('waarschuwing') or m.get('ssid_komt_overeen') is False for m in measurements):
            print('Bekijk de meetwaarschuwingen bij je resultaten.')
        return
    observed = set()
    warnings = 0
    for measurement in data['metingen']:
        if not isinstance(measurement, dict):
            continue
        bssid = normal_bssid(measurement.get('bssid'))
        if bssid:
            observed.add(bssid)
        accesspoints = measurement.get('accesspoints', [])
        if isinstance(accesspoints, list):
            for accesspoint in accesspoints:
                if isinstance(accesspoint, dict):
                    bssid = normal_bssid(accesspoint.get('bssid'))
                    if bssid:
                        observed.add(bssid)
        if measurement.get('waarschuwing'):
            warnings += 1
    print('\nMeetoverzicht')
    print(f'  Kamermetingen: {len(data["metingen"])}')
    print(f'  Waargenomen accesspoints: {len(observed)}')
    print(f'  Benoemde accesspoints: {len(accesspoint_names(data))}')
    print(f'  Metingen met waarschuwing: {warnings}')
    print(f'  Bestand: {Path(path).resolve()}')


def select_session(directory):
    """Toon leesbare sessies; alleen de gekozen bestandsnaam gaat naar de shell."""
    sessions = []
    for path in Path(directory).glob('*.json'):
        try:
            data = load_dataset(path)
            sessions.append((path.stat().st_mtime_ns, path, data))
        except (OSError, ValueError):
            continue
    sessions.sort(key=lambda item: item[0], reverse=True)
    if not sessions:
        print('Er zijn nog geen hervatbare meetrondes.', file=sys.stderr)
        return
    print('\nMet welke meetronde wil je verder?\n', file=sys.stderr)
    for index, (_, path, data) in enumerate(sessions, 1):
        try:
            started = datetime.datetime.fromisoformat(data['gestart_op_utc'].replace('Z', '+00:00'))
            label = started.astimezone().strftime('%d-%m-%Y %H:%M')
        except (KeyError, TypeError, ValueError):
            label = path.stem
        print(f'  [{index}] {label} · {data["verwacht_ssid"]} · {len(data["metingen"])} meting(en)', file=sys.stderr)
    print('  [0] Terug', file=sys.stderr)
    while True:
        print('Keuze [1]: ', end='', file=sys.stderr, flush=True)
        answer = sys.stdin.readline()
        if not answer or answer.strip() == '0':
            return
        answer = answer.strip() or '1'
        if answer.isdecimal() and 1 <= int(answer) <= len(sessions):
            print(sessions[int(answer) - 1][1].resolve())
            return
        print('Kies een nummer uit de lijst.', file=sys.stderr)


def scan_candidates(raw):
    """Vat een identificatiescan samen, zonder link-RSSI met scan-RSSI te mengen."""
    scan_levels = collections.defaultdict(list)
    link_levels = collections.defaultdict(list)
    channels = collections.defaultdict(list)
    seen_in = collections.defaultdict(set)
    connected = set()
    scans = raw.get('scans', [])
    if not isinstance(scans, list):
        scans = []
    for i, scan in enumerate(scans):
        if not isinstance(scan, dict):
            continue
        linked = normal_bssid(scan.get('verbonden_bssid'))
        linked_rssi = integer_rssi(scan.get('verbonden_rssi_dbm'))
        if linked:
            connected.add(linked)
            if linked_rssi is not None:
                link_levels[linked].append(linked_rssi)
                seen_in[linked].add(i)
        aps = scan.get('aps', [])
        if not isinstance(aps, list):
            continue
        for ap in aps:
            if not isinstance(ap, dict):
                continue
            bssid = normal_bssid(ap.get('bssid'))
            rssi = integer_rssi(ap.get('rssi_dbm'))
            if not bssid or rssi is None:
                continue
            scan_levels[bssid].append(rssi)
            seen_in[bssid].add(i)
            if isinstance(ap.get('kanaal'), int):
                channels[bssid].append(ap['kanaal'])
    result = []
    for bssid in set(scan_levels) | set(link_levels):
        levels = scan_levels[bssid] or link_levels[bssid]
        common_channel = collections.Counter(channels[bssid]).most_common(1)
        result.append({
            'bssid': bssid,
            'rssi_gemiddeld_dbm': one_decimal(levels),
            'kanaal': common_channel[0][0] if common_channel else None,
            'aantal_scans_gezien': len(seen_in[bssid]),
            'verbonden': bssid in connected
        })
    return sorted(result, key=lambda item: (-item['rssi_gemiddeld_dbm'], item['bssid']))


def identify(path, rawpath):
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    with open(rawpath, encoding='utf-8') as f:
        raw = json.load(f)
    candidates = scan_candidates(raw)
    if not candidates:
        print('Geen BSSID-identificeerbare accesspoints gevonden; er is niets benoemd.')
        return
    names = accesspoint_names(data)
    print('\nZichtbare accesspoints, sterkste eerst:')
    for i, candidate in enumerate(candidates, 1):
        bssid = candidate['bssid']
        channel = candidate['kanaal'] if candidate['kanaal'] is not None else '?'
        flags = []
        if candidate['verbonden']:
            flags.append('verbonden')
        if bssid in names:
            flags.append(f'heet nu {names[bssid]!r}')
        suffix = f" [{' · '.join(flags)}]" if flags else ''
        print(f"  {i:>2}. {bssid}  {candidate['rssi_gemiddeld_dbm']:+g} dBm  kanaal {channel}{suffix}")
    print('Eén fysiek accesspoint kan meerdere BSSID’s/radio’s hebben; selecteer die nummers samen.')
    try:
        answer = input('Nummer(s), gescheiden door komma/spatie [1]; 0 = annuleren: ').strip()
    except EOFError:
        print('\nBenoemen geannuleerd.')
        return
    if answer.lower() in {'0', ':q', 'q'}:
        print('Benoemen geannuleerd.')
        return
    tokens = ['1'] if not answer else answer.replace(',', ' ').split()
    try:
        indexes = list(dict.fromkeys(int(token) for token in tokens))
    except ValueError:
        print('Ongeldige keuze; er is niets gewijzigd.')
        return
    if not indexes or any(index < 1 or index > len(candidates) for index in indexes):
        print('Ongeldige keuze; er is niets gewijzigd.')
        return
    try:
        name = input('Naam voor dit fysieke accesspoint: ').strip()
    except EOFError:
        print('\nBenoemen geannuleerd.')
        return
    if not name:
        print('Lege naam; er is niets gewijzigd.')
        return
    if len(name) > 100 or any(ord(character) < 32 for character in name):
        print('Naam is ongeldig of langer dan 100 tekens; er is niets gewijzigd.')
        return
    selected = [candidates[index - 1]['bssid'] for index in indexes]
    for bssid in selected:
        names[bssid] = name
    data['accesspoint_namen'] = dict(sorted(names.items()))
    atomic_write(path, data)
    print(f"Opgeslagen: {name!r} voor {', '.join(selected)}")


def aggregate(data, raw, room, started, ended, ssid_start, ssid_end, bssid_start, bssid_end):
    scans = raw.get('scans', [])
    if not isinstance(scans, list):
        scans = []
    bssid_start = normal_bssid(bssid_start)
    bssid_end = normal_bssid(bssid_end)
    link_start = bssid_start or next((normal_bssid(s.get('verbonden_bssid')) for s in scans if isinstance(s, dict) and normal_bssid(s.get('verbonden_bssid'))), None)
    link_end = bssid_end or next((normal_bssid(s.get('verbonden_bssid')) for s in reversed(scans) if isinstance(s, dict) and normal_bssid(s.get('verbonden_bssid'))), None)
    used_links = [b for b in [link_start] + [normal_bssid(s.get('verbonden_bssid')) for s in scans if isinstance(s, dict)] + [link_end] if b]
    prev = normal_bssid(data['metingen'][-1].get('bssid')) if data['metingen'] else None
    swapped = prev != link_end if prev and link_end else None
    ap_rssis = collections.defaultdict(list)
    ap_channels = collections.defaultdict(list)
    ap_noise = collections.defaultdict(list)
    scan_index = collections.defaultdict(set)
    link_rssis = []
    warnings = raw.get('waarschuwingen', [])
    if not isinstance(warnings, list):
        warnings = []
    warnings = [str(v) for v in warnings if v]
    for i, scan in enumerate(scans):
        if not isinstance(scan, dict):
            continue
        r = integer_rssi(scan.get('verbonden_rssi_dbm'))
        if r is not None:
            link_rssis.append(r)
        aps = scan.get('aps', [])
        if not isinstance(aps, list):
            continue
        for ap in aps:
            if not isinstance(ap, dict):
                continue
            b = normal_bssid(ap.get('bssid'))
            r = integer_rssi(ap.get('rssi_dbm'))
            if not b or r is None:
                continue
            ap_rssis[b].append(r)
            scan_index[b].add(i)
            if isinstance(ap.get('kanaal'), int):
                ap_channels[b].append(ap['kanaal'])
            if integer_rssi(ap.get('ruis_dbm')) is not None:
                ap_noise[b].append(ap['ruis_dbm'])
    aps = []
    for bssid, levels in ap_rssis.items():
        channel = collections.Counter(ap_channels[bssid]).most_common(1)
        noise = one_decimal(ap_noise[bssid])
        aps.append({
            'bssid': bssid,
            'rssi_gemiddeld_dbm': one_decimal(levels),
            'rssi_min_dbm': min(levels),
            'rssi_max_dbm': max(levels),
            'rssi_laatste_dbm': levels[-1],
            'aantal_metingen': len(levels),
            'aantal_scans_gezien': len(scan_index[bssid]),
            'dekking_procent': round(100 * len(scan_index[bssid]) / len(scans)) if scans else 0,
            'ruis_gemiddeld_dbm': noise,
            'kanaal': channel[0][0] if channel else None,
            'verbonden_bij_afsluiten': bssid == link_end
        })
    aps.sort(key=lambda x: (-x['rssi_gemiddeld_dbm'], x['bssid']))
    strongest = aps[0]['bssid'] if aps else None
    current_scan_ap = next((ap for ap in aps if ap['bssid'] == link_end), None)
    gap = round(aps[0]['rssi_gemiddeld_dbm'] - current_scan_ap['rssi_gemiddeld_dbm'], 1) if aps and current_scan_ap else None
    if not scans:
        warnings.append('Geen scans uitgevoerd: de CoreWLAN-helper is niet gestart of gaf geen JSON terug.')
    elif not aps:
        warnings.append('Geen identificeerbare BSSID in de scanresultaten. Controleer Location Services voor WifiKamermeting.')
    if ssid_end and ssid_end != data['verwacht_ssid']:
        warnings.append(f'Bij afsluiten verbonden met een ander SSID: {ssid_end!r}.')
    if len(set(used_links)) > 1:
        warnings.append('BSSID van de actieve verbinding veranderde tijdens de kamermeting.')
    selected_ssid = ssid_end or ssid_start or None
    if not selected_ssid:
        warnings.append('De actuele SSID is niet uit te lezen.')
    link_avg = one_decimal(link_rssis)
    connected_bssid = link_end
    rssi = link_avg
    snr = None
    connected_noise = current_scan_ap.get('ruis_gemiddeld_dbm') if current_scan_ap else None
    if rssi is not None and connected_noise is not None:
        snr = round(rssi - connected_noise, 1)
    record = {
        'nummer': len(data['metingen']) + 1,
        'kamer': room,
        'tijdstip_utc': ended,
        'meting_gestart_utc': started,
        'ssid': selected_ssid,
        'ssid_komt_overeen': selected_ssid == data['verwacht_ssid'] if selected_ssid else None,
        'bssid': connected_bssid,
        'vorige_bssid': prev,
        'accesspoint_gewisseld': swapped,
        'rssi_dbm': rssi,
        'ruis_dbm': connected_noise,
        'snr_db': snr,
        'kanaal': current_scan_ap.get('kanaal') if current_scan_ap else None,
        'bron': 'CoreWLAN-scan + Shortcuts (indien beschikbaar)',
        'waarschuwing': ' | '.join(dict.fromkeys(warnings)) if warnings else None,
        'opmerking': '',
        'scan_aantal': len(scans),
        'verbonden_bssid_begin': link_start,
        'verbonden_bssid_einde': link_end,
        'verbonden_bssid_tijdens_scans': sorted(set(used_links)),
        'verbonden_rssi_gemiddeld_dbm': link_avg,
        'accesspoints': aps,
        'sterkste_bssid': strongest,
        'verschil_sterkste_en_verbonden_db': gap,
        'scan_details': scans
    }
    return record


def add(path, rawpath, room, started, ended, ssid_start, ssid_end, bssid_start, bssid_end):
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    with open(rawpath, encoding='utf-8') as f:
        raw = json.load(f)
    names = accesspoint_names(data)
    record = aggregate(data, raw, room, started, ended, ssid_start, ssid_end, bssid_start, bssid_end)
    data['metingen'].append(record)
    atomic_write(path, data)
    if os.environ.get('WIFI_APP_MANAGED') == '1':
        rssi = record['rssi_dbm']
        signal = 'geen leesbare signaalwaarde' if rssi is None else (
            'goed signaal' if rssi >= -65 else 'redelijk signaal' if rssi >= -75 else 'zwak signaal')
        print(f'\nBewaard: {record["kamer"]} · {signal}.')
        if record['waarschuwing']:
            print(f'  Let op: {record["waarschuwing"]}')
        print('Je resultaten in de browser worden automatisch bijgewerkt.\n')
        return
    print(f'\nKamer {record["nummer"]}: {record["kamer"]}  ({record["scan_aantal"]} scans)')
    print(f'  Verbonden BSSID: {record["bssid"] or "onbekend"}, signaal: {record["rssi_dbm"] if record["rssi_dbm"] is not None else "?"} dBm')
    if not record['accesspoints']:
        print('  Geen BSSID-identificeerbare alternatieve accesspoints gevonden.')
    for ap in record['accesspoints']:
        mark = ' [VERBONDEN]' if ap['verbonden_bij_afsluiten'] else ''
        label = f'{names[ap["bssid"]]} · ' if ap['bssid'] in names else ''
        print(f'  {label}{ap["bssid"]}: gemiddeld {ap["rssi_gemiddeld_dbm"]:+g} dBm; min {ap["rssi_min_dbm"]}, max {ap["rssi_max_dbm"]}; gezien {ap["aantal_scans_gezien"]}/{record["scan_aantal"]} scans{mark}')
    if record['verschil_sterkste_en_verbonden_db'] is not None and record['verschil_sterkste_en_verbonden_db'] > 0:
        print(f'  Sterkste andere AP: {record["verschil_sterkste_en_verbonden_db"]:g} dB sterker (scan-RSSI)')
    if record['accesspoint_gewisseld'] is True:
        print('  >>> Mac verbonden met ander AP dan in vorige kamer.')
    if record['waarschuwing']:
        print(f'  LET OP: {record["waarschuwing"]}')
    print(f'  JSON opgeslagen: {path}\n')


def main():
    if len(sys.argv) < 2:
        raise SystemExit('Gebruik: dataset.py init|identify|add|field|summary ...')
    if sys.argv[1] == 'init' and len(sys.argv) == 7:
        init_file(sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5]), float(sys.argv[6]))
    elif sys.argv[1] == 'identify' and len(sys.argv) == 4:
        identify(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == 'add' and len(sys.argv) == 11:
        add(*sys.argv[2:])
    elif sys.argv[1] == 'field' and len(sys.argv) == 4:
        dataset_field(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == 'summary' and len(sys.argv) == 3:
        dataset_summary(sys.argv[2])
    elif sys.argv[1] == 'select-session' and len(sys.argv) == 3:
        select_session(sys.argv[2])
    else:
        raise SystemExit('Ongeldige argumenten voor dataset.py')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise SystemExit(f'Fout: {error}')
