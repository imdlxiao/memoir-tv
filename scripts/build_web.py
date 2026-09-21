"""Build checked-in legacy assets without a runtime Node dependency. Author: donglixiao."""
import argparse
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import subprocess
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
VERSION = '0.25.10'


def inputs():
    paths = sorted((ROOT / 'web/js').glob('*.js')) + [Path(__file__)]
    return {str(p.relative_to(ROOT)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download', action='store_true', help='Download the pinned standalone esbuild compiler, verifying npm integrity')
    parser.add_argument('--check', action='store_true', help='Verify committed assets match their source and artifact fingerprints')
    args = parser.parse_args()
    output = ROOT / 'web/compat'
    manifest = output / 'manifest.json'
    if args.check:
        saved = json.loads(manifest.read_text(encoding='utf-8'))
        assert saved['sources'] == inputs(), 'Legacy assets are stale: run python scripts/build_web.py --download'
        for name, digest in saved['outputs'].items():
            assert hashlib.sha256((output / name).read_bytes()).hexdigest() == digest, name
        print('Compatibility assets are current')
        return
    system = 'win32' if os.name == 'nt' else 'darwin' if platform.system() == 'Darwin' else 'linux'
    arch = 'arm64' if platform.machine().lower() in {'aarch64', 'arm64'} else 'x64'
    binary = ROOT / '.local/tools' / f'esbuild-{VERSION}-{system}-{arch}' / ('esbuild.exe' if os.name == 'nt' else 'esbuild')
    if not binary.exists():
        if not args.download:
            parser.error('First build requires --download; the website itself does not need this compiler')
        with urllib.request.urlopen(f'https://registry.npmjs.org/@esbuild/{system}-{arch}/{VERSION}', timeout=30) as response:
            metadata = json.load(response)
        with urllib.request.urlopen(metadata['dist']['tarball'], timeout=30) as response:
            payload = response.read()
        integrity = 'sha512-' + base64.b64encode(hashlib.sha512(payload).digest()).decode()
        if integrity != metadata['dist']['integrity']:
            raise ValueError('Compiler archive integrity mismatch')
        with tarfile.open(fileobj=io.BytesIO(payload), mode='r:gz') as archive:
            member = archive.getmember('package/esbuild.exe' if os.name == 'nt' else 'package/bin/esbuild')
            binary.parent.mkdir(parents=True, exist_ok=True)
            binary.write_bytes(archive.extractfile(member).read())
            binary.chmod(0o755)
    output.mkdir(exist_ok=True)
    for entry in ['app', 'login', 'admin']:
        subprocess.run([str(binary), str(ROOT / f'web/js/{entry}.js'), '--bundle', '--format=iife', '--target=chrome58',
            '--charset=utf8', '--minify', '--legal-comments=none',
            '--banner:js=/* Author: donglixiao. Generated compatibility bundle; edit web/js sources. */',
            f'--outfile={output / (entry + ".js")}'], check=True)
    manifest.write_text(json.dumps({'compiler': f'esbuild {VERSION}', 'target': 'chrome58', 'sources': inputs(),
        'outputs': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output.glob('*.js'))}}, indent=2) + '\n', encoding='utf-8', newline='\n')


if __name__ == '__main__':
    main()
