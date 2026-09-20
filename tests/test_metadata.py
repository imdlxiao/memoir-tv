"""Original metadata, caching, WGS84 edits and preservation. Author: donglixiao."""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from memoir.domain import validate_edit
from memoir.metadata import normalize, read_metadata
from memoir.scanner import scan
from memoir.storage import Repository


class CaptureTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('MEMOIR_EXIFTOOL') or shutil.which('exiftool'), 'Optional ExifTool is not installed')
    def test_real_quicktime_fixture(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(__file__).parent / 'fixtures' / 'capture.mov'
            original = path.read_bytes()
            self.assertLess(original.index(b'mdat'), original.index(b'moov'))
            data = read_metadata(path, Path(directory), 'fixture', os.environ.get('MEMOIR_EXIFTOOL', 'exiftool'), True)
            self.assertEqual(data['coordinates'], {'latitude': 22.3, 'longitude': 114.17})
            self.assertEqual(data['capture']['model'], 'Test Camera')
            self.assertEqual(data['capture']['takenAt'], '2024-02-29T11:03:02+08:00')
            self.assertEqual(data['capture']['width'], 64)
            self.assertEqual(path.read_bytes(), original)

    def test_coordinates_reject_invalid_values_and_allow_equator(self):
        for value in [{'latitude': True, 'longitude': 0}, {'latitude': 91, 'longitude': 0},
                      {'latitude': 0, 'longitude': float('nan')}, {'latitude': 1},
                      {'latitude': '12', 'longitude': 1}, [1, 2],
                      {'latitude': 1, 'longitude': 1, 'extra': 0}]:
            with self.assertRaises(ValueError):
                validate_edit({'coordinates': value})
        self.assertEqual(validate_edit({'coordinates': None}), {'coordinates': None})
        self.assertEqual(validate_edit({'coordinates': {'latitude': 0, 'longitude': 0}})['coordinates']['latitude'], 0)

    def test_original_time_camera_and_southern_hemisphere(self):
        result = normalize({'GPSLatitude': 33.8, 'GPSLongitude': 151.2, 'GPSLatitudeRef': 'S',
                            'Model': 'Fixture Camera', 'DateTimeOriginal': '2024:02:29 11:03:02',
                            'OffsetTimeOriginal': '+08:00', 'FNumber': 1.8, 'ISO': 80})
        self.assertEqual(result['coordinates']['latitude'], -33.8)
        self.assertEqual(result['capture']['takenAt'], '2024-02-29T11:03:02+08:00')
        self.assertEqual(result['capture']['iso'], 80)
        self.assertNotIn('takenAt', normalize({'DateTimeOriginal': '2023:02:29 11:03:02'})['capture'])
        self.assertNotIn('takenAt', normalize({'CreateDate': '2024:02:29 11:03:02'})['capture'])

    def test_quicktime_creation_date_and_negative_coordinates(self):
        data = normalize({'CreationDate': '2024:06:03 20:01:02-04:00', 'GPSLatitude': 40.7,
                          'GPSLongitude': -74.0, 'Duration': 15.2, 'ImageWidth': 1920})
        self.assertEqual(data['coordinates']['longitude'], -74)
        self.assertEqual(data['capture']['dateTag'], 'CreationDate')
        self.assertEqual(data['capture']['duration'], 15.2)

    def test_cache_avoids_repeated_process_and_uses_utf8_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / '相片.jpg'
            source.write_bytes(b'original')
            process = SimpleNamespace(returncode=0, stdout=json.dumps([{'Model': 'Test'}]).encode())
            with patch('memoir.metadata.subprocess.run', return_value=process) as run:
                result = read_metadata(source, root, 'fingerprint', extract=True)
                self.assertEqual(result['capture']['model'], 'Test')
                self.assertEqual(read_metadata(source, root, 'fingerprint'), result)
                run.assert_called_once()
                self.assertIn('相片.jpg', run.call_args.kwargs['input'].decode('utf-8'))
                self.assertEqual(read_metadata(source, root, 'changed')['metadataStatus'], 'pending')
                self.assertEqual(read_metadata(source, root, 'fingerprint', executable='other')['metadataStatus'], 'pending')
            self.assertEqual(source.read_bytes(), b'original')

    def test_scans_preserve_manual_dates_and_removed_gps(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            media = root / 'media'; media.mkdir()
            (media / '20200101.jpg').write_bytes(b'original')
            repository = Repository(root / 'data')
            original = {'coordinates': {'latitude': 22, 'longitude': 114},
                        'capture': {'takenAt': '2024-02-29T11:03:02'}, 'metadataStatus': 'read'}
            with patch('memoir.scanner.read_metadata', return_value=original):
                repository.replace_index(scan(media, repository.directory, previews=False))
                item = repository.catalog()['items'][0]
                self.assertEqual(item['dateSource'], 'embedded')
                repository.save(item['id'], {'coordinates': None, 'date': '2023-07', 'precision': 'month'})
                repository.replace_index(scan(media, repository.directory, previews=False))
                item = repository.catalog()['items'][0]
                self.assertIsNone(item['coordinates'])
                self.assertEqual(item['date'], '2023-07')
                self.assertEqual(item['capture']['takenAt'], '2024-02-29T11:03:02')

    def test_failed_tool_is_retryable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch('memoir.metadata.subprocess.run', side_effect=OSError):
                self.assertEqual(read_metadata(root / 'photo.jpg', root, 'one', extract=True)['metadataStatus'], 'unavailable')
            self.assertFalse((root / 'metadata').exists())
