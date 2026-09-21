"""Isolated acceptance tests for organizing and rediscovering memories. Author: donglixiao."""
import base64
import datetime as dt
import json
import shutil
import sys
import tempfile
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from memoir.exporter import export_static
from memoir.http import Application, handler_for
from memoir.scanner import scan
from memoir.storage import Repository
from playwright.sync_api import sync_playwright, expect
from browser_support import launch_browser
from auth_support import browser_owner


def main():
    with tempfile.TemporaryDirectory(prefix='memoir-features-') as directory:
        root = Path(directory)
        media = root / 'media'
        media.mkdir()
        pixel = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jBz0AAAAASUVORK5CYII=')
        for name in ['one.png', 'two.png']:
            (media / name).write_bytes(pixel)
        shutil.copy2(ROOT / 'tests' / 'fixtures' / 'playback.mp4', media / 'clip.mp4')
        repository = Repository(root / 'data')
        repository.replace_index(scan(media, repository.directory, previews=False))
        ids = {item['filename']: item['id'] for item in repository.catalog()['items']}
        today = dt.date.today()
        past = f'{today.year - 4:04}-{today.month:02}-{today.day:02}'
        repository.save(ids['one.png'], {'title': '往年的今天', 'date': past, 'precision': 'day', 'tags': ['原有标签']})
        repository.save(ids['two.png'], {'title': '只记得这个月', 'date': past[:7], 'precision': 'month', 'tags': ['原有标签']})
        repository.save(ids['clip.mp4'], {'title': '测试短片', 'tags': ['原有标签']})
        server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(Application(media, repository, ROOT / 'web', 'unavailable-ffmpeg')))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with sync_playwright() as p:
                browser = launch_browser(p)
                page = browser.new_page(viewport={'width':1440, 'height':1000})
                browser_owner(page, server, repository)
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(f'http://127.0.0.1:{server.server_port}')
                expect(page.locator('.memory-card')).to_have_count(3)

                page.locator('#anniversary-button').click()
                expect(page.locator('.anniversary-section').nth(0).locator('.anniversary-memory')).to_have_count(1)
                expect(page.locator('.anniversary-section').nth(1).locator('.anniversary-memory')).to_have_count(1)
                page.locator('.anniversary-memory').first.click()
                expect(page.locator('#viewer-dialog')).to_be_visible()
                page.keyboard.press('Escape')
                result = page.evaluate("""async () => {
                    const {anniversaryGroups}=await import('./js/discovery.js');
                    const items=[{date:'2020-02-29',precision:'day'},{date:'2020-02',precision:'month'},
                        {date:'2024-02-29',precision:'day'},{date:'',precision:'unknown'}];
                    const groups=anniversaryGroups(items,new Date(2024,1,29));
                    return [groups.today.length,groups.month.length];
                }""")
                assert result == [1, 1], result

                page.locator('#batch-toggle').click()
                page.locator('#select-page').click()
                expect(page.locator('#selection-count')).to_have_text('已选 3 条')
                page.locator('#batch-edit').click()
                form = page.locator('#batch-dialog')
                form.locator('[name=applyDate]').check()
                form.locator('[name=date]').fill('2023-04')
                form.locator('[name=applyLocation]').check()
                form.locator('[name=location]').fill('杭州 · 家里')
                form.locator('[name=applyTags]').check()
                form.locator('[name=tags]').fill('假日，春天')
                form.locator('[type=submit]').click()
                expect(form).not_to_be_visible()
                expect(page.locator('#batch-toolbar')).not_to_be_visible()
                records = repository.catalog()['items']
                assert all(item['date'] == '2023-04' and item['precision'] == 'month' for item in records)
                assert all(item['tags'] == ['原有标签', '假日', '春天'] for item in records)
                assert all(item['location'] == '杭州 · 家里' for item in records)
                assert set(item['title'] for item in records) == {'往年的今天', '只记得这个月', '测试短片'}
                page.reload()
                expect(page.locator('.card-date').first).to_contain_text('大约')
                page.locator('#filter-toggle').click()
                page.locator('#month-filter').select_option('04')
                expect(page.locator('.memory-card')).to_have_count(3)
                expect(page.locator('[data-clear=month]')).to_contain_text('4 月')
                page.locator('#reset-filters').click()

                page.locator('#grid-view').click()
                page.reload()
                expect(page.locator('#grid-view')).to_have_attribute('aria-pressed', 'true')
                expect(page.locator('#feed')).to_have_class('feed grid-view')

                page.locator(f'[data-id="{ids["clip.mp4"]}"] .media-frame').click()
                page.wait_for_function("document.querySelector('video')?.readyState >= 1")
                page.evaluate("document.querySelector('video').currentTime = 12")
                page.wait_for_function("document.querySelector('video')?.currentTime >= 12 && !document.querySelector('video').seeking")
                page.evaluate("document.querySelector('video').pause()")
                page.keyboard.press('Escape')
                expect(page.locator('#resume-button')).to_be_visible()
                expect(page.locator('.progress-badge')).to_contain_text('看到 0:12')
                page.reload()
                page.locator('#resume-button').click()
                expect(page.locator('.resume-notice')).to_be_visible()
                page.wait_for_function("document.querySelector('video')?.currentTime >= 12")
                page.locator('[data-speed]').select_option('1.5')
                assert page.locator('video').evaluate('(video)=>video.playbackRate') == 1.5
                page.locator('[data-loop]').click()
                assert page.locator('video').evaluate('(video)=>video.loop')
                page.locator('[data-loop]').click()
                page.locator('[data-restart]').click()
                page.wait_for_function("document.querySelector('video')?.currentTime < 3")
                page.locator('.viewer-details summary').click()
                expect(page.locator('.viewer-details')).to_contain_text('clip.mp4')
                with page.expect_download() as download:
                    page.locator('.viewer-details a').click()
                assert download.value.suggested_filename == 'clip.mp4'
                page.evaluate("document.querySelector('video').currentTime=29.7; document.querySelector('video').play()")
                page.wait_for_function("document.querySelector('video')?.ended")
                page.keyboard.press('Escape')
                expect(page.locator('#resume-button')).not_to_be_visible()

                page.locator('[data-tab=photo]').click()
                page.locator('.media-frame').first.click()
                page.wait_for_function("document.querySelector('#viewer-dialog img')?.naturalWidth > 0")
                page.locator('[data-zoom]').click()
                expect(page.locator('.viewer-media')).to_have_class('viewer-media zoomed')
                page.locator('[data-zoom]').click()
                page.locator('[data-interval]').select_option('5')
                page.locator('[data-continuous]').click()
                expect(page.locator('.viewer-toolbar h2')).to_have_text('往年的今天', timeout=8000)
                page.locator('[data-continuous]').click()
                expect(page.locator('[data-continuous]')).to_have_attribute('aria-pressed','false')
                page.keyboard.press('Escape')
                page.locator('#random-button').click()
                expect(page.locator('#viewer-dialog img')).to_be_visible()
                page.keyboard.press('Escape')

                for width in [360,390,768,1440,1920]:
                    page.set_viewport_size({'width':width,'height':900})
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), width
                assert not errors, errors

                export_static(ROOT / 'web', repository, media, '../media/', root / 'album', allow_public=True)
                static_server = ThreadingHTTPServer(('127.0.0.1',0),partial(SimpleHTTPRequestHandler,directory=str(root)))
                threading.Thread(target=static_server.serve_forever, daemon=True).start()
                try:
                    page.goto(f'http://127.0.0.1:{static_server.server_port}/album/')
                    expect(page.locator('.memory-card')).to_have_count(3)
                    page.locator('#batch-toggle').click()
                    page.locator('#select-page').click()
                    page.locator('#batch-edit').click()
                    page.locator('#batch-dialog [name=applyTags]').check()
                    page.locator('#batch-dialog [name=tags]').fill('仅在浏览器')
                    page.locator('#batch-dialog [type=submit]').click()
                    expect(page.locator('#batch-dialog')).not_to_be_visible()
                    page.reload()
                    expect(page.locator('.card-tag',has_text='仅在浏览器')).to_have_count(3)
                    assert all('仅在浏览器' not in item['tags'] for item in repository.catalog()['items'])
                    assert not errors, errors
                finally:
                    static_server.shutdown()
                    static_server.server_close()
                browser.close()
                print('PASS: atomic batch editing, appended tags, preserved stories, anniversary precision, resume across reload, speed, loop, restart, download, completed progress cleanup, photo zoom/slideshow, random filtered replay, remembered layout, five viewport widths, static batch persistence.')
        finally:
            server.shutdown()
            server.server_close()


if __name__ == '__main__':
    main()
