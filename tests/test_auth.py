"""Authorization boundaries and account lifecycle with synthetic media. Author: donglixiao."""
import copy
import http.client
import json
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from memoir.auth import AuthService, AccessError, check_password
from memoir.exporter import export_static
from memoir.http import Application, handler_for
from memoir.scanner import scan
from memoir.storage import Repository
from auth_support import PASSWORD


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        media = self.root / 'media'; media.mkdir()
        for name in ('public.mp4', 'private.mp4', 'selected.png'):
            (media / name).write_bytes(b'0123456789')
        self.repo = Repository(self.root / 'data')
        self.repo.replace_index(scan(media, self.repo.directory, previews=False))
        self.ids = {item['filename']: item['id'] for item in self.repo.catalog()['items']}
        private = self.ids['private.mp4']
        index = self.repo.catalog()
        thumb = f'{private}-10-123.jpg'
        (self.repo.directory / 'thumbnails' / thumb).write_bytes(b'thumbnail')
        for item in index['items']:
            if item['id'] == private:
                item['thumbnail'] = '/thumbnails/' + thumb
        self.repo.replace_index(index)
        self.app = Application(media, self.repo, Path(__file__).parents[1] / 'web', 'missing-ffmpeg')
        self.auth = self.app.auth
        self.code = self.auth.store.setup_code()
        self.owner, session = self.auth.create({'username': 'owner', 'password': PASSWORD, 'code': self.code}, setup=True)
        self.owner_token = session[0]
        self.user, session = self.auth.create({'username': 'member', 'password': PASSWORD, 'role': 'admin'})
        self.user_token = session[0]
        self.other, session = self.auth.create({'username': 'other', 'password': PASSWORD})
        self.other_token = session[0]
        self.auth.set_visibility(self.owner, self.ids['public.mp4'], {'scope': 'all'}, '')
        self.auth.set_visibility(self.owner, self.ids['selected.png'], {'scope': 'selected', 'users': [self.user['id']]}, '')
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(self.app))
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.temporary.cleanup()

    def request(self, path, method='GET', value=None, token=None, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port)
        request_headers = dict(headers or {})
        if token:
            request_headers['Cookie'] = 'memoir_session=' + token
        if value is not None:
            request_headers['Content-Type'] = 'application/json'
        connection.request(method, path, json.dumps(value) if value is not None else None, request_headers)
        response = connection.getresponse()
        result = (response.status, dict(response.getheaders()), response.read())
        connection.close()
        return result

    def test_setup_and_registration_cannot_escalate(self):
        self.assertEqual(self.user['role'], 'user')
        self.assertFalse(self.auth.store.setup_path.exists())
        self.assertNotIn('password', self.owner)
        with self.assertRaises(AccessError):
            self.auth.create({'username': 'imposter', 'password': PASSWORD, 'code': self.code}, setup=True)
        with self.assertRaises(ValueError):
            self.auth.create({'username': 'MEMBER', 'password': PASSWORD})
        for password in ['short1', '1234567890123', 'abcdefghijklm']:
            with self.assertRaises(ValueError):
                self.auth.create({'username': 'newmember', 'password': password})
        stored = self.auth.store.state['users'][self.user['id']]['password']
        self.assertNotIn(PASSWORD, self.auth.store.path.read_text(encoding='utf-8'))
        self.assertTrue(check_password(PASSWORD, stored))

    def test_unauthenticated_routes_and_forged_token(self):
        self.assertEqual(self.request('/')[0], 303)
        self.assertEqual(self.request('/admin.html')[0], 303)
        for path in ['/api/catalog', '/data/catalog.json', '/api/backup', '/api/status', '/media/' + self.ids['public.mp4']]:
            for method in ('GET', 'HEAD'):
                self.assertEqual(self.request(path, method)[0], 401, path)
        self.assertEqual(self.request('/api/catalog', token=self.user_token + 'x')[0], 401)
        status, _, body = self.request('/api/auth/me')
        self.assertEqual(status, 200)
        self.assertIsNone(json.loads(body)['user'])
        for path in ['/data/security/accounts.json', '/security/setup-code.txt', '/data/memories.json']:
            self.assertEqual(self.request(path)[0], 404)

    def test_catalog_and_media_audiences_and_etags(self):
        # Use the cached synthetic catalog here to preserve its test thumbnail.
        with self.app.catalog_lock:
            self.app.inventory.changed()
        visible = {}
        for name, token in [('owner', self.owner_token), ('member', self.user_token), ('other', self.other_token)]:
            status, headers, body = self.request('/api/catalog', token=token)
            self.assertEqual(status, 200)
            catalog = json.loads(body)
            visible[name] = {item['filename'] for item in catalog['items']}
            self.assertTrue(all('path' not in item for item in catalog['items']))
            self.assertEqual(self.request('/api/catalog', token=token, headers={'If-None-Match': headers['ETag']})[0], 304)
            if name == 'owner':
                owner_tag = headers['ETag']
            else:
                self.assertNotEqual(headers['ETag'], owner_tag)
        self.assertEqual(len(visible['owner']), 3)
        self.assertEqual(visible['member'], {'public.mp4', 'selected.png'})
        self.assertEqual(visible['other'], {'public.mp4'})
        for kind in ('private.mp4', 'selected.png'):
            self.assertEqual(self.request('/media/' + self.ids[kind], token=self.other_token, headers={'Range': 'bytes=1-3'})[0], 403)
        status, headers, body = self.request('/media/' + self.ids['public.mp4'], token=self.user_token, headers={'Range': 'bytes=1-3'})
        self.assertEqual((status, body), (206, b'123'))
        self.assertEqual(headers['Cache-Control'], 'private, no-store')
        self.assertEqual(self.request('/thumbnails/' + self.ids['private.mp4'] + '-10-123.jpg', token=self.user_token)[0], 403)

    def test_member_cannot_write_or_read_administration(self):
        for path in ['/api/admin/users', '/api/admin/settings', '/api/admin/logs', '/api/status', '/api/backup']:
            self.assertEqual(self.request(path, token=self.user_token)[0], 403)
        for method, path, value in [
            ('PATCH', '/api/memories/' + self.ids['public.mp4'], {'title': 'tamper'}),
            ('PATCH', '/api/admin/visibility/' + self.ids['private.mp4'], {'scope': 'all'}),
            ('PATCH', '/api/admin/users/' + self.user['id'], {'role': 'admin'}),
            ('POST', '/api/scan', {}), ('POST', '/api/import', {}), ('POST', '/api/batch', {})]:
            self.assertEqual(self.request(path, method, value, self.user_token)[0], 403)

    def test_revocation_disabled_reset_logout_and_expiry(self):
        self.auth.update_user(self.owner, self.user['id'], {'enabled': False}, '')
        self.assertEqual(self.request('/api/catalog', token=self.user_token)[0], 401)
        self.auth.update_user(self.owner, self.user['id'], {'enabled': True}, '')
        self.assertIsNone(self.auth.resolve(self.user_token))
        _, session = self.auth.login({'username': 'member', 'password': PASSWORD}, '')
        self.auth.update_user(self.owner, self.user['id'], {'password': 'New-Password-1234'}, '')
        self.assertIsNone(self.auth.resolve(session[0]))
        self.auth.logout(self.other_token, self.other, '')
        self.assertIsNone(self.auth.resolve(self.other_token))
        state = copy.deepcopy(self.auth.store.state)
        for session in state['sessions'].values():
            session['expires'] = time.time() - 1
        self.auth.store.save(state)
        self.assertEqual(self.request('/api/catalog', token=self.owner_token)[0], 401)

    def test_cookie_flags_restart_and_csrf(self):
        status, headers, _ = self.request('/api/auth/login', 'POST', {'username': 'member', 'password': PASSWORD})
        self.assertEqual(status, 200)
        cookie = headers['Set-Cookie']
        for expected in ('HttpOnly', 'SameSite=Strict', 'Max-Age=2592000', 'Path=/'):
            self.assertIn(expected, cookie)
        self.assertNotIn('Domain=', cookie)
        restarted = AuthService(self.repo.directory)
        self.assertEqual(restarted.resolve(self.user_token)['id'], self.user['id'])
        for headers in [{'Origin': 'http://evil.example'}, {'Sec-Fetch-Site': 'cross-site'}]:
            self.assertEqual(self.request('/api/auth/logout', 'POST', {}, self.user_token, headers)[0], 403)
        self.app.secure_cookies = True
        self.assertIn('Secure', self.request('/api/auth/login', 'POST', {'username': 'member', 'password': PASSWORD})[1]['Set-Cookie'])

    def test_owner_protection_settings_and_default_visibility(self):
        for patch in [{'enabled': False}, {'role': 'user'}, {'password': PASSWORD}]:
            with self.assertRaises(AccessError):
                self.auth.update_user(self.owner, self.owner['id'], patch, '')
        self.request('/api/catalog', token=self.owner_token)
        self.request('/api/admin/settings', 'PATCH', {'registration': False, 'defaultVisibility': 'all', 'sessionDays': 7}, self.owner_token)
        self.assertFalse(self.auth.can_view(self.user, self.ids['private.mp4']))
        self.assertTrue(self.auth.can_view(self.user, 'future-item'))
        self.assertEqual(self.request('/api/auth/register', 'POST', {'username': 'another', 'password': PASSWORD})[0], 403)
        self.assertEqual(self.request('/api/admin/visibility/' + self.ids['private.mp4'], 'PATCH', {'scope': 'selected', 'users': ['missing']}, self.owner_token)[0], 400)

    def test_audit_visits_rate_limit_and_public_export(self):
        self.request('/media/' + self.ids['public.mp4'], token=self.user_token)
        self.request('/media/' + self.ids['public.mp4'], token=self.user_token, headers={'Range': 'bytes=1-3'})
        entries = self.auth.store.logs()['items']
        self.assertEqual(sum(event['action'] == 'media.view' for event in entries), 1)
        for _ in range(20):
            self.auth.throttle('rate-fixture')
        with self.assertRaises(AccessError):
            self.auth.throttle('rate-fixture')
        with self.assertRaises(ValueError):
            export_static(self.app.web, self.repo, self.app.root, '/media/', self.root / 'export')
        exported = export_static(self.app.web, self.repo, self.app.root, '/media/', self.root / 'export', allow_public=True)
        self.assertEqual([i['filename'] for i in exported['items']], ['public.mp4'])
        self.assertFalse((self.root / 'export' / 'data' / 'security').exists())
        with self.assertRaises(ValueError):
            export_static(self.app.web, self.repo, self.app.root, '/media/', self.root / 'export', allow_public=True)

    def test_audit_pagination_has_no_duplicates(self):
        for number in range(260):
            self.auth.record('test', self.owner, target=str(number))
        result = self.auth.store.logs()
        seen = []
        while True:
            seen.extend(event['target'] for event in result['items'] if event['action'] == 'test')
            if result['cursor'] is None:
                break
            result = self.auth.store.logs(result['day'], result['cursor'])
        self.assertEqual(seen, list(map(str, reversed(range(260)))))

    def test_change_password_and_local_owner_recovery(self):
        with self.assertRaises(AccessError):
            self.auth.change_password(self.user, {'currentPassword': 'wrong', 'password': 'Changed-password-123'}, '')
        self.auth.change_password(self.user, {'currentPassword': PASSWORD, 'password': 'Changed-password-123'}, '')
        self.assertIsNone(self.auth.resolve(self.user_token))
        self.assertEqual(self.auth.login({'username': 'member', 'password': 'Changed-password-123'}, '')[0]['id'], self.user['id'])
        self.assertEqual(self.auth.recover_owner('Recovered-password-123'), 'owner')
        self.assertIsNone(self.auth.resolve(self.owner_token))
        self.assertEqual(self.auth.login({'username': 'owner', 'password': 'Recovered-password-123'}, '')[0]['role'], 'admin')
