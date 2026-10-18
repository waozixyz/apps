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
WORK = parser.parse_args().output.resolve()
WORK.mkdir(parents=True, exist_ok=True)
subprocess.run([sys.executable, str(ROOT / 'scripts/generate-ui-locales.py'), '--check'], cwd=ROOT, check=True)
flags = [] if (ROOT / 'ziran.local.toml').exists() else ['--locked']
subprocess.run([str(ROOT / 'scripts/ziran.sh'), 'bundle', '--project', *flags,
                '--root', str(ROOT / 'ui'), '--entry', 'apps:Main', '--define', 'KRYON_HOSTED_UI',
                '-o', str(WORK / 'apps.zib'), str(ROOT / 'ui/apps.zi')], cwd=ROOT, check=True)
digest = hashlib.sha256((WORK / 'apps.zib').read_bytes()).hexdigest()
(WORK / 'apps.sha256').write_text(digest + '\n')
(WORK / 'manifest.json').write_text(json.dumps(dict(id='apps', protocol='app/1', sha256=digest), indent=2) + '\n')
print(f'Built shared Apps UI and trusted digest in {WORK}')
