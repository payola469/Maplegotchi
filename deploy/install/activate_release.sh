#!/bin/sh
# Owner-run on paolo-core, as root — deploy AND rollback use this one script:
#   sudo sh activate_release.sh <commit-sha> [--allow-migration]
#
# Points /opt/maplegotchi/current at an installed, complete release (atomic
# symlink swap), remembers the previous one in /opt/maplegotchi/previous,
# installs that release's systemd unit if it differs, and verifies the unit.
# It does not start or restart Maple; the owner does that next.
#
# Schema safety (docs/deployment.md, "Rollback"): Maple's database is never
# touched here. If the database's schema is NEWER than the release understands,
# activation is refused (Maple would refuse to start: SchemaTooNewError). If the
# release would MIGRATE the database forward on start, --allow-migration is
# required, after taking a verified backup copy first.
set -eu
OPT=/opt/maplegotchi
DB=/data/maple/maple.db
UNIT=/etc/systemd/system/maplegotchi.service

die() { echo "activate_release: $*" >&2; exit 1; }
[ "$(id -u)" -eq 0 ] || die "run as root (sudo)"
[ $# -ge 1 ] || die "usage: activate_release.sh <commit-sha> [--allow-migration]"
SHA=$1
ALLOW_MIGRATION=${2:-}
echo "$SHA" | grep -Eq '^[0-9a-f]{40}$' || die "not a commit id: $SHA"
REL=$OPT/releases/$SHA
[ -f "$REL/.complete" ] || die "$REL is not an installed, complete release"

code_version=$("$REL/venv/bin/python" -I -c \
    'from maplegotchi.storage.migrations import latest_version; print(latest_version())')
if [ -f "$DB" ]; then
    db_version=$("$REL/venv/bin/python" -I -c '
import sqlite3, sys
conn = sqlite3.connect("file:" + sys.argv[1] + "?mode=ro", uri=True)
print(conn.execute("PRAGMA user_version").fetchone()[0])
' "$DB")
    if [ "$db_version" -gt "$code_version" ]; then
        die "database schema v$db_version is newer than release schema v$code_version; \
choose a newer release or restore a matching database backup (see docs/deployment.md)"
    fi
    if [ "$db_version" -lt "$code_version" ] && [ "$ALLOW_MIGRATION" != "--allow-migration" ]; then
        die "release migrates the database v$db_version -> v$code_version on start. Take a copy first:
  /usr/local/sbin/maple-db-snapshot stage --source $DB --dest /root/maple-pre-$SHA.db
then re-run with --allow-migration"
    fi
    echo "activate_release: database schema v$db_version, release schema v$code_version"
fi

if [ -L "$OPT/current" ]; then
    ln -sfn "$(readlink "$OPT/current")" "$OPT/previous.new"
    mv -Tf "$OPT/previous.new" "$OPT/previous"
fi
ln -sfn "releases/$SHA" "$OPT/current.new"
mv -Tf "$OPT/current.new" "$OPT/current"
echo "activate_release: current -> releases/$SHA (previous -> $(readlink "$OPT/previous" 2>/dev/null || echo none))"

if ! cmp -s "$REL/deploy/systemd/maplegotchi.service" "$UNIT"; then
    install -o root -g root -m 0644 "$REL/deploy/systemd/maplegotchi.service" "$UNIT"
    systemctl daemon-reload
    echo "activate_release: installed $UNIT and reloaded systemd"
fi
systemd-analyze verify "$UNIT"
echo "activate_release: next: systemctl restart maplegotchi   (first install: systemctl enable --now maplegotchi)"
