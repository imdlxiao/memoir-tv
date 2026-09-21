"""Synchronize live directory membership independently of preview jobs. Author: donglixiao."""
import threading
import time
from pathlib import Path
from .scanner import scan
from .storage import read_json
from .inventory import DirectoryInventory
from .auth import AuthService


class Application:
    def __init__(self, root, repository, web, ffmpeg, exiftool='exiftool'):
        self.root = Path(root).resolve()
        self.repository, self.web, self.ffmpeg = repository, Path(web).resolve(), ffmpeg
        self.exiftool = exiftool
        self.scan_lock = threading.Lock()
        self.catalog_lock = threading.Lock()
        self.scan_status = {'running': False, 'error': ''}
        self.inventory = DirectoryInventory(self.root)
        self.last_check = 0
        self.auth = AuthService(repository.directory)

    def _synchronize(self, force=False, background=False, snapshot=True):
        # Never hold this lock while decoding video. A page refresh must not wait
        # for previews, and a finished preview job must not publish stale paths.
        with self.catalog_lock:
            if background and time.monotonic() - self.last_check < 2:
                return self.repository.catalog() if snapshot else None, False
            changed = self.inventory.changed(force=force)
            self.last_check = time.monotonic()
            if not changed and not force and self.repository.index_path.exists():
                return self.repository.catalog() if snapshot else None, False
            previous = read_json(self.repository.index_path, {'items': []})
            try:
                current = scan(self.root, self.repository.directory, self.ffmpeg, previews=False, exiftool=self.exiftool,
                               files=self.inventory.signature, previous=None if force else previous['items'])
            except Exception:
                self.inventory.signature = None
                raise
            previous_files = {
                (item['id'], item.get('size'), item.get('modified'))
                for item in previous['items']
            }
            needs_previews = any(
                (not item['thumbnail'] or item.get('metadataStatus') == 'pending') and
                (item['id'], item['size'], item['modified']) not in previous_files
                for item in current['items']
            )
            if previous['items'] != current['items'] or not self.repository.index_path.exists():
                self.repository.replace_index(current)
            return self.repository.catalog() if snapshot else None, needs_previews

    def catalog_payload(self, background=False):
        _, needs_previews = self._synchronize(background=background, snapshot=False)
        if needs_previews:
            self.start_scan()
        return self.repository.catalog_payload()

    def catalog(self, background=False):
        catalog, needs_previews = self._synchronize(background=background)
        if needs_previews:
            self.start_scan()
        return catalog

    def start_scan(self):
        if not self.scan_lock.acquire(blocking=False):
            return False
        self.scan_status = {'running': True, 'error': ''}

        def run():
            try:
                self._synchronize(force=True)
                previews = scan(self.root, self.repository.directory, self.ffmpeg, exiftool=self.exiftool)
                # Re-discover membership after the potentially slow preview pass.
                # A file moved away during decoding cannot reappear in the index.
                self._synchronize(force=True)
                self.scan_status = {'running': False, 'error': '', 'warnings': previews['warnings']}
            except Exception as exc:
                self.scan_status = {'running': False, 'error': str(exc)}
            finally:
                self.scan_lock.release()

        threading.Thread(target=run, daemon=True).start()
        return True
