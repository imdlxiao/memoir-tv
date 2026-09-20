"""Retain memory IDs when an explicit migration changes relative paths. Author: donglixiao."""
import re
from pathlib import PurePosixPath
from .storage import read_json


def path_identities(directory):
    document = read_json(directory / 'identities.json', {})
    if not isinstance(document, dict):
        raise ValueError('素材身份映射格式不正确')
    mappings = document.get('paths', {})
    if not isinstance(mappings, dict):
        raise ValueError('素材身份映射格式不正确')
    ids = set()
    for path, identity in mappings.items():
        if not isinstance(path, str) or PurePosixPath(path).is_absolute() or '..' in PurePosixPath(path).parts or '\\' in path:
            raise ValueError('素材身份映射路径不正确')
        if not isinstance(identity, str) or not re.fullmatch(r'[a-f0-9]{20}', identity) or identity in ids:
            raise ValueError('素材身份映射必须一一对应')
        ids.add(identity)
    return mappings
