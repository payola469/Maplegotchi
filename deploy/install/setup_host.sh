#!/bin/sh
# Owner-run on paolo-core, as root, once (idempotent; safe to re-run):
#   sudo sh setup_host.sh /opt/maplegotchi/releases/<commit-sha>
#
# Creates the service account and Maple's directories; installs the env-file
# template (never overwrites an existing one) and the polkit deny rule.
# It does not install the systemd unit or start anything.
set -eu
umask 022
ACCOUNT=maple-svc

die() { echo "setup_host: $*" >&2; exit 1; }
[ "$(id -u)" -eq 0 ] || die "run as root (sudo)"
[ $# -eq 1 ] || die "usage: setup_host.sh <installed release dir>"
REL=$1
[ -f "$REL/.complete" ] || die "$REL is not a complete release"

# 1. System account: no shell, no home, no password, no supplementary groups.
if ! getent passwd "$ACCOUNT" >/dev/null; then
    useradd --system --user-group --no-create-home --home-dir /nonexistent \
        --shell /usr/sbin/nologin --comment "Maplegotchi service" "$ACCOUNT"
fi
[ "$(getent passwd "$ACCOUNT" | cut -d: -f7)" = /usr/sbin/nologin ] || die "$ACCOUNT has a login shell"
[ "$(getent passwd "$ACCOUNT" | cut -d: -f6)" = /nonexistent ] || die "$ACCOUNT has a home directory"
[ "$(id -Gn "$ACCOUNT")" = "$ACCOUNT" ] || die "$ACCOUNT has supplementary groups: $(id -Gn "$ACCOUNT")"

# 2. Directories (see docs/deployment.md for the layout).
install -d -o root -g root -m 0755 /opt/maplegotchi /opt/maplegotchi/releases /opt/maplegotchi/python
install -d -o root -g "$ACCOUNT" -m 0750 /etc/maplegotchi
install -d -o "$ACCOUNT" -g "$ACCOUNT" -m 0750 /data/maple

# 3. Settings (template only on first run; the owner edits MAPLE_ALLOWED_ORIGINS).
if [ ! -e /etc/maplegotchi/maplegotchi.env ]; then
    install -o root -g "$ACCOUNT" -m 0640 "$REL/deploy/etc/maplegotchi/maplegotchi.env" \
        /etc/maplegotchi/maplegotchi.env
    echo "setup_host: installed /etc/maplegotchi/maplegotchi.env — set MAPLE_ALLOWED_ORIGINS"
fi
chown root:"$ACCOUNT" /etc/maplegotchi/maplegotchi.env
chmod 0640 /etc/maplegotchi/maplegotchi.env

# 4. polkit: maple-svc is never authorized for anything.
install -o root -g root -m 0644 "$REL/deploy/polkit/50-maplegotchi-deny.rules" \
    /etc/polkit-1/rules.d/50-maplegotchi-deny.rules

echo "setup_host: done. $(id "$ACCOUNT")"
