#!/bin/sh
# Run the shared host's actual nested-bundle fixture on Win64 under Wine.
set -eu
runtime=${1:?pass the intended Win64 libziran.a}
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
work=${APPS_WINDOWS_TEST_OUTPUT:-"$root/build/windows-test"}
mkdir -p "$work"
work=$(CDPATH= cd -- "$work" && pwd)
exec 9>"$work/check.lock"
flock -n 9 || { echo 'Apps Windows checks are already running' >&2; exit 1; }
unset DISPLAY WAYLAND_DISPLAY XAUTHORITY DBUS_SESSION_BUS_ADDRESS SESSION_MANAGER LD_PRELOAD
export YUE_DESKTOP_RECOVERY=0
export APPS_TEST_PLATFORM=windows APPS_TEST_OUTPUT="$work/native"
export WINEPREFIX="$work/wine" WINEARCH=win64 WINEDEBUG=-all
export WINEDLLOVERRIDES='mscoree,mshtml,winemenubuilder.exe=d'
cleanup() {
    if test -d "$WINEPREFIX"; then
        wineserver -k || :
        wineserver -w || :
    fi
}
trap cleanup EXIT HUP INT TERM
xvfb-run -a "${PYTHON:-python3}" "$root/tests/native_fixture.py" "$runtime"
