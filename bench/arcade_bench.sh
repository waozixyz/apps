#!/bin/sh
# Times Arcade's list and games under the Ziran VM. Pass the libziran.a to
# measure (default: the toolchain's) and set BENCH_FRAMES to change the count.
# ZIRAN_VM_PROFILE=FILE also writes the VM's per-function profile.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"
flags=--locked
if [ -f ziran.local.toml ]; then flags=; fi
toolchain=$(ziran pkg path ziran $flags)
library=${1:-$toolchain/build/libziran.a}
work=$root/build/arcade-bench
bundle=${BENCH_BUNDLE:-$root/../arcade/build/arcade.zib}
mkdir -p "$work"
scripts/ziran.sh build --project $flags --target=c --no-main --entry arcade_bench:Main \
    --root bench -o "$work/c" bench/arcade_bench.zi
cat > "$work/main.c" <<'C'
#define _POSIX_C_SOURCE 199309L
#include <time.h>
#include "arcade_bench.h"
double bench_seconds(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return t.tv_sec + t.tv_nsec / 1e9; }
int main(void) { return Main(); }
C
includes=$(find "$work/c" -type d -printf '-iquote %p ')
# shellcheck disable=SC2086
"${CC:-cc}" -std=c11 -O2 ${BENCH_CFLAGS:-} -I"$toolchain/include" $includes "$work/main.c" \
    $(find "$work/c" -name '*.c') "$library" -lm -lpthread -o "$work/bench"
controller=$(sha256sum build/ui/apps.zib | cut -c1-64)
env -u DISPLAY -u WAYLAND_DISPLAY BENCH_BUNDLE="$bundle" \
    BENCH_SHA256="$(sha256sum "$bundle" | cut -c1-64)" BENCH_ID=inbe.arcade BENCH_EXPECTED=arcade \
    BENCH_CONTROLLER="$controller" BENCH_GAMES="${BENCH_GAMES:-arcade.pushy-player,arcade.pushy-player/arcade.pushy,arcade.pushy-player/arcade.pushy-island}" \
    "$work/bench"
