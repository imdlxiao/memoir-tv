"""Command line entry point and static publishing. Author: donglixiao."""
import argparse
import json
import shutil
from pathlib import Path
from urllib.parse import quote
from .http import Application, serve
from .scanner import scan
from .storage import Repository, atomic_json

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description='拾光 · 家庭回忆录')
    parser.add_argument('command', nargs='?', choices=['serve', 'scan', 'export'], default='serve')
    parser.add_argument('--config', type=Path, default=ROOT / 'config.local.json')
    parser.add_argument('--host')
    parser.add_argument('--port', type=int)
    parser.add_argument('--no-previews', action='store_true')
    parser.add_argument('--media-base', help='静态站点媒体 URL 前缀，例如 /family-media/')
    parser.add_argument('--out', type=Path, default=ROOT / 'dist')
    args = parser.parse_args()
    config_path = args.config if args.config.exists() else ROOT / 'config.example.json'
    config = json.loads(config_path.read_text(encoding='utf-8-sig'))
    repository = Repository(ROOT / 'data')
    media = Path(config['media_root']).resolve()
    ffmpeg = config.get('ffmpeg', 'ffmpeg')
    if args.command == 'scan':
        catalog = scan(media, repository.directory, ffmpeg, not args.no_previews)
        repository.replace_index(catalog)
        print(f"Indexed {len(catalog['items'])} memories; {len(catalog['warnings'])} preview warnings.")
    elif args.command == 'export':
        if not args.media_base:
            parser.error('export 需要 --media-base 指定静态媒体地址，不会复制原片')
        if not repository.index_path.exists():
            parser.error('请先运行 python -m memoir scan')
        out = args.out.resolve()
        if out == ROOT or out.is_relative_to(ROOT / 'web') or media == out or media.is_relative_to(out) or out.is_relative_to(media):
            parser.error('导出目录不能覆盖项目或原始素材')
        shutil.copytree(ROOT / 'web', out, dirs_exist_ok=True)
        shutil.copytree(repository.directory / 'thumbnails', out / 'thumbnails', dirs_exist_ok=True)
        catalog = repository.catalog()
        for item in catalog['items']:
            item['url'] = args.media_base.rstrip('/') + '/' + quote(item.pop('path'), safe='/')
            if item.get('thumbnail'):
                item['thumbnail'] = '.' + item['thumbnail']
        catalog['mode'] = 'static'
        atomic_json(out / 'data' / 'catalog.json', catalog)
        print(f'Static site exported to {out}')
    else:
        if not repository.index_path.exists():
            repository.replace_index(scan(media, repository.directory, ffmpeg, previews=False))
        app = Application(media, repository, ROOT / 'web', ffmpeg)
        app.start_scan()
        serve(app, args.host or config.get('host', '127.0.0.1'), args.port or config.get('port', 8765))


if __name__ == '__main__':
    main()
