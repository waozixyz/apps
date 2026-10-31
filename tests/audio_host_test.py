"""Apps' real node/2 + app/1 audio boundary, dummy and actual null-device hosts."""
import json
import os
from pathlib import Path
import subprocess
import sys
import wave

import native_fixture as native

ROOT = native.ROOT
WORK = ROOT / 'work/audio-host-adoption'
ZIRAN = native.ZIRAN


def run(*args, env=None):
    subprocess.run(list(map(str, args)), cwd=ROOT, env=env, check=True)


def main():
    if len(sys.argv) != 2:
        raise SystemExit('Pass exact libziran.a')
    for key in ('DISPLAY', 'WAYLAND_DISPLAY', 'XAUTHORITY', 'DBUS_SESSION_BUS_ADDRESS',
                'SESSION_MANAGER', 'DESKTOP_SESSION', 'XDG_SESSION_ID', 'XDG_SESSION_TYPE',
                'PIPEWIRE_REMOTE', 'PIPEWIRE_RUNTIME_DIR'):
        os.environ.pop(key, None)
    run('git', 'check-ignore', 'work/audio-host-adoption/tone.wav')
    WORK.mkdir(parents=True, exist_ok=True)
    native.WORK = WORK
    controller = WORK / 'ui/apps.zx'
    run(sys.executable, ROOT / 'scripts/build-ui.py', '--output', controller.parent)
    os.environ['APPS_FIXTURE_HARNESS_SHA256'] = native.digest(controller)
    paths = {}
    for kind, identifier in [('NODE', 'fixture.audio'), ('CHILD', 'fixture.audio.child'),
                             ('DONOR', 'fixture.audio.donor'), ('CONTEXT', 'fixture.context')]:
        assets = WORK / kind.lower() / 'assets/audio'
        assets.mkdir(parents=True, exist_ok=True)
        (assets / 'catalog.json').write_text(json.dumps(dict(id=identifier, name='audio',
            contract_version=1, module_api=2, host_api=12, save_schema=1)))
        with wave.open(str(assets / 'tone.wav'), 'wb') as output:
            output.setnchannels(1); output.setsampwidth(2); output.setframerate(8000)
            output.writeframes(bytes(16000))
        if kind == 'NODE':
            with (assets / 'large.wav').open('wb') as output:
                output.truncate(8388609)
        path = WORK / (kind.lower() + '.zx')
        source = 'audio_context' if kind == 'CONTEXT' else 'audio_node'
        args = [ZIRAN, 'bundle', '--project', '--locked', '--offline', '--root', ROOT / 'fixtures',
                '--entry', source + ':Main', '--define', 'KRYON_HOSTED_UI',
                '--asset-dir', 'assets=' + str(assets.parent), '-o', path]
        if kind == 'CONTEXT':
            args += ['--define', 'APPS_AUDIO_CONTEXT_FIXTURE']
        run(*args, ROOT / 'fixtures' / (source + '.zi'))
        paths[kind] = path
    paths['LIBRARY'] = WORK / 'library.zx'
    native.bundle('counter', paths['LIBRARY'], WORK / 'node/assets')
    paths['THIN'] = WORK / 'thin.zx'
    native.bundle('counter_addon', paths['THIN'], library=paths['LIBRARY'])
    donor = native.child('fixture.audio.donor', paths['DONOR'], 'node/2', 'audio', 'assets/donor.zx')
    child = native.child('fixture.audio.child', paths['CHILD'], 'node/2', 'audio', 'assets/child.zx')
    child.update(dependencies=['fixture.audio.donor'], resources=[dict(dependency='fixture.audio.donor',
        path='assets/audio/shared.wav', source='assets/audio/tone.wav')])
    paths['ROOT'] = WORK / 'root.zx'
    native.bundle('collection', paths['ROOT'], native.stage('root-stage', 'fixture.audio.root',
        [donor, child], {'assets/donor.zx': paths['DONOR'], 'assets/child.zx': paths['CHILD']}, controller))
    for kind, path in paths.items():
        os.environ['APPS_AUDIO_' + kind + '_BUNDLE'] = str(path)
        os.environ['APPS_AUDIO_' + kind + '_SHA256'] = native.digest(path)
    toolchain = Path(subprocess.check_output([ZIRAN, 'pkg', 'path', 'ziran'], cwd=ROOT, text=True).strip())
    kryon = Path(subprocess.check_output([ZIRAN, 'pkg', 'path', 'kryon'], cwd=ROOT, text=True).strip())
    raylib = Path(os.environ['RAYLIB_A'])
    # Use Raylib's actual decoder/mixer with miniaudio's paced null backend.
    # ALSA null consumes without pacing and cannot verify a playback clock.
    audio_source = raylib.parent / 'source/raudio.c'
    null_audio = WORK / 'null-audio.o'
    run(os.environ.get('CC', 'cc'), '-O1', '-ffunction-sections', '-fdata-sections',
        '-DMA_ENABLE_ONLY_SPECIFIC_BACKENDS', '-DMA_ENABLE_NULL',
        '-I' + str(audio_source.parent), '-c', audio_source, '-o', null_audio)
    # Like consumer_test.py, extend the actual resolved package map only for
    # test entry modules outside the package's published module roots.
    mapping = WORK / 'module-map.tsv'
    lines = (ROOT / 'build/.ziran/module-map.tsv').read_text().splitlines()
    lines += ['M\troot\t' + name + '\t' + str(ROOT / 'tests' / (name + '.zi'))
              for name in ('audio_host_behavior', 'native_behavior')]
    mapping.write_text('\n'.join(lines) + '\n')
    os.environ['ZIRAN_PACKAGE_MAP'] = str(mapping)
    for actual in (False, True):
        output = WORK / 'c'
        defines = ['--define', 'APPS_AUDIO_NATIVE_TEST'] if actual else []
        run(toolchain / 'build/bin/zi2c', '--prune-stale', '--no-main',
            '--module-path', toolchain / 'std',
            '--entry', 'audio_host_behavior:AudioCheck', *defines,
            '--root', ROOT / 'tests', '-o', output, ROOT / 'tests/audio_host_behavior.zi', ROOT / 'tests/native_behavior.zi')
        (output / 'entry.c').write_text('#include <stdio.h>\n#include "audio_host_behavior.h"\n'
            'int main(void) { int r=AudioCheck(); if(r) fprintf(stderr,"Apps audio test %d failed\\n",r); return r?1:0; }\n')
        includes = [arg for p in [output, *sorted(output.rglob('*'))] if p.is_dir() for arg in ('-iquote', str(p))]
        libs = []
        if actual:
            libs = [str(null_audio), str(raylib), *subprocess.check_output(['pkg-config', '--libs', 'sdl2', 'libdrm', 'gbm', 'egl', 'glesv2'], text=True).split(), '-ldl']
        executable = WORK / 'test'
        run(os.environ.get('CC', 'cc'), '-std=c11', '-O1', '-ffunction-sections', '-fdata-sections',
            '-I' + str(toolchain / 'include'), *includes, *sorted(output.rglob('*.c')),
            ROOT / 'tests/preparation_host.c', sys.argv[1], *libs,
            '-Wl,--gc-sections', '-Wl,--wrap=BundleOpenBytes', '-Wl,--wrap=BundleOpenBytesWithLibraries',
            '-Wl,--wrap=BundleInstantiate', '-Wl,--wrap=BundleInstanceRun', '-Wl,--wrap=BundleClose',
            '-lm', '-lpthread', '-o', executable)
        config = WORK / 'alsa.conf'
        config.write_text('pcm.!default { type null }\nctl.!default { type null }\n')
        env = dict(os.environ, ALSA_CONFIG_PATH=str(config), SDL_AUDIODRIVER='dummy',
            PULSE_SERVER='unix:' + str(WORK / 'no-pulse'), JACK_DEFAULT_SERVER='apps-test-no-server',
            JACK_NO_START_SERVER='1', YUE_DESKTOP_RECOVERY='0')
        result = subprocess.run([str(executable)], cwd=ROOT, env=env, text=True, capture_output=True, timeout=90)
        (WORK / ('native.log' if actual else 'dummy.log')).write_text(result.stdout + result.stderr)
        if result.returncode:
            print((result.stdout + result.stderr)[-6000:])
            result.check_returncode()
        print('Apps audio: ' + ('actual Raylib/null device' if actual else 'dummy/no provider') + ' passed')
    print('Apps audio package: ' + str(kryon))


if __name__ == '__main__':
    main()
