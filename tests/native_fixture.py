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
WINDOWS = os.environ.get('APPS_TEST_PLATFORM') == 'windows'


def run(*arguments):
    subprocess.run(arguments, cwd=ROOT, check=True)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def runtime_path(path):
    path = Path(path).resolve()
    return 'Z:' + str(path).replace('/', '\\') if WINDOWS else str(path)


def child(identifier, path, protocol, expected, asset='assets/child.zx'):
    return dict(id=identifier, title=identifier, bundle=asset,
                protocol=protocol, expected_id=expected, version='1', sha256=digest(path))


def bundle(source, path, assets=None, library=None):
    arguments = [ZIRAN, 'bundle', '--project', *LOCK_FLAGS, '--root', str(ROOT / 'fixtures'),
                 '--entry', source + ':Main', '-o', str(path)]
    if assets:
        arguments += ['--asset-dir', 'assets=' + str(assets)]
    if library:
        arguments += ['--library', str(library)]
    run(*arguments, str(ROOT / 'fixtures' / (source + '.zi')))


def stage(name, identifier, entries, payloads, controller):
    assets = WORK / name / 'assets'
    (assets / 'apps').mkdir(parents=True, exist_ok=True)
    for packed, payload in payloads.items():
        destination = assets / packed.removeprefix('assets/')
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(payload, destination)
    shutil.copyfile(controller, assets / 'apps/apps.zx')
    # Tiny binary image fixture; it is never a source or product screenshot.
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    (assets / 'preview.png').write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)) +
                                       chunk(b'IDAT', zlib.compress(bytes([0, 40, 160, 100]))) + chunk(b'IEND', b''))
    for entry in entries:
        entry['preview'] = 'assets/preview.png'
        entry['icon'] = 'assets/preview.png'
    (assets / 'apps/catalog.json').write_text(json.dumps(dict(
        schema=1, id=identifier, title=identifier, harness='assets/apps/apps.zx', children=entries)))
    return assets


def main():
    if len(sys.argv) not in (2, 3):
        raise SystemExit('Pass exact libziran.a and optionally a retained Chess node/2 bundle')
    for key in ('DISPLAY', 'WAYLAND_DISPLAY', 'XAUTHORITY', 'DBUS_SESSION_BUS_ADDRESS', 'SESSION_MANAGER'):
        os.environ.pop(key, None)
    WORK.mkdir(parents=True, exist_ok=True)
    leaf, middle, root = [WORK / (name + '.zx') for name in ('counter', 'middle', 'root')]
    controller, node = Path(os.environ.get('APPS_TEST_UI', ROOT / 'build/ui/apps.zx')).resolve(), WORK / 'node.zx'
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
               child('fixture.node', node, 'node/2', 'node', 'assets/node.zx')]
    payloads = {'assets/child.zx': leaf, 'assets/node.zx': node}
    if len(sys.argv) == 3:
        chess = Path(sys.argv[2]).resolve()
        entries.append(child('inbe.chess', chess, 'node/2', 'chess', 'assets/chess.zx'))
        payloads['assets/chess.zx'] = chess
        os.environ['APPS_FIXTURE_CHESS_SHA256'] = digest(chess)
    bundle('collection', middle, stage('middle-stage', 'fixture.middle', entries, payloads, controller))
    bundle('collection', root, stage('root-stage', 'fixture.root',
        [child('fixture.middle', middle, 'collection/1', 'collection')], {'assets/child.zx': middle}, controller))
    # A collection that declares a game it does not pack, as Arcade does.
    remote_root = WORK / 'remote-root.zx'
    bundle('collection', remote_root, stage('remote-stage', 'fixture.remote-root',
        [child('fixture.counter', leaf, 'app/1', 'counter'),
         child('fixture.remote', leaf, 'app/1', 'counter', 'assets/remote.zx')], {'assets/child.zx': leaf}, controller))
    dependency_root = WORK / 'dependency-root.zx'
    editor = child('fixture.editor', leaf, 'app/1', 'counter', 'assets/editor.zx')
    editor.update(dependencies=['fixture.node'], resources=[dict(dependency='fixture.node',
        path='assets/counter/shared.wav', source='assets/node/sound.wav')])
    bundle('collection', dependency_root, stage('dependency-stage', 'fixture.dependencies',
        [child('fixture.node', node, 'node/2', 'node', 'assets/node.zx'), editor],
        {'assets/node.zx': node, 'assets/editor.zx': leaf}, controller))
    thin = WORK / 'counter-addon.zx'
    bundle('counter_addon', thin, library=leaf)
    thin_entry = child('fixture.addon', thin, 'app/1', 'counter-addon', 'assets/addon.zx')
    thin_entry.update(dependencies=['fixture.counter'], shared_code=True)
    thin_root = WORK / 'thin-root.zx'
    bundle('collection', thin_root, stage('thin-stage', 'fixture.thin',
        [child('fixture.counter', leaf, 'app/1', 'counter'), thin_entry],
        {'assets/child.zx': leaf, 'assets/addon.zx': thin}, controller))
    # A slim collection like Arcade's: no packed controller, and its children's
    # preview art in one separate bundle.
    art_assets = WORK / 'art-stage/assets'
    art_assets.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(WORK / 'remote-stage/assets/preview.png', art_assets / 'preview.png')
    art = WORK / 'art.zx'
    bundle('collection', art, art_assets)
    slim_assets = stage('slim-stage', 'fixture.slim', [child('fixture.counter', leaf, 'app/1', 'counter')],
                        {'assets/child.zx': leaf}, controller)
    (slim_assets / 'apps/apps.zx').unlink()
    (slim_assets / 'preview.png').unlink()
    slim_catalog = json.loads((slim_assets / 'apps/catalog.json').read_text())
    slim_catalog['art'] = dict(sha256=digest(art), bytes=art.stat().st_size)
    (slim_assets / 'apps/catalog.json').write_text(json.dumps(slim_catalog))
    slim_root = WORK / 'slim-root.zx'
    bundle('collection', slim_root, slim_assets)
    os.environ['APPS_FIXTURE_SLIM_ROOT_BUNDLE'] = runtime_path(slim_root)
    os.environ['APPS_FIXTURE_SLIM_ROOT_SHA256'] = digest(slim_root)
    os.environ['APPS_FIXTURE_ART_BUNDLE'] = runtime_path(art)
    os.environ['APPS_FIXTURE_THIN_ROOT_BUNDLE'] = runtime_path(thin_root)
    os.environ['APPS_FIXTURE_THIN_ROOT_SHA256'] = digest(thin_root)
    native_catalog = json.loads((ROOT / 'fixtures/consumer/catalog.json').read_text())
    for name in ('native', 'seen', 'no-update', 'changed-update', 'preview', 'download', 'downloading',
                 'download-failed', 'download-ready', 'download-request', 'cover-download', 'cover-grid', 'cover-grid-download', 'cover-grid-dependencies', 'reorder-list', 'reorder-grid', 'simple-grid', 'simple-list', 'simple-downloading'):
        import copy
        candidate = copy.deepcopy(native_catalog)
        if name == 'seen':
            candidate['children'][0]['update_seen'] = True
        if name == 'no-update':
            candidate['children'][0]['update_available'] = False
        if name == 'changed-update':
            candidate['children'][0]['available_sha256'] = 'd' * 64
        if name in ('download', 'downloading', 'download-failed', 'download-request', 'cover-download', 'simple-downloading'):
            candidate['children'][1].update(on_device=False, downloading=name in ('downloading', 'simple-downloading'),
                                            bytes=4096, actions=['open', 'install'],
                                            permissions=['account', 'media', 'unknown-later'])
        if name == 'downloading':
            candidate['children'][1]['progress'] = 40
        if name == 'download-failed':
            candidate['children'][1]['download_failed'] = True
        if name == 'download-request':
            candidate['presentation'].update(download_id='native.clock', download_request=1)
        if name == 'cover-download':
            candidate['presentation']['mode'] = 'preview'
            candidate['children'] = [candidate['children'][1]]
            candidate['children'][0]['cover'] = {'portrait': 'assets/preview.png', 'action': 'open'}
        if name.startswith('simple-'):
            candidate['presentation']['hide_sizes'] = True
            candidate['presentation']['mode'] = 'list' if name == 'simple-list' else 'icon'
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
        if name in ('cover-grid', 'cover-grid-download', 'cover-grid-dependencies'):
            candidate['presentation']['mode'] = 'covers'
            for card in candidate['children']:
                card['cover'] = {'portrait': 'assets/preview.png', 'landscape': 'assets/preview.png',
                                 'logo': 'assets/preview.png', 'action': 'open'}
        if name == 'cover-grid-download':
            candidate['children'][1].update(on_device=False, bytes=4096, actions=['open', 'install'])
        if name == 'cover-grid-dependencies':
            candidate['children'][1].update(on_device=False, bytes=140, actions=['open', 'install'], downloads=[
                dict(title='Breathing', bytes=100, dependency=True), dict(title='Clock', bytes=40, dependency=False)])
        (WORK / (name + '-catalog.json')).write_text(json.dumps(candidate))
    os.environ['APPS_FIXTURE_NATIVE_CATALOG_ROOT'] = runtime_path(WORK)
    output = WORK / 'c'
    output.mkdir(exist_ok=True)
    defines = ['--define', '_WIN32'] if WINDOWS else []
    run(ZIRAN, 'build', '--project', *LOCK_FLAGS, '--target=c', '--no-main', '--entry', 'native_behavior:Check',
        *defines, '--root', str(ROOT / 'tests'), '-o', str(output), str(ROOT / 'tests/native_behavior.zi'))
    (output / 'main.c').write_text('#include <stdio.h>\n#include "native_behavior.h"\nint main(void) { int r=Check(); if(r) fprintf(stderr,"Apps native check %d failed\\n",r); return r ? 1 : 0; }\n')
    toolchain = Path(subprocess.check_output([ZIRAN, 'pkg', 'path', 'ziran', *LOCK_FLAGS], cwd=ROOT, text=True).strip())
    includes = [argument for path in [output, *sorted(output.rglob('*'))] if path.is_dir() for argument in ('-iquote', str(path))]
    compiler = os.environ.get('CC', 'x86_64-w64-mingw32-gcc' if WINDOWS else 'cc')
    executable = WORK / ('test.exe' if WINDOWS else 'test')
    platform_flags = ['-static'] if WINDOWS else ['-lpthread']
    if WINDOWS and os.environ.get('MCFGTHREADS'):
        platform_flags.append('-L' + os.environ['MCFGTHREADS'] + '/lib')
    run(compiler, '-std=c11', '-O2', '-ffunction-sections', '-fdata-sections', '-I' + str(toolchain / 'include'),
        *shlex.split(os.environ.get('CFLAGS', '')),
        *includes, *map(str, sorted(output.rglob('*.c'))), str(ROOT / 'tests/preparation_host.c'),
        sys.argv[1], '-Wl,--gc-sections', '-Wl,--wrap=BundleOpenBytes',
        '-Wl,--wrap=BundleOpenBytesWithLibraries',
        '-Wl,--wrap=BundleInstantiate', '-Wl,--wrap=BundleInstanceRun', '-Wl,--wrap=BundleClose',
        '-lm', *platform_flags, '-o', str(executable))
    os.environ['APPS_FIXTURE_UI_BUNDLE'] = runtime_path(controller)
    os.environ['APPS_FIXTURE_ROOT_BUNDLE'] = runtime_path(root)
    os.environ['APPS_FIXTURE_ROOT_SHA256'] = digest(root)
    os.environ['APPS_FIXTURE_REMOTE_ROOT_BUNDLE'] = runtime_path(remote_root)
    os.environ['APPS_FIXTURE_REMOTE_ROOT_SHA256'] = digest(remote_root)
    os.environ['APPS_FIXTURE_DEPENDENCY_ROOT_BUNDLE'] = runtime_path(dependency_root)
    os.environ['APPS_FIXTURE_DEPENDENCY_ROOT_SHA256'] = digest(dependency_root)
    os.environ['APPS_FIXTURE_HARNESS_SHA256'] = digest(controller)
    os.environ['APPS_FIXTURE_NODE_BUNDLE'] = runtime_path(node)
    os.environ['APPS_FIXTURE_NODE_SHA256'] = digest(node)
    os.environ['APPS_FIXTURE_COUNTER_BUNDLE'] = runtime_path(leaf)
    os.environ['APPS_FIXTURE_COUNTER_SHA256'] = digest(leaf)
    command = [str(executable)]
    if WINDOWS:
        command.insert(0, os.environ.get('WINDOWS_WINE', 'wine'))
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=90)
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
