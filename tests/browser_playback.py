"""Mobile quality switching and buffer diagnosis using synthetic media. Author: donglixiao."""
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from playwright.sync_api import sync_playwright, expect
from browser_support import launch_browser
from tv_fixture import tv_library
from auth_support import PASSWORD
from memoir.storage import PlaybackCache


def main():
    with tv_library() as (server, repo), sync_playwright() as p:
        browser = launch_browser(p)
        base = f'http://127.0.0.1:{server.server_port}'
        catalog = repo.catalog()
        cache = PlaybackCache(repo.directory)
        for item in catalog['items']:
            source = repo.directory.parent / 'media' / item['path']
            target = cache.target(item['id'], source)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        for legacy in [False, True]:
            context = browser.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True)
            page = context.new_page()
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.route('https://**/*', lambda route: route.abort())
            page.goto(base + '/login.html')
            page.locator('[name=username]').fill('test-owner')
            page.locator('[name=password]').fill(PASSWORD)
            page.locator('[type=submit]').click()
            expect(page.locator('.memory-card')).to_have_count(2)
            if legacy:
                page.goto(base + '/?compat=1')
            page.locator('.media-frame').first.click()
            page.wait_for_function('document.querySelector("video").src.includes("/playback/") && document.querySelector("video").readyState >= 2')
            expect(page.locator('[data-playback-status]')).to_contain_text('流畅版')
            page.evaluate('''() => { const v=document.querySelector('video');v.pause();v.currentTime=12;v.playbackRate=1.25; }''')
            page.wait_for_function('!document.querySelector("video").seeking')
            page.locator('[data-quality]').select_option('original')
            page.wait_for_function('document.querySelector("video").src.includes("/media/") && document.querySelector("video").readyState >= 2 && document.querySelector("video").currentTime >= 11')
            assert page.evaluate('document.querySelector("video").paused && document.querySelector("video").playbackRate === 1.25')
            page.locator('[data-quality]').select_option('smooth')
            page.wait_for_function('document.querySelector("video").src.includes("/playback/") && document.querySelector("video").currentTime >= 11')
            page.get_by_text('播放诊断', exact=True).click()
            expect(page.locator('[data-playback-metrics]')).to_contain_text('已缓冲')
            expect(page.locator('[data-playback-metrics]')).to_contain_text('实际来源：流畅版 H.264')
            expect(page.locator('[data-playback-metrics]')).not_to_contain_text('原片平均')
            page.locator('[data-playback-test]').click()
            expect(page.locator('[data-playback-test-result]')).to_contain_text('Mbps')
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.screenshot(path=str(ROOT / 'test-results' / ('playback-mobile-legacy.png' if legacy else 'playback-mobile.png')))
            page.locator('#viewer-dialog [data-close]').click()
            page.locator('.media-frame').first.click()
            page.wait_for_function('document.querySelector("video").currentTime >= 11')
            expect(page.locator('.resume-notice')).to_be_visible()
            # Explicit smooth must stop the original while a rendition is queued.
            identity = page.evaluate('document.querySelector("video").src.split("/").pop()')
            state = {'state': 'queued', 'message': '等待生成流畅版'}
            page.route('**/api/playback/' + identity, lambda route: route.fulfill(json=state))
            page.locator('#viewer-dialog [data-close]').click()
            page.locator('.media-frame').first.click()
            page.wait_for_function('document.querySelector("video").currentTime >= 11')
            page.locator('[data-quality]').select_option('smooth')
            expect(page.locator('[data-playback-status]')).to_contain_text('已停止原画')
            assert page.evaluate('!document.querySelector("video").getAttribute("src")')
            state.update(state='ready', url='/playback/' + identity, size=10000)
            page.wait_for_function('document.querySelector("video").currentSrc.includes("/playback/") && document.querySelector("video").currentTime >= 11', timeout=10000)
            page.unroute('**/api/playback/' + identity)
            # A failed encoder is visible and never destroys the original player.
            page.locator('#viewer-dialog [data-close]').click()
            for target in cache.directory.glob('*.mp4'):
                target.unlink()
            page.locator('.media-frame').first.click()
            if not legacy:
                expect(page.locator('[data-prepare-playback]')).to_be_visible()
                page.locator('[data-prepare-playback]').click()
            expect(page.locator('[data-playback-status]')).to_contain_text('不可用', timeout=10000)
            assert page.evaluate('document.querySelector("video").src.includes("/media/")')
            assert not errors, errors
            # Restore synthetic derivatives for the next browser mode.
            for item in catalog['items']:
                source = repo.directory.parent / 'media' / item['path']
                shutil.copy2(source, cache.target(item['id'], source))
            context.close()
        browser.close()
    print('PASS: mobile quality, resume, diagnostics, encoder failure and legacy bundles')


if __name__ == '__main__':
    main()


