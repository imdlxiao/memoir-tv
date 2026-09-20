"""Measure synthetic catalog polling without real media or decoding. Author: donglixiao."""
import argparse
import json
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from memoir.library import Application
from memoir.scanner import scan
from memoir.storage import Repository


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--items', type=int, default=10000)
    args = parser.parse_args()
    if not 1 <= args.items <= 100000:
        parser.error('items must be between 1 and 100000')
    with tempfile.TemporaryDirectory(prefix='memoir-scale-') as directory:
        root = Path(directory)
        media = root / 'media'
        for number in range(args.items):
            month = media / str(2020 + number // 6000) / f'{1 + number // 500 % 12:02}'
            month.mkdir(parents=True, exist_ok=True)
            (month / f'fixture-{number:06}.mp4').touch()
        repository = Repository(root / 'data')
        started = time.perf_counter()
        repository.replace_index(scan(media, repository.directory, previews=False))
        initial = time.perf_counter() - started
        app = Application(media, repository, ROOT / 'web', 'unavailable-ffmpeg')
        body, tag = app.catalog_payload()
        timings = []
        for _ in range(10):
            started = time.perf_counter()
            current, current_tag = app.catalog_payload()
            timings.append((time.perf_counter() - started) * 1000)
            assert current is body and current_tag == tag
        (month / 'one-new-arrival.mp4').touch()
        started = time.perf_counter()
        # The benchmark excludes decoding; discover and publish only the new item.
        app._synchronize(snapshot=False)
        new_arrival = (time.perf_counter() - started) * 1000
        result = {'items': args.items, 'directories': len(app.inventory.directories),
                  'initialScanSeconds': round(initial, 3), 'unchangedPollMedianMs': round(statistics.median(timings), 3),
                  'fullCatalogBytes': len(body), 'unchangedResponseBodyBytes': 0,
                  'wireBufferReused': True, 'decodedMedia': 0}
        result['newArrivalIndexMs'] = round(new_arrival, 3)
        print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
