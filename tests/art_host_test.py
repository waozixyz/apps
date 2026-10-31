#!/usr/bin/env python3
"""Real failed HTTP transfer -> Apps retry -> drawable pixels, without a display."""
import http.server
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time

import native_fixture as native

ROOT = native.ROOT
WORK = ROOT / 'work/art-host'

def run(*args):
    subprocess.run(list(map(str, args)), cwd=ROOT, check=True)


def main():
    if len(sys.argv) != 2:
        raise SystemExit('Pass exact libziran.a')
    for key in ('DISPLAY', 'WAYLAND_DISPLAY', 'XAUTHORITY', 'DBUS_SESSION_BUS_ADDRESS',
                'SESSION_MANAGER', 'DESKTOP_SESSION', 'XDG_SESSION_ID', 'XDG_SESSION_TYPE'):
        os.environ.pop(key, None)
    os.environ.update(YUE_DESKTOP_RECOVERY='0', ZIRAN_PAR_THREADS='1')
    run('git', 'check-ignore', 'work/art-host/data')
    WORK.mkdir(parents=True, exist_ok=True)
    native.WORK = WORK
    controller = WORK / 'ui/apps.zx'
    run(sys.executable, ROOT / 'scripts/build-ui.py', '--output', controller.parent)
    leaf, art, root = [WORK / (name + '.zx') for name in ('leaf', 'art', 'root')]
    native.bundle('counter', leaf)
    assets = native.stage('stage', 'fixture.slim',
                          [native.child('fixture.counter', leaf, 'app/1', 'counter')],
                          {'assets/child.zx': leaf}, controller)
    art_assets = WORK / 'art-stage/assets'
    art_assets.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(assets / 'preview.png', art_assets / 'preview.png')
    native.bundle('collection', art, art_assets)
    catalog = assets / 'apps/catalog.json'
    value = json.loads(catalog.read_text())
    value['art'] = dict(sha256=native.digest(art), bytes=art.stat().st_size)
    catalog.write_text(json.dumps(value))
    (assets / 'preview.png').unlink()
    (assets / 'apps/apps.zx').unlink()
    native.bundle('collection', root, assets)
    toolchain, kryon, raylib = [Path(subprocess.check_output(
        [native.ZIRAN, 'pkg', 'path', name], cwd=ROOT, text=True).strip())
        for name in ('ziran', 'kryon', 'raylib')]
    mapping = WORK / 'module-map.tsv'
    lines = (ROOT / 'build/.ziran/module-map.tsv').read_text().splitlines()
    lines += ['M\troot\tnative_behavior\t' + str(ROOT / 'tests/native_behavior.zi'),
              'M\troot\tart_host_behavior\t' + str(ROOT / 'tests/art_host_behavior.zi'),
              'D\troot\tart_decode\t' + kryon.name + '\traylib_image_decode']
    mapping.write_text('\n'.join(lines) + '\n')
    os.environ['ZIRAN_PACKAGE_MAP'] = str(mapping)
    output = WORK / 'c'
    run(toolchain / 'build/bin/zi2c', '--prune-stale', '--no-main', '--module-path', toolchain / 'std',
        '--define', 'PLATFORM_DESKTOP', '--entry', 'art_host_behavior:ArtCheck', '--root', ROOT / 'tests', '-o', output,
        ROOT / 'tests/art_host_behavior.zi')
    (output / 'entry.c').write_text('#include <stdio.h>\n#include "art_host_behavior.h"\n'
        'int main(void) { int r=ArtCheck(); if(r) fprintf(stderr,"Apps art test %d failed\\n",r); return r?1:0; }\n')
    includes = [arg for p in [output, *sorted(output.rglob('*'))] if p.is_dir() for arg in ('-iquote', str(p))]
    cc = os.environ.get('CC', 'cc')
    # Only Raylib's CPU image decoder is linked; no window or graphics context exists.
    support = WORK / 'raylib_support.c'
    support.write_text('#include <stdlib.h>\n'
        'void TraceLog(int level, const char *text, ...) { (void)level; (void)text; }\n'
        'void *MemAlloc(unsigned int size) { return calloc(size, 1); }\n'
        'void *MemRealloc(void *data, unsigned int size) { return realloc(data, size); }\n'
        'void MemFree(void *data) { free(data); }\n'
        'const char *rlGetPixelFormatName(unsigned int format) { (void)format; return ""; }\n')
    decoder = WORK / 'rtextures.o'
    run(cc, '-O1', '-ffunction-sections', '-fdata-sections', '-I' + str(raylib / 'src'),
        '-c', raylib / 'src/rtextures.c', '-o', decoder)
    executable = WORK / 'test'
    run(cc, '-std=c11', '-O1', '-ffunction-sections', '-fdata-sections',
        '-I' + str(toolchain / 'include'), *includes, *sorted(output.rglob('*.c')),
        ROOT / 'tests/preparation_host.c', support, sys.argv[1], decoder,
        '-Wl,--gc-sections', '-Wl,--wrap=BundleOpenBytes', '-Wl,--wrap=BundleOpenBytesWithLibraries',
        '-Wl,--wrap=BundleInstantiate', '-Wl,--wrap=BundleInstanceRun', '-Wl,--wrap=BundleClose',
        '-lm', '-lpthread', '-o', executable)
    class Handler(http.server.BaseHTTPRequestHandler):
        calls = 0
        def do_GET(self):
            type(self).calls += 1
            # Hold the first response so repeated asset accesses see Downloading.
            if self.calls == 1:
                time.sleep(0.15)
                self.send_error(503)
                return
            self.send_response(200)
            self.send_header('Content-Length', str(art.stat().st_size))
            self.end_headers()
            with art.open('rb') as stream:
                shutil.copyfileobj(stream, self.wfile)
        def log_message(self, *args):
            pass
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    env = dict(os.environ, APPS_ART_URL=f'http://127.0.0.1:{server.server_port}/art.zx',
               APPS_ART_DESTINATION=str(WORK / 'download.zx'),
               APPS_FIXTURE_SLIM_ROOT_BUNDLE=str(root), APPS_FIXTURE_SLIM_ROOT_SHA256=native.digest(root),
               APPS_FIXTURE_UI_BUNDLE=str(controller), APPS_FIXTURE_HARNESS_SHA256=native.digest(controller))
    try:
        result = subprocess.run([executable], cwd=ROOT, env=env, capture_output=True, text=True, timeout=60)
        (WORK / 'run.log').write_text(result.stdout + result.stderr)
        if result.returncode:
            print((result.stdout + result.stderr)[-4000:])
            result.check_returncode()
        assert Handler.calls == 2, Handler.calls
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    print('Apps art: rejected dispatch/reply, paced retry, real HTTP 503 -> retry -> decoded RGB pixels, hash/size rejection with paced recovery and cached offline art passed')


if __name__ == '__main__':
    main()
