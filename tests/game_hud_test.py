#!/usr/bin/env python3
"""Display-free native tree and portable/hosted shared HUD contract tests.

Run through build-queue; all compiler/linker children inherit its single slot.
"""
from pathlib import Path
import os
import subprocess
import sys
import tomllib
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'work/game-hud'
ZIRAN = ROOT / 'scripts/ziran.sh'

def run(*args):
    return subprocess.run(list(map(str, args)), cwd=ROOT, check=True,
                          text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout

def main():
    sys.stdout.reconfigure(line_buffering=True)
    for name in ('DISPLAY', 'WAYLAND_DISPLAY', 'XAUTHORITY', 'DBUS_SESSION_BUS_ADDRESS',
                 'SESSION_MANAGER', 'DESKTOP_SESSION', 'XDG_SESSION_ID', 'XDG_SESSION_TYPE'):
        os.environ.pop(name, None)
    os.environ.update(YUE_DESKTOP_RECOVERY='0', ZIRAN_PAR_THREADS='1', ZIRAN_JOBS='2')
    run('git', 'check-ignore', 'work/game-hud/test')
    WORK.mkdir(parents=True, exist_ok=True)
    scratch = WORK / 'runtime'
    scratch.mkdir(exist_ok=True)
    os.environ.update(TMPDIR=str(scratch), ZIRAN_NATIVE_DIR=str(scratch), ZIRAN_NATIVE_CACHE='0')
    assert tomllib.loads((ROOT / 'ziran.toml').read_text())['exports']['game_hud'] == 'src/game_hud.zi'
    for name in ('profile', 'dew'):
        with Image.open(ROOT / f'assets/hud/{name}.webp') as image:
            assert image.format == 'WEBP' and max(image.size) <= 256
            assert image.mode == 'RGBA' and image.getextrema()[3][0] == 0
    run('python3', ROOT / 'scripts/generate-ui-locales.py', '--check')
    flags = [] if (ROOT / 'ziran.local.toml').exists() else ['--locked']
    # Keep test-only modules outside the public package roots.
    toolchain = Path(run(ZIRAN, 'pkg', 'path', 'ziran').strip())
    compiler = toolchain / 'build/bin/ziran'
    run(ZIRAN, 'check', '--project', *flags, ROOT / 'src/game_hud.zi')
    lines = (ROOT / 'build/.ziran/module-map.tsv').read_text().splitlines()
    for module in ('game_hud_behavior', 'game_hud_host', 'game_hud_hosted'):
        lines.append(f'M\troot\t{module}\t{ROOT / "tests" / (module + ".zi")}')
    mapping = WORK / 'module-map.tsv'
    mapping.write_text('\n'.join(lines) + '\n')
    os.environ['ZIRAN_PACKAGE_MAP'] = str(mapping)
    output = WORK / 'native'
    run(toolchain / 'build/bin/zi2c', '--prune-stale', '--no-main', '--module-path', toolchain / 'std',
        '--entry', 'game_hud_behavior:Check', '--root', ROOT / 'tests', '-o', output,
        ROOT / 'tests/game_hud_behavior.zi')
    (output / 'entry.c').write_text('#include "game_hud_behavior.h"\nint main(void) { return Check(); }\n')
    includes = [arg for path in [output, *sorted(output.rglob('*'))] if path.is_dir()
                for arg in ('-iquote', str(path))]
    run(os.environ.get('CC', 'cc'), '-std=c11', '-O1', '-ffunction-sections', '-fdata-sections',
        '-I' + str(toolchain / 'include'), *includes, *sorted(output.rglob('*.c')),
        toolchain / 'build/libziran.a', '-Wl,--gc-sections', '-lm', '-lpthread',
        '-o', output / 'game_hud_behavior')
    run(WORK / 'native/game_hud_behavior')
    print('PASS native: tree semantics, both action results, consumption, 320 narrow/offset bounds and empty bounds')
    bindings = {
        'font_metrics:MeasureGlyphWidth': 'MeasureGlyphWidth',
        'font_metrics:MeasureGlyphLineHeight': 'MeasureGlyphLineHeight',
        'image_raster:ImageWidth': 'ImageWidth', 'image_raster:ImageHeight': 'ImageHeight',
        'raster_text:RasterText': 'RasterText', 'raster_text:RasterTextClipped': 'RasterTextClipped',
        'raster_shape:RasterRoundedRectangle': 'RasterRoundedRectangle',
        'raster_shape:RasterRoundedRectangleOutline': 'RasterRoundedRectangleOutline',
        'raster:RasterLine': 'RasterLine', 'paint_queue:RasterImage': 'RasterImage',
        'paint_queue:RasterImageMesh': 'RasterImageMesh',
    }
    args = [arg for source, target in bindings.items() for arg in
            ('--bind', f'kryon/{source}=game_hud_host:{target}')]
    bundle = WORK / 'tree.zx'
    run(toolchain / 'build/bin/zi2zx', 'bundle', '--module-path', toolchain / 'std', '--root', ROOT / 'tests',
        '--entry', 'game_hud_behavior:Check', *args, '-o', bundle, ROOT / 'tests/game_hud_behavior.zi')
    assert run(toolchain / 'build/bin/zi2zx', 'run', '--vm', bundle).strip() == '0'
    print('PASS portable: same retained-tree behavior and bounds')
    args = [arg for source, target in [('image_widget:ImageHostedHost', 'HudImage'),
            ('button_widget:ButtonHostedHost', 'HudButton'), ('box_widget:BoxHostedHost', 'HudBox'),
            ('widget_palette:WidgetPaletteHostedHost', 'HudPalette'),
            ('widget_palette:WidgetPaletteRestoreHostedHost', 'HudPaletteRestore'), ('text_widget:TextHostedHost', 'HudText')]
            for arg in ('--bind', f'kryon/{source}=game_hud_hosted:{target}')]
    bundle = WORK / 'hosted.zx'
    run(toolchain / 'build/bin/zi2zx', 'bundle', '--module-path', toolchain / 'std', '--root', ROOT / 'tests', '--define', 'KRYON_HOSTED_UI',
        '--entry', 'game_hud_hosted:Check', *args, '-o', bundle, ROOT / 'tests/game_hud_hosted.zi')
    assert run(toolchain / 'build/bin/zi2zx', 'run', '--vm', bundle).strip() == '0'
    print('PASS hosted portable: images, invisible translated actions, amount, default/custom asset paths and results')
    print('PASS assets: transparent WebP thumbnails <=256px; package export and translations')
    os.environ.pop('ZIRAN_PACKAGE_MAP')
    os.environ['APPS_TREE_TEST_OUTPUT'] = str(WORK / 'apps-tree')
    print(run('sh', ROOT / 'tests/tree_test.sh', ZIRAN, toolchain / 'build/libziran.a').strip())

if __name__ == '__main__':
    try:
        main()
    except subprocess.CalledProcessError as error:
        print(error.stdout[-6000:] if error.stdout else str(error))
        raise SystemExit(error.returncode)
