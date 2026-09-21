"""Publish a merged static snapshot without copying source media. Author: donglixiao."""
import shutil
from pathlib import Path
from urllib.parse import quote, urlsplit
from .storage import atomic_json, read_json
from .domain import default_visibility


def export_static(web, repository, media_root, media_base, out, allow_public=False):
    web, media_root, out = Path(web).resolve(), Path(media_root).resolve(), Path(out).resolve()
    data = repository.directory.resolve()
    protected = [web, media_root, data]
    if any(out == path or out.is_relative_to(path) or path.is_relative_to(out) for path in protected):
        raise ValueError('导出目录不能覆盖项目源码、回忆记录或原始素材')
    if urlsplit(media_base).scheme not in {'', 'http', 'https'}:
        raise ValueError('媒体地址必须为 HTTP(S) 或相对路径')
    catalog = repository.catalog()
    security = read_json(data / 'security' / 'accounts.json', {})
    if security.get('users'):
        if not allow_public:
            raise ValueError('静态站点不能校验用户身份。确需公开副本时使用 --public，仅导出全部用户可见的内容')
        if out.exists() and any(out.iterdir()):
            raise ValueError('公开副本必须导出到新建的空目录，避免残留旧私密素材')
        permissions = security.get('permissions', {})
        catalog['items'] = [item for item in catalog['items'] if permissions.get(item['id'],
            {'scope': default_visibility(security['settings'], item.get('kind'))})['scope'] == 'all']
        catalog['warnings'] = []
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
