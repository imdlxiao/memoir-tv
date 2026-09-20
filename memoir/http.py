"""HTTP adapter: static assets, byte ranges, and metadata API. Author: donglixiao."""
import json
import mimetypes
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, unquote
from .domain import validate_edit
from .scanner import scan
from .storage import read_json


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


class Application:
    def __init__(self, root, repository, web, ffmpeg):
        self.root = Path(root).resolve()
        self.repository, self.web, self.ffmpeg = repository, Path(web).resolve(), ffmpeg
        self.scan_lock = threading.Lock()
        self.scan_status = {'running': False, 'error': ''}

    def start_scan(self):
        if not self.scan_lock.acquire(blocking=False):
            return False
        self.scan_status = {'running': True, 'error': ''}
        def run():
            try:
                self.repository.replace_index(scan(self.root, self.repository.directory, self.ffmpeg))
                self.scan_status = {'running': False, 'error': ''}
            except Exception as exc:
                self.scan_status = {'running': False, 'error': str(exc)}
            finally:
                self.scan_lock.release()
        threading.Thread(target=run, daemon=True).start()
        return True


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
            self.end_headers()
            if self.command != 'HEAD':
                self.wfile.write(body)

        def do_HEAD(self):
            self.do_GET()

        def do_GET(self):
            route = unquote(urlsplit(self.path).path)
            if route == '/api/catalog':
                return self.json_response({**app.repository.catalog(), 'mode': 'library'})
            if route == '/api/status':
                return self.json_response(app.scan_status)
            if route == '/api/backup':
                return self.json_response({'version': 1, 'memories': read_json(app.repository.edits_path, {})})
            if route.startswith('/media/'):
                media_id = route.removeprefix('/media/')
                item = next((i for i in app.repository.catalog()['items'] if i['id'] == media_id), None)
                if not item:
                    return self.json_response({'error': '素材不存在'}, 404)
                path = (app.root / item['path']).resolve()
                if not path.is_relative_to(app.root):
                    return self.json_response({'error': '无效素材路径'}, 403)
                return self.serve_file(path)
            if route.startswith('/thumbnails/'):
                base = (app.repository.directory / 'thumbnails').resolve()
                path = (base / route.removeprefix('/thumbnails/')).resolve()
            else:
                base = app.web
                path = (base / (route.lstrip('/') or 'index.html')).resolve()
            if not path.is_relative_to(base):
                return self.json_response({'error': '无效路径'}, 403)
            self.serve_file(path)

        def serve_file(self, path):
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
                    self.send_header('Cache-Control', 'no-cache')
                    if status == 206:
                        self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
                    self.end_headers()
                    if self.command == 'HEAD':
                        return
                    file.seek(start)
                    remaining = end - start + 1
                    while remaining > 0:
                        chunk = file.read(min(256 * 1024, remaining))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        remaining -= len(chunk)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass

        def mutate(self):
            origin = self.headers.get('Origin')
            if origin and urlsplit(origin).netloc != self.headers.get('Host'):
                return self.json_response({'error': '不允许跨站修改'}, 403)
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                return self.json_response({'error': '需要 JSON 请求'}, 415)
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 4 * 1024 * 1024:
                    return self.json_response({'error': '请求内容大小超限'}, 413)
                value = json.loads(self.rfile.read(length))
                route = urlsplit(self.path).path
                if self.command == 'PATCH' and route.startswith('/api/memories/'):
                    app.repository.save(route.rsplit('/', 1)[-1], validate_edit(value))
                    return self.json_response({'ok': True})
                if self.command == 'POST' and route == '/api/scan':
                    return self.json_response({'started': app.start_scan()}, 202)
                if self.command == 'POST' and route == '/api/import':
                    if not isinstance(value, dict) or value.get('version') != 1:
                        raise ValueError('不支持的备份版本')
                    count = app.repository.import_edits(value.get('memories'))
                    return self.json_response({'count': count})
                return self.json_response({'error': '接口不存在'}, 404)
            except (ValueError, TypeError) as exc:
                return self.json_response({'error': str(exc)}, 400)
            except KeyError:
                return self.json_response({'error': '回忆不存在'}, 404)
            except OSError:
                return self.json_response({'error': '保存失败，请检查磁盘空间与写入权限'}, 500)

        do_POST = mutate
        do_PATCH = mutate

    return Handler


def serve(app, host, port):
    server = ThreadingHTTPServer((host, port), handler_for(app))
    print(f'Memoir TV: http://{host}:{port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
