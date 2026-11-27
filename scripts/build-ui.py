#!/usr/bin/env python3
"""Build the shared Apps controller and its exact trusted payload digest."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path, default=ROOT / 'build/ui')
parser.add_argument('--project', type=Path, default=ROOT, help='consumer project selecting the controller compiler and dependency graph')
parser.add_argument('--compiler', type=Path, default=ROOT / 'scripts/ziran.sh', help='compiler selected by the consumer project')
args = parser.parse_args()
WORK = args.output.resolve()
project = args.project.resolve()
if project != ROOT:
    lock = json.loads((project / 'ziran.lock').read_text())
    identity = lock['root']['dependencies']['apps']
    if next(item for item in lock['packages'] if item['id'] == identity)['name'] != 'Apps':
        parser.error('consumer apps dependency must be Apps')
WORK.mkdir(parents=True, exist_ok=True)
subprocess.run([sys.executable, str(ROOT / 'scripts/generate-ui-locales.py'), '--check'], cwd=ROOT, check=True)
flags = [] if (project / 'ziran.local.toml').exists() else ['--locked']
source = ROOT / 'ui/apps.zi'
# Lock identities select revisions; generated module names use dependency
# aliases. Ask the selected compiler to resolve the actual source first.
subprocess.run([str(args.compiler.resolve()), 'check', '--project', *flags,
                '--root', str(ROOT / 'ui'), str(source)], cwd=project, check=True)
modules = []
for line in (project / 'build/.ziran/module-map.tsv').read_text().splitlines():
    fields = line.split('\t')
    if len(fields) == 4 and fields[0] == 'M' and Path(fields[3]).resolve() == source:
        modules.append(fields[2] if fields[1] == 'root' else f'{fields[1]}__{fields[2]}')
if len(modules) != 1:
    parser.error('controller source must have one identity in the selected package graph')
entry = modules[0] + ':Main'
subprocess.run([str(args.compiler.resolve()), 'bundle', '--project', *flags,
                '--root', str(ROOT / 'ui'), '--entry', entry, '--define', 'KRYON_HOSTED_UI',
                '-o', str(WORK / 'apps.zx'), str(ROOT / 'ui/apps.zi')], cwd=project, check=True)
with (WORK / 'apps.zx').open('rb') as stream:
    digest_state = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b''):
        digest_state.update(chunk)
    digest = digest_state.hexdigest()
(WORK / 'apps.sha256').write_text(digest + '\n')
(WORK / 'manifest.json').write_text(json.dumps(dict(id='apps', protocol='app/1', sha256=digest), indent=2) + '\n')
print(f'Built shared Apps UI and trusted digest in {WORK}')
