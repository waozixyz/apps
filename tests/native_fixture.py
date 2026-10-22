"""Build real nested bundles and exercise the exact released runtime."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import shlex
import struct
import subprocess
import sys
import zlib

ROOT = Path(__file__).resolve().parents[1]
WORK = Path(os.environ.get('APPS_TEST_OUTPUT', ROOT / 'build/native-test')).resolve()
ZIRAN = str(ROOT / 'scripts/ziran.sh')
LOCK_FLAGS = [] if (ROOT / 'ziran.local.toml').exists() else ['--locked']


def run(*arguments):
    subprocess.run(arguments, cwd=ROOT, check=True)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def child(identifier, path, protocol, expected, asset='assets/child.zib'):
    return dict(id=identifier, title=identifier, bundle=asset,
                protocol=protocol, expected_id=expected, version='1', sha256=digest(path))


def bundle(source, path, assets=None):
    arguments = [ZIRAN, 'bundle', '--project', *LOCK_FLAGS, '--root', str(ROOT / 'fixtures'),
                 '--entry', source + ':Main', '-o', str(path)]
    if assets:
        arguments += ['--asset-dir', 'assets=' + str(assets)]
    run(*arguments, str(ROOT / 'fixtures' / (source + '.zi')))


def stage(name, identifier, entries, payloads, controller):
    assets = WORK / name / 'assets'
    (assets / 'apps').mkdir(parents=True, exist_ok=True)
    for packed, payload in payloads.items():
        destination = assets / packed.removeprefix('assets/')
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(payload, destination)
    shutil.copyfile(controller, assets / 'apps/apps.zib')
    # Tiny binary image fixture; it is never a source or product screenshot.
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    (assets / 'preview.png').write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)) +
                                       chunk(b'IDAT', zlib.compress(bytes([0, 40, 160, 100]))) + chunk(b'IEND', b''))
    for entry in entries:
        entry['preview'] = 'assets/preview.png'
        entry['icon'] = 'assets/preview.png'
    (assets / 'apps/catalog.json').write_text(json.dumps(dict(
        schema=1, id=identifier, title=identifier, harness='assets/apps/apps.zib', children=entries)))
    return assets


def main():
    if len(sys.argv) not in (2, 3):
        raise SystemExit('Pass exact libziran.a and optionally a retained Chess node/2 bundle')
    for key in ('DISPLAY', 'WAYLAND_DISPLAY', 'XAUTHORITY', 'DBUS_SESSION_BUS_ADDRESS', 'SESSION_MANAGER'):
        os.environ.pop(key, None)
    WORK.mkdir(parents=True, exist_ok=True)
    leaf, middle, root = [WORK / (name + '.zib') for name in ('counter', 'middle', 'root')]
    controller, node = Path(os.environ.get('APPS_TEST_UI', ROOT / 'build/ui/apps.zib')).resolve(), WORK / 'node.zib'
    if not os.environ.get('APPS_TEST_UI'):
        run(sys.executable, str(ROOT / 'scripts/build-ui.py'))
    bundle('counter', leaf)
    node_assets = WORK / 'node-stage/assets/node'
    (node_assets / 'locales').mkdir(parents=True, exist_ok=True)
    (node_assets / 'catalog.json').write_text(json.dumps(dict(id='fixture.node', name='node', contract_version=1, module_api=2, host_api=12, save_schema=1)))
    (node_assets / 'locales/en.txt').write_text('[node_label]\nNode fixture\n---\n')
    # Tiny generated PCM tone; a sound is only an opaque packed asset here.
    import wave
    with wave.open(str(node_assets / 'sound.wav'), 'wb') as sound:
        sound.setnchannels(1); sound.setsampwidth(2); sound.setframerate(8000)
        sound.writeframes(bytes(64))
    bundle('node', node, node_assets.parent)
    entries = [child('fixture.counter', leaf, 'app/1', 'counter'),
               child('fixture.node', node, 'node/2', 'node', 'assets/node.zib')]
    payloads = {'assets/child.zib': leaf, 'assets/node.zib': node}
    if len(sys.argv) == 3:
        chess = Path(sys.argv[2]).resolve()
        entries.append(child('inbe.chess', chess, 'node/2', 'chess', 'assets/chess.zib'))
        payloads['assets/chess.zib'] = chess
        os.environ['APPS_FIXTURE_CHESS_SHA256'] = digest(chess)
    bundle('collection', middle, stage('middle-stage', 'fixture.middle', entries, payloads, controller))
    bundle('collection', root, stage('root-stage', 'fixture.root',
        [child('fixture.middle', middle, 'collection/1', 'collection')], {'assets/child.zib': middle}, controller))
    native_catalog = json.loads((ROOT / 'fixtures/consumer/catalog.json').read_text())
    for name in ('native', 'seen', 'no-update', 'changed-update', 'preview', 'download', 'downloading', 'reorder-list', 'reorder-grid'):
        import copy
        candidate = copy.deepcopy(native_catalog)
        if name == 'seen':
            candidate['children'][0]['update_seen'] = True
        if name == 'no-update':
            candidate['children'][0]['update_available'] = False
        if name == 'changed-update':
            candidate['children'][0]['available_sha256'] = 'd' * 64
        if name in ('download', 'downloading'):
            candidate['children'][1].update(on_device=False, downloading=name == 'downloading',
                                            bytes=4096, actions=['open', 'install'])
        if name.startswith('reorder-'):
            candidate['presentation'].update(mode='list' if name == 'reorder-list' else 'icon', section_break=1, columns=3)
            for card in candidate['children']:
                card['reorderable'] = True
            if name == 'reorder-list':
                candidate['children'][1]['reorderable'] = False
        if name == 'preview':
            candidate['presentation']['mode'] = 'preview'
            for card in candidate['children']:
                card['preview'] = 'assets/preview.png'
        (WORK / (name + '-catalog.json')).write_text(json.dumps(candidate))
    os.environ['APPS_FIXTURE_NATIVE_CATALOG_ROOT'] = str(WORK)
    output = WORK / 'c'
    output.mkdir(exist_ok=True)
    run(ZIRAN, 'build', '--project', *LOCK_FLAGS, '--target=c', '--no-main', '--entry', 'native_behavior:Check',
        '--root', str(ROOT / 'tests'), '-o', str(output), str(ROOT / 'tests/native_behavior.zi'))
    (output / 'main.c').write_text('#include <stdio.h>\n#include "native_behavior.h"\nint main(void) { int r=Check(); if(r) fprintf(stderr,"Apps native check %d failed\\n",r); return r ? 1 : 0; }\n')
    toolchain = Path(subprocess.check_output([ZIRAN, 'pkg', 'path', 'ziran', *LOCK_FLAGS], cwd=ROOT, text=True).strip())
    includes = [argument for path in [output, *sorted(output.rglob('*'))] if path.is_dir() for argument in ('-iquote', str(path))]
    run(os.environ.get('CC', 'cc'), '-std=c11', '-O2', '-ffunction-sections', '-fdata-sections', '-I' + str(toolchain / 'include'),
        *shlex.split(os.environ.get('CFLAGS', '')),
        *includes, *map(str, sorted(output.rglob('*.c'))), str(ROOT / 'tests/preparation_host.c'),
        sys.argv[1], '-Wl,--gc-sections', '-Wl,--wrap=BundleOpenBytes',
        '-Wl,--wrap=BundleInstantiate', '-Wl,--wrap=BundleInstanceRun', '-Wl,--wrap=BundleClose',
        '-lm', '-lpthread', '-o', str(WORK / 'test'))
    os.environ['APPS_FIXTURE_UI_BUNDLE'] = str(controller)
    os.environ['APPS_FIXTURE_ROOT_BUNDLE'] = str(root)
    os.environ['APPS_FIXTURE_ROOT_SHA256'] = digest(root)
    os.environ['APPS_FIXTURE_HARNESS_SHA256'] = digest(controller)
    os.environ['APPS_FIXTURE_NODE_BUNDLE'] = str(node)
    os.environ['APPS_FIXTURE_NODE_SHA256'] = digest(node)
    os.environ['APPS_FIXTURE_COUNTER_BUNDLE'] = str(leaf)
    os.environ['APPS_FIXTURE_COUNTER_SHA256'] = digest(leaf)
    result = subprocess.run([str(WORK / 'test')], cwd=ROOT, text=True, capture_output=True)
    # The final wrong-identity test deliberately trips the VM's foreign-call
    # gate. Keep that expected diagnostic without presenting it as a failure.
    (WORK / 'run.log').write_text(result.stdout + result.stderr)
    if result.returncode:
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
        result.check_returncode()
    print('Apps native: asynchronous root/child preparation and favorites, safe cancellation and Back, screenshot/icon cards, menus, update/rollback targets, 12 locales, nested node/2, resource bounds and stable locators passed')


if __name__ == '__main__':
    main()
