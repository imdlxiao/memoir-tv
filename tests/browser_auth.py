"""Isolated end-to-end owner, member and audience checks. Author: donglixiao."""
import base64
import copy
import shutil
import sys
import tempfile
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from memoir.http import Application, handler_for
from memoir.scanner import scan
from memoir.storage import Repository
from playwright.sync_api import sync_playwright, expect
from browser_support import launch_browser
from auth_support import PASSWORD


def main():
    with tempfile.TemporaryDirectory(prefix='memoir-auth-') as folder:
        root = Path(folder); media = root / 'media'; media.mkdir()
        shutil.copy2(ROOT / 'tests/fixtures/playback.mp4', media / 'public.mp4')
        shutil.copy2(ROOT / 'tests/fixtures/playback.mp4', media / 'private.mp4')
        (media / 'selected.png').write_bytes(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jBz0AAAAASUVORK5CYII='))
        repo = Repository(root / 'data'); repo.replace_index(scan(media, repo.directory, previews=False))
        ids = {item['filename']: item['id'] for item in repo.catalog()['items']}
        app = Application(media, repo, ROOT / 'web', 'missing-ffmpeg')
        server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(app))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f'http://127.0.0.1:{server.server_port}'
        try:
            with sync_playwright() as p:
                browser = launch_browser(p)
                owner = browser.new_context(viewport={'width': 1440, 'height': 1000})
                page = owner.new_page(); errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(base)
                expect(page).to_have_url(base + '/login.html')
                expect(page.locator('#setup-field')).to_be_visible()
                for width in [360, 390, 768, 1440, 1920]:
                    page.set_viewport_size({'width': width, 'height': 1000})
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), width
                page.set_viewport_size({'width': 1440, 'height': 1000})
                page.locator('[name=code]').fill(app.auth.store.setup_code())
                page.locator('[name=username]').fill('family-owner')
                page.locator('[name=password]').fill(PASSWORD)
                page.locator('[type=submit]').click()
                expect(page.locator('.memory-card')).to_have_count(3)
                page.locator('#account-button').click()
                page.get_by_role('link', name='用户、可见权限与系统管理 →').click()
                expect(page.locator('#create-user')).to_be_visible()
                form = page.locator('#create-user')
                form.locator('[name=username]').fill('family-member')
                form.locator('[name=password]').fill(PASSWORD)
                form.locator('button').click()
                expect(page.locator('#user-list')).to_contain_text('family-member')
                page.locator('[data-panel=visibility]').click()
                row = page.locator(f'[data-media="{ids["public.mp4"]}"]')
                row.locator('[name=scope]').select_option('all')
                row.get_by_role('button', name='保存可见范围').click()
                expect(row.locator('[role=status]')).to_contain_text('已保存')
                selected = page.locator(f'[data-media="{ids["selected.png"]}"]')
                selected.locator('[name=scope]').select_option('selected')
                selected.get_by_label('family-member', exact=True).check()
                selected.get_by_role('button', name='保存可见范围').click()
                expect(selected.locator('[role=status]')).to_contain_text('已保存')
                for width in [360, 390, 768, 1440, 1920]:
                    page.set_viewport_size({'width': width, 'height': 1000})
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), width
                page.set_viewport_size({'width': 1440, 'height': 1000})
                output = ROOT / 'test-results'; output.mkdir(exist_ok=True)
                page.screenshot(path=str(output / 'auth-admin.png'), full_page=True)
                member = browser.new_context(viewport={'width': 390, 'height': 844})
                phone = member.new_page(); phone.on('pageerror', lambda error: errors.append(str(error)))
                phone.goto(base)
                expect(phone.locator('#setup-field')).not_to_be_visible()
                phone.screenshot(path=str(output / 'auth-login-mobile.png'), full_page=True)
                phone.locator('[name=username]').fill('family-member')
                phone.locator('[name=password]').fill(PASSWORD)
                phone.locator('[type=submit]').click()
                expect(phone.locator('.memory-card')).to_have_count(2)
                expect(phone.locator('[data-action=edit]').first).not_to_be_visible()
                assert member.request.get(base + '/media/' + ids['private.mp4']).status == 403
                assert member.request.get(base + '/api/admin/users').status == 403
                phone.goto(base + '/admin.html')
                expect(phone).to_have_url(base + '/?denied=1')
                phone.locator(f'[data-id="{ids["public.mp4"]}"] .media-frame').click()
                phone.wait_for_function('document.querySelector("video")?.readyState >= 2')
                phone.keyboard.press('Escape')
                cookies = member.cookies()
                assert any(cookie['httpOnly'] and cookie['expires'] > 0 for cookie in cookies if cookie['name'] == 'memoir_session')
                assert 'memoir_session' not in phone.evaluate('document.cookie')
                saved = member.storage_state(); member.close()
                member = browser.new_context(storage_state=saved, viewport={'width': 390, 'height': 844})
                phone = member.new_page(); phone.goto(base)
                expect(phone.locator('.memory-card')).to_have_count(2)
                # Change permissions while the member is already browsing.
                row.locator('[name=scope]').select_option('admin')
                row.get_by_role('button', name='保存可见范围').click()
                expect(phone.locator('.memory-card')).to_have_count(1, timeout=12000)
                assert member.request.get(base + '/media/' + ids['public.mp4'], headers={'Range': 'bytes=0-9'}).status == 403
                page.locator('[data-panel=users]').click()
                member_row = page.locator('[data-user]').filter(has=page.get_by_role('heading', name='family-member', exact=False))
                member_row.get_by_role('button', name='停用账号').click()
                expect(phone).to_have_url(base + '/login.html?expired=1', timeout=12000)
                assert member.request.get(base + '/data/catalog.json').status == 401
                # Registration is always an ordinary account and signs in automatically.
                phone.locator('#register-tab').click()
                phone.locator('[name=username]').fill('new-family')
                phone.locator('[name=password]').fill(PASSWORD)
                phone.locator('[name=phone]').fill('13800000000')
                phone.locator('[type=submit]').click()
                expect(phone).to_have_url(base + '/')
                expect(phone.locator('.memory-card')).to_have_count(0)
                assert member.request.get(base + '/api/auth/me').json()['user']['role'] == 'user'
                phone.locator('#account-button').click()
                phone.locator('#logout-button').click()
                expect(phone).to_have_url(base + '/login.html')
                assert member.request.get(base + '/api/catalog').status == 401
                page.locator('[data-panel=logs]').click()
                expect(page.locator('#log-list')).to_contain_text('查看原片')
                page.locator('[data-panel=settings]').click()
                page.locator('[name=registration]').uncheck()
                page.get_by_role('button', name='保存设置').click()
                expect(page.locator('#admin-message')).to_contain_text('设置已保存')
                phone.reload()
                expect(phone.locator('#register-tab')).not_to_be_visible()
                # Expired credentials force login even while a dialog is open.
                page.goto(base)
                page.locator('#account-button').click()
                with app.auth.store.lock:
                    state = copy.deepcopy(app.auth.store.state)
                    for session in state['sessions'].values(): session['expires'] = 0
                    app.auth.store.save(state)
                expect(page).to_have_url(base + '/login.html?expired=1', timeout=12000)
                assert not errors, errors
                browser.close()
            print('PASS: owner setup, register/login, durable HttpOnly session, audiences, direct URL denial, revocation, admin screens, responsive layouts')
        finally:
            server.shutdown(); server.server_close()


if __name__ == '__main__':
    main()
