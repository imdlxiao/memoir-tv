"""Quiet login startup with a single-instance guard. Author: donglixiao."""
import contextlib
from datetime import datetime
import json
import os
from pathlib import Path
import runpy
import socket
import sys
import time
import traceback


ROOT = Path(__file__).resolve().parent.parent


@contextlib.contextmanager
def instance_lock(path):
    """The OS releases the lock even when the process crashes or Windows stops."""
    with path.open('a+b') as handle:
        handle.seek(0, os.SEEK_END)
        if not handle.tell():
            handle.write(b'0')
            handle.flush()
        handle.seek(0)
        acquired = False
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except OSError:
            pass
        try:
            yield acquired
        finally:
            if acquired:
                handle.seek(0)
                if os.name == 'nt':
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def port_in_use(host, port):
    address = {'0.0.0.0': '127.0.0.1', '::': '::1'}.get(host, host)
    try:
        with socket.create_connection((address, port), timeout=2):
            return True
    except OSError:
        return False


def wait_for_media(path, seconds=120):
    """Do not scan an unavailable external drive as an empty family library."""
    deadline = time.monotonic() + seconds
    while not path.is_dir():
        if time.monotonic() >= deadline:
            return False
        time.sleep(min(2, max(0, deadline - time.monotonic())))
    return True


def run_startup(root=ROOT):
    runtime = root / '.local'
    runtime.mkdir(exist_ok=True)
    with instance_lock(runtime / 'startup.lock') as acquired:
        if not acquired:
            return 0
        log_path = runtime / 'startup.log'
        if log_path.exists() and log_path.stat().st_size > 2 * 1024 * 1024:
            log_path.replace(runtime / 'startup.previous.log')
        with log_path.open('a', encoding='utf-8', buffering=1) as log:
            with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
                print(f'\n[{datetime.now().astimezone().isoformat(timespec="seconds")}] startup pid={os.getpid()}', flush=True)
                old_directory, old_arguments = Path.cwd(), sys.argv
                sys.path.insert(0, str(root))
                try:
                    config_path = root / 'config.local.json'
                    config = json.loads(config_path.read_text(encoding='utf-8-sig'))
                    host, port = config.get('host', '127.0.0.1'), int(config.get('port', 8765))
                    if port_in_use(host, port):
                        print(f'Port {port} is already occupied; no duplicate server was started.', flush=True)
                        return 0
                    media = Path(config['media_root'])
                    if not media.is_absolute():
                        media = root / media
                    if not media.is_dir():
                        print('Waiting up to 120 seconds for the media directory.', flush=True)
                    if not wait_for_media(media):
                        raise FileNotFoundError('Media directory is unavailable; library startup was cancelled.')
                    os.chdir(root)
                    sys.argv = ['memoir', 'serve', '--config', str(config_path)]
                    print(f'Starting memoir-tv at {host}:{port}.', flush=True)
                    runpy.run_module('memoir', run_name='__main__')
                    return 0
                except Exception:
                    traceback.print_exc()
                    return 1
                finally:
                    os.chdir(old_directory)
                    sys.argv = old_arguments
                    sys.path.pop(0)


if __name__ == '__main__':
    raise SystemExit(run_startup())
