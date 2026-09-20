"""Verified copies and stable identity regressions. Author: donglixiao."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from memoir.migration import plan_move, copy_verified, confined
from memoir.scanner import scan
from memoir.storage import Repository, atomic_json


class MigrationTests(unittest.TestCase):
    def test_copy_verify_and_preserve_identity_annotations(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, target = root / 'source', root / 'target'
            source.mkdir()
            original = source / '20240315.mp4'
            original.write_bytes(b'original video fixture')
            repository = Repository(root / 'data')
            repository.replace_index(scan(source, repository.directory, previews=False))
            item = repository.catalog()['items'][0]
            repository.save(item['id'], {'title': 'family story', 'date': '2024-02', 'precision': 'month', 'tags': ['family']})
            plan = plan_move(source, target, repository.catalog()['items'])
            self.assertEqual(plan['entries'][0]['target'], '2024/2024-02/20240315.mp4')
            copy_verified(plan, root / 'journal.json')
            self.assertEqual(plan['phase'], 'verified')
            self.assertTrue(original.exists())  # Copy stage never deletes originals.
            self.assertEqual((target / plan['entries'][0]['target']).read_bytes(), original.read_bytes())
            self.assertEqual((target / plan['entries'][0]['target']).stat().st_mtime_ns, original.stat().st_mtime_ns)
            atomic_json(repository.directory / 'identities.json', {'paths': {plan['entries'][0]['target']: item['id']}})
            repository.replace_index(scan(target, repository.directory, previews=False))
            restored = repository.catalog()['items'][0]
            self.assertEqual(restored['id'], item['id'])
            self.assertEqual(restored['title'], 'family story')
            self.assertEqual(restored['date'], '2024-02')
            # A new arrival reusing the old filename must not inherit the old ID.
            (target / original.name).write_bytes(b'new memory')
            items = scan(target, repository.directory, previews=False)['items']
            self.assertEqual(len({i['id'] for i in items}), 2)

    def test_invalid_target_overwrite_and_changed_source_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'; source.mkdir()
            (source / 'unknown.mp4').write_bytes(b'original')
            items = scan(source, root / 'data', previews=False)['items']
            with self.assertRaises(ValueError):
                plan_move(source, source / 'nested', items)
            with self.assertRaises(ValueError):
                confined(source, '../outside')
            plan = plan_move(source, root / 'target', items)
            self.assertTrue(plan['entries'][0]['target'].startswith('日期待补/'))
            target = root / 'target' / plan['entries'][0]['target']
            target.parent.mkdir(parents=True); target.write_bytes(b'keep existing')
            with self.assertRaises(ValueError):
                copy_verified(plan, root / 'journal.json')
            self.assertEqual(target.read_bytes(), b'keep existing')
            (source / 'unknown.mp4').write_bytes(b'changed')
            with self.assertRaises(ValueError):
                plan_move(source, root / 'other', items)

    def test_failed_hash_keeps_source_and_does_not_publish(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'; source.mkdir()
            original = source / 'video.mp4'; original.write_bytes(b'original')
            plan = plan_move(source, root / 'target', scan(source, root / 'data', previews=False)['items'])
            with patch('memoir.migration.sha256_file', return_value='wrong'):
                with self.assertRaises(ValueError):
                    copy_verified(plan, root / 'journal.json')
            self.assertEqual(original.read_bytes(), b'original')
            self.assertFalse((root / 'target' / plan['entries'][0]['target']).exists())
            self.assertNotIn('verified', plan['entries'][0])
