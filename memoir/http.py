"""HTTP adapter: static assets, byte ranges, and metadata API. Author: donglixiao."""
import json
import mimetypes
import re
import time
from http.cookies import SimpleCookie, CookieError
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, unquote, parse_qs
from .domain import validate_edit
from .library import Application
from .storage import read_json
from .auth import AccessError


def byte_range(header, size):
    match = re.fullmatch(r'bytes=(\d*)-(\d*)', header)
    if not match or not any(match.groups()) or size == 0:
        raise ValueError('Invalid range')
    first, last = match.groups()
    if not first:
        if int(last) == 0:
            raise ValueError('Invalid suffix')
        return max(0, size - int(last)), size - 1
    start, end = int(first), min(int(last), size - 1) if last else size - 1
    if start >= size or end < start:
        raise ValueError('Unsatisfiable range')
    return start, end


def handler_for(app):
    class Handler(BaseHTTPRequestHandler):
        server_version = 'Memoir/1.0'

        def log_message(self, format, *args):
            pass

        def json_response(self, value, status=200):
            body = json.dumps(value, ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            if getattr(self, 'session_cookie', None):
                self.send_header('Set-Cookie', self.session_cookie)
            self.end_headers()
            if self.command != 'HEAD':
                self.wfile.write(body)

        def token(self):
            try:
                cookies = SimpleCookie(self.headers.get('Cookie', ''))
                return cookies['memoir_session'].value if 'memoir_session' in cookies else ''
            except CookieError:
                return ''

        def set_session(self, session=None):
            token, age = session or ('', 0)
            self.session_cookie = f'memoir_session={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={age}'
            if getattr(app, 'secure_cookies', False):
                self.session_cookie += '; Secure'

        def identity(self, admin=False):
            user = app.auth.resolve(self.token())
            if not user:
                raise AccessError('登录已过期或账号已停用，请重新登录', 401)
            if admin:
                app.auth.require_admin(user)
            return user

        def redirect(self, path):
            self.send_response(303)
            self.send_header('Location', path)
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', '0')
            self.end_headers()

        def do_HEAD(self):
            self.do_GET()

        def do_GET(self):
            try:
                self.get_resource()
            except AccessError as exc:
                if exc.status == 401:
                    self.set_session()
                self.json_response({'error': str(exc)}, exc.status)
            except (ValueError, TypeError):
                self.json_response({'error': '请求参数无效'}, 400)

        def get_resource(self):
            route = unquote(urlsplit(self.path).path)
            if route.startswith(('/api/playback/', '/playback/')):
                user = self.identity()
                identity = route.rsplit('/', 1)[-1]
                item = app.repository.find(identity)
                if not app.auth.can_view(user, identity, item.get('kind') if item else None):
                    raise AccessError('没有这条回忆的查看权限')
                try:
                    if route.startswith('/api/'):
                        return self.json_response(app.playback.status(identity))
                    _, _, target = app.playback.source(identity)
                    if target.is_file() and self.command != 'HEAD':
                        app.auth.viewed(user, identity, self.client_address[0], item.get('title') or item.get('filename', ''))
                    return self.serve_file(target, 'private, no-store', identity, 'video')
                except (KeyError, OSError):
                    return self.json_response({'error': '原片或流畅版不存在'}, 404)
            if route == '/api/auth/me':
                return self.json_response(app.auth.status(self.token()))
            if route in {'/', '/index.html', '/admin.html'}:
                if not app.auth.resolve(self.token()):
                    return self.redirect('/login.html')
                if route == '/admin.html':
                    try:
                        self.identity(admin=True)
                    except AccessError:
                        return self.redirect('/?denied=1')
            if route.startswith('/api/admin/'):
                actor = self.identity(admin=True)
                if route == '/api/admin/users':
                    return self.json_response({'users': app.auth.users(actor)})
                if route == '/api/admin/settings':
                    return self.json_response(app.auth.settings(actor))
                if route == '/api/admin/logs':
                    query = parse_qs(urlsplit(self.path).query)
                    cursor = int(query.get('cursor', ['0'])[0])
                    if cursor < 0:
                        raise ValueError('日志游标无效')
                    return self.json_response(app.auth.store.logs(query.get('day', [''])[0], cursor))
                return self.json_response({'error': '接口不存在'}, 404)
            if route in {'/api/catalog', '/data/catalog.json'}:
                user = self.identity()
                try:
                    body, etag = app.catalog_payload(background=parse_qs(urlsplit(self.path).query).get('background') == ['1'])
                    body, etag = app.auth.catalog(body, etag, user)
                    unchanged = self.headers.get('If-None-Match') == etag
                    self.send_response(304 if unchanged else 200)
                    self.send_header('ETag', etag)
                    self.send_header('Cache-Control', 'private, no-store')
                    self.send_header('Vary', 'Cookie')
                    self.send_header('Content-Type', 'application/json; charset=utf-8')
                    self.send_header('X-Content-Type-Options', 'nosniff')
                    if not unchanged:
                        self.send_header('Content-Length', str(len(body)))
                    self.end_headers()
                    if not unchanged and self.command != 'HEAD':
                        self.wfile.write(body)
                    return
                except (OSError, ValueError):
                    return self.json_response({'error': '素材目录暂不可用，请检查磁盘连接和目录配置'}, 503)
            if route == '/api/status':
                self.identity(admin=True)
                return self.json_response({**app.scan_status, 'storage': {
                    'mediaRoot': str(app.root), 'dataRoot': str(app.repository.directory.resolve())}})
            if route == '/api/backup':
                self.identity(admin=True)
                return self.json_response({'version': 1, 'memories': read_json(app.repository.edits_path, {})})
            if route.startswith('/media/'):
                user = self.identity()
                media_id = route.removeprefix('/media/')
                item = app.repository.find(media_id)
                if not app.auth.can_view(user, media_id, item.get('kind') if item else None):
                    raise AccessError('没有这条回忆的查看权限')
                if not item:
                    return self.json_response({'error': '素材不存在'}, 404)
                path = (app.root / item['path']).resolve()
                if not path.is_relative_to(app.root):
                    return self.json_response({'error': '无效素材路径'}, 403)
                if path.is_file() and self.command != 'HEAD':
                    app.auth.viewed(user, media_id, self.client_address[0], item.get('title') or item.get('filename', ''))
                return self.serve_file(path, 'private, no-store', media_id, item.get('kind'))
            if route.startswith('/thumbnails/'):
                user = self.identity()
                filename = route.removeprefix('/thumbnails/')
                media_id = filename.split('-')[0]
                item = app.repository.find(media_id)
                if not app.auth.can_view(user, media_id, item.get('kind') if item else None):
                    raise AccessError('没有这条回忆的查看权限')
                if not item or unquote(urlsplit(item.get('thumbnail', '')).path).rsplit('/', 1)[-1] != filename:
                    return self.json_response({'error': '封面不存在'}, 404)
                base = (app.repository.directory / 'thumbnails').resolve()
                path = (base / route.removeprefix('/thumbnails/')).resolve()
            else:
                if route.startswith(('/api/', '/data/')):
                    return self.json_response({'error': '接口不存在'}, 404)
                base = app.web
                path = (base / (route.lstrip('/') or 'index.html')).resolve()
            if not path.is_relative_to(base):
                return self.json_response({'error': '无效路径'}, 403)
            self.serve_file(path, 'private, no-store' if route.startswith('/thumbnails/') or path.suffix == '.html' else 'no-cache')

        def serve_file(self, path, cache_control='no-cache', media_id=None, media_kind=None):
            if not path.is_file():
                return self.json_response({'error': '文件不存在'}, 404)
            try:
                with path.open('rb') as file:
                    size = path.stat().st_size
                    start, end, status = 0, size - 1, 200
                    if self.headers.get('Range'):
                        try:
                            start, end = byte_range(self.headers['Range'], size)
                            status = 206
                        except ValueError:
                            self.send_response(416)
                            self.send_header('Content-Range', f'bytes */{size}')
                            self.send_header('Content-Length', '0')
                            self.end_headers()
                            return
                    mime = {'.js': 'text/javascript', '.m4v': 'video/mp4', '.mov': 'video/quicktime'}.get(path.suffix.lower()) or mimetypes.guess_type(str(path))[0] or 'application/octet-stream'
                    self.send_response(status)
                    self.send_header('Content-Type', mime)
                    self.send_header('Content-Length', str(end - start + 1))
                    self.send_header('Accept-Ranges', 'bytes')
                    self.send_header('X-Content-Type-Options', 'nosniff')
                    self.send_header('Referrer-Policy', 'same-origin')
                    self.send_header('X-Frame-Options', 'DENY')
                    self.send_header('Cache-Control', cache_control)
                    if status == 206:
                        self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
                    self.end_headers()
                    if self.command == 'HEAD':
                        return
                    file.seek(start)
                    remaining = end - start + 1
                    last_auth_check = 0
                    while remaining > 0:
                        if media_id and time.monotonic() - last_auth_check > 1:
                            if not app.auth.can_view(app.auth.resolve(self.token()), media_id, media_kind):
                                break
                            last_auth_check = time.monotonic()
                        chunk = file.read(min(256 * 1024, remaining))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        remaining -= len(chunk)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass

        def mutate(self):
            origin = self.headers.get('Origin')
            if (origin and urlsplit(origin).netloc != self.headers.get('Host')) or self.headers.get('Sec-Fetch-Site') == 'cross-site':
                return self.json_response({'error': '不允许跨站修改'}, 403)
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                return self.json_response({'error': '需要 JSON 请求'}, 415)
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 4 * 1024 * 1024:
                    return self.json_response({'error': '请求内容大小超限'}, 413)
                value = json.loads(self.rfile.read(length))
                if not isinstance(value, dict):
                    raise ValueError('请求必须是 JSON 对象')
                route = urlsplit(self.path).path
                ip = self.client_address[0]
                if self.command == 'POST' and route in {'/api/auth/login', '/api/auth/register', '/api/auth/setup'}:
                    app.auth.throttle(ip)
                    if route.endswith('/login'):
                        user, session = app.auth.login(value, ip)
                    else:
                        user, session = app.auth.create(value, ip, setup=route.endswith('/setup'))
                    self.set_session(session)
                    return self.json_response({'user': user})
                if self.command == 'POST' and route == '/api/auth/logout':
                    app.auth.logout(self.token(), app.auth.resolve(self.token()), ip)
                    self.set_session()
                    return self.json_response({'ok': True})
                actor = self.identity()
                if self.command == 'POST' and route.startswith('/api/playback/'):
                    identity = route.rsplit('/', 1)[-1]
                    item = app.repository.find(identity)
                    if not app.auth.can_view(actor, identity, item.get('kind') if item else None):
                        raise AccessError('没有这条回忆的查看权限')
                    return self.json_response(app.playback.request(identity), 202)
                if self.command == 'POST' and route == '/api/auth/password':
                    app.auth.throttle(ip)
                    app.auth.change_password(actor, value, ip)
                    self.set_session()
                    return self.json_response({'ok': True})
                app.auth.require_admin(actor)
                if self.command == 'POST' and route == '/api/admin/users':
                    user, _ = app.auth.create(value, ip, actor=actor)
                    return self.json_response({'user': user}, 201)
                if self.command == 'PATCH' and route.startswith('/api/admin/users/'):
                    return self.json_response({'user': app.auth.update_user(actor, route.rsplit('/', 1)[-1], value, ip)})
                if self.command == 'PATCH' and route.startswith('/api/admin/visibility/'):
                    identity = route.rsplit('/', 1)[-1]
                    if not app.repository.find(identity):
                        raise KeyError(identity)
                    return self.json_response(app.auth.set_visibility(actor, identity, value, ip))
                if self.command == 'PATCH' and route == '/api/admin/settings':
                    # Discover media before changing the default for future arrivals.
                    app.auth.catalog(*app.catalog_payload(), actor)
                    return self.json_response(app.auth.settings(actor, value, ip))
                if self.command == 'POST' and route == '/api/batch':
                    app.catalog()
                    count = app.repository.save_many(value)
                    app.auth.record('media.batch', actor, ip, str(count))
                    return self.json_response({'count': count})
                if self.command == 'PATCH' and route.startswith('/api/memories/'):
                    app.repository.save(route.rsplit('/', 1)[-1], validate_edit(value))
                    app.auth.record('media.edit', actor, ip, route.rsplit('/', 1)[-1])
                    return self.json_response({'ok': True})
                if self.command == 'POST' and route == '/api/scan':
                    started = app.start_scan()
                    app.auth.record('library.scan', actor, ip)
                    return self.json_response({'started': started}, 202)
                if self.command == 'POST' and route == '/api/import':
                    if not isinstance(value, dict) or value.get('version') != 1:
                        raise ValueError('不支持的备份版本')
                    count = app.repository.import_edits(value.get('memories'))
                    app.auth.record('library.import', actor, ip, str(count))
                    return self.json_response({'count': count})
                return self.json_response({'error': '接口不存在'}, 404)
            except AccessError as exc:
                if exc.status == 401:
                    self.set_session()
                return self.json_response({'error': str(exc)}, exc.status)
            except (ValueError, TypeError) as exc:
                return self.json_response({'error': str(exc)}, 400)
            except KeyError:
                return self.json_response({'error': '回忆不存在'}, 404)
            except OSError:
                return self.json_response({'error': '保存失败，请检查磁盘空间与写入权限'}, 500)

        do_POST = mutate
        do_PATCH = mutate

    return Handler


def serve(app, host, port, open_browser=False):
    server = ThreadingHTTPServer((host, port), handler_for(app))
    print(f'memoir-tv: http://{host}:{port}', flush=True)
    if open_browser:
        import webbrowser
        browser_host = '127.0.0.1' if host == '0.0.0.0' else host
        webbrowser.open(f'http://{browser_host}:{port}')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        app.playback.close()
        server.server_close()
