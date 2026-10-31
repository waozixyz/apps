#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
ziran=${1:-ziran}
runtime=${2:?pass the intended toolchain runtime library}
flags=--locked
if [ -f "$root/ziran.local.toml" ]; then flags=; fi
toolchain=$("$ziran" pkg path ziran)
work=${APPS_TREE_TEST_OUTPUT:-"$root/build/tree-test"}
unset DISPLAY WAYLAND_DISPLAY XAUTHORITY DBUS_SESSION_BUS_ADDRESS SESSION_MANAGER
mkdir -p "$work/c"
mkdir -p "$work/consent"
mkdir -p "$work/legacy-consent"
rm -f "$work/consent/node-connection" "$work/legacy-consent/node-connection"
printf 'on\nhttps://content.test' > "$work/legacy-consent/node-connection"
APPS_TREE_CONSENT="$work/consent"
APPS_TREE_LEGACY_CONSENT="$work/legacy-consent"
export APPS_TREE_CONSENT
export APPS_TREE_LEGACY_CONSENT
"$ziran" build --project $flags --target=c --no-main --entry tree_behavior:Check --root "$root/tests" \
    -o "$work/c" "$root/tests/tree_behavior.zi"
cat > "$work/c/main.c" <<'C'
#include <stdio.h>
#include "tree_behavior.h"
int main(void) {
    int result = Check();
    if (result) fprintf(stderr, "Apps tree check %d failed\n", result);
    return result ? 1 : 0;
}
C
includes=$(find "$work/c" -type d -printf ' -iquote %p')
# shellcheck disable=SC2046,SC2086
"${CC:-cc}" -std=c11 -O2 -I"$toolchain/include" $includes $(find "$work/c" -name '*.c') \
    "$runtime" -Wl,--gc-sections -lm -lpthread -o "$work/test"
"$work/test"
echo 'Apps: strict requests/catalogs, content consent, deferred transitions, rollback, stable locators, account effects and 80-level routes passed'
