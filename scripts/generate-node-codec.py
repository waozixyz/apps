#!/usr/bin/env python3
"""Generate the shared node/2 value codec with Kryon's canonical generator."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
KRYON = Path(subprocess.check_output(
    [str(ROOT / 'scripts/ziran.sh'), 'pkg', 'path', 'kryon'], cwd=ROOT, text=True).strip())
command = [sys.executable, str(KRYON / 'scripts/generate-widget-codecs.py'),
           '--output', str(ROOT / 'src/node_codec.zi'),
           '--uses', str(KRYON / 'src/backend/widget_codec.zi'),
           '--generated-by', 'scripts/generate-node-codec.py',
           '--source', str(KRYON / 'src/ui/session.zi'),
           '--source', str(ROOT / 'src/node_types.zi')]
for name in ['AppMessage', 'AppUiFrame', 'AppPerson', 'AppShared', 'AppSharedItem',
             'AppInvitation', 'AppSharedCommand', 'MediaEntry', 'MediaStatus']:
    command += ['--root', name]
for line in ['"std/bundle_host"', '"std/byte_text_linux"', '"kryon/hosted_values"',
             '"kryon/widget_codec"', '"kryon/session"', ', file "node_types.zi";']:
    command += ['--import', line]
sys.exit(subprocess.run(command + sys.argv[1:], cwd=ROOT).returncode)
