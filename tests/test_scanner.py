"""Scanner and static publisher regression tests. Author: donglixiao."""
import tempfile
import unittest
from pathlib import Path
from memoir.exporter import export_static
from memoir.scanner import scan
from memoir.storage import Repository


class ScannerTests(unittest.TestCase):
    def test_recursive_scan_and_stable_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            media = root / 'media' / 'family'
            media.mkdir(parents=True)
            (media / '20240229.jpg').write_bytes(b'photo')
            (media / 'IMG_0908.MOV').write_bytes(b'video')
            (media / 'notes.txt').write_text('skip')
            one = scan(root / 'media', root / 'data', previews=False)
            two = scan(root / 'media', root / 'data', previews=False)
            self.assertEqual(len(one['items']), 2)
            self.assertEqual([i['id'] for i in one['items']], [i['id'] for i in two['items']])
            self.assertEqual(one['items'][0]['date'], '2024-02-29')
            self.assertEqual(one['items'][1]['precision'], 'unknown')

    def test_export_merges_metadata_and_does_not_copy_media(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            media, web = root / 'media', root / 'web'
            media.mkdir()
            web.mkdir()
            (web / 'index.html').write_text('<!doctype html>')
            (media / '家庭 20240715.jpg').write_bytes(b'private photo')
            repository = Repository(root / 'data')
            repository.replace_index(scan(media, repository.directory, previews=False))
            identity = repository.catalog()['items'][0]['id']
            repository.save(identity, {'title': 'our memory', 'date': '2024-07', 'precision': 'month'})
            catalog = export_static(web, repository, media, '/family/', root / 'output')
            self.assertEqual(catalog['items'][0]['title'], 'our memory')
            self.assertIn('%20', catalog['items'][0]['url'])
            self.assertNotIn('path', catalog['items'][0])
            self.assertFalse((root / 'output' / '家庭 20240715.jpg').exists())
            for destination in [media, web, root, repository.directory]:
                with self.assertRaises(ValueError):
                    export_static(web, repository, media, '/family/', destination)
