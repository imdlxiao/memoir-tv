"""Synchronize live directory membership independently of preview jobs. Author: donglixiao."""
import threading
from pathlib import Path
from .scanner import scan
from .storage import read_json


class Application:
    def __init__(self, root, repository, web, ffmpeg):
        self.root = Path(root).resolve()
        self.repository, self.web, self.ffmpeg = repository, Path(web).resolve(), ffmpeg
        self.scan_lock = threading.Lock()
        self.catalog_lock = threading.Lock()
        self.scan_status = {'running': False, 'error': ''}

    def _synchronize(self):
        # Never hold this lock while decoding video. A page refresh must not wait
        # for previews, and a finished preview job must not publish stale paths.
        with self.catalog_lock:
            previous = read_json(self.repository.index_path, {'items': []})
            current = scan(self.root, self.repository.directory, self.ffmpeg, previews=False)
            previous_files = {
                (item['id'], item.get('size'), item.get('modified'))
                for item in previous['items']
            }
            needs_previews = any(
                not item['thumbnail'] and
                (item['id'], item['size'], item['modified']) not in previous_files
                for item in current['items']
            )
            if previous['items'] != current['items'] or not self.repository.index_path.exists():
                self.repository.replace_index(current)
            return self.repository.catalog(), needs_previews

    def catalog(self):
        catalog, needs_previews = self._synchronize()
        if needs_previews:
            self.start_scan()
        return catalog

    def start_scan(self):
        if not self.scan_lock.acquire(blocking=False):
            return False
        self.scan_status = {'running': True, 'error': ''}

        def run():
            try:
                self._synchronize()
                previews = scan(self.root, self.repository.directory, self.ffmpeg)
                # Re-discover membership after the potentially slow preview pass.
                # A file moved away during decoding cannot reappear in the index.
                self._synchronize()
                self.scan_status = {'running': False, 'error': '', 'warnings': previews['warnings']}
            except Exception as exc:
                self.scan_status = {'running': False, 'error': str(exc)}
            finally:
                self.scan_lock.release()

        threading.Thread(target=run, daemon=True).start()
        return True
