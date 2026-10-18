#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"
flags=--locked
if [ -f ziran.local.toml ]; then flags=; fi
tool_root=$(ziran pkg path ziran $flags)
compiler="$tool_root/build/bin/ziran"
if [ ! -x "$compiler" ]; then
    compiler="$root/build/toolchain/bin/ziran"
    env -u DISPLAY -u WAYLAND_DISPLAY -u XAUTHORITY -u DBUS_SESSION_BUS_ADDRESS \
        make -s -C "$tool_root" BUILD_DIR="$root/build/toolchain" all >&2
fi
exec "$compiler" "$@"
