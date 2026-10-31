#!/usr/bin/env python3
"""Apps authorized document adapter: real portable guests and optional IDBFS."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import native_fixture as native
ROOT = native.ROOT
WORK = ROOT / 'work/document-host'
ZIRAN = native.ZIRAN

def run(*args):
    subprocess.run(list(map(str, args)), cwd=ROOT, check=True)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('runtime', type=Path)
    parser.add_argument('--browser-runtime', type=Path)
    args = parser.parse_args()
    for key in ('DISPLAY', 'WAYLAND_DISPLAY', 'XAUTHORITY', 'DBUS_SESSION_BUS_ADDRESS',
                'SESSION_MANAGER', 'DESKTOP_SESSION', 'XDG_SESSION_ID', 'XDG_SESSION_TYPE'):
        os.environ.pop(key, None)
    os.environ.update(MAKEFLAGS='-j1', CMAKE_BUILD_PARALLEL_LEVEL='1', EMCC_CORES='1',
                      ZIRAN_PAR_THREADS='1', YUE_DESKTOP_RECOVERY='0')
    if hasattr(os, 'sched_getaffinity'):
        os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    run('git', 'check-ignore', 'work/document-host/data')
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / 'root.txt').write_text(str(WORK / 'data'))
    for name in ('context', 'node'):
        assets = WORK / name / 'assets/document'
        assets.mkdir(parents=True, exist_ok=True)
        (assets / 'catalog.json').write_text(json.dumps(dict(id='fixture.document', name='document',
            contract_version=1, module_api=2, host_api=12, save_schema=1)))
        path = WORK / (name + '.zx')
        defines = ['--define', 'APPS_DOCUMENT_NODE'] if name == 'node' else []
        run(ZIRAN, 'bundle', '--project', *native.LOCK_FLAGS, '--root', ROOT / 'fixtures',
            '--entry', 'document_guest:Main', *defines,
            '--asset-dir', 'assets=' + str(assets.parent), '-o', path, ROOT / 'fixtures/document_guest.zi')
        (WORK / (name + '.sha256')).write_text(hashlib.sha256(path.read_bytes()).hexdigest())
    toolchain = Path(subprocess.check_output([ZIRAN, 'pkg', 'path', 'ziran'], cwd=ROOT, text=True).strip())
    kryon = Path(subprocess.check_output([ZIRAN, 'pkg', 'path', 'kryon'], cwd=ROOT, text=True).strip())
    mapping = WORK / 'module-map.tsv'
    lines = (ROOT / 'build/.ziran/module-map.tsv').read_text().splitlines()
    lines += ['M\troot\t' + name + '\t' + str(ROOT / 'tests' / (name + '.zi'))
              for name in ('document_host_behavior', 'native_behavior')]
    mapping.write_text('\n'.join(lines) + '\n')
    os.environ['ZIRAN_PACKAGE_MAP'] = str(mapping)
    for web in ([False, True] if args.browser_runtime else [False]):
        output = WORK / 'c'
        defines = ['--define', 'PLATFORM_WEB'] if web else []
        run(toolchain / 'build/bin/zi2c', '--prune-stale', '--module-path', toolchain / 'std', '--no-main',
            '--entry', 'document_host_behavior:DocumentCheck', *defines, '--root', ROOT / 'tests',
            '-o', output, ROOT / 'tests/document_host_behavior.zi')
        (output / 'entry.c').write_text('#include <stdio.h>\n#include "document_host_behavior.h"\n'
            'int main(void) { int r=DocumentCheck(); if(r) fprintf(stderr,"Apps document test %d failed\\n",r); return r; }\n')
        includes = [arg for p in [output, *sorted(output.rglob('*'))] if p.is_dir() for arg in ('-iquote', str(p))]
        flags = ['-std=c11', '-O1', '-ffunction-sections', '-fdata-sections',
            '-I' + str(toolchain / 'include'), *includes, *sorted(output.rglob('*.c'))]
        if not web:
            run(os.environ.get('CC', 'cc'), *flags, args.runtime, '-Wl,--gc-sections', '-lm', '-lpthread', '-o', WORK / 'test')
            run(WORK / 'test')
        else:
            emcc = os.environ.get('EMCC') or shutil.which('emcc') or str(Path.home() / 'emsdk/upstream/emscripten/emcc')
            os.environ['EM_CACHE'] = str(WORK / 'emscripten-cache')
            shell = WORK / 'shell.html'
            shell.write_text('''<!doctype html><meta charset="utf-8"><pre id="result">pending</pre><script>
var storageTestMode=Number(new URLSearchParams(location.search).get('reload')||0);
var Module={preRun:[()=>{if(storageTestMode===2) indexedDB.open=()=>{throw new Error('IDB unavailable')};const sync=FS.syncfs;FS.syncfs=(p,cb)=>sync(p,e=>setTimeout(()=>cb(e),40));}],onExit:c=>document.getElementById('result').textContent=c?'FAIL '+c:'PASS',onAbort:e=>document.getElementById('result').textContent='ABORT '+e};
</script>{{{ SCRIPT }}}''')
            run(emcc, *flags, args.browser_runtime, '--js-library', toolchain / 'web/ziran_web.js',
                '-lidbfs.js', '-sASYNCIFY', '-sSTACK_SIZE=16777216', '-sASYNCIFY_STACK_SIZE=1048576',
                '-sASSERTIONS=1', '-sALLOW_MEMORY_GROWTH=1', '-sINITIAL_MEMORY=134217728',
                '-sSINGLE_FILE=1', '-sEXIT_RUNTIME=1', '-sEXPORTED_RUNTIME_METHODS=FS', '-sENVIRONMENT=web',
                '--embed-file', str(WORK / 'context.zx') + '@work/document-host/context.zx',
                '--embed-file', str(WORK / 'node.zx') + '@work/document-host/node.zx',
                '--embed-file', str(WORK / 'context.sha256') + '@work/document-host/context.sha256',
                '--embed-file', str(WORK / 'node.sha256') + '@work/document-host/node.sha256',
                '--shell-file', shell, '-o', WORK / 'test.html')
            profile = WORK / 'browser-profile'
            shutil.rmtree(profile, ignore_errors=True)
            run('node', kryon / 'tests/document_storage_test.mjs', (WORK / 'test.html').as_uri(), profile)
        print('Apps document adapter: ' + ('browser IDBFS' if web else 'native') + ' portable guests passed', flush=True)
if __name__ == '__main__':
    main()
