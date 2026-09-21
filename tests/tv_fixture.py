"""Disposable TV integration library; contains synthetic media only. Author: donglixiao."""
import argparse
import shutil
import sys
import tempfile
import threading
from contextlib import contextmanager
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from memoir.http import Application, handler_for
from memoir.scanner import scan
from memoir.storage import Repository
from auth_support import owner_session


@contextmanager
def tv_library(port=0):
    with tempfile.TemporaryDirectory(prefix='memoir-tv-remote-') as folder:
        root = Path(folder)
        media = root / 'media'
        media.mkdir()
        for name in ['20260101-test.mp4', '20260202-test.mp4']:
            shutil.copy2(ROOT / 'tests/fixtures/playback.mp4', media / name)
        repo = Repository(root / 'data')
        repo.replace_index(scan(media, repo.directory, previews=False))
        app = Application(media, repo, ROOT / 'web', 'missing-ffmpeg')
        owner_session(app)
        server = ThreadingHTTPServer(('127.0.0.1', port), handler_for(app))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            yield server, repo
        finally:
            server.shutdown()
            server.server_close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=18765)
    args = parser.parse_args()
    with tv_library(args.port) as (server, _):
        print(f'Synthetic TV fixture on 127.0.0.1:{server.server_port}', flush=True)
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            pass
