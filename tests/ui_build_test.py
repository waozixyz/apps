#!/usr/bin/env python3
"""A consumer compiler must run in its consumer graph, with a qualified entry."""
import json
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class ControllerBuildTest(unittest.TestCase):
    def test_consumer_graph_and_standalone_default(self):
        scratch = ROOT / 'build/ui-builder-test'
        subprocess.run(['git', 'check-ignore', '-q', str(scratch)], cwd=ROOT, check=True)
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as folder:
            consumer = Path(folder)
            (consumer / 'ziran.lock').write_text(json.dumps({
                'root': {'dependencies': {'apps': 'pconsumer'}},
                'packages': [{'id': 'pconsumer', 'name': 'Apps'}]}))
            compiler = consumer / 'selected-ziran'
            output = consumer / 'output'
            output.mkdir()
            # No compiler is executed in this forwarding regression. Actual
            # compiled format and native startup are covered by Shovey's UI test.
            def invoke(command, **kwargs):
                if 'bundle' in command:
                    (output / 'apps.zx').write_bytes(b'controller-test-output')
            for extra, cwd, entry, selected in [
                (['--project', str(consumer), '--compiler', str(compiler)],
                 consumer, 'pconsumer_apps:Main', compiler),
                ([], ROOT, 'apps:Main', ROOT / 'scripts/ziran.sh')]:
                with patch.object(sys, 'argv', ['build-ui', '--output', str(output), *extra]), \
                     patch('subprocess.run', side_effect=invoke) as calls:
                    runpy.run_path(str(ROOT / 'scripts/build-ui.py'), run_name='__main__')
                command = calls.call_args_list[-1].args[0]
                self.assertEqual(calls.call_args_list[-1].kwargs['cwd'], cwd)
                self.assertEqual(command[0], str(selected))
                self.assertEqual(command[command.index('--entry') + 1], entry)
                self.assertIn('--project', command)
                self.assertEqual((output / 'apps.sha256').read_text().strip(),
                                 json.loads((output / 'manifest.json').read_text())['sha256'])


if __name__ == '__main__':
    unittest.main()
