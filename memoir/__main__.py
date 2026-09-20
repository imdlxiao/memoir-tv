"""Command line entry point and static publishing. Author: donglixiao."""
import argparse
import json
from pathlib import Path
from .exporter import export_static
from .http import Application, serve
from .scanner import scan
from .storage import Repository

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description='memoir-tv · 家庭回忆录')
    parser.add_argument('command', nargs='?', choices=['serve', 'scan', 'export'], default='serve')
    parser.add_argument('--config', type=Path, default=ROOT / 'config.local.json')
    parser.add_argument('--host')
    parser.add_argument('--port', type=int)
    parser.add_argument('--open', action='store_true', help='服务就绪后打开本机浏览器')
    parser.add_argument('--no-previews', action='store_true')
    parser.add_argument('--media-base', help='静态站点媒体 URL 前缀，例如 /family-media/')
    parser.add_argument('--out', type=Path, default=ROOT / 'dist')
    args = parser.parse_args()
    config_path = args.config if args.config.exists() else ROOT / 'config.example.json'
    config = json.loads(config_path.read_text(encoding='utf-8-sig'))
    data_root = Path(config.get('data_root', ROOT / 'data'))
    if not data_root.is_absolute():
        data_root = ROOT / data_root
    repository = Repository(data_root.resolve())
    media = Path(config['media_root']).resolve()
    ffmpeg = config.get('ffmpeg', 'ffmpeg')
    exiftool = config.get('exiftool', 'exiftool')
    if args.command == 'scan':
        catalog = scan(media, repository.directory, ffmpeg, not args.no_previews, exiftool)
        repository.replace_index(catalog)
        print(f"Indexed {len(catalog['items'])} memories; {len(catalog['warnings'])} preview warnings.")
    elif args.command == 'export':
        if not args.media_base:
            parser.error('export 需要 --media-base 指定静态媒体地址，不会复制原片')
        if not repository.index_path.exists():
            parser.error('请先运行 python -m memoir scan')
        out = args.out.resolve()
        try:
            export_static(ROOT / 'web', repository, media, args.media_base, out)
        except ValueError as exc:
            parser.error(str(exc))
        print(f'Static site exported to {out}')
    else:
        if not repository.index_path.exists():
            repository.replace_index(scan(media, repository.directory, ffmpeg, previews=False))
        app = Application(media, repository, ROOT / 'web', ffmpeg, exiftool)
        app.start_scan()
        serve(app, args.host or config.get('host', '127.0.0.1'), args.port or config.get('port', 8765), args.open)


if __name__ == '__main__':
    main()
