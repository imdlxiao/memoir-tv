"""Range streaming and path confinement integration tests. Author: donglixiao."""
import http.client
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from memoir.http import Application, byte_range, handler_for
from memoir.storage import Repository


class RangeTests(unittest.TestCase):
    def test_ranges(self):
        self.assertEqual(byte_range('bytes=0-3', 10), (0, 3))
        self.assertEqual(byte_range('bytes=7-', 10), (7, 9))
        self.assertEqual(byte_range('bytes=-3', 10), (7, 9))
        for header in ['bytes=10-', 'bytes=-0', 'bytes=3-1', 'bytes=0-1,3-4']:
            with self.assertRaises(ValueError):
                byte_range(header, 10)

    def test_http_stream_and_security(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            media = root / 'media'
            media.mkdir()
            (media / 'test.mp4').write_bytes(b'0123456789')
            repository = Repository(root / 'data')
            repository.replace_index({'items': [{'id': 'test', 'path': 'test.mp4'}, {'id': 'bad', 'path': '../secret.txt'}]})
            server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(Application(media, repository, root / 'web', 'ffmpeg')))
            threading.Thread(target=server.serve_forever, daemon=True).start()
            connection = http.client.HTTPConnection('127.0.0.1', server.server_port)
            try:
                connection.request('GET', '/media/test', headers={'Range': 'bytes=2-5'})
                response = connection.getresponse()
                self.assertEqual(response.status, 206)
                self.assertEqual(response.read(), b'2345')
                connection.request('GET', '/media/bad')
                response = connection.getresponse()
                self.assertEqual(response.status, 403)
                response.read()
                connection.request('PATCH', '/api/memories/test', json.dumps({'title': 'test'}), {'Content-Type': 'application/json', 'Origin': 'https://evil.example'})
                response = connection.getresponse()
                self.assertEqual(response.status, 403)
                response.read()
            finally:
                connection.close()
                server.shutdown()
                server.server_close()
