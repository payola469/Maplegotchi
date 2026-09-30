#!/bin/sh
# Owner-run on paolo-core, as root:
#   sudo sh install_release.sh <maplegotchi-SHA.tar.gz> <bundle-sha256> <path-to-uv>
#
# Installs one immutable release under /opt/maplegotchi/releases/<commit-sha>:
#   - verifies the bundle's SHA-256 (printed by scripts/build_release.sh) and
#     every file against the bundle's SHA256SUMS;
#   - installs uv-managed CPython 3.12 (pinned patch) under /opt/maplegotchi/python;
#   - builds the release venv from uv.lock (hash-verified, no dev dependencies);
#   - makes everything root-owned and non-writable for anyone else.
# It does NOT switch `current`, touch systemd, or start anything
# (activate_release.sh does the switch; the owner starts the service).
# Re-running for an already-complete release is a no-op; a half-installed
# release (no .complete marker) is removed and rebuilt.
set -eu
umask 022

PYTHON_VERSION=3.12.14   # uv-managed CPython (D1); bump deliberately, per release
OPT=/opt/maplegotchi
RELEASES=$OPT/releases
PYTHON_DIR=$OPT/python

die() { echo "install_release: $*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "run as root (sudo)"
[ $# -eq 3 ] || die "usage: install_release.sh <bundle.tar.gz> <bundle-sha256> <uv>"
BUNDLE=$1
EXPECTED=$2
UV=$3
[ -f "$BUNDLE" ] || die "no such bundle: $BUNDLE"
[ -x "$UV" ] || die "uv is not executable: $UV"

actual=$(sha256sum "$BUNDLE" | cut -d' ' -f1)
[ "$actual" = "$EXPECTED" ] || die "bundle SHA-256 mismatch: got $actual"

install -d -o root -g root -m 0755 "$OPT" "$RELEASES" "$PYTHON_DIR"

STAGE=$(mktemp -d "$RELEASES/.incoming.XXXXXX")
CACHE=$(mktemp -d /root/.maplegotchi-uv-cache.XXXXXX)
FINAL=""
cleanup() {
    rm -rf -- "$STAGE" "$CACHE"
    if [ -n "$FINAL" ] && [ -d "$FINAL" ] && [ ! -f "$FINAL/.complete" ]; then
        rm -rf -- "$FINAL"
    fi
}
trap cleanup EXIT

tar -xzf "$BUNDLE" -C "$STAGE" --no-same-owner
(cd "$STAGE" && sha256sum --quiet --strict -c SHA256SUMS) || die "bundle contents do not match SHA256SUMS"
SHA=$(sed -n 's/^commit=//p' "$STAGE/RELEASE")
echo "$SHA" | grep -Eq '^[0-9a-f]{40}$' || die "bad commit id in RELEASE: $SHA"

if [ -f "$RELEASES/$SHA/.complete" ]; then
    echo "install_release: $SHA is already installed (immutable); nothing to do"
    exit 0
fi
[ -e "$RELEASES/$SHA" ] && rm -rf -- "${RELEASES:?}/$SHA"   # a previous, incomplete attempt
mv -T "$STAGE" "$RELEASES/$SHA"
FINAL=$RELEASES/$SHA

# uv-managed CPython, pinned, outside any home directory, never on PATH.
export UV_PYTHON_INSTALL_DIR="$PYTHON_DIR" UV_CACHE_DIR="$CACHE" UV_NO_CONFIG=1 \
       UV_PYTHON_PREFERENCE=only-managed UV_LINK_MODE=copy
"$UV" python install --no-bin --install-dir "$PYTHON_DIR" "$PYTHON_VERSION"
set -- "$PYTHON_DIR"/cpython-"$PYTHON_VERSION"-linux-x86_64-gnu/bin/python3.12
[ $# -eq 1 ] && [ -x "$1" ] || die "managed CPython $PYTHON_VERSION not found under $PYTHON_DIR"
PY=$1

# The release venv, built in its final place (venvs are not relocatable).
UV_PROJECT_ENVIRONMENT="$FINAL/venv" "$UV" sync --project "$FINAL/backend" \
    --locked --no-dev --no-editable --compile-bytecode --no-python-downloads --python "$PY"

"$FINAL/venv/bin/python" -I -c '
import sys, maplegotchi.cli, psutil, dbus_fast, fastapi, uvicorn
assert sys.version_info[:2] == (3, 12), sys.version
print("install_release: venv ok:", sys.version.split()[0], sys.executable)
'
[ -f "$FINAL/frontend/dist/index.html" ] || die "release has no built frontend"

chown -R root:root "$FINAL" "$PYTHON_DIR"
chmod -R u+rwX,go+rX,go-w "$FINAL" "$PYTHON_DIR"
printf 'commit=%s\ninstalled_at=%s\npython=%s\n' "$SHA" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$PY" \
    > "$FINAL/.complete"
chmod 0644 "$FINAL/.complete"
echo "install_release: installed $FINAL (not active yet; run activate_release.sh $SHA)"
