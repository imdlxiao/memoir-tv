"""Incremental inventory and cached index performance contracts. Author: donglixiao."""
import http.client
import json
import os
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from auth_support import owner_session
from memoir.inventory import DirectoryInventory
from memoir.http import Application, handler_for
from memoir.scanner import scan
from memoir.storage import Repository


class InventoryTests(unittest.TestCase):
    def test_new_arrival_reuses_existing_media_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            media = root / 'media'; media.mkdir()
            for number in range(10):
                (media / f'{number}.mp4').write_bytes(b'fixture')
            repository = Repository(root / 'data')
            repository.replace_index(scan(media, repository.directory, previews=False))
            app = Application(media, repository, root / 'web', 'missing-ffmpeg')
            app.catalog()
            (media / 'new.mp4').write_bytes(b'new fixture')
            from memoir.metadata import read_metadata
            with patch('memoir.scanner.read_metadata', wraps=read_metadata) as metadata, patch.object(app, 'start_scan'):
                self.assertEqual(len(app.catalog()['items']), 11)
                metadata.assert_called_once()
                self.assertEqual(metadata.call_args.args[0].name, 'new.mp4')

    def test_unchanged_directories_avoid_listing_and_detect_move(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            month = root / '2024' / '2024-02'; month.mkdir(parents=True)
            original = month / 'one.mp4'; original.write_bytes(b'video')
            inventory = DirectoryInventory(root)
            self.assertTrue(inventory.changed())
            with patch('memoir.inventory.os.scandir', side_effect=AssertionError('Unchanged directory should be cached')):
                self.assertFalse(inventory.changed())
            original.rename(month / 'renamed.mp4')
            self.assertTrue(inventory.changed())
            (month / 'renamed.mp4').unlink()
            self.assertTrue(inventory.changed())

    def test_periodic_reconcile_detects_content_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'one.mp4'; source.write_bytes(b'one')
            inventory = DirectoryInventory(root)
            self.assertTrue(inventory.changed())
            stamp = root.stat()
            source.write_bytes(b'longer video')
            os.utime(root, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
            self.assertFalse(inventory.changed())
            self.assertTrue(inventory.changed(force=True))

    def test_cached_catalog_is_isolated_and_reuses_wire_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Repository(Path(directory))
            repo.replace_index({'items': [{'id': 'one', 'path': 'one.mp4', 'tags': []}]})
            body, tag = repo.catalog_payload()
            item = repo.find('one'); item['tags'].append('not persisted')
            self.assertEqual(repo.find('one')['tags'], [])
            self.assertIs(repo.catalog_payload()[0], body)
            repo.save('one', {'title': 'changed'})
            self.assertNotEqual(repo.catalog_payload()[1], tag)
            self.assertEqual(repo.find('one')['title'], 'changed')

    def test_conditional_poll_does_not_scan_unchanged_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            media = root / 'media'; media.mkdir()
            source = media / 'video.mp4'; source.write_bytes(b'fixture')
            repository = Repository(root / 'data')
            repository.replace_index(scan(media, repository.directory, previews=False))
            app = Application(media, repository, root / 'web', 'missing-ffmpeg')
            cookie = owner_session(app)
            server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(app))
            threading.Thread(target=server.serve_forever, daemon=True).start()
            connection = http.client.HTTPConnection('127.0.0.1', server.server_port)
            try:
                connection.request('GET', '/data/catalog.json', headers={'Cookie': cookie})
                response = connection.getresponse(); etag = response.getheader('ETag')
                item = json.loads(response.read())['items'][0]
                with patch('memoir.library.scan', side_effect=AssertionError('Unchanged catalog must not rescan')):
                    connection.request('GET', '/data/catalog.json?background=1', headers={'If-None-Match': etag, 'Cookie': cookie})
                    response = connection.getresponse()
                    self.assertEqual(response.status, 304); self.assertEqual(response.read(), b'')
                repository.save(item['id'], {'title': 'new title'})
                connection.request('GET', '/data/catalog.json?background=1', headers={'If-None-Match': etag, 'Cookie': cookie})
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(json.loads(response.read())['items'][0]['title'], 'new title')
                source.unlink()
                connection.request('GET', '/data/catalog.json', headers={'If-None-Match': etag, 'Cookie': cookie})
                response = connection.getresponse()
                self.assertEqual(json.loads(response.read())['items'], [])
            finally:
                connection.close(); server.shutdown(); server.server_close()
