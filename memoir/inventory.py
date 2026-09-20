"""Cache directory membership; periodically reconcile in-place file changes. Author: donglixiao."""
import os
import time
from pathlib import Path
from .domain import PHOTO_EXTENSIONS, VIDEO_EXTENSIONS


class DirectoryInventory:
    def __init__(self, root, reconcile_seconds=60):
        self.root = Path(root).resolve()
        self.reconcile_seconds = reconcile_seconds
        self.directories = {}
        self.signature = None
        self.last_full = 0

    def changed(self, force=False):
        if not self.root.is_dir():
            raise ValueError('素材目录暂不可用')
        now = time.monotonic()
        full = force or now - self.last_full >= self.reconcile_seconds
        pending, visited, files = [self.root], set(), []
        updated, refreshed = {}, False
        while pending:
            directory = pending.pop()
            resolved = directory.resolve()
            if resolved in visited or not resolved.is_relative_to(self.root):
                continue
            visited.add(resolved)
            try:
                stamp = directory.stat().st_mtime_ns
                cached = self.directories.get(directory)
                if not full and cached and cached[0] == stamp:
                    children, entries = cached[1:]
                else:
                    refreshed = True
                    children, entries = [], []
                    with os.scandir(directory) as stream:
                        for entry in stream:
                            if entry.is_symlink():
                                continue
                            try:
                                if entry.is_dir(follow_symlinks=False):
                                    children.append(Path(entry.path))
                                elif Path(entry.name).suffix.lower() in PHOTO_EXTENSIONS | VIDEO_EXTENSIONS and entry.is_file(follow_symlinks=False):
                                    stat = entry.stat(follow_symlinks=False)
                                    entries.append((entry.path, stat.st_size, stat.st_mtime_ns, stat.st_ino))
                            except FileNotFoundError:
                                continue
                updated[directory] = (stamp, children, entries)
                pending.extend(child for child in children if child not in visited)
                files.extend(entries)
            except FileNotFoundError:
                if directory == self.root:
                    raise ValueError('素材目录暂不可用')
        if not self.root.is_dir():
            raise ValueError('素材目录暂不可用')
        signature = tuple(sorted(files)) if refreshed or set(updated) != set(self.directories) else self.signature
        changed = signature != self.signature
        self.signature, self.directories = signature, updated
        if full:
            self.last_full = now
        return changed
