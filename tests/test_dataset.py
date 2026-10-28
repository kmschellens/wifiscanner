import json
import io
import os
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

from app import dataset


class AccesspointNamingTests(unittest.TestCase):
    def test_resume_picker_uses_recent_valid_sessions_and_returns_selected_path(self):
        with tempfile.TemporaryDirectory() as directory:
            older = Path(directory) / 'oud.json'
            newer = Path(directory) / 'nieuw.json'
            dataset.init_file(older, 'Testnet', 'en0', 4, 2)
            dataset.init_file(newer, 'Testnet', 'en0', 4, 2)
            (Path(directory) / 'ongeldig.json').write_text('[]', encoding='utf-8')
            os.utime(older, (10, 10))
            os.utime(newer, (20, 20))
            with mock.patch('sys.stdin', io.StringIO('99\n1\n')), \
                    mock.patch('sys.stderr', io.StringIO()), redirect_stdout(io.StringIO()) as output:
                dataset.select_session(directory)
            self.assertEqual(output.getvalue().strip(), str(newer.resolve()))

    def test_new_dataset_contains_empty_name_mapping(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'meting.json'
            dataset.init_file(path, 'Testnet', 'en0', 4, 2)
            data = json.loads(path.read_text(encoding='utf-8'))

        self.assertEqual(data['schema_versie'], 3)
        self.assertEqual(data['accesspoint_namen'], {})

    def test_candidates_are_sorted_and_do_not_mix_link_with_scan_rssi(self):
        raw = {
            'scans': [
                {
                    'verbonden_bssid': 'AA:BB:CC:DD:EE:01',
                    'verbonden_rssi_dbm': -80,
                    'aps': [
                        {'bssid': 'aa:bb:cc:dd:ee:01', 'rssi_dbm': -40, 'kanaal': 36},
                        {'bssid': 'aa:bb:cc:dd:ee:02', 'rssi_dbm': -55, 'kanaal': 1},
                    ],
                },
                {
                    'verbonden_bssid': 'aa:bb:cc:dd:ee:01',
                    'verbonden_rssi_dbm': -82,
                    'aps': [
                        {'bssid': 'aa:bb:cc:dd:ee:01', 'rssi_dbm': -42, 'kanaal': 36},
                        {'bssid': 'aa:bb:cc:dd:ee:02', 'rssi_dbm': -57, 'kanaal': 1},
                    ],
                },
            ]
        }

        candidates = dataset.scan_candidates(raw)

        self.assertEqual([item['bssid'] for item in candidates], [
            'aa:bb:cc:dd:ee:01',
            'aa:bb:cc:dd:ee:02',
        ])
        self.assertEqual(candidates[0]['rssi_gemiddeld_dbm'], -41.0)
        self.assertTrue(candidates[0]['verbonden'])

    def test_identify_assigns_one_name_to_multiple_bssids(self):
        with tempfile.TemporaryDirectory() as directory:
            data_path = Path(directory) / 'meting.json'
            raw_path = Path(directory) / 'scan.json'
            dataset.init_file(data_path, 'Testnet', 'en0', 4, 2)
            raw_path.write_text(json.dumps({
                'scans': [{
                    'aps': [
                        {'bssid': 'aa:bb:cc:dd:ee:01', 'rssi_dbm': -35, 'kanaal': 36},
                        {'bssid': 'aa:bb:cc:dd:ee:02', 'rssi_dbm': -39, 'kanaal': 1},
                    ]
                }]
            }), encoding='utf-8')

            with mock.patch('builtins.input', side_effect=['1, 2', 'AP zolder']):
                dataset.identify(data_path, raw_path)
            data = json.loads(data_path.read_text(encoding='utf-8'))

        self.assertEqual(data['accesspoint_namen'], {
            'aa:bb:cc:dd:ee:01': 'AP zolder',
            'aa:bb:cc:dd:ee:02': 'AP zolder',
        })

    def test_old_or_invalid_name_mapping_is_safe(self):
        self.assertEqual(dataset.accesspoint_names({'metingen': []}), {})
        self.assertEqual(dataset.accesspoint_names({
            'accesspoint_namen': {
                'AA:BB:CC:DD:EE:01': '  Geldig  ',
                'ongeldig': 'Niet meenemen',
                'aa:bb:cc:dd:ee:02': '',
            }
        }), {'aa:bb:cc:dd:ee:01': 'Geldig'})

    def test_resume_fields_and_summary_are_available(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'meting.json'
            dataset.init_file(path, 'Testnet', 'en0', 4, 2)
            data = json.loads(path.read_text(encoding='utf-8'))
            data['accesspoint_namen'] = {'aa:bb:cc:dd:ee:01': 'AP test'}
            data['metingen'].append({
                'kamer': 'Testkamer',
                'bssid': 'aa:bb:cc:dd:ee:01',
                'accesspoints': [
                    {'bssid': 'aa:bb:cc:dd:ee:01'},
                    {'bssid': 'aa:bb:cc:dd:ee:02'},
                ],
                'waarschuwing': 'Testwaarschuwing',
            })
            path.write_text(json.dumps(data), encoding='utf-8')

            with redirect_stdout(io.StringIO()) as output:
                dataset.dataset_field(path, 'laatste_kamer')
            self.assertEqual(output.getvalue().strip(), 'Testkamer')

            with redirect_stdout(io.StringIO()) as output:
                dataset.dataset_summary(path)
            summary = output.getvalue()

        self.assertIn('Kamermetingen: 1', summary)
        self.assertIn('Waargenomen accesspoints: 2', summary)
        self.assertIn('Benoemde accesspoints: 1', summary)
        self.assertIn('Metingen met waarschuwing: 1', summary)

    def test_invalid_resume_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'ongeldig.json'
            path.write_text('{"metingen": []}', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'verwacht_ssid'):
                dataset.load_dataset(path)


if __name__ == '__main__':
    unittest.main()
