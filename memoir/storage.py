"""Atomic JSON repository; metadata never writes to source media. Author: donglixiao."""
import json
import os
import threading
import uuid
from pathlib import Path


def read_json(path, default):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f'.{path.name}.{uuid.uuid4().hex}.tmp')
    try:
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class Repository:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.lock = threading.RLock()
        self.index_path = self.directory / 'catalog.json'
        self.edits_path = self.directory / 'memories.json'

    def catalog(self):
        with self.lock:
            index = read_json(self.index_path, {'items': [], 'scannedAt': None})
            edits = read_json(self.edits_path, {})
            return {**index, 'items': [{**item, **edits.get(item['id'], {})} for item in index['items']]}

    def save(self, media_id, changes):
        with self.lock:
            if not any(item['id'] == media_id for item in self.catalog()['items']):
                raise KeyError(media_id)
            edits = read_json(self.edits_path, {})
            edits[media_id] = {**edits.get(media_id, {}), **changes}
            if self.edits_path.exists():
                atomic_json(self.directory / 'memories.backup.json', read_json(self.edits_path, {}))
            atomic_json(self.edits_path, edits)

    def replace_index(self, index):
        with self.lock:
            atomic_json(self.index_path, index)

    def save_many(self, value):
        from .domain import validate_batch, validate_edit
        ids, changes, tag_mode = validate_batch(value)
        with self.lock:
            current = {item['id']: item for item in self.catalog()['items']}
            if any(identity not in current for identity in ids):
                raise KeyError('部分素材已移出，请刷新后重新选择')
            previous = read_json(self.edits_path, {})
            updated = dict(previous)
            for identity in ids:
                patch = dict(changes)
                if 'tags' in changes:
                    existing = current[identity].get('tags', [])
                    if tag_mode == 'append':
                        patch['tags'] = list(dict.fromkeys(existing + changes['tags']))
                    elif tag_mode == 'remove':
                        patch['tags'] = [tag for tag in existing if tag not in changes['tags']]
                # Validate the merged tags before writing any record.
                patch = validate_edit(patch)
                updated[identity] = {**previous.get(identity, {}), **patch}
            atomic_json(self.directory / 'memories.backup.json', previous)
            atomic_json(self.edits_path, updated)
        return len(ids)

    def import_edits(self, edits):
        from .domain import validate_edit
        if not isinstance(edits, dict) or len(edits) > 100000:
            raise ValueError('备份格式不正确')
        validated = {key: validate_edit(value) for key, value in edits.items() if isinstance(key, str)}
        with self.lock:
            previous = read_json(self.edits_path, {})
            atomic_json(self.directory / 'memories.backup.json', previous)
            atomic_json(self.edits_path, {**previous, **validated})
        return len(validated)
