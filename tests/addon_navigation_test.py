#!/usr/bin/env python3
"""Real portable guests, native shared AppHost/tree, consent and compatibility.

Run: build-queue -- python3 tests/addon_navigation_test.py [exact libziran.a]
No display, browser, downloaded packages, or account data is used.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import native_fixture as native

ROOT = native.ROOT
WORK = ROOT / 'work/arcade-addon'


def run(*args):
    subprocess.run(list(map(str, args)), cwd=ROOT, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('runtime', nargs='?', type=Path)
    parser.add_argument('--compatibility', action='store_true', help='also run existing tree and full native host suites')
    args = parser.parse_args()
    sys.stdout.reconfigure(line_buffering=True)
    for key in ('DISPLAY', 'WAYLAND_DISPLAY', 'XAUTHORITY', 'DBUS_SESSION_BUS_ADDRESS',
                'SESSION_MANAGER', 'DESKTOP_SESSION', 'XDG_SESSION_ID', 'XDG_SESSION_TYPE'):
        os.environ.pop(key, None)
    os.environ.update(MAKEFLAGS='-j1', ZIRAN_PAR_THREADS='1', YUE_DESKTOP_RECOVERY='0')
    run('git', 'check-ignore', 'work/arcade-addon/test')
    WORK.mkdir(parents=True, exist_ok=True)
    scratch = WORK / 'scratch'
    scratch.mkdir(exist_ok=True)
    os.environ['TMPDIR'] = str(scratch)
    toolchain = Path(subprocess.check_output([native.ZIRAN, 'pkg', 'path', 'ziran'], cwd=ROOT, text=True).strip())
    runtime = args.runtime or toolchain / 'build/libziran.a'
    sources = ('src/host.zi', 'src/preparation.zi', 'src/tree.zi', 'src/protocol.zi',
               'ui/apps.zi', 'tests/addon_navigation_behavior.zi')
    before = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in sources}
    run(sys.executable, ROOT / 'scripts/build-ui.py', '--output', WORK / 'controller')
    controller = WORK / 'controller/apps.zx'
    for protocol in (1, 2):
        assets = WORK / f'node-{protocol}/assets/navigation'
        assets.mkdir(parents=True, exist_ok=True)
        (assets / 'catalog.json').write_text(json.dumps(dict(id='fixture.game', name='navigation',
            contract_version=1, module_api=2, host_api=42, save_schema=1)))
        game = WORK / f'game-{protocol}.zx'
        defines = ['--define', 'APPS_ADDON_NODE'] if protocol == 2 else []
        run(native.ZIRAN, 'bundle', '--project', *native.LOCK_FLAGS, '--root', ROOT / 'fixtures',
            '--entry', 'addon_navigation_guest:Main', *defines, '--asset-dir', 'assets=' + str(assets.parent),
            '-o', game, ROOT / 'fixtures/addon_navigation_guest.zi')
        addon = WORK / 'game-1.zx'
        entries = [native.child('fixture.game', game, 'app/1' if protocol == 1 else 'node/2', 'navigation'),
                   native.child('fixture.addon', addon, 'app/1', 'navigation', 'assets/addon.zx'),
                   native.child('fixture.unrelated', addon, 'app/1', 'navigation', 'assets/unrelated.zx')]
        entries[1].update(title='Installed private editor', cover=dict(portrait='assets/preview.png', action='internal'),
                          dependencies=['fixture.game'])
        entries[2].update(cover=dict(portrait='assets/preview.png', action='internal'))
        native.WORK = WORK
        packed = native.stage(f'root-{protocol}', 'fixture.root', entries, {'assets/child.zx': game}, controller)
        root = WORK / f'root-{protocol}.zx'
        native.bundle('collection', root, packed)
        (WORK / f'root-{protocol}.sha256').write_text(hashlib.sha256(root.read_bytes()).hexdigest())
    (WORK / 'controller.sha256').write_text(hashlib.sha256(controller.read_bytes()).hexdigest())
    # Arcade's downloaded game is about 50 MB and its thin editor about 1 MB.
    # Keep the collection small; pack a real large asset in a verified base,
    # and compile a real linked guest against it. No inflated accounting mocks.
    native.WORK = WORK
    large_assets = WORK / 'large-assets'
    (large_assets / 'counter').mkdir(parents=True, exist_ok=True)
    (large_assets / 'large.bin').unlink(missing_ok=True)
    with (large_assets / 'counter/large.bin').open('wb') as stream:
        stream.truncate(50_340_876)
    (large_assets / 'counter/shared.bin').write_bytes(b'library')
    addon_assets = WORK / 'large-addon-assets'
    (addon_assets / 'counter-addon').mkdir(parents=True, exist_ok=True)
    with (addon_assets / 'counter-addon/editor.bin').open('wb') as stream:
        stream.truncate(1_083_716)
    large_base = WORK / 'large-base.zx'
    large_addon = WORK / 'large-addon.zx'
    native.bundle('counter', large_base, large_assets)
    native.bundle('counter_addon', large_addon, addon_assets, library=large_base)
    with large_base.open('rb') as stream:
        large_digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    large_entries = [dict(id='fixture.counter', title='fixture.counter', bundle='assets/child.zx',
                          protocol='app/1', expected_id='counter', version='1', sha256=large_digest),
                     native.child('fixture.addon', large_addon, 'app/1', 'counter-addon', 'assets/addon.zx')]
    large_entries[1].update(dependencies=['fixture.counter'], shared_code=True,
        cover=dict(portrait='assets/preview.png', action='internal'),
        resources=[dict(dependency='fixture.counter', path='assets/counter-addon/shared.bin', source='assets/counter/shared.bin'),
                   dict(dependency='fixture.counter', path='assets/counter-addon/large.bin', source='assets/counter/large.bin')])
    large_root = WORK / 'large-root.zx'
    native.bundle('collection', large_root, native.stage('large-root', 'fixture.large', large_entries, {}, controller))
    (WORK / 'large-root.sha256').write_text(native.digest(large_root))
    print(f'Weighted bundles: base={large_base.stat().st_size} addon={large_addon.stat().st_size} limit=67108864')
    lines = (ROOT / 'build/.ziran/module-map.tsv').read_text().splitlines()
    lines += [f'M\troot\t{name}\t{ROOT / "tests" / (name + ".zi")}'
              for name in ('addon_navigation_behavior', 'native_behavior')]
    mapping = WORK / 'module-map.tsv'
    mapping.write_text('\n'.join(lines) + '\n')
    os.environ['ZIRAN_PACKAGE_MAP'] = str(mapping)
    output = WORK / 'c'
    run(toolchain / 'build/bin/zi2c', '--prune-stale', '--module-path', toolchain / 'std', '--no-main',
        '--entry', 'addon_navigation_behavior:AddonCheck', '--root', ROOT / 'tests',
        '-o', output, ROOT / 'tests/addon_navigation_behavior.zi')
    (output / 'entry.c').write_text('#include <stdio.h>\n#include "addon_navigation_behavior.h"\n'
        'int main(void) { int r=AddonCheck(); if(r) fprintf(stderr,"Apps addon navigation test %d failed\\n",r); return r ? 1 : 0; }\n')
    includes = [arg for p in [output, *sorted(output.rglob('*'))] if p.is_dir() for arg in ('-iquote', str(p))]
    run(os.environ.get('CC', 'cc'), '-std=c11', '-O1', '-ffunction-sections', '-fdata-sections',
        '-I' + str(toolchain / 'include'), *includes, *sorted(output.rglob('*.c')),
        runtime, '-Wl,--gc-sections', '-lm', '-lpthread', '-o', WORK / 'test')
    run(WORK / 'test')
    print('PASS add-on navigation: app/1 + node/2, consent/Back, stale authorization/account; 50 MB shared-code base opens under 64 MiB, exact-source leases, cancellation and retired resource lifetime')
    after = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in sources}
    if before != after:
        raise RuntimeError('Apps production source changed during the local test')
    (WORK / 'local-tests.json').write_text(json.dumps(dict(status='passed', command=sys.argv,
        sources=after, controller_sha256=hashlib.sha256(controller.read_bytes()).hexdigest()), indent=2) + '\n')
    if not args.compatibility:
        return
    os.environ.pop('ZIRAN_PACKAGE_MAP')
    os.environ['APPS_TREE_TEST_OUTPUT'] = str(WORK / 'tree')
    run('sh', ROOT / 'tests/tree_test.sh', native.ZIRAN, runtime)
    os.environ['APPS_TEST_OUTPUT'] = str(WORK / 'host')
    os.environ['APPS_TEST_UI'] = str(controller)
    run(sys.executable, ROOT / 'tests/native_fixture.py', runtime)
    final = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in sources}
    if before != final:
        raise RuntimeError('Apps production source changed during compatibility local tests')
    (WORK / 'compatibility-local-tests.json').write_text(json.dumps(dict(status='passed',
        command=sys.argv, sources=final), indent=2) + '\n')


if __name__ == '__main__':
    main()
