"""Identity, revocable sessions and media authorization. Author: donglixiao."""
import copy
import hashlib
import hmac
import secrets
import threading
import time
from .domain import validate_account, validate_password, validate_visibility, validate_security_settings, default_visibility
from .storage import SecurityRepository


class AccessError(Exception):
    def __init__(self, message, status=403):
        super().__init__(message)
        self.status = status


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), bytes.fromhex(salt), 600000).hex()
    return f'pbkdf2-sha256$600000${salt}${digest}'


def check_password(password, encoded):
    if not isinstance(password, str) or len(password) > 128:
        return False
    return hmac.compare_digest(password_hash(password, encoded.split('$')[2]), encoded)


def public_user(user):
    return {key: user[key] for key in ('id', 'username', 'phone', 'role', 'enabled', 'createdAt', 'lastLogin')}


class AuthService:
    def __init__(self, directory):
        self.store = SecurityRepository(directory)
        self.store.setup_code()
        self.attempts = {}
        self.access_times = {}
        self.rate_lock = threading.Lock()
        self.dummy_hash = password_hash('unused-account-password1')
        self.catalog_cache = {}
        self.catalog_bytes = 0

    def record(self, action, user=None, ip='', target='', outcome='ok'):
        self.store.audit({'action': action, 'actor': user['username'] if user else '',
                          'userId': user['id'] if user else '', 'ip': ip, 'target': target, 'outcome': outcome})

    def throttle(self, ip):
        now = time.time()
        with self.rate_lock:
            self.attempts = {key: [t for t in times if now - t < 900]
                             for key, times in self.attempts.items() if times and now - times[-1] < 900}
            times = self.attempts.setdefault(ip, [])
            if len(times) >= 20 or len(self.attempts) > 10000:
                raise AccessError('尝试过于频繁，请 15 分钟后再试', 429)
            times.append(now)

    def status(self, token):
        import json
        user = self.resolve(token)
        with self.store.lock:
            return {'user': public_user(user) if user else None, 'setupRequired': not bool(self.store.state['users']),
                    'accessRevision': hashlib.sha256(json.dumps(self.store.state['permissions'], sort_keys=True).encode()).hexdigest() if user else '',
                    'registration': bool(self.store.state['users']) and self.store.state['settings']['registration']}

    def resolve(self, token):
        if not token or len(token) > 128:
            return None
        key = hashlib.sha256(token.encode()).hexdigest()
        with self.store.lock:
            session = self.store.state['sessions'].get(key)
            if not session or session['expires'] <= time.time():
                return None
            user = self.store.state['users'].get(session['user'])
            return copy.deepcopy(user) if user and user['enabled'] else None

    @staticmethod
    def require_admin(user):
        if not user or user['role'] != 'admin':
            raise AccessError('此操作仅超级管理员可用')

    def _session(self, state, user):
        now = time.time()
        state['sessions'] = {key: session for key, session in state['sessions'].items() if session['expires'] > now}
        own = [key for key, session in state['sessions'].items() if session['user'] == user['id']]
        for key in own[:-19]:
            del state['sessions'][key]
        token = secrets.token_urlsafe(32)
        age = state['settings']['sessionDays'] * 86400
        state['sessions'][hashlib.sha256(token.encode()).hexdigest()] = {'user': user['id'], 'expires': now + age}
        user['lastLogin'] = now
        return token, age

    def create(self, value, ip='', actor=None, setup=False):
        username, password, phone = validate_account(value)
        with self.store.lock:
            state = copy.deepcopy(self.store.state)
            if setup:
                code = value.get('code', '')
                expected = self.store.setup_code()
                if not expected or not isinstance(code, str) or not hmac.compare_digest(code, expected):
                    raise AccessError('初始化码无效，或管理员已经创建')
            elif actor:
                self.require_admin(actor)
            elif not state['users'] or not state['settings']['registration']:
                raise AccessError('当前未开放注册')
            if any(u['username'].casefold() == username.casefold() for u in state['users'].values()):
                raise ValueError('用户名已存在')
            if len(state['users']) >= 1000:
                raise ValueError('家庭账号数量已达上限')
            uid = secrets.token_hex(16)
            user = {'id': uid, 'username': username, 'password': password_hash(password), 'phone': phone,
                    'role': 'admin' if setup else 'user', 'enabled': True, 'createdAt': time.time(), 'lastLogin': None}
            state['users'][uid] = user
            session = self._session(state, user) if not actor else None
            self.store.save(state)
            if setup:
                self.store.setup_path.unlink(missing_ok=True)
            self.record('account.setup' if setup else 'account.create', actor or user, ip, uid)
            if session:
                self.record('login', user, ip)
            return public_user(user), session

    def login(self, value, ip):
        username, password = value.get('username', ''), value.get('password', '')
        if not isinstance(username, str):
            raise ValueError('用户名格式错误')
        with self.store.lock:
            state = copy.deepcopy(self.store.state)
            user = next((u for u in state['users'].values() if u['username'].casefold() == username.casefold()), None)
            valid = check_password(password, user['password'] if user else self.dummy_hash)
            if not valid or not user or not user['enabled']:
                self.record('login', None, ip, username[:32], 'denied')
                raise AccessError('账号或密码错误，或账号已停用', 401)
            session = self._session(state, user)
            self.store.save(state)
            self.record('login', user, ip)
            return public_user(user), session

    def logout(self, token, user, ip):
        with self.store.lock:
            state = copy.deepcopy(self.store.state)
            state['sessions'].pop(hashlib.sha256(token.encode()).hexdigest(), None)
            self.store.save(state)
            self.record('logout', user, ip)

    def users(self, actor):
        self.require_admin(actor)
        with self.store.lock:
            return [public_user(u) for u in self.store.state['users'].values()]

    def update_user(self, actor, uid, value, ip):
        self.require_admin(actor)
        if not value or set(value) - {'enabled', 'password', 'role'}:
            raise ValueError('账号操作无效')
        if 'role' in value and value['role'] != 'user':
            raise ValueError('网页只能分配普通用户角色')
        if 'enabled' in value and type(value['enabled']) is not bool:
            raise ValueError('账号状态无效')
        if 'password' in value:
            validate_password(value['password'])
        with self.store.lock:
            state = copy.deepcopy(self.store.state)
            user = state['users'].get(uid)
            if not user:
                raise KeyError(uid)
            if user['role'] == 'admin':
                raise AccessError('超级管理员不能被禁用、改角色或在这里重置密码；请使用本人修改密码')
            if 'enabled' in value:
                user['enabled'] = value['enabled']
            if 'password' in value:
                user['password'] = password_hash(value['password'])
            state['sessions'] = {k: s for k, s in state['sessions'].items() if s['user'] != uid}
            self.store.save(state)
            for action in value:
                event = ('enable' if user['enabled'] else 'disable') if action == 'enabled' else action
                self.record('account.' + event, actor, ip, user['username'] + ' · ' + uid)
            return public_user(user)

    def change_password(self, user, value, ip):
        validate_password(value.get('password'))
        with self.store.lock:
            state = copy.deepcopy(self.store.state)
            current = state['users'][user['id']]
            if not check_password(value.get('currentPassword'), current['password']):
                raise AccessError('当前密码错误')
            current['password'] = password_hash(value['password'])
            state['sessions'] = {k: s for k, s in state['sessions'].items() if s['user'] != user['id']}
            self.store.save(state)
            self.record('account.password', user, ip, user['id'])

    def recover_owner(self, password):
        """Local CLI only; no HTTP route exposes administrator recovery."""
        validate_password(password)
        with self.store.lock:
            state = copy.deepcopy(self.store.state)
            user = next((u for u in state['users'].values() if u['role'] == 'admin'), None)
            if not user:
                raise ValueError('尚未创建超级管理员，请先在登录页初始化')
            user['password'] = password_hash(password)
            state['sessions'] = {k: s for k, s in state['sessions'].items() if s['user'] != user['id']}
            self.store.save(state)
            self.record('account.recover', user, 'local-cli', user['id'])
            return user['username']

    def visibility(self, identity, kind=None):
        with self.store.lock:
            return copy.deepcopy(self.store.state['permissions'].get(identity,
                {'scope': default_visibility(self.store.state['settings'], kind), 'users': []}))

    def can_view(self, user, identity, kind=None):
        if not user:
            return False
        if user['role'] == 'admin':
            return True
        permission = self.visibility(identity, kind)
        return permission['scope'] == 'all' or (permission['scope'] == 'selected' and user['id'] in permission['users'])

    def set_visibility(self, actor, identity, value, ip):
        self.require_admin(actor)
        with self.store.lock:
            state = copy.deepcopy(self.store.state)
            permission = validate_visibility(value, state['users'])
            state['permissions'][identity] = permission
            self.store.save(state)
            self.record('media.visibility', actor, ip, identity + ':' + permission['scope'] + ':' + ','.join(permission['users']))
            return permission

    def settings(self, actor, value=None, ip=''):
        self.require_admin(actor)
        with self.store.lock:
            if value is not None:
                state = copy.deepcopy(self.store.state)
                state['settings'] = {**state['settings'], **validate_security_settings(value)}
                self.store.save(state)
                self.record('settings.update', actor, ip)
            return copy.deepcopy(self.store.state['settings'])

    def catalog(self, body, etag, user):
        import json
        with self.store.lock:
            key = (etag, self.store.revision, user['id'])
            if key in self.catalog_cache:
                return self.catalog_cache[key]
            # Fix the default at first discovery; changing the setting affects new media only.
            raw = json.loads(body)
            missing = [item for item in raw['items'] if item['id'] not in self.store.state['permissions']]
            if missing:
                state = copy.deepcopy(self.store.state)
                for item in missing:
                    state['permissions'][item['id']] = {'scope': default_visibility(state['settings'], item.get('kind')), 'users': []}
                self.store.save(state)
            key = (etag, self.store.revision, user['id'])
            if key in self.catalog_cache:
                return self.catalog_cache[key]
            items = []
            for item in raw['items']:
                if self.can_view(user, item['id']):
                    item.pop('path', None)
                    if item.get('thumbnail'):
                        item['thumbnail'] += '?access=1'
                    if user['role'] == 'admin':
                        item['visibility'] = self.visibility(item['id'])
                    items.append(item)
            raw = {**raw, 'items': items, 'warnings': [], 'user': public_user(user)}
            raw.pop('root', None)
            filtered = json.dumps(raw, ensure_ascii=False).encode('utf-8')
            tag = '"' + hashlib.sha256(user['id'].encode() + filtered).hexdigest() + '"'
            if len(self.catalog_cache) >= 16 or self.catalog_bytes + len(filtered) > 32 * 1024 * 1024:
                self.catalog_cache.clear()
                self.catalog_bytes = 0
            if len(filtered) <= 32 * 1024 * 1024:
                self.catalog_cache[key] = (filtered, tag)
                self.catalog_bytes += len(filtered)
            return filtered, tag

    def viewed(self, user, identity, ip, title=''):
        now = time.monotonic()
        key = (user['id'], identity, ip)
        with self.rate_lock:
            # A player issues many byte ranges; record one visit per minute.
            if now - self.access_times.get(key, -1000) < 60:
                return
            self.access_times = {k: t for k, t in self.access_times.items() if now - t < 60}
            self.access_times[key] = now
        self.record('media.view', user, ip, title + ' · ' + identity)
