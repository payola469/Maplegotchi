#!/bin/sh
# Owner-run, read-only: prove the patched backup script differs from the
# pre-patch copy ONLY by the Maplegotchi block and one restic path argument.
#   sh check_patch.sh [patched] [original] [maple-block.bash]
# Defaults: /usr/local/sbin/paolo-core-backup, its .pre-maple copy, and the
# block shipped in the current Maplegotchi release.
set -eu
PATCHED=${1:-/usr/local/sbin/paolo-core-backup}
ORIGINAL=${2:-/usr/local/sbin/paolo-core-backup.pre-maple}
BLOCK=${3:-/opt/maplegotchi/current/deploy/backup/maple-block.bash}
HELPER=${MAPLE_DB_SNAPSHOT:-/usr/local/sbin/maple-db-snapshot}
# The exact line added to the restic command (literal text, not expanded here).
# shellcheck disable=SC2016,SC1003
RESTIC_ARG='${MAPLE_DB_STAGED:+"$MAPLE_DB_STAGED"} \'
HEADER='# --- Maplegotchi database (Phase 7, ADR-0024) -------------------------------'

failed=0
report() {  # report <0|1> <message>
    if [ "$1" -eq 0 ]; then echo "[PASS] $2"; else echo "[FAIL] $2"; failed=1; fi
}
strip() { sed 's/^[[:space:]]*//; s/[[:space:]]*$//'; }
ok() { if "$@"; then echo 0; else echo 1; fi; }

report "$(ok bash -n "$PATCHED")" "patched script parses (bash -n)"

removed=$(diff "$ORIGINAL" "$PATCHED" | grep -c '^<' || true)
report "$(ok [ "$removed" -eq 0 ])" "no original line removed or changed ($removed)"

added=$(diff "$ORIGINAL" "$PATCHED" | sed -n 's/^> //p' | strip)
expected=$( { cat "$BLOCK"; printf '%s\n' "$RESTIC_ARG"; } | strip)
report "$(ok [ "$added" = "$expected" ])" "added lines are exactly the Maple block + the restic argument"

block_at=$(grep -n -F -x "$HEADER" "$PATCHED" | cut -d: -f1 || true)
arg_at=$(grep -n -F 'MAPLE_DB_STAGED:+' "$PATCHED" | cut -d: -f1 || true)
rundir_at=$(grep -n 'RUN_DIR=' "$PATCHED" | head -1 | cut -d: -f1 || true)
order=1
if [ -n "$rundir_at" ] && [ -n "$block_at" ] && [ "$rundir_at" -lt "$block_at" ]; then order=0; fi
report "$order" "block comes after RUN_DIR is created (line ${rundir_at:-?} < ${block_at:-?})"
order=1
if [ -n "$block_at" ] && [ -n "$arg_at" ] && [ "$block_at" -lt "$arg_at" ]; then order=0; fi
report "$order" "restic argument comes after the block (line ${arg_at:-?})"
# Walking back from the argument, every line must be a continuation (ends in a
# backslash) up to the line that invokes restic with the `backup` subcommand.
inside=$(awk -v n="${arg_at:-0}" '
    NR < n { line[NR] = $0 }
    END {
        for (i = n - 1; i >= 1; i--) {
            if (line[i] !~ /\\[[:space:]]*$/) { print "no"; exit }
            if (line[i] ~ /restic/ && line[i] ~ /[[:space:]]backup([[:space:]]|$)/) { print "yes"; exit }
        }
        print "no"
    }' "$PATCHED")
report "$(ok [ "$inside" = yes ])" "argument is inside the final restic backup command"
report "$(ok [ -x "$HELPER" ])" "helper installed ($HELPER)"

if [ "$failed" -eq 0 ]; then echo "check_patch: OK"; else echo "check_patch: FAILED"; fi
exit "$failed"
