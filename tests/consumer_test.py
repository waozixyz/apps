"""Compile a separate Ziran package through actual apps/* exported imports.

The source stays in fixtures/consumer. An explicit test-only module map binds
this unpublished local package; no Git URL, lock entry or source checkout is
invented. The map is derived from Ziran's own resolved dependency map.
"""
from pathlib import Path
import os
import subprocess
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
CONSUMER = ROOT / 'fixtures/consumer'
WORK = ROOT / 'build/consumer-test'
ZIRAN = str(ROOT / 'scripts/ziran.sh')


def run(*args):
    subprocess.run(args, cwd=ROOT, check=True)


def main():
    if len(sys.argv) != 2:
        raise SystemExit('Pass the intended libziran.a')
    for name in ('DISPLAY', 'WAYLAND_DISPLAY', 'XAUTHORITY', 'DBUS_SESSION_BUS_ADDRESS'):
        os.environ.pop(name, None)
    if not os.environ.get('APPS_TEST_UI'):
        run(sys.executable, str(ROOT / 'scripts/build-ui.py'))
    package = 'p0000000000000001'
    lines = ['P\troot\t' + str(CONSUMER), 'M\troot\tmain\t' + str(CONSUMER / 'main.zi')]
    for line in (ROOT / 'build/.ziran/module-map.tsv').read_text().splitlines():
        values = line.split('\t')
        if len(values) > 1 and values[1] == 'root':
            values[1] = package
        lines.append('\t'.join(values))
        # The consumer imports Kryon independently, using Apps' resolved graph.
        if len(values) > 2 and values[0] == 'D' and values[1] == package:
            consumer_edge = values.copy()
            consumer_edge[1] = 'root'
            lines.append('\t'.join(consumer_edge))
    for name, filename in tomllib.loads((ROOT / 'ziran.toml').read_text())['exports'].items():
        module = Path(filename).stem
        lines.append(f'D\troot\tapps/{name}\t{package}\t{module}')
    WORK.mkdir(parents=True, exist_ok=True)
    mapping = WORK / 'module-map.tsv'
    mapping.write_text('\n'.join(lines) + '\n')
    output = WORK / 'c'
    toolchain = Path(subprocess.check_output([ZIRAN, 'pkg', 'path', 'ziran'], cwd=ROOT, text=True).strip())
    os.environ['ZIRAN_PACKAGE_MAP'] = str(mapping)
    run(str(toolchain / 'build/bin/zi2c'), '--prune-stale', '--no-main', '--entry', 'main:Check', '--module-path', str(toolchain / 'std'),
        '--root', str(CONSUMER), '-o', str(output), str(CONSUMER / 'main.zi'))
    (output / 'entry.c').write_text('#include "main.h"\nint main(void) { return Check(); }\n')
    includes = [arg for path in [output, *sorted(output.rglob('*'))] if path.is_dir() for arg in ('-iquote', str(path))]
    run(os.environ.get('CC', 'cc'), '-std=c11', '-O2', '-ffunction-sections', '-fdata-sections',
        '-I' + str(toolchain / 'include'), *includes, *map(str, sorted(output.rglob('*.c'))),
        sys.argv[1], '-Wl,--gc-sections', '-lm', '-lpthread', '-o', str(WORK / 'test'))
    run(str(WORK / 'test'))
    print('Apps external consumer: package exports, state callback, legacy records and runtime access passed')


if __name__ == '__main__':
    main()
