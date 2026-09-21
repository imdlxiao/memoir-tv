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
    parser.add_argument('command', nargs='?', choices=['serve', 'scan', 'export', 'reset-admin'], default='serve')
    parser.add_argument('--config', type=Path, default=ROOT / 'config.local.json')
    parser.add_argument('--host')
    parser.add_argument('--port', type=int)
    parser.add_argument('--open', action='store_true', help='服务就绪后打开本机浏览器')
    parser.add_argument('--public', action='store_true', help='明确导出无登录保护的公开静态副本，仅包含全部用户可见的素材')
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
    if args.command == 'reset-admin':
        import getpass
        from .auth import AuthService
        print('请先停止 memoir-tv 服务，恢复完成后重新启动。仅在素材电脑本机执行。')
        password = getpass.getpass('新管理员密码（至少 12 位，含字母和数字）：')
        if password != getpass.getpass('再次输入：'):
            parser.error('两次密码不一致')
        try:
            username = AuthService(repository.directory).recover_owner(password)
        except ValueError as exc:
            parser.error(str(exc))
        print(f'已重置 {username} 的密码并撤销其全部登录，请重新启动网站。')
    elif args.command == 'scan':
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
            export_static(ROOT / 'web', repository, media, args.media_base, out, allow_public=args.public)
        except ValueError as exc:
            parser.error(str(exc))
        print(f'Static site exported to {out}')
    else:
        if not repository.index_path.exists():
            repository.replace_index(scan(media, repository.directory, ffmpeg, previews=False))
        app = Application(media, repository, ROOT / 'web', ffmpeg, exiftool)
        app.secure_cookies = config.get('secure_cookies', False) is True
        if not app.auth.store.state['users']:
            print(f'首次创建超级管理员：请在登录页填写本机初始化码，文件位置：{app.auth.store.setup_path}', flush=True)
        app.start_scan()
        serve(app, args.host or config.get('host', '127.0.0.1'), args.port or config.get('port', 8765), args.open)


if __name__ == '__main__':
    main()
