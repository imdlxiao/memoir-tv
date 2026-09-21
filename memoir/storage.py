"""Atomic JSON repository; metadata never writes to source media. Author: donglixiao."""
import json
import os
import threading
import uuid
import copy
import hashlib
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


class PlaybackCache:
    """Versioned derivatives only; source timestamps invalidate stale playback copies."""
    def __init__(self, directory):
        self.directory = Path(directory) / 'playback'

    def target(self, identity, source):
        stat = source.stat()
        key = hashlib.sha256(f'smooth-v1:{identity}:{source}:{stat.st_size}:{stat.st_mtime_ns}'.encode()).hexdigest()
        return self.directory / (key + '.mp4')

    def available(self):
        import shutil
        self.directory.mkdir(parents=True, exist_ok=True)
        used = sum(p.stat().st_size for p in self.directory.glob('*.mp4'))
        # Reserve headroom for a long video and never fill the archive disk.
        return min(20 * 1024**3 - used, shutil.disk_usage(self.directory).free - 1024**3)


class SecurityRepository:
    """Private account state and append-only daily audit, outside the web root."""
    def __init__(self, directory):
        self.directory = Path(directory) / 'security'
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / 'accounts.json'
        self.setup_path = self.directory / 'setup-code.txt'
        self.lock = threading.RLock()
        self.revision = 0
        self.state = read_json(self.path, {'users': {}, 'sessions': {}, 'permissions': {},
            'settings': {'registration': True, 'defaultVisibility': 'admin', 'defaultVideoVisibility': 'all', 'sessionDays': 30}})

    def save(self, state):
        atomic_json(self.path, state)
        self.state = state
        self.revision += 1

    def setup_code(self):
        import secrets
        with self.lock:
            if self.state['users']:
                return None
            if not self.setup_path.exists():
                with self.setup_path.open('x', encoding='utf-8') as file:
                    file.write(secrets.token_urlsafe(32))
            return self.setup_path.read_text(encoding='utf-8').strip()

    def audit(self, event):
        import datetime as dt
        now = dt.datetime.now(dt.timezone.utc)
        with self.lock:
            folder = self.directory / 'audit'
            folder.mkdir(exist_ok=True)
            with (folder / f'{now:%Y-%m-%d}.jsonl').open('a', encoding='utf-8', newline='\n') as file:
                file.write(json.dumps({'time': now.isoformat(), **event}, ensure_ascii=False) + '\n')

    def logs(self, day='', cursor=0):
        import re
        with self.lock:
            folder = self.directory / 'audit'
            days = sorted((p.stem for p in folder.glob('*.jsonl')), reverse=True)
            day = day or (days[0] if days else '')
            if day and not re.fullmatch(r'\d{4}-\d{2}-\d{2}', day):
                raise ValueError('日志日期无效')
            path = folder / f'{day}.jsonl'
            if not path.exists():
                return {'days': days, 'day': day, 'items': [], 'cursor': None}
            with path.open('rb') as file:
                end = min(cursor or path.stat().st_size, path.stat().st_size)
                start = max(0, end - 65536)
                file.seek(start)
                if start:
                    file.readline()
                    start = file.tell()
                lines = file.read(end - start).splitlines(keepends=True)
                selected = lines[-100:]
                next_cursor = end - sum(map(len, selected))
                return {'days': days, 'day': day, 'items': [json.loads(line) for line in reversed(selected)],
                        'cursor': next_cursor if next_cursor > 0 else None}


class Repository:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.lock = threading.RLock()
        self.index_path = self.directory / 'catalog.json'
        self.edits_path = self.directory / 'memories.json'
        self._stamp = None
        self._catalog = None
        self._by_id = {}
        self._body = b''
        self._etag = ''

    def _refresh_cache(self):
        stamp = []
        for path in (self.index_path, self.edits_path):
            try:
                stat = path.stat()
                stamp.append((stat.st_ino, stat.st_size, stat.st_mtime_ns))
            except FileNotFoundError:
                stamp.append(None)
        if stamp == self._stamp:
            return
        index = read_json(self.index_path, {'items': [], 'scannedAt': None})
        edits = read_json(self.edits_path, {})
        self._catalog = {**index, 'items': [{**item, **edits.get(item['id'], {})} for item in index['items']]}
        self._by_id = {item['id']: item for item in self._catalog['items']}
        self._body = json.dumps({**self._catalog, 'mode': 'library'}, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        self._etag = '"' + hashlib.sha256(self._body).hexdigest() + '"'
        self._stamp = stamp

    def catalog_payload(self):
        with self.lock:
            self._refresh_cache()
            return self._body, self._etag

    def find(self, identity):
        with self.lock:
            self._refresh_cache()
            return copy.deepcopy(self._by_id.get(identity))

    def catalog(self):
        with self.lock:
            self._refresh_cache()
            return copy.deepcopy(self._catalog)

    def save(self, media_id, changes):
        with self.lock:
            if self.find(media_id) is None:
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
