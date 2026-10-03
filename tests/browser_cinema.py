"""TV cinema sizing, remote overlays and fullscreen fallback. Author: donglixiao."""
import base64
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from playwright.sync_api import sync_playwright, expect
from auth_support import PASSWORD
from browser_support import launch_browser
from memoir.scanner import scan
from tv_fixture import tv_library


def open_library(browser, base, legacy, television=True):
    options = {'viewport': {'width': 1280, 'height': 720}}
    if television:
        options['user_agent'] = 'Mozilla/5.0 Android TV; TVBrowser'
    context = browser.new_context(**options)
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.route('https://**/*', lambda route: route.abort())
    response = page.request.post(base + '/api/auth/login', data={
        'username': 'test-owner', 'password': PASSWORD})
    assert response.status == 200, response.text()
    page.goto(base + ('/?compat=1' if legacy else '/'))
    page.wait_for_function('window.memoirReady === true')
    expect(page.locator('.memory-card')).to_have_count(3)
    if legacy:
        expect(page.locator('script[src="./compat/app.js"]')).to_have_count(1)
    return context, page, errors


def open_memory(page, identity):
    page.locator(f'[data-id="{identity}"] .media-frame').click()
    expect(page.locator('#viewer-dialog')).to_be_visible()


def assert_full_viewport(page, media='video'):
    # Header/buttons must overlay the picture, rather than reserve vertical space.
    page.wait_for_function("""(media) => {
        const selectors = ['#viewer-dialog', '.viewer-stage', '.viewer-media',
                           '.viewer-media ' + media];
        return selectors.every(selector => {
            const element = document.querySelector(selector);
            if (!element) return false;
            const rect = element.getBoundingClientRect();
            return Math.abs(rect.x) <= 1 && Math.abs(rect.y) <= 1 &&
                Math.abs(rect.width - innerWidth) <= 2 &&
                Math.abs(rect.height - innerHeight) <= 2;
        });
    }""", arg=media)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    assert page.evaluate("""() => {
        const dialog = document.querySelector('#viewer-dialog');
        return dialog.scrollHeight <= dialog.clientHeight + 1 &&
               dialog.scrollWidth <= dialog.clientWidth + 1;
    }""")


def capture(page, name, enabled):
    if enabled:
        (ROOT / '.local').mkdir(exist_ok=True)
        page.screenshot(path=str(ROOT / '.local' / ('cinema-' + name + '.png')))


def switch_clip(page, direction, original_source, native_fullscreen):
    page.locator(f'[data-{direction}]').click()
    page.wait_for_function('''(previous) => {
        const video = document.querySelector('video');
        return video && video.readyState >= 2 && video.currentSrc !== previous;
    }''', arg=original_source)
    page.wait_for_function('document.querySelector(".viewer-stage").classList.contains("cinema")', timeout=5000)
    if native_fullscreen:
        assert page.evaluate('document.fullscreenElement === document.querySelector(".viewer-stage")'), 'Changing clips must preserve native fullscreen'
    else:
        assert not page.evaluate('!!document.fullscreenElement')
    assert_full_viewport(page)
    expect(page.locator('video')).to_have_css('object-fit', 'cover')
    page.evaluate('document.querySelector("video").pause()')
    page.locator('[data-remote-play]').focus()
    page.keyboard.press('Enter')
    page.wait_for_function('!document.querySelector("video").paused')
    page.keyboard.press('Enter')
    page.wait_for_function('document.querySelector("video").paused')
    return page.locator('video').evaluate('(video) => video.currentSrc')


def tv_cinema(page, video_id, photo_id, screenshots=False):
    open_memory(page, video_id)
    page.wait_for_function('document.querySelector("video").readyState >= 2')
    stage = page.locator('.viewer-stage')
    expect(stage).to_have_class('viewer-stage cinema')
    for width, height in [(960, 540), (1280, 720), (1920, 1080)]:
        page.set_viewport_size({'width': width, 'height': height})
        assert_full_viewport(page)
    page.set_viewport_size({'width': 1280, 'height': 720})
    assert_full_viewport(page)
    expect(page.locator('video')).to_have_css('object-fit', 'contain')
    expect(page.locator('.cinema-panel')).to_be_hidden()
    # Keep the synthetic clip playing long enough for both idle and wake checks.
    page.evaluate('document.querySelector("video").loop = true')
    page.mouse.move(0, 0)
    capture(page, 'playing', screenshots)
    page.wait_for_function('document.querySelector(".viewer-stage").classList.contains("cinema-idle")')
    capture(page, 'idle', screenshots)
    page.keyboard.press('Enter')
    page.wait_for_function('!document.querySelector(".viewer-stage").classList.contains("cinema-idle")')
    expect(page.locator('[data-remote-play]')).to_be_focused()
    assert page.evaluate('!document.querySelector("video").paused'), 'Wake must not activate a stale focused button'
    page.keyboard.press('Enter')
    page.wait_for_function('document.querySelector("video").paused')
    # Pausing must leave an operable controller, even beyond the idle timeout.
    page.wait_for_timeout(4500)
    assert not stage.evaluate('(element) => element.classList.contains("cinema-idle")')
    page.locator('[data-player-settings]').focus()
    page.keyboard.press('Enter')
    panel = page.locator('.cinema-panel')
    expect(panel).to_be_visible()
    assert_full_viewport(page)
    capture(page, 'settings', screenshots)
    for key in ['ArrowDown', 'ArrowRight', 'ArrowDown', 'ArrowUp', 'ArrowLeft']:
        page.keyboard.press(key)
        assert page.evaluate('!!document.activeElement.closest(".cinema-panel")')
    page.locator('[data-player-fit]').select_option('cover')
    expect(page.locator('video')).to_have_css('object-fit', 'cover')
    page.locator('[data-player-fit]').select_option('contain')
    expect(page.locator('video')).to_have_css('object-fit', 'contain')
    page.locator('[data-player-fit]').select_option('cover')
    page.keyboard.press('Escape')
    expect(panel).to_be_hidden()
    expect(page.locator('#viewer-dialog')).to_be_visible()
    page.locator('[data-fullscreen]').click()
    page.wait_for_function('document.fullscreenElement === document.querySelector(".viewer-stage")')
    assert_full_viewport(page)
    original_source = page.locator('video').evaluate('(video) => video.currentSrc')
    next_source = switch_clip(page, 'next', original_source, native_fullscreen=True)
    previous_source = switch_clip(page, 'previous', next_source, native_fullscreen=True)
    assert previous_source == original_source
    page.locator('[data-player-settings]').click()
    page.keyboard.press('Escape')
    expect(panel).to_be_hidden()
    assert page.evaluate('!!document.fullscreenElement'), 'Back must close settings before leaving fullscreen'
    page.keyboard.press('Escape')
    page.wait_for_function('!document.fullscreenElement')
    expect(page.locator('#viewer-dialog')).to_be_visible()
    assert_full_viewport(page)
    page.keyboard.press('Escape')
    expect(page.locator('#viewer-dialog')).to_be_hidden()
    open_memory(page, photo_id)
    page.wait_for_function('document.querySelector(".viewer-media img").naturalWidth > 0')
    assert_full_viewport(page, 'img')
    expect(page.locator('.viewer-media img')).to_have_css('object-fit', 'contain')
    page.keyboard.press('Escape')
    expect(page.locator('#viewer-dialog')).to_be_hidden()


def rejected_fullscreen(page, video_id):
    open_memory(page, video_id)
    page.evaluate('document.querySelector("video").pause()')
    assert not page.locator('.viewer-stage').evaluate('(element) => element.classList.contains("cinema")')
    page.evaluate("""() => {
        document.querySelector('.viewer-stage').requestFullscreen = () =>
            Promise.reject(new Error('Synthetic fullscreen refusal'));
    }""")
    page.locator('[data-fullscreen]').click()
    assert_full_viewport(page)
    assert not page.evaluate('!!document.fullscreenElement')
    page.set_viewport_size({'width': 568, 'height': 320})
    assert_full_viewport(page)
    page.locator('[data-player-settings]').click()
    page.wait_for_function('''() => {
        const panel = document.querySelector('.cinema-panel');
        const rect = panel.getBoundingClientRect();
        return rect.height >= 296 && rect.top >= 0 && rect.bottom <= innerHeight &&
            rect.left >= 0 && rect.right <= innerWidth &&
            panel.scrollWidth <= panel.clientWidth + 1;
    }''')
    page.locator('[data-player-fit]').select_option('cover')
    page.keyboard.press('Escape')
    expect(page.locator('.cinema-panel')).to_be_hidden()
    page.set_viewport_size({'width': 1280, 'height': 720})
    original_source = page.locator('video').evaluate('(video) => video.currentSrc')
    next_source = switch_clip(page, 'next', original_source, native_fullscreen=False)
    previous_source = switch_clip(page, 'previous', next_source, native_fullscreen=False)
    assert previous_source == original_source
    page.keyboard.press('Escape')
    expect(page.locator('#viewer-dialog')).to_be_visible()
    assert not page.locator('.viewer-stage').evaluate('(element) => element.classList.contains("cinema")')
    page.keyboard.press('Escape')
    expect(page.locator('#viewer-dialog')).to_be_hidden()


def video_only_fullscreen(page, video_id):
    # Capability simulation in Chromium, not a claim of real Safari/iPhone testing.
    open_memory(page, video_id)
    page.wait_for_function('document.querySelector("video").readyState >= 2')
    page.evaluate('''() => {
        const stage = document.querySelector('.viewer-stage');
        const video = document.querySelector('video');
        video.pause();
        stage.requestFullscreen = undefined;
        stage.webkitRequestFullscreen = undefined;
        video.webkitEnterFullscreen = () => video.dataset.nativeFullscreenCalled = 'yes';
    }''')
    page.locator('[data-fullscreen]').click()
    expect(page.locator('video')).to_have_attribute('data-native-fullscreen-called', 'yes')
    assert_full_viewport(page)
    page.evaluate('document.querySelector("video").dispatchEvent(new Event("webkitendfullscreen"))')
    page.wait_for_function('!document.querySelector(".viewer-stage").classList.contains("cinema")')
    expect(page.locator('#viewer-dialog')).to_be_visible()
    assert page.locator('video').evaluate('(video) => video.controls')
    page.keyboard.press('Escape')
    expect(page.locator('#viewer-dialog')).to_be_hidden()


def main():
    with tv_library() as (server, repo), sync_playwright() as p:
        media = repo.directory.parent / 'media'
        (media / '20260303-photo.png').write_bytes(base64.b64decode(
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jBz0AAAAASUVORK5CYII='))
        repo.replace_index(scan(media, repo.directory, previews=False))
        items = repo.catalog()['items']
        video_id = next(item['id'] for item in items if item['filename'] == '20260202-test.mp4')
        photo_id = next(item['id'] for item in items if item['kind'] == 'photo')
        base = f'http://127.0.0.1:{server.server_port}'
        browser = launch_browser(p)
        try:
            for legacy in [False, True]:
                context, page, errors = open_library(browser, base, legacy)
                tv_cinema(page, video_id, photo_id, screenshots=not legacy)
                assert errors == [], errors
                context.close()
                context, page, errors = open_library(browser, base, legacy, television=False)
                rejected_fullscreen(page, video_id)
                video_only_fullscreen(page, video_id)
                assert errors == [], errors
                context.close()
        finally:
            browser.close()
    print('PASS: modern/legacy TV cinema, three TV viewport sizes, narrow landscape settings, idle remote wake, settings focus, fit, fullscreen Back, photos, fullscreen clip switching, rejected-fullscreen fallback and simulated video-only fullscreen.')


if __name__ == '__main__':
    main()
