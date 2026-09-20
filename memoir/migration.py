"""Plan and verify media copies while retaining stable memory identities. Author: donglixiao."""
import datetime as dt
import hashlib
import os
import shutil
import uuid
from pathlib import Path
from .domain import validate_edit
from .storage import atomic_json


def confined(root, relative):
    root = Path(root).resolve()
    path = (root / relative).resolve()
    if path == root or not path.is_relative_to(root):
        raise ValueError('迁移路径超出指定目录')
    return path


def plan_move(source, destination, items):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if source == destination or source.is_relative_to(destination) or destination.is_relative_to(source):
        raise ValueError('迁移源和目标目录不能重叠')
    entries, used = [], set()
    for item in items:
        path = confined(source, item['path'])
        stat = path.stat()
        if not path.is_file() or (stat.st_size, stat.st_mtime_ns) != (item['size'], item['modified']):
            raise ValueError('素材已变化，请重新生成迁移计划')
        date = validate_edit({'date': item['date'], 'precision': item['precision']})['date']
        folder = f'{date[:4]}/{date[:7]}' if date else '日期待补'
        relative = f'{folder}/{path.name}'
        if relative.casefold() in used:
            relative = f'{folder}/{path.stem}-{item["id"][:8]}{path.suffix}'
        if relative.casefold() in used or confined(destination, relative).exists():
            raise ValueError('目标文件已存在，停止以免覆盖原片')
        used.add(relative.casefold())
        entries.append({'id': item['id'], 'source': item['path'], 'target': relative,
                        'size': stat.st_size, 'modified': stat.st_mtime_ns, 'inode': stat.st_ino})
    required = sum(entry['size'] for entry in entries)
    anchor = destination
    while not anchor.exists():
        anchor = anchor.parent
    if shutil.disk_usage(anchor).free < required + 1024 ** 3:
        raise ValueError('目标磁盘空间不足，需额外保留至少 1 GiB')
    return {'version': 1, 'createdAt': dt.datetime.now(dt.timezone.utc).isoformat(),
            'sourceRoot': str(source), 'destinationRoot': str(destination),
            'bytes': required, 'phase': 'planned', 'entries': entries}


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def copy_verified(plan, journal, progress=None):
    """Never delete sources. Publish each target only after its full hash matches."""
    plan['phase'] = 'copying'
    atomic_json(journal, plan)
    for entry in plan['entries']:
        source = confined(plan['sourceRoot'], entry['source'])
        target = confined(plan['destinationRoot'], entry['target'])
        stat = source.stat()
        if (stat.st_size, stat.st_mtime_ns, stat.st_ino) != (entry['size'], entry['modified'], entry['inode']):
            raise ValueError('源文件已变化，停止迁移')
        if entry.get('verified'):
            if not target.exists() or sha256_file(target) != entry['sha256']:
                raise ValueError('已校验的目标文件发生变化，停止迁移')
            continue
        if target.exists():
            raise ValueError('目标路径已存在，禁止覆盖')
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f'.{target.name}.{uuid.uuid4().hex}.partial')
        digest = hashlib.sha256()
        copied = 0
        with source.open('rb') as original, temporary.open('xb') as output:
            for chunk in iter(lambda: original.read(8 * 1024 * 1024), b''):
                digest.update(chunk)
                output.write(chunk)
                copied += len(chunk)
                if progress:
                    progress(entry, copied, 'copying')
            output.flush()
            os.fsync(output.fileno())
        after = source.stat()
        if copied != entry['size'] or (after.st_size, after.st_mtime_ns, after.st_ino) != (stat.st_size, stat.st_mtime_ns, stat.st_ino):
            raise ValueError('复制过程中原片变化，保留源文件并停止')
        if progress:
            progress(entry, copied, 'verifying')
        checksum = digest.hexdigest()
        if sha256_file(temporary) != checksum:
            raise ValueError('目标文件校验失败，保留源文件并停止')
        shutil.copystat(source, temporary)
        # Same-volume rename is atomic and refuses an existing destination on Windows.
        if target.exists():
            raise ValueError('目标路径已存在，禁止覆盖')
        temporary.rename(target)
        entry.update(sha256=checksum, verified=True)
        atomic_json(journal, plan)
        if progress:
            progress(entry, copied, 'verified')
    plan['phase'] = 'verified'
    atomic_json(journal, plan)
    return plan
