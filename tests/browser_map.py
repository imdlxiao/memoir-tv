"""Map acceptance tests with synthetic positions and intercepted tiles. Author: donglixiao."""
import base64
import json
import sys
import tempfile
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from memoir.exporter import export_static
from memoir.http import Application, handler_for
from memoir.scanner import scan
from memoir.storage import Repository
from playwright.sync_api import sync_playwright, expect
from browser_support import launch_browser


def main():
    with tempfile.TemporaryDirectory(prefix='memoir-map-') as directory:
        root = Path(directory)
        media = root / 'media'; media.mkdir()
        pixel = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jBz0AAAAASUVORK5CYII=')
        for name in ['one.png', 'two.png', 'three.png']:
            (media / name).write_bytes(pixel)
        repository = Repository(root / 'data')
        original = {'coordinates': None, 'capture': {'make': 'Test', 'model': 'Test Camera', 'iso': 80, 'aperture': 1.8, 'width': 4000, 'height': 3000, 'takenAt': '2024-02-29T11:03:02+08:00'}, 'metadataStatus': 'read'}
        # Provide deterministic embedded metadata independently of installed ExifTool.
        with patch('memoir.scanner.read_metadata', return_value=original):
            repository.replace_index(scan(media, repository.directory, previews=False))
            for item in repository.catalog()['items']:
                thumb = repository.directory / 'thumbnails' / f"{item['id']}-{item['size']}-{item['modified']}.jpg"
                thumb.write_bytes(pixel)
            repository.replace_index(scan(media, repository.directory, previews=False))
            ids = {item['filename']: item['id'] for item in repository.catalog()['items']}
            for name in ['one.png', 'two.png']:
                repository.save(ids[name], {'title': name, 'location': '测试海湾', 'coordinates': {'latitude': 22.3, 'longitude': 114.17}})
            server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(Application(media, repository, ROOT / 'web', 'missing-ffmpeg')))
            threading.Thread(target=server.serve_forever, daemon=True).start()
            try:
                with sync_playwright() as p:
                    browser = launch_browser(p)
                    page = browser.new_page(viewport={'width': 1440, 'height': 1000})
                    errors, external = [], []
                    fail_tiles = False
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    def intercept(route):
                        if route.request.url.startswith('http://127.0.0.1:'):
                            route.continue_()
                        else:
                            external.append(route.request.url)
                            if fail_tiles:
                                route.abort('failed')
                            else:
                                route.fulfill(status=200, content_type='image/png', body=pixel)
                    page.route('**/*', intercept)
                    page.goto(f'http://127.0.0.1:{server.server_port}/')
                    expect(page.locator('.memory-card')).to_have_count(3)
                    page.locator('#map-shortcut').click()
                    expect(page.locator('.photo-pin')).to_have_count(1)
                    expect(page.locator('.photo-pin b')).to_have_text('2')
                    assert page.locator('.photo-pin').evaluate('(p)=>p.querySelector("img").getBoundingClientRect().width <= p.getBoundingClientRect().width')
                    assert not external, external
                    page.locator('.photo-pin').click()
                    expect(page.locator('.atlas-memory')).to_have_count(2)
                    page.locator('[data-map-open]').first.click()
                    expect(page.locator('#viewer-dialog')).to_be_visible()
                    page.locator('.viewer-details summary').click()
                    expect(page.locator('.capture-card')).to_contain_text('Test Camera')
                    expect(page.locator('.capture-card')).to_contain_text('4000 × 3000')
                    expect(page.locator('.capture-card')).to_contain_text('ISO')
                    page.locator('[data-capture-map]').click()
                    expect(page.locator('.photo-pin b')).to_have_text('')
                    page.locator('[data-map-nearby]').click()
                    expect(page.locator('.photo-pin b')).to_have_text('2')
                    page.locator('[data-map-tiles]').click()
                    expect(page.locator('[data-map-status]')).to_have_text('街道地图 · OpenStreetMap')
                    assert external and all(url.startswith('https://tile.openstreetmap.org/') for url in external)
                    expect(page.locator('.leaflet-control-attribution')).to_contain_text('OpenStreetMap contributors')
                    page.locator('[data-map-tiles]').click()
                    expect(page.locator('[data-map-status]')).to_have_text('离线概览 · 无需 Key')
                    fail_tiles = True
                    page.locator('[data-map-in]').click()
                    page.wait_for_timeout(300)
                    page.locator('[data-map-tiles]').click()
                    expect(page.locator('[data-map-status]')).to_have_text('街道暂时无法加载，可切回离线')
                    page.locator('[data-map-tiles]').click()
                    fail_tiles = False
                    page.locator('[data-map-missing]').click()
                    expect(page.locator('.atlas-memory')).to_have_count(1)
                    page.locator('[data-map-edit]').click()
                    expect(page.locator('#editor-dialog')).to_be_visible()
                    page.locator('[data-pick-location]').click()
                    expect(page.locator('[data-pick-save]')).to_be_disabled()
                    page.locator('#memory-map').click(position={'x': 640, 'y': 300})
                    expect(page.locator('[data-pick-save]')).to_be_enabled()
                    page.locator('[data-pick-save]').click()
                    expect(page.locator('#map-dialog')).not_to_be_visible()
                    expect(page.locator('#editor-dialog')).to_be_visible()
                    assert page.locator('[name=latitude]').input_value()
                    page.locator('#editor-dialog [type=submit]').click()
                    expect(page.locator('#editor-dialog')).not_to_be_visible()
                    assert repository.catalog()['items'][[i['id'] for i in repository.catalog()['items']].index(ids['three.png'])]['coordinates']
                    page.reload()
                    page.locator('#map-shortcut').click()
                    expect(page.locator('[data-map-caption]')).to_contain_text('3 份有位置 · 0 份待补位置')
                    for width, height in [(360, 800), (390, 844), (768, 900), (1440, 1000), (1920, 1080), (844,390)]:
                        page.set_viewport_size({'width': width, 'height': height})
                        page.wait_for_timeout(250)  # Leaflet batches resize handling.
                        assert page.locator('#map-dialog').evaluate('(d)=>d.scrollWidth <= innerWidth'), width
                        expect(page.locator('[data-map-close]')).to_be_in_viewport()
                        expect(page.locator('.leaflet-control-attribution')).to_be_in_viewport()
                        for pin in page.locator('.photo-pin').all():
                            assert pin.evaluate('(p)=>p.querySelector("img").getBoundingClientRect().width <= p.getBoundingClientRect().width')
                    page.set_viewport_size({'width': 390, 'height': 844})
                    page.wait_for_timeout(250)
                    page.screenshot(path=str(ROOT / '.local' / 'map-mobile.png'))
                    page.set_viewport_size({'width': 1440, 'height': 1000})
                    page.wait_for_timeout(250)
                    page.screenshot(path=str(ROOT / '.local' / 'map-desktop.png'))
                    page.keyboard.press('Escape')
                    expect(page.locator('#map-dialog')).not_to_be_visible()
                    # Removal explicitly persists null instead of resurrecting original GPS.
                    page.locator(f'[data-id="{ids["one.png"]}"] [data-action=edit]').first.click()
                    page.locator('[data-clear-location]').click()
                    page.locator('#editor-dialog [type=submit]').click()
                    expect(page.locator('#editor-dialog')).not_to_be_visible()
                    assert next(i for i in repository.catalog()['items'] if i['id'] == ids['one.png'])['coordinates'] is None
                    result = page.evaluate("""async () => {
                      const {clusterPoints,validCoordinates}=await import('./js/geo.js');
                      const points=[{x:79,y:1},{x:81,y:1},{x:400,y:1}];
                      return [clusterPoints(points,p=>p,80).map(g=>g.items.length),validCoordinates({latitude:true,longitude:0})];
                    }""")
                    assert result == [[2,1], False], result
                    export_static(ROOT / 'web', repository, media, '../media/', root / 'album')
                    static = ThreadingHTTPServer(('127.0.0.1', 0), partial(SimpleHTTPRequestHandler, directory=str(root)))
                    threading.Thread(target=static.serve_forever, daemon=True).start()
                    try:
                        page.goto(f'http://127.0.0.1:{static.server_port}/album/')
                        expect(page.locator('.memory-card')).to_have_count(3)
                        page.locator('#map-shortcut').click()
                        expect(page.locator('.photo-pin')).to_have_count(2)
                        page.keyboard.press('Escape')
                        page.locator(f'[data-id="{ids["one.png"]}"] [data-action=edit]').first.click()
                        page.locator('[name=latitude]').fill('0')
                        page.locator('[name=longitude]').fill('0')
                        page.locator('#editor-dialog [type=submit]').click()
                        expect(page.locator('#editor-dialog')).not_to_be_visible()
                        page.reload()
                        expect(page.locator('.memory-card')).to_have_count(3)
                        backup = page.evaluate("async () => (await import('./js/api.js')).backup()")
                        assert backup['memories'][ids['one.png']]['coordinates'] == {'latitude': 0, 'longitude': 0}
                        assert next(i for i in repository.catalog()['items'] if i['id'] == ids['one.png'])['coordinates'] is None
                    finally:
                        static.shutdown(); static.server_close()
                    assert not errors, errors
                    browser.close()
                    print('PASS: local map, clustering, nearby photos, camera info, tile opt-in and attribution, manual picker, coordinate persistence/removal, responsive layouts, static nested export and backup. No external requests left the test.')
            finally:
                server.shutdown(); server.server_close()


if __name__ == '__main__':
    main()


