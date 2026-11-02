#!/usr/bin/env python3
"""Real node/2 and app/1 guests through Apps' verified notification boundary."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import native_fixture as native

ROOT = native.ROOT
WORK = ROOT / 'work/notification-host'
ZIRAN = native.ZIRAN


def run(*args):
    subprocess.run(list(map(str, args)), cwd=ROOT, check=True)


def main():
    if len(sys.argv) != 2:
        raise SystemExit('Pass exact libziran.a')
    for key in ('DISPLAY', 'WAYLAND_DISPLAY', 'XAUTHORITY', 'DBUS_SESSION_BUS_ADDRESS',
                'SESSION_MANAGER', 'DESKTOP_SESSION', 'XDG_SESSION_ID', 'XDG_SESSION_TYPE'):
        os.environ.pop(key, None)
    os.environ.update(MAKEFLAGS='-j1', ZIRAN_PAR_THREADS='1', YUE_DESKTOP_RECOVERY='0')
    run('git', 'check-ignore', 'work/notification-host/test')
    WORK.mkdir(parents=True, exist_ok=True)
    toolchain = Path(subprocess.check_output([ZIRAN, 'pkg', 'path', 'ziran'], cwd=ROOT, text=True).strip())
    for game, identifier in [('wurm', 'xyz.waozi.wurm'), ('shovey', 'arcade.shovey')]:
        assets = WORK / game / 'assets/notification'
        assets.mkdir(parents=True, exist_ok=True)
        (assets / 'catalog.json').write_text(json.dumps(dict(id=identifier, name='notification',
            contract_version=1, module_api=2, host_api=42, save_schema=1)))
        for protocol in (1, 2):
            path = WORK / f'{game}-{protocol}.zx'
            defines = ['--define', 'KRYON_HOSTED_UI']
            if protocol == 2:
                defines += ['--define', 'APPS_NOTIFICATION_NODE']
            if game == 'shovey':
                defines += ['--define', 'APPS_NOTIFICATION_SHOVEY']
            common = [ZIRAN, 'bundle', '--project', *native.LOCK_FLAGS, '--root', ROOT / 'fixtures',
                      '--entry', 'notification_guest:Main', *defines]
            run(*common,
                '--asset-dir', 'assets=' + str(assets.parent), '-o', path,
                ROOT / 'fixtures/notification_guest.zi')
            (WORK / f'{game}-{protocol}.sha256').write_text(hashlib.sha256(path.read_bytes()).hexdigest())
            ir = WORK / f'ir-{game}-{protocol}'
            run(ZIRAN, 'ir', '--project', *native.LOCK_FLAGS, '--root', ROOT / 'fixtures',
                '--entry', 'notification_guest:Main', *defines, '-o', ir,
                ROOT / 'fixtures/notification_guest.zi')
            saved = WORK / f'{game}-{protocol}-saved.zx'
            run(toolchain / 'build/bin/zi2zx', 'bundle', '--root', ir, '--module-path', ir,
                '--entry', 'notification_guest:Main', '--asset-dir', 'assets=' + str(assets.parent),
                '-o', saved, ir / 'notification_guest.zir')
            if path.read_bytes() != saved.read_bytes():
                raise RuntimeError(f'Source/saved portable output differs: {game} protocol {protocol}')
    run(ZIRAN, 'bundle', '--project', *native.LOCK_FLAGS, '--root', ROOT / 'fixtures',
        '--entry', 'notification_guest:Main', '--define', 'KRYON_HOSTED_UI',
        '--define', 'APPS_NOTIFICATION_WRONG_ID', '-o', WORK / 'wrong-1.zx',
        ROOT / 'fixtures/notification_guest.zi')
    (WORK / 'wrong-1.sha256').write_text(hashlib.sha256((WORK / 'wrong-1.zx').read_bytes()).hexdigest())
    # Substitute only the native scheduler provider in the resolved package map.
    # Guest bundles above always compile the actual hosted Kryon implementation.
    provider = WORK / 'notification_schedule.zi'
    shutil.copyfile(ROOT / 'tests/notification_provider.zi', provider)
    lines = (ROOT / 'build/.ziran/module-map.tsv').read_text().splitlines()
    replaced = 0
    for index, line in enumerate(lines):
        fields = line.split('\t')
        if len(fields) == 4 and fields[0] == 'M' and fields[2] == 'notification_schedule':
            fields[3] = str(provider)
            lines[index] = '\t'.join(fields)
            replaced += 1
    if replaced != 1:
        raise RuntimeError(f'Expected one native notification provider, found {replaced}')
    lines += ['M\troot\t' + name + '\t' + str(ROOT / 'tests' / (name + '.zi'))
              for name in ('notification_host_behavior', 'native_behavior')]
    mapping = WORK / 'module-map.tsv'
    mapping.write_text('\n'.join(lines) + '\n')
    os.environ['ZIRAN_PACKAGE_MAP'] = str(mapping)
    output = WORK / 'c'
    run(toolchain / 'build/bin/zi2c', '--prune-stale', '--module-path', toolchain / 'std', '--no-main',
        '--entry', 'notification_host_behavior:NotificationCheck', '--root', ROOT / 'tests',
        '-o', output, ROOT / 'tests/notification_host_behavior.zi')
    (output / 'entry.c').write_text('#include <stdio.h>\n#include "notification_host_behavior.h"\n'
        'int main(void) { int r=NotificationCheck(); if(r) fprintf(stderr,"Apps notification test %d failed\\n",r); return r; }\n')
    includes = [arg for p in [output, *sorted(output.rglob('*'))] if p.is_dir() for arg in ('-iquote', str(p))]
    run(os.environ.get('CC', 'cc'), '-std=c11', '-O1', '-ffunction-sections', '-fdata-sections',
        '-I' + str(toolchain / 'include'), *includes, *sorted(output.rglob('*.c')),
        sys.argv[1], '-Wl,--gc-sections', '-lm', '-lpthread', '-o', WORK / 'test')
    run(WORK / 'test')
    print('Apps notifications: real Wurm/Shovey node/2 + app/1 guests, identity, scope, permission and focus isolation passed')


if __name__ == '__main__':
    main()
