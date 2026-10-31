#!/usr/bin/env python3
"""Headless signed node catalog integration with real HTTP, ZX and Ed25519.

Run under build-queue; all generated fixtures and private cache stay in the
ignored work/remote-catalog directory. No external node, display or phone.
"""
import copy
import hashlib
import http.server
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
from urllib.parse import parse_qs, urlsplit

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import native_fixture as native

ROOT = native.ROOT
WORK = ROOT / 'work/remote-catalog'


def run(*args, **kwargs):
    subprocess.run(list(map(str, args)), cwd=ROOT, check=True, **kwargs)


def package(name):
    return Path(subprocess.check_output([native.ZIRAN, 'pkg', 'path', name,
                                        *native.LOCK_FLAGS], cwd=ROOT, text=True).strip())


def descriptor(key, payload, sequence=10, **changes):
    value = dict(app_id='inbe.arcade', sequence=sequence, version='1.0.0',
                 runtime='kryon-app-v1', host_api=41, module_api=1, data_schema=0,
                 key_id='fixture-2026', artifacts=[dict(variant='module',
                 sha256=hashlib.sha256(payload).hexdigest(), size=len(payload))], dependencies=[])
    value.update(changes)
    fields = ['daochi-zib-release-v2', *[str(value[k]) for k in
              ('app_id', 'sequence', 'version', 'runtime', 'host_api', 'module_api',
               'data_schema', 'key_id')], str(len(value['artifacts']))]
    for artifact in value['artifacts']:
        fields += [str(artifact[k]) for k in ('variant', 'sha256', 'size')]
    fields += [str(len(value['dependencies']))]
    for dependency in value['dependencies']:
        fields += [str(dependency[k]) for k in ('app_id', 'version', 'sha256', 'size')]
    value['signature'] = key.sign(('\n'.join(fields) + '\n').encode()).hex()
    return value


def compile_fixture(toolchain, runtime):
    # Both bundles are real portable programs, and both are executed by the
    # native behavioral test. The root's assets contain the real Apps schema.
    for name, result in [('leaf_fixture', 91), ('catalog_fixture', 73)]:
        (WORK / (name + '.zi')).write_text(
            f'#program_export\nMain :: () -> s32 {{ return {result} }}\n')
    leaf = WORK / 'leaf.zx'

    def bundle(name, output, assets=None):
        args = [native.ZIRAN, 'bundle', '--project', *native.LOCK_FLAGS,
                '--root', WORK, '--entry', name + ':Main', '-o', output]
        if assets:
            args += ['--asset-dir', 'assets=' + str(assets)]
        run(*args, WORK / (name + '.zi'))

    bundle('leaf_fixture', leaf)
    assets = WORK / 'assets'
    (assets / 'apps').mkdir(parents=True, exist_ok=True)
    shutil.copyfile(leaf, assets / 'leaf.zx')
    children = [dict(id='fixture.one', title='One', bundle='assets/leaf.zx', protocol='app/1',
                     expected_id='leaf', version='1', sha256=native.digest(leaf))]
    payloads = {}
    for name, count, identifier, schema in [('one', 1, 'inbe.arcade', 1),
                                           ('two', 2, 'inbe.arcade', 1),
                                           ('three', 2, 'inbe.arcade', 1),
                                           ('wrong-id', 2, 'other.collection', 1),
                                           ('wrong-schema', 2, 'inbe.arcade', 2)]:
        entries = copy.deepcopy(children)
        if count == 2:
            entries += [dict(entries[0], id='fixture.two', title='Two')]
        (assets / 'apps/catalog.json').write_text(json.dumps(dict(
            schema=schema, id=identifier, title=name, harness='assets/apps/apps.zx', children=entries)))
        output = WORK / (name + '.zx')
        bundle('catalog_fixture', output, assets)
        payloads[name] = output.read_bytes()
    output = WORK / 'c'
    run(native.ZIRAN, 'build', '--project', *native.LOCK_FLAGS, '--target=c', '--no-main',
        '--define', 'PLATFORM_DESKTOP', '--entry', 'remote_catalog_behavior:RemoteCheck',
        '--root', ROOT / 'tests', '-o', output, ROOT / 'tests/remote_catalog_behavior.zi')
    host = WORK / 'host.c'
    host.write_text(r'''#define _DEFAULT_SOURCE
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <time.h>
#include <unistd.h>
#include <openssl/evp.h>
#include "remote_catalog_behavior.h"
double TestNow(void) {
    struct timespec now;
    clock_gettime(CLOCK_MONOTONIC, &now);
    return (double)now.tv_sec + (double)now.tv_nsec / 1e9;
}
void TestYield(void) { usleep(1000); }
bool TestVerify(uint8_t *signature, uint8_t *public_key, uint8_t *message, size_t length) {
    EVP_PKEY *key = EVP_PKEY_new_raw_public_key(EVP_PKEY_ED25519, NULL, public_key, 32);
    EVP_MD_CTX *context = EVP_MD_CTX_new();
    bool valid = key && context && EVP_DigestVerifyInit(context, NULL, NULL, NULL, key) == 1 &&
        EVP_DigestVerify(context, signature, 64, message, length) == 1;
    EVP_MD_CTX_free(context);
    EVP_PKEY_free(key);
    return valid;
}
int main(void) {
    int result = RemoteCheck();
    if (result) fprintf(stderr, "Remote catalog behavior %d failed\n", result);
    return result ? 1 : 0;
}
''')
    includes = [arg for p in [output, *sorted(output.rglob('*'))] if p.is_dir()
                for arg in ('-iquote', str(p))]
    executable = WORK / 'test'
    run(os.environ.get('CC', 'cc'), '-std=c11', '-O1', '-ffunction-sections', '-fdata-sections',
        '-I' + str(toolchain / 'include'), *includes, *sorted(output.rglob('*.c')), host,
        runtime, '-Wl,--gc-sections', '-lcrypto', '-l:libcurl.so.4', '-lm', '-lpthread', '-o', executable)
    return executable, payloads


def main():
    if len(sys.argv) != 2:
        raise SystemExit('Pass exact package libziran.a; run through build-queue')
    for key in ('DISPLAY', 'WAYLAND_DISPLAY', 'XAUTHORITY', 'DBUS_SESSION_BUS_ADDRESS',
                'SESSION_MANAGER', 'DESKTOP_SESSION', 'XDG_SESSION_ID', 'XDG_SESSION_TYPE'):
        os.environ.pop(key, None)
    os.environ.update(YUE_DESKTOP_RECOVERY='0', ZIRAN_PAR_THREADS='1', NO_PROXY='127.0.0.1',
                      no_proxy='127.0.0.1')
    run('git', 'check-ignore', 'work/remote-catalog/data')
    WORK.mkdir(parents=True, exist_ok=True)
    toolchain = package('ziran')
    runtime = Path(sys.argv[1]).resolve()
    exact_runtime = (toolchain / 'build/libziran.a').resolve()
    if runtime != exact_runtime:
        raise SystemExit(f'Runtime must match resolved package compiler: {exact_runtime}; got {runtime}')
    print(f'Resolved compiler: {toolchain / "build/bin/zi2c"}; runtime: {runtime}', flush=True)
    executable, payloads = compile_fixture(toolchain, runtime)
    host_digest = native.digest(executable)
    data = WORK / 'data'
    if data.exists():
        shutil.rmtree(data)
    data.mkdir()
    key = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
    public = key.public_key().public_bytes(serialization.Encoding.Raw,
                                           serialization.PublicFormat.Raw).hex()
    state = dict(metadata=None, payload=b'', calls=[], hold=None, errors=[])
    received, release, sent = [WORK / name for name in ('received', 'release', 'sent')]

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlsplit(self.path)
            state['calls'].append((parsed.path, parse_qs(parsed.query)))
            if self.headers.get('Authorization') or self.headers.get('Cookie'):
                state['errors'].append('Unexpected account credentials')
            if self.headers.get('Cache-Control'):
                state['errors'].append('Custom cache header would trigger browser preflight')
            if self.headers.get('User-Agent') != 'Kryon-Apps/1.0':
                state['errors'].append('Native publisher endpoint requires Apps User-Agent')
            latest = parsed.path == '/api/v2/packages/inbe.arcade/latest'
            expected = '/api/v2/packages/inbe.arcade/' + state['metadata']['artifacts'][0]['sha256'] + '.zx'
            if not latest and parsed.path != expected:
                state['errors'].append('Unexpected artifact path: ' + parsed.path)
                self.send_error(404)
                return
            if latest and parse_qs(parsed.query) != dict(host_api=['41'], module_api=['1'],
                                                       bucket=['99'], format=['zx']):
                state['errors'].append('Wrong compatibility query')
            response = json.dumps(state['metadata']).encode() if latest else state['payload']
            if state['hold'] == ('metadata' if latest else 'payload'):
                received.write_text('received')
                deadline = time.monotonic() + 10
                while not release.exists() and time.monotonic() < deadline:
                    time.sleep(0.002)
                if not release.exists():
                    state['errors'].append('Cancellation did not release held response')
            try:
                self.send_response(200)
                self.send_header('Content-Length', str(len(response)))
                self.end_headers()
                self.wfile.write(response)
            except (BrokenPipeError, ConnectionResetError):
                pass  # A real revoked transfer may close before the reply.
            finally:
                if state['hold'] == ('metadata' if latest else 'payload'):
                    sent.write_text('sent')

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    origin = f'http://127.0.0.1:{server.server_port}'
    passed = []

    def case(name, metadata, payload, mode='reject', baseline=None, expected='two', ready=True,
             calls=1, floor='0', hold=None, mutate_cache=None):
        cache = data / name
        if baseline:
            shutil.copytree(baseline, cache)
        else:
            cache.mkdir()
        if mutate_cache:
            mutate_cache(cache)
        for marker in (received, release, sent):
            marker.unlink(missing_ok=True)
        state.update(metadata=metadata, payload=payload, calls=[], hold=hold, errors=[])
        before = {p.name: p.read_bytes() for p in cache.glob('*') if p.name != '.lock'}
        env = dict(os.environ, APPS_REMOTE_ORIGIN=origin, APPS_REMOTE_KEY=public,
                   APPS_REMOTE_CACHE=str(cache), APPS_REMOTE_MODE=mode,
                   APPS_REMOTE_BASE_READY='yes' if ready else 'no', APPS_REMOTE_FLOOR=floor,
                   APPS_REMOTE_HASH=hashlib.sha256(payloads[expected]).hexdigest(),
                   APPS_REMOTE_CHILDREN='1' if expected == 'one' else '2',
                   APPS_REMOTE_RECEIVED=str(received), APPS_REMOTE_RELEASE=str(release),
                   APPS_REMOTE_SENT=str(sent))
        with (WORK / 'run.log').open('a') as log:
            log.write(name + '\n')
            log.flush()
            result = subprocess.run([executable], cwd=ROOT, env=env, stdout=log,
                                    stderr=log, timeout=30)
        if result.returncode:
            with (WORK / 'run.log').open('rb') as log:
                log.seek(0, 2)
                log.seek(max(0, log.tell() - 3000))
                print(log.read().decode(errors='replace'))
            raise AssertionError(name + ': native test failed')
        assert not state['errors'], (name, state['errors'])
        assert len(state['calls']) == calls, (name, state['calls'])
        if mode in ('reject', 'revoke', 'restore', 'offline', 'no-consent', 'empty-reject'):
            after = {p.name: p.read_bytes() for p in cache.glob('*')
                     if p.name not in ('.lock', 'node-connection') and not p.name.endswith('.zx')}
            # Restore may retain previous.json; neither rejection nor revoke may
            # rewrite the current signed descriptor or immutable cached bundle.
            assert after.get('current.json') == before.get('current.json'), name
            for filename, value in before.items():
                if filename.endswith('.zx'):
                    assert (cache / filename).read_bytes() == value, name
        if mode in ('accept', 'same'):
            assert json.loads((cache / 'current.json').read_text()) == metadata, name
            retained = {p.stem for p in cache.glob('*.zx') if len(p.stem) == 64}
            expected_hashes = {metadata['artifacts'][0]['sha256']}
            if (cache / 'previous.json').exists():
                expected_hashes.add(json.loads((cache / 'previous.json').read_text())['artifacts'][0]['sha256'])
            assert retained == expected_hashes, name + ': catalog snapshots accumulated or fallback lost'
        for filename in ('keep.zx', 'notes.txt'):
            if filename in before:
                assert (cache / filename).read_bytes() == before[filename], name
        passed.append(name)
        print('PASS ' + name, flush=True)
        return cache

    one, two = payloads['one'], payloads['two']
    first = descriptor(key, one)
    good = descriptor(key, two, 11)
    try:
        case('no-network-before-consent', first, one, 'no-consent', ready=False, calls=0)
        initial = case('initial-signed-catalog', first, one, 'accept', expected='one', ready=False, calls=2)
        baseline = case('refresh-without-host-rebuild', good, two, 'accept', baseline=initial, calls=2)
        def corrupt_signature(cache):
            value = json.loads((cache / 'current.json').read_text())
            value['signature'] = '00' * 64
            (cache / 'current.json').write_text(json.dumps(value))

        def corrupt_payload(cache):
            path = cache / (hashlib.sha256(two).hexdigest() + '.zx')
            value = path.read_bytes()
            path.write_bytes(value[:-1] + bytes([value[-1] ^ 1]))

        case('cached-invalid-signature', good, two, 'no-consent', baseline=baseline,
             ready=False, calls=0, mutate_cache=corrupt_signature)
        case('cached-invalid-payload', good, two, 'no-consent', baseline=baseline,
             ready=False, calls=0, mutate_cache=corrupt_payload)
        case('restore-previous-root', good, two, 'restore', baseline=initial, calls=2)
        same = descriptor(key, two, 12)
        newer = case('same-payload-sequence-advance', same, two, 'same', baseline=baseline)
        bad = dict(descriptor(key, one, 13), signature='00' * 64)
        case('wrong-signature', bad, one, baseline=baseline)
        stranger = Ed25519PrivateKey.from_private_bytes(bytes(reversed(range(32))))
        case('wrong-public-key', descriptor(stranger, one, 13), one, baseline=baseline)
        for name, changes in [
            ('wrong-key-id', dict(key_id='different-key')),
            ('wrong-release-id', dict(app_id='other.collection')),
            ('wrong-runtime', dict(runtime='other-runtime')),
            ('host-too-new', dict(host_api=42)), ('host-too-old', dict(host_api=8)),
            ('wrong-module-api', dict(module_api=2)), ('wrong-data-schema', dict(data_schema=1)),
            ('unexpected-dependency', dict(dependencies=[dict(app_id='other.app', version='1.0.0',
                sha256='a' * 64, size=10)])),
        ]:
            case(name, descriptor(key, one, 13, **changes), one, baseline=baseline)
        case('rollback', first, one, baseline=baseline)
        case('rollback-after-sequence-only-refresh', good, two, baseline=newer)
        case('same-sequence-different-hash', descriptor(key, one, 11), one, baseline=baseline)
        wrong_size = descriptor(key, two, 13, artifacts=[dict(variant='module',
            sha256=hashlib.sha256(two).hexdigest(), size=len(two) + 1)])
        case('same-hash-wrong-declared-size', wrong_size, two, baseline=baseline)
        case('minimum-sequence-floor', descriptor(key, one, 19), one, 'empty-reject',
             baseline=baseline, ready=False, floor='20')
        case('wrong-hash', descriptor(key, one, 13), bytes([one[0] ^ 1]) + one[1:],
             baseline=baseline, calls=2)
        case('truncated-size', descriptor(key, one, 13), one[:-1], baseline=baseline, calls=2)
        case('excess-size', descriptor(key, one, 13), one + b'x', baseline=baseline, calls=2)
        oversized = descriptor(key, one, 13, artifacts=[dict(variant='module', sha256='a' * 64, size=262145)])
        case('collection-size-limit', oversized, one, baseline=baseline)
        case('metadata-size-limit', dict(descriptor(key, one, 13), padding='x' * 65536),
             one, baseline=baseline)
        for name in ('wrong-id', 'wrong-schema'):
            payload = payloads[name]
            case('catalog-' + name, descriptor(key, payload, 13), payload, baseline=baseline, calls=2)
        payload = b'not a ZX collection'
        case('invalid-zx', descriptor(key, payload, 13), payload, baseline=baseline, calls=2)
        def unrelated_files(cache):
            (cache / 'keep.zx').write_bytes(b'not a managed snapshot')
            (cache / 'notes.txt').write_text('preserve unrelated cache files')

        third = case('third-refresh-bounded-cache', descriptor(key, payloads['three'], 13),
                     payloads['three'], 'accept', baseline=baseline, expected='three', calls=2,
                     mutate_cache=unrelated_files)
        case('fourth-refresh-bounded-cache', descriptor(key, one, 14), one, 'accept',
             baseline=third, expected='one', calls=2)
        case('revoke-during-metadata', descriptor(key, one, 13), one, 'revoke',
             baseline=baseline, hold='metadata')
        case('revoke-during-payload', descriptor(key, one, 13), one, 'revoke',
             baseline=baseline, calls=2, hold='payload')
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    # The listener is now gone. Opening, validating and executing cache must
    # still succeed with the remembered node unreachable and consent unset.
    case('cached-offline-launch', good, two, 'offline', baseline=baseline, calls=0)
    assert native.digest(executable) == host_digest, 'Native host changed during refresh'
    print(f'Apps remote catalog: {len(passed)} signed loopback cases passed; '
          'origin-bound consent exercised in every native process. No APK, display or phone used.')


if __name__ == '__main__':
    main()
