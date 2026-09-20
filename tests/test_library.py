"""Live directory membership and preview race regressions. Author: donglixiao."""
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from memoir.library import Application
from memoir.scanner import scan
from memoir.storage import Repository, read_json


class LibrarySyncTests(unittest.TestCase):
    def test_move_out_and_back_preserves_annotations(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            media = root / 'media'
            media.mkdir()
            source = media / 'memory.mp4'
            source.write_bytes(b'fixture')
            repository = Repository(root / 'data')
            repository.replace_index(scan(media, repository.directory, previews=False))
            app = Application(media, repository, root / 'web', 'ffmpeg')
            identity = repository.catalog()['items'][0]['id']
            repository.save(identity, {'date': '2024-07', 'precision': 'month', 'tags': ['family']})
            source.rename(root / 'moved.mp4')
            self.assertEqual(app.catalog()['items'], [])
            self.assertIn(identity, read_json(repository.edits_path, {}))
            (root / 'moved.mp4').rename(source)
            with patch.object(app, 'start_scan'):
                restored = app.catalog()['items'][0]
            self.assertEqual(restored['id'], identity)
            self.assertEqual(restored['date'], '2024-07')
            self.assertEqual(restored['tags'], ['family'])

    def test_slow_preview_cannot_resurrect_removed_media(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            media = root / 'media'
            media.mkdir()
            source = media / 'memory.mp4'
            source.write_bytes(b'fixture')
            repository = Repository(root / 'data')
            repository.replace_index(scan(media, repository.directory, previews=False))
            app = Application(media, repository, root / 'web', 'ffmpeg')
            entered, release = threading.Event(), threading.Event()

            def slow_scan(root, directory, ffmpeg, previews=True):
                snapshot = scan(root, directory, ffmpeg, previews=False)
                if previews:
                    entered.set()
                    if not release.wait(5):
                        raise TimeoutError('test preview job did not resume')
                return snapshot

            with patch('memoir.library.scan', side_effect=slow_scan):
                self.assertTrue(app.start_scan())
                try:
                    self.assertTrue(entered.wait(3))
                    source.rename(root / 'moved.mp4')
                    # Catalog refresh remains responsive while decoding is blocked.
                    self.assertEqual(app.catalog()['items'], [])
                finally:
                    release.set()
                self.assertTrue(app.scan_lock.acquire(timeout=3))
                app.scan_lock.release()
            self.assertEqual(repository.catalog()['items'], [])
            self.assertEqual(app.scan_status['error'], '')

    def test_disconnected_root_preserves_previous_index(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repository = Repository(root / 'data')
            repository.replace_index({'items': [{'id': 'existing', 'path': 'memory.mp4'}]})
            app = Application(root / 'unavailable', repository, root / 'web', 'ffmpeg')
            with self.assertRaises(ValueError):
                app.catalog()
            self.assertEqual(repository.catalog()['items'][0]['id'], 'existing')
