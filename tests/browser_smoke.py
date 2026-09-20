"""Isolated browser acceptance checks, never edit the family catalog. Author: donglixiao.

Run: python tests/browser_smoke.py (requires playwright and installed Chrome).
"""
import base64
import json
import sys
import tempfile
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from memoir.http import Application, handler_for
from memoir.exporter import export_static
from memoir.scanner import scan
from memoir.storage import Repository
from playwright.sync_api import sync_playwright, expect


def main():
    with tempfile.TemporaryDirectory(prefix='memoir-test-') as directory:
        root = Path(directory)
        media = root / 'media'
        media.mkdir()
        # A one-pixel fixture, independent of real family media.
        (media / '20240715.png').write_bytes(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jBz0AAAAASUVORK5CYII='))
        (media / 'unknown.mp4').write_bytes(b'not-a-video')
        repository = Repository(root / 'data')
        repository.replace_index(scan(media, repository.directory, previews=False))
        server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(Application(media, repository, ROOT / 'web', 'ffmpeg')))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(channel='chrome', headless=True)
                page = browser.new_page(viewport={'width':1440, 'height':1050})
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(f'http://127.0.0.1:{server.server_port}')
                expect(page.locator('.memory-card')).to_have_count(2)
                page.locator('.memory-card').first.locator('[data-action=edit]').first.click()
                page.locator('[name=title]').fill('测试回忆')
                page.locator('[name=precision]').select_option('month')
                page.locator('[name=date]').fill('2024-07')
                page.locator('[name=location]').fill('杭州 · 家里')
                page.locator('[name=tags]').fill('家人，夏天')
                page.locator('#editor-dialog [type=submit]').click()
                expect(page.locator('#editor-dialog')).not_to_be_visible()
                page.reload()
                expect(page.locator('.card-title').first).to_have_text('测试回忆')
                expect(page.locator('.card-date').first).to_contain_text('大约')
                page.locator('.memory-card').first.locator('[data-action=favorite]').click()
                expect(page.locator('#favorite-count')).to_have_text('1')
                page.locator('[data-view=favorites]').click()
                expect(page.locator('.memory-card')).to_have_count(1)
                page.locator('[data-view=all]').click()
                page.locator('#filter-toggle').click()
                page.locator('#location-filter').select_option('杭州 · 家里')
                expect(page.locator('.memory-card')).to_have_count(1)
                page.locator('#reset-filters').click()
                page.locator('#search').fill('不存在的内容')
                expect(page.locator('.empty-state')).to_be_visible()
                page.locator('[data-action=reset]').click()
                page.locator('.memory-card').first.locator('.media-frame').click()
                expect(page.locator('#viewer-dialog img')).to_be_visible()
                page.wait_for_function("document.querySelector('#viewer-dialog img').naturalWidth > 0")
                page.keyboard.press('Escape')
                expect(page.locator('#viewer-dialog')).not_to_be_visible()
                page.locator('#library-button').click()
                with page.expect_download() as download:
                    page.locator('#export-backup').click()
                backup_path = root / 'backup.json'
                download.value.save_as(backup_path)
                assert json.loads(backup_path.read_text(encoding='utf-8'))['memories']
                page.locator('#backup-file').set_input_files(backup_path)
                page.locator('#confirm-import').click()
                expect(page.locator('#import-message')).to_contain_text('已合并备份')
                page.locator('#library-dialog [data-close]').click()
                page.locator('#tv-button').click()
                expect(page.locator('body')).to_have_class('tv-mode')
                page.keyboard.press('ArrowRight')
                page.keyboard.press('Escape')
                expect(page.locator('body')).not_to_have_class('tv-mode')
                for width in [360,390,768,1440,1920]:
                    page.set_viewport_size({'width':width,'height':900})
                    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), f'Overflow at {width}'
                page.set_viewport_size({'width':390,'height':844})
                page.locator('[data-mobile-view=photo]').click()
                expect(page.locator('.memory-card')).to_have_count(1)
                page.locator('#theme-button').click()
                expect(page.locator('html')).to_have_attribute('data-theme','dark')
                assert not errors, errors
                # A nested, entirely static site must preserve edits without an API.
                export_static(ROOT / 'web', repository, media, '../media/', root / 'album')
                static_server = ThreadingHTTPServer(('127.0.0.1', 0), partial(SimpleHTTPRequestHandler, directory=str(root)))
                threading.Thread(target=static_server.serve_forever, daemon=True).start()
                try:
                    page.goto(f'http://127.0.0.1:{static_server.server_port}/album/')
                    expect(page.locator('.memory-card')).to_have_count(2)
                    page.locator('.memory-card').first.locator('[data-action=edit]').first.click()
                    page.locator('[name=title]').fill('仅保存在静态浏览器')
                    page.locator('#editor-dialog [type=submit]').click()
                    expect(page.locator('#editor-dialog')).not_to_be_visible()
                    page.reload()
                    expect(page.locator('.card-title').first).to_have_text('仅保存在静态浏览器')
                    assert repository.catalog()['items'][0]['title'] == '测试回忆'
                    page.locator('.memory-card').first.locator('.media-frame').click()
                    page.wait_for_function("document.querySelector('#viewer-dialog img').naturalWidth > 0")
                    page.keyboard.press('Escape')
                    page.locator('.memory-card').nth(1).locator('.media-frame').click()
                    expect(page.locator('.viewer-error')).to_be_visible()
                    page.keyboard.press('Escape')
                    assert not errors, errors
                finally:
                    static_server.shutdown()
                    static_server.server_close()
                browser.close()
                print('PASS: editing, month precision, persistence, favorites, search, filters, photo viewer, backup/import, TV, dark theme, 5 viewport widths, nested static export, static edits, unsupported video fallback; no JS errors.')
        finally:
            server.shutdown()
            server.server_close()


if __name__ == '__main__':
    main()
