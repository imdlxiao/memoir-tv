"""Metadata validation and repository regression tests. Author: donglixiao."""
import tempfile
import unittest
from pathlib import Path
from memoir.domain import inferred_date, validate_edit
from memoir.storage import Repository


class MetadataTests(unittest.TestCase):
    def test_filename_date_is_not_file_time(self):
        self.assertEqual(inferred_date('DJI_20260221123210.MP4'), '2026-02-21')
        self.assertEqual(inferred_date('IMG_0908.MOV'), '')
        self.assertEqual(inferred_date('20260230.mp4'), '')

    def test_date_precision_and_validation(self):
        self.assertEqual(validate_edit({'date': '2024-02', 'precision': 'month'})['date'], '2024-02')
        for value in [{'date': '2025-02-29', 'precision': 'day'}, {'date': '2025-13', 'precision': 'month'}, {'path': '../secret'}]:
            with self.assertRaises(ValueError):
                validate_edit(value)

    def test_rescan_preserves_edits(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Repository(directory)
            repository.replace_index({'items': [{'id': 'a', 'title': ''}]})
            repository.save('a', {'title': '一家人的夏天', 'date': '2024-07', 'precision': 'month'})
            repository.replace_index({'items': [{'id': 'a', 'title': '', 'size': 20}]})
            self.assertEqual(repository.catalog()['items'][0]['title'], '一家人的夏天')
            repository.save('a', {'favorite': True})
            self.assertTrue((Path(directory) / 'memories.backup.json').exists())

    def test_import_is_validated_before_write(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Repository(directory)
            with self.assertRaises(ValueError):
                repository.import_edits({'a': {'title': 'hello'}, 'b': {'favorite': 'yes'}})
            self.assertFalse(repository.edits_path.exists())


if __name__ == '__main__':
    unittest.main()
