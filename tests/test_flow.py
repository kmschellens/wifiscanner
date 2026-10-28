"""Controleer de automatische voorbereiding en de levensduur van de resultatenserver."""
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

from app import launcher, server


class PreparationTests(unittest.TestCase):
    def test_build_only_when_scanner_missing_or_source_changed(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            binary, source = base / 'scanner', base / 'source'
            source.write_text('voorbeeld', encoding='utf-8')
            with mock.patch.object(launcher, 'SCANNER', binary), mock.patch.object(launcher, 'SOURCES', [source]):
                self.assertTrue(launcher.scanner_needs_build())
                binary.write_text('voorbeeld', encoding='utf-8')
                binary.chmod(0o700)
                os.utime(source, (10, 10))
                os.utime(binary, (20, 20))
                self.assertFalse(launcher.scanner_needs_build())
                os.utime(source, (30, 30))
                self.assertTrue(launcher.scanner_needs_build())

    def test_normal_start_prepares_before_showing_choices_and_cleans_up(self):
        with mock.patch.object(launcher, 'ResultsServer') as factory, \
                mock.patch.object(launcher, 'prepare_scanner') as prepare, \
                mock.patch('builtins.input', return_value='4'), redirect_stdout(io.StringIO()):
            launcher.main([])
        factory.return_value.start.assert_called_once_with(8765)
        prepare.assert_called_once()
        factory.return_value.close.assert_called_once()

    def test_measurement_returns_to_app_without_starting_a_second_launcher(self):
        with mock.patch.object(launcher, 'prepare_scanner', return_value=True), \
                mock.patch.object(launcher.subprocess, 'run') as run:
            run.return_value.returncode = 0
            results = mock.Mock(url='http://127.0.0.1:8765')
            launcher.run_measurement(results)
        call = run.call_args
        self.assertEqual(call.kwargs['env']['WIFI_APP_MANAGED'], '1')
        self.assertEqual(call.kwargs['env']['WIFI_DASHBOARD_URL'], results.url)
        self.assertEqual(call.args[0][0], 'bash')


class ResultsLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.data = Path(self.directory.name)
        self.patch = mock.patch.object(server, 'DATA_DIR', self.data)
        self.patch.start()
        self.results = launcher.ResultsServer()
        self.results.start(0)
        self.addCleanup(self.directory.cleanup)
        self.addCleanup(self.patch.stop)
        self.addCleanup(self.results.close)

    def request(self, path):
        return launcher.LOCAL_HTTP.open(self.results.url + path, timeout=2)

    def test_result_catalog_changes_when_saved_and_source_code_is_not_served(self):
        path = self.data / 'voorbeeld.json'
        path.write_text('{"metingen":[]}', encoding='utf-8')
        with self.request('/api/catalog') as response:
            before = json.load(response)
        path.write_text('{"metingen":[{"kamer":"Voorbeeldkamer"}]}', encoding='utf-8')
        with self.request('/api/catalog') as response:
            after = json.load(response)
        self.assertNotEqual(before[0]['revision'], after[0]['revision'])
        with self.request('/voorbeeld.json') as response:
            self.assertEqual(json.load(response)['metingen'][0]['kamer'], 'Voorbeeldkamer')
        for url in ('/server.py', '/../start.sh', '/%2e%2e/start.sh'):
            with self.assertRaises(launcher.urllib.error.HTTPError) as error:
                self.request(url)
            self.assertEqual(error.exception.code, 404)

    def test_second_window_reuses_server_and_leaves_it_running(self):
        second = launcher.ResultsServer()
        second.start(self.results.port)
        self.assertEqual(second.port, self.results.port)
        self.assertIsNone(second.httpd)
        second.close()
        self.assertTrue(launcher.matching_server(self.results.port))

    def test_occupied_port_uses_another_port_and_does_not_stop_other_service(self):
        with mock.patch.object(launcher, 'matching_server', return_value=False):
            second = launcher.ResultsServer()
            try:
                second.start(self.results.port)
                self.assertNotEqual(second.port, self.results.port)
            finally:
                second.close()
        self.assertTrue(launcher.matching_server(self.results.port))

    def test_close_releases_owned_port(self):
        port = self.results.port
        self.results.close()
        self.assertFalse(launcher.matching_server(port))


if __name__ == '__main__':
    unittest.main()
