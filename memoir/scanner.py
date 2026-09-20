"""Read-only media discovery and optional preview generation. Author: donglixiao."""
import datetime as dt
import hashlib
import subprocess
from pathlib import Path
from .domain import PHOTO_EXTENSIONS, VIDEO_EXTENSIONS, inferred_date
from .metadata import read_metadata


def scan(root, directory, ffmpeg='ffmpeg', previews=True, exiftool='exiftool'):
    root, directory = Path(root).resolve(), Path(directory)
    if not root.is_dir():
        raise ValueError('素材目录不存在，请检查 config.local.json 中的 media_root')
    thumbnails = directory / 'thumbnails'
    thumbnails.mkdir(parents=True, exist_ok=True)
    items, warnings = [], []
    for path in sorted(root.rglob('*')):
        extension = path.suffix.lower()
        if extension not in PHOTO_EXTENSIONS | VIDEO_EXTENSIONS or not path.is_file():
            continue
        if not path.resolve().is_relative_to(root):
            continue
        relative = path.relative_to(root).as_posix()
        identity = hashlib.sha256(relative.encode('utf-8')).hexdigest()[:20]
        try:
            stat = path.stat()
        except FileNotFoundError:
            # Files can be moved while a directory is being discovered.
            continue
        date = inferred_date(path.name)
        kind = 'photo' if extension in PHOTO_EXTENSIONS else 'video'
        item = dict(id=identity, path=relative, filename=path.name, kind=kind,
                    title='', description='', date=date, precision='day' if date else 'unknown',
                    dateSource='filename' if date else 'unknown', location='', tags=[], favorite=False,
                    size=stat.st_size, modified=stat.st_mtime_ns)
        fingerprint = f'{identity}-{stat.st_size}-{stat.st_mtime_ns}'
        item.update(read_metadata(path, directory, fingerprint, exiftool, extract=previews))
        if previews and item['metadataStatus'] == 'unavailable' and not any('ExifTool' in warning for warning in warnings):
            warnings.append('部分原片信息未能读取，请检查 ExifTool 配置后重新扫描；手动标注仍可使用')
        if item['capture'].get('takenAt'):
            item.update(date=item['capture']['takenAt'][:10], precision='day', dateSource='embedded')
        thumb = thumbnails / f'{fingerprint}.jpg'
        if previews and not thumb.exists():
            command = [ffmpeg, '-hide_banner', '-loglevel', 'error', '-y']
            if kind == 'video':
                command += ['-ss', '1']
            command += ['-i', str(path), '-frames:v', '1', '-vf', 'scale=1000:1000:force_original_aspect_ratio=decrease', '-q:v', '4', str(thumb)]
            try:
                result = subprocess.run(command, capture_output=True, timeout=90, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                if result.returncode:
                    thumb.unlink(missing_ok=True)
                    warnings.append(f'{path.name}：未能生成预览，仍可打开原文件')
            except (OSError, subprocess.TimeoutExpired):
                thumb.unlink(missing_ok=True)
                warnings.append(f'{path.name}：预览工具不可用或超时')
        item['thumbnail'] = f'/thumbnails/{thumb.name}' if thumb.exists() else ''
        items.append(item)
    items.sort(key=lambda item: (item['date'], item['filename']), reverse=True)
    return {'version': 1, 'scannedAt': dt.datetime.now(dt.timezone.utc).isoformat(), 'items': items, 'warnings': warnings}
