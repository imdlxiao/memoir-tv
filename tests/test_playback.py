"""Playback isolation, generation lifecycle and derivative authorization. Author: donglixiao."""
import http.client
import io
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from memoir.http import Application, handler_for
from memoir.storage import Repository
from auth_support import owner_session, PASSWORD


class PlaybackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.media = self.root / 'media'
        self.media.mkdir()
        self.original = self.media / 'movie.mp4'
        self.original.write_bytes(b'original-video-contents')
        self.repo = Repository(self.root / 'data')
        self.repo.replace_index({'items': [{'id': 'movie', 'path': 'movie.mp4', 'kind': 'video',
                                           'capture': {'duration': 30}}]})
        self.app = Application(self.media, self.repo, self.root / 'web', 'missing-ffmpeg')
        self.addCleanup(self.app.playback.close)

    def test_generation_reuses_cache_invalidates_changes_and_preserves_original(self):
        commands = []
        class Process:
            def __init__(self, command, **kwargs):
                commands.append(command)
                Path(command[-1]).write_bytes(b'playback-copy')
                self.stdout = io.StringIO('out_time_us=15000000\nprogress=end\n')
            def wait(self): return 0
            def poll(self): return 0
            def kill(self): pass
        service = self.app.playback
        with patch('memoir.playback.subprocess.Popen', Process):
            for _ in range(5): service.request('movie')
            service.pending.join()
        self.assertEqual(len(commands), 1)
        self.assertEqual(service.status('movie')['state'], 'ready')
        self.assertEqual(self.original.read_bytes(), b'original-video-contents')
        self.assertEqual(list(service.cache.directory.glob('*.part.mp4')), [])
        self.assertIn('+faststart', commands[0])
        self.assertIn('-map_metadata', commands[0])
        self.original.write_bytes(b'replaced-original')
        self.assertEqual(service.status('movie')['state'], 'missing')
        self.original.unlink()
        with self.assertRaises(KeyError): service.status('movie')

    def test_failure_and_path_confinement(self):
        self.app.playback.request('movie')
        self.app.playback.pending.join()
        self.assertEqual(self.app.playback.status('movie')['state'], 'failed')
        self.assertEqual(list(self.app.playback.cache.directory.glob('*.part.mp4')), [])
        outside = self.root / 'private.mp4'
        outside.write_bytes(b'private')
        self.repo.replace_index({'items': [{'id': 'bad', 'path': '../private.mp4', 'kind': 'video'}]})
        with self.assertRaises(KeyError): self.app.playback.request('bad')

    def test_changed_source_and_low_disk_never_publish(self):
        source = self.original
        class Process:
            def __init__(self, command, **kwargs):
                Path(command[-1]).write_bytes(b'partial-playback')
                source.write_bytes(b'changed-during-conversion')
                self.stdout = io.StringIO('progress=end\n')
            def wait(self): return 0
            def poll(self): return 0
            def kill(self): pass
        service = self.app.playback
        item, original, target = service.source('movie')
        with patch('memoir.playback.subprocess.Popen', Process):
            service.generate(item, original, target)
        self.assertFalse(target.exists())
        self.assertEqual(list(service.cache.directory.glob('*.part.mp4')), [])
        item, original, target = service.source('movie')
        with patch.object(service.cache, 'available', return_value=0), patch('memoir.playback.subprocess.Popen') as spawn:
            service.generate(item, original, target)
            spawn.assert_not_called()
        self.assertEqual(service.status('movie')['state'], 'failed')
        self.assertIn('空间不足', service.status('movie')['message'])

    def test_authorization_ranges_and_source_removal(self):
        owner_cookie = owner_session(self.app)
        actor = self.app.auth.resolve(owner_cookie.split('=', 1)[1])
        user, session = self.app.auth.create({'username': 'reader', 'password': PASSWORD}, ip='test')
        cookie = 'memoir_session=' + session[0]
        _, _, target = self.app.playback.source('movie')
        target.parent.mkdir(parents=True)
        target.write_bytes(b'0123456789')
        server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(self.app))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        conn = http.client.HTTPConnection('127.0.0.1', server.server_port)
        self.addCleanup(conn.close)
        def request(path, cookie_value=cookie, method='GET'):
            headers = {'Cookie': cookie_value, 'Range': 'bytes=2-5'}
            if method == 'POST': headers['Content-Type'] = 'application/json'
            conn.request(method, path, body='{}' if method == 'POST' else None, headers=headers)
            response = conn.getresponse()
            return response.status, response.read(), response.getheader('Cache-Control')
        self.assertEqual(request('/playback/movie', '')[0], 401)
        self.assertEqual(request('/playback/movie'), (206, b'2345', 'private, no-store'))
        self.app.auth.set_visibility(actor, 'movie', {'scope': 'admin', 'users': []}, 'test')
        for path, method in [('/playback/movie', 'GET'), ('/api/playback/movie', 'GET'), ('/api/playback/movie', 'POST')]:
            self.assertEqual(request(path, method=method)[0], 403)
        self.assertEqual(request('/playback/movie', owner_cookie)[0], 206)
        self.original.unlink()
        self.assertEqual(request('/playback/movie', owner_cookie)[0], 404)
