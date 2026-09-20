"""Publish a merged static snapshot without copying source media. Author: donglixiao."""
import shutil
from pathlib import Path
from urllib.parse import quote, urlsplit
from .storage import atomic_json


def export_static(web, repository, media_root, media_base, out):
    web, media_root, out = Path(web).resolve(), Path(media_root).resolve(), Path(out).resolve()
    data = repository.directory.resolve()
    protected = [web, media_root, data]
    if any(out == path or out.is_relative_to(path) or path.is_relative_to(out) for path in protected):
        raise ValueError('导出目录不能覆盖项目源码、回忆记录或原始素材')
    if urlsplit(media_base).scheme not in {'', 'http', 'https'}:
        raise ValueError('媒体地址必须为 HTTP(S) 或相对路径')
    catalog = repository.catalog()
    shutil.copytree(web, out, dirs_exist_ok=True)
    for item in catalog['items']:
        item['url'] = media_base.rstrip('/') + '/' + quote(item.pop('path'), safe='/')
        if item.get('thumbnail'):
            filename = Path(item['thumbnail']).name
            source = data / 'thumbnails' / filename
            if source.exists():
                (out / 'thumbnails').mkdir(exist_ok=True)
                shutil.copy2(source, out / 'thumbnails' / filename)
                item['thumbnail'] = f'./thumbnails/{filename}'
            else:
                item['thumbnail'] = ''
    catalog['mode'] = 'static'
    atomic_json(out / 'data' / 'catalog.json', catalog)
    return catalog
