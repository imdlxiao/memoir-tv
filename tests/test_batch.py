"""Atomic batch editing, partial field updates, and tag semantics. Author: donglixiao."""
import tempfile
import unittest
from pathlib import Path
from memoir.storage import Repository


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.repository = Repository(self.directory.name)
        self.ids = ['a' * 20, 'b' * 20]
        self.repository.replace_index({'items': [
            {'id': self.ids[0], 'title': 'first', 'tags': ['family'], 'location': 'home'},
            {'id': self.ids[1], 'title': 'second', 'tags': ['trip'], 'location': 'park'},
        ]})

    def test_append_date_and_preserve_other_fields(self):
        count = self.repository.save_many({'ids': self.ids, 'changes': {
            'date': '2024-07', 'precision': 'month', 'tags': ['summer', 'family']}})
        items = self.repository.catalog()['items']
        self.assertEqual(count, 2)
        self.assertEqual(items[0]['title'], 'first')
        self.assertEqual(items[1]['location'], 'park')
        self.assertEqual(items[0]['tags'], ['family', 'summer'])
        self.assertEqual(items[1]['tags'], ['trip', 'summer', 'family'])
        self.assertTrue(all(item['date'] == '2024-07' for item in items))

    def test_tag_replace_and_remove(self):
        self.repository.save_many({'ids': self.ids, 'changes': {'tags': ['one', 'two']}, 'tagMode': 'replace'})
        self.repository.save_many({'ids': self.ids, 'changes': {'tags': ['one']}, 'tagMode': 'remove'})
        self.assertTrue(all(item['tags'] == ['two'] for item in self.repository.catalog()['items']))

    def test_invalid_or_missing_item_never_partially_writes(self):
        for changes in [
            {'ids': self.ids, 'changes': {'date': '2025-02-30', 'precision': 'day'}},
            {'ids': self.ids, 'changes': {'tags': [str(i) for i in range(20)]}},
            {'ids': self.ids, 'changes': {'title': 'not allowed'}},
            {'ids': self.ids + ['c' * 20], 'changes': {'favorite': True}},
        ]:
            with self.assertRaises((ValueError, KeyError)):
                self.repository.save_many(changes)
            self.assertFalse(self.repository.edits_path.exists())
