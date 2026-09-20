"""Read original EXIF/QuickTime metadata locally, with fingerprint caching. Author: donglixiao."""
import datetime as dt
import hashlib
import json
import math
import re
import subprocess
from .domain import validate_coordinates
from .storage import atomic_json, read_json

TAGS = ('GPSLatitude', 'GPSLongitude', 'GPSLatitudeRef', 'GPSLongitudeRef', 'Make', 'Model', 'LensModel', 'DateTimeOriginal',
        'CreationDate', 'OffsetTimeOriginal', 'ExposureTime', 'FNumber', 'ISO',
        'FocalLength', 'ExposureCompensation', 'ImageWidth', 'ImageHeight', 'Duration',
        'VideoFrameRate', 'Rotation', 'FileType')


def normalize(raw):
    result = {'coordinates': None, 'capture': {}}
    capture = result['capture']
    try:
        latitude, longitude = raw.get('GPSLatitude'), raw.get('GPSLongitude')
        if raw.get('GPSLatitudeRef') in ('S', 'South') and isinstance(latitude, (int, float)):
            latitude = -abs(latitude)
        if raw.get('GPSLongitudeRef') in ('W', 'West') and isinstance(longitude, (int, float)):
            longitude = -abs(longitude)
        result['coordinates'] = validate_coordinates({
            'latitude': latitude, 'longitude': longitude})
    except ValueError:
        pass
    for tag, key in [('Make', 'make'), ('Model', 'model'), ('LensModel', 'lens'), ('FileType', 'format')]:
        if isinstance(raw.get(tag), str):
            capture[key] = raw[tag][:200]
    for tag, key in [('ExposureTime', 'exposure'), ('FNumber', 'aperture'), ('ISO', 'iso'),
                     ('FocalLength', 'focalLength'), ('ExposureCompensation', 'exposureBias'),
                     ('ImageWidth', 'width'), ('ImageHeight', 'height'), ('Duration', 'duration'),
                     ('VideoFrameRate', 'frameRate'), ('Rotation', 'rotation')]:
        number = raw.get(tag)
        if isinstance(number, (int, float)) and not isinstance(number, bool) and math.isfinite(number):
            capture[key] = number
    # QuickTime CreateDate may be an export/container timestamp. Only use explicit
    # camera capture fields; retain original local time without guessing a timezone.
    for tag in ('DateTimeOriginal', 'CreationDate'):
        value = raw.get(tag, '')
        if not isinstance(value, str):
            continue
        match = re.fullmatch(r'(\d{4}):(\d{2}):(\d{2})[ T](\d{2}:\d{2}:\d{2})(\.\d+)?(Z|[+-]\d{2}:\d{2})?', value)
        if match:
            year, month, day, time, fraction, zone = match.groups()
            offset = raw.get('OffsetTimeOriginal', '') if tag == 'DateTimeOriginal' else ''
            zone = zone or (offset if isinstance(offset, str) and re.fullmatch(r'[+-]\d{2}:\d{2}', offset) else '')
            stamp = f'{year}-{month}-{day}T{time}{fraction or ""}{zone}'
            try:
                dt.datetime.fromisoformat(stamp)
            except ValueError:
                continue
            capture.update(takenAt=stamp, dateTag=tag)
            break
    return result


def read_metadata(path, directory, fingerprint, executable='exiftool', extract=False):
    tool_key = hashlib.sha256(str(executable).encode()).hexdigest()[:10]
    cache = directory / 'metadata' / f'{fingerprint}-{tool_key}-v2.json'
    try:
        cached = read_json(cache, None)
    except (OSError, ValueError):
        cached = None
    if cached is not None:
        return cached
    if not extract:
        return {'coordinates': None, 'capture': {}, 'metadataStatus': 'pending'}
    try:
        if '\n' in str(path) or '\r' in str(path):
            raise ValueError('Newlines cannot be represented in an ExifTool argument file')
        # -fast2 stops at QuickTime mdat, losing moov metadata stored after video.
        command = [str(executable), '-config', '', '-json', '-n', '-fast', '-api', 'LargeFileSupport=1', '-charset', 'filename=UTF8',
                   *['-' + tag for tag in TAGS], '-@', '-']
        # UTF-8 argument stream avoids Windows ANSI command-line path conversion.
        process = subprocess.run(command, input=(str(path.resolve()) + '\n').encode('utf-8'), capture_output=True, timeout=30,
                                 creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if process.returncode:
            raise ValueError('Metadata read failed')
        raw = json.loads(process.stdout.decode('utf-8'))
        if not isinstance(raw, list) or not raw or not isinstance(raw[0], dict):
            raise ValueError('Invalid metadata response')
        result = normalize(raw[0])
        result['metadataStatus'] = 'read'
    except (OSError, ValueError, IndexError, TypeError, subprocess.TimeoutExpired):
        # Do not cache failures: an explicit rescan can retry after installing the tool.
        return {'coordinates': None, 'capture': {}, 'metadataStatus': 'unavailable'}
    atomic_json(cache, result)
    return result
