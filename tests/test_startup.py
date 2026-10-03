"""Background startup guards use temporary libraries only. Author: donglixiao."""
import json
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch
from scripts.start_background import instance_lock, port_in_use, run_startup, wait_for_media


class StartupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'media').mkdir()
        (self.root / 'config.local.json').write_text(json.dumps({
            'media_root': 'media', 'host': '127.0.0.1', 'port': 8765,
        }), encoding='utf-8')

    def test_lock_rejects_duplicate_and_releases_after_exit(self):
        path = self.root / 'startup.lock'
        with instance_lock(path) as first:
            self.assertTrue(first)
            with instance_lock(path) as second:
                self.assertFalse(second)
        with instance_lock(path) as third:
            self.assertTrue(third)

    def test_existing_server_does_not_start_another(self):
        with patch('scripts.start_background.port_in_use', return_value=True), \
                patch('scripts.start_background.runpy.run_module') as server:
            self.assertEqual(run_startup(self.root), 0)
            server.assert_not_called()

    def test_missing_drive_does_not_scan_or_create_a_library(self):
        (self.root / 'media').rmdir()
        with patch('scripts.start_background.port_in_use', return_value=False), \
                patch('scripts.start_background.wait_for_media', return_value=False), \
                patch('scripts.start_background.runpy.run_module') as server:
            self.assertEqual(run_startup(self.root), 1)
            server.assert_not_called()
        self.assertFalse((self.root / 'data').exists())

    def test_local_config_is_required_instead_of_example_fallback(self):
        (self.root / 'config.local.json').unlink()
        with patch('scripts.start_background.runpy.run_module') as server:
            self.assertEqual(run_startup(self.root), 1)
            server.assert_not_called()

    def test_launch_holds_lock_and_restores_working_directory(self):
        previous = Path.cwd()
        def serve(*args, **kwargs):
            self.assertEqual(Path.cwd(), self.root)
            self.assertEqual(run_startup(self.root), 0)
        with patch('scripts.start_background.port_in_use', return_value=False), \
                patch('scripts.start_background.runpy.run_module', side_effect=serve) as server:
            self.assertEqual(run_startup(self.root), 0)
            self.assertEqual(server.call_count, 1)
        self.assertEqual(Path.cwd(), previous)

    def test_drive_wait_and_real_port_probe(self):
        self.assertTrue(wait_for_media(self.root / 'media', seconds=0))
        self.assertFalse(wait_for_media(self.root / 'missing', seconds=0))
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            listener.listen()
            self.assertTrue(port_in_use('0.0.0.0', listener.getsockname()[1]))


if __name__ == '__main__':
    unittest.main()
