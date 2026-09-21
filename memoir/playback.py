"""Bounded, reusable H.264 playback copies; never rewrite originals. Author: donglixiao."""
import os
import queue
import subprocess
import threading
import uuid
from .storage import PlaybackCache


class PlaybackService:
    def __init__(self, root, repository, ffmpeg, encoder='libx264'):
        self.root, self.repository, self.ffmpeg = root, repository, ffmpeg
        if encoder not in {'libx264', 'h264_amf', 'h264_nvenc', 'h264_qsv'}:
            raise ValueError('Unsupported playback encoder')
        self.encoder = encoder
        self.cache = PlaybackCache(repository.directory)
        self.lock = threading.RLock()
        self.jobs = {}
        self.pending = queue.Queue(maxsize=8)
        self.worker = None
        self.stopped = threading.Event()
        self.process = None

    def source(self, identity):
        item = self.repository.find(identity)
        if not item or item.get('kind') != 'video':
            raise KeyError(identity)
        source = (self.root / item['path']).resolve()
        if not source.is_relative_to(self.root) or not source.is_file():
            raise KeyError(identity)
        return item, source, self.cache.target(identity, source)

    def status(self, identity):
        _, _, target = self.source(identity)
        with self.lock:
            if target.is_file():
                return {'state': 'ready', 'url': f'/playback/{identity}', 'size': target.stat().st_size}
            return dict(self.jobs.get(str(target), {'state': 'missing'}))

    def request(self, identity):
        with self.lock:
            state = self.status(identity)
            if state['state'] != 'missing':
                return state
            item, source, target = self.source(identity)
            if self.pending.full():
                return {'state': 'busy', 'message': '生成队列已满，请稍后再试'}
            # Bound terminal status memory as well as concurrent work.
            if len(self.jobs) > 512:
                self.jobs = {k: v for k, v in self.jobs.items() if v['state'] in {'queued', 'processing'}}
            self.jobs[str(target)] = {'state': 'queued', 'message': '等待生成流畅版'}
            self.pending.put_nowait((item, source, target))
            if not self.worker or not self.worker.is_alive():
                self.worker = threading.Thread(target=self.run, daemon=True)
                self.worker.start()
            return dict(self.jobs[str(target)])

    def run(self):
        while not self.stopped.is_set():
            try:
                item, source, target = self.pending.get(timeout=1)
            except queue.Empty:
                # Exit under the same lock used by request to avoid a lost wakeup.
                with self.lock:
                    if self.pending.empty():
                        self.worker = None
                        return
                continue
            try:
                self.generate(item, source, target)
            finally:
                self.pending.task_done()

    def generate(self, item, source, target):
        temporary = target.with_name(target.stem + '.' + uuid.uuid4().hex + '.part.mp4')
        process = None
        watchdog = None
        try:
            budget = min(self.cache.available(), 4 * 1024**3)
            if budget < 256 * 1024**2:
                raise ValueError('流畅版缓存空间不足，请管理员清理播放缓存（上限 20 GB）')
            with self.lock:
                self.jobs[str(target)] = {'state': 'processing', 'progress': 0, 'message': '正在生成流畅版'}
            command = [str(self.ffmpeg), '-hide_banner', '-loglevel', 'error', '-nostdin', '-y',
                       '-threads', '2', '-i', str(source), '-map', '0:v:0', '-map', '0:a:0?',
                       '-map_metadata', '-1', '-map_chapters', '-1', '-filter_threads', '1',
                       '-vf', "scale=w='min(1280,iw)':h='min(720,ih)':force_original_aspect_ratio=decrease:force_divisible_by=2,setsar=1,fps=30,format=yuv420p",
                       '-c:v', self.encoder, '-threads', '2', '-b:v', '2200k', '-maxrate', '2800k',
                       '-bufsize', '5600k', '-g', '60', '-c:a', 'aac', '-b:a', '128k', '-ac', '2',
                       '-movflags', '+faststart', '-progress', 'pipe:1', str(temporary)]
            if self.encoder == 'libx264':
                command[-1:-1] = ['-preset', 'veryfast']
            with self.lock:
                if self.stopped.is_set():
                    raise ValueError('服务已停止，下次打开视频可重新生成')
                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                    text=True, creationflags=(getattr(subprocess, 'CREATE_NO_WINDOW', 0) |
                                              getattr(subprocess, 'BELOW_NORMAL_PRIORITY_CLASS', 0)))
                self.process = process
            watchdog = threading.Timer(21600, process.kill)
            watchdog.daemon = True
            watchdog.start()
            duration = item.get('capture', {}).get('duration', 0)
            for line in process.stdout:
                if temporary.exists() and temporary.stat().st_size > budget:
                    process.kill()
                    raise ValueError('流畅版超过缓存空间限制，原片仍可播放')
                if line.startswith('out_time_us=') and duration:
                    try:
                        progress = min(99, int(float(line.split('=')[1]) / 10000 / duration))
                    except ValueError:
                        continue
                    with self.lock:
                        self.jobs[str(target)]['progress'] = max(0, progress)
            code = process.wait()
            if code != 0 or not temporary.is_file() or temporary.stat().st_size == 0:
                raise ValueError(f'生成失败（FFmpeg 退出码 {code}），请检查 H.264 编码器配置；原片仍可播放')
            if temporary.stat().st_size > budget:
                raise ValueError('流畅版超过缓存空间限制，原片仍可播放')
            if self.cache.target(item['id'], source) != target or self.source(item['id'])[1] != source:
                raise ValueError('原片已变更，请重新打开视频')
            os.replace(temporary, target)
            with self.lock:
                self.jobs.pop(str(target), None)
        except (OSError, ValueError, KeyError) as exc:
            message = str(exc) if isinstance(exc, ValueError) else '原片或转码工具不可用，请检查本机配置'
            with self.lock:
                self.jobs[str(target)] = {'state': 'failed', 'message': message}
        finally:
            if watchdog:
                watchdog.cancel()
            if process:
                if process.poll() is None:
                    process.kill()
                process.wait()
                process.stdout.close()
            temporary.unlink(missing_ok=True)
            with self.lock:
                self.process = None

    def warm(self):
        """Optional startup warmup, shortest first; shares the one-worker queue."""
        def run():
            items = sorted(self.repository.catalog()['items'], key=lambda i: i.get('size', 0))
            for item in items:
                if item.get('kind') != 'video' or self.stopped.is_set():
                    continue
                try:
                    while not self.stopped.is_set():
                        state = self.request(item['id'])['state']
                        if state in {'ready', 'failed'}:
                            break
                        self.stopped.wait(2)
                except (KeyError, OSError):
                    continue
        threading.Thread(target=run, daemon=True).start()

    def close(self):
        with self.lock:
            self.stopped.set()
            if self.process and self.process.poll() is None:
                self.process.kill()
        if self.worker:
            self.worker.join(timeout=5)
