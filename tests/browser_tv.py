"""Remote navigation and shipped legacy bundles against synthetic media. Author: donglixiao."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from playwright.sync_api import sync_playwright, expect
from browser_support import launch_browser
from tv_fixture import tv_library
from auth_support import PASSWORD


def main():
    with tv_library() as (server, repo), sync_playwright() as p:
        browser = launch_browser(p)
        base = f'http://127.0.0.1:{server.server_port}'
        for legacy in [False, True]:
            context = browser.new_context(viewport={'width': 1280, 'height': 720},
                                          user_agent='Mozilla/5.0 Android TV; TVBrowser')
            page = context.new_page()
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            # No map tiles or external services are needed for these fixtures.
            page.route('https://**/*', lambda route: route.abort())
            page.goto(base + '/login.html' + ('?compat=1' if legacy else ''))
            page.wait_for_function('window.memoirReady === true')
            if legacy:
                expect(page.locator('script[src="./compat/login.js"]')).to_have_count(1)
            page.keyboard.press('ArrowDown')
            expect(page.locator('[name=username]')).to_be_focused()
            page.keyboard.insert_text('test-owner')
            page.keyboard.press('ArrowDown')
            expect(page.locator('[name=password]')).to_be_focused()
            page.keyboard.insert_text(PASSWORD)
            page.keyboard.press('ArrowLeft')
            expect(page.locator('[name=password]')).to_be_focused()
            page.keyboard.press('ArrowDown')
            expect(page.locator('[type=submit]')).to_be_focused()
            page.keyboard.press('Enter')
            expect(page.locator('.memory-card')).to_have_count(2)
            if legacy:
                page.goto(base + '/?compat=1')
                expect(page.locator('.memory-card')).to_have_count(2)
                expect(page.locator('script[src="./compat/app.js"]')).to_have_count(1)
            expect(page.locator('body')).to_have_class('tv-mode')
            cards = page.locator('[data-action=open].media-frame')
            cards.first.focus()
            page.keyboard.press('ArrowRight')
            expect(cards.nth(1)).to_be_focused()
            selected_id = cards.nth(1).locator('xpath=ancestor::article').get_attribute('data-id')
            # A background library refresh must not steal the current remote focus.
            refreshed_title = 'A refreshed fixture ' + str(legacy)
            repo.save(selected_id, {'title': refreshed_title})
            page.wait_for_function("([id,title]) => document.querySelector('[data-id=\"' + id + '\"] h3').textContent === title", arg=[selected_id, refreshed_title])
            expect(page.locator(f'[data-id="{selected_id}"] .media-frame')).to_be_focused()
            page.keyboard.press('Enter')
            expect(page.locator('#viewer-dialog')).to_be_visible()
            page.wait_for_function('document.querySelector("video").readyState >= 2')
            page.locator('[data-remote-play]').focus()
            page.evaluate('document.querySelector("video").pause()')
            page.keyboard.press('Enter')
            page.wait_for_function('!document.querySelector("video").paused')
            page.keyboard.press('Enter')
            page.wait_for_function('document.querySelector("video").paused')
            page.keyboard.press('ArrowRight')
            expect(page.locator('[data-remote-back]')).to_be_focused()
            page.keyboard.press('ArrowRight')
            expect(page.locator('[data-remote-forward]')).to_be_focused()
            page.keyboard.press('Enter')
            page.wait_for_function('document.querySelector("video").currentTime >= 10')
            page.locator('[data-speed]').focus()
            page.keyboard.press('ArrowRight')
            assert page.evaluate('document.querySelector("video").playbackRate') == 1.25
            # Focus must stay inside a modal until Back/Escape closes it.
            for key in ['ArrowDown', 'ArrowDown', 'ArrowRight', 'ArrowUp']:
                page.keyboard.press(key)
                assert page.evaluate('!!document.activeElement.closest("#viewer-dialog")')
            page.keyboard.press('Escape')
            expect(page.locator('#viewer-dialog')).not_to_be_visible()
            page.goto(base + '/admin.html' + ('?compat=1' if legacy else ''))
            expect(page.locator('#create-user')).to_be_visible()
            page.locator('#create-user [name=username]').focus()
            page.keyboard.press('ArrowDown')
            assert page.evaluate('document.activeElement !== document.body')
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            assert errors == [], errors
            context.close()
        browser.close()
    print('PASS: TV login, legacy bundles, spatial navigation, refresh focus, playback, seeking, speed, modal Back and admin navigation.')


if __name__ == '__main__':
    main()
