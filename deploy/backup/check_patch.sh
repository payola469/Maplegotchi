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
# The argument must sit inside one logical, backslash-continued shell command
# that invokes restic with the `backup` subcommand. The real script spreads it
# over lines (`restic \`, `--repo … \`, `--password-file … \`, `backup \`, paths),
# so the command is rebuilt from its first line, not matched on one line. A line
# continues only if it ends in an odd number of backslashes with nothing after
# them; a comment line ends the command. Global options before the subcommand
# must be known restic options (value options consume the next word); anything
# else fails closed. The argument must directly follow "$RUN_DIR/metrics.db".
inside=$(RESTIC_ARG="$RESTIC_ARG" awk '
    function trim(s) { sub(/^[[:space:]]+/, "", s); sub(/[[:space:]]+$/, "", s); return s }
    function continues(s,    i, k) {
        if (s ~ /^[[:space:]]*#/) return 0
        k = 0
        for (i = length(s); i > 0 && substr(s, i, 1) == "\\"; i--) k++
        return k % 2 == 1
    }
    { line[NR] = $0; if (trim($0) == ENVIRON["RESTIC_ARG"]) { hits++; at = NR } }
    END {
        if (hits != 1) { print "no: argument line found " hits + 0 " times"; exit }
        if (!continues(line[at])) { print "no: argument line does not continue"; exit }
        start = at
        while (start > 1 && continues(line[start - 1])) start--
        if (start == at) { print "no: argument is not part of a continued command"; exit }
        words = ""
        for (i = start; i < at; i++) { w = line[i]; sub(/\\$/, "", w); words = words " " w }
        n = split(words, tok, /[[:space:]]+/)
        first = 1
        while (first <= n && tok[first] == "") first++
        if (tok[first] !~ /^(\/[^[:space:]]*\/)?restic$/) {
            print "no: command starting at line " start " is not restic"; exit
        }
        cmd = ""
        for (i = first + 1; i <= n; i++) {
            t = tok[i]
            if (t == "") continue
            if (t ~ /^-/) {
                if (t ~ /=/) continue
                if (t ~ /^(-r|--repo|--repository-file|-p|--password-file|--password-command|--cache-dir|--cacert|--tls-client-cert|-o|--option|--limit-upload|--limit-download|--pack-size|--compression|--key-hint)$/) { i++; continue }
                if (t ~ /^(-v|--verbose|-q|--quiet|--no-cache|--no-lock|--json|--cleanup-cache|--insecure-tls)$/) continue
                print "no: unrecognised restic global option " t " before the subcommand"; exit
            }
            cmd = t; break
        }
        if (cmd != "backup") { print "no: restic subcommand is \"" cmd "\", not backup"; exit }
        if (trim(line[at - 1]) != "\"$RUN_DIR/metrics.db\" \\") {
            print "no: line " at - 1 " is not the \"$RUN_DIR/metrics.db\" argument"; exit
        }
        print "yes: restic backup command, lines " start "-" at
    }' "$PATCHED")
# shellcheck disable=SC2016
label='argument is inside the restic backup command, directly after "$RUN_DIR/metrics.db"'
case $inside in
    yes:*) report 0 "$label (${inside#yes: })" ;;
    *) report 1 "$label (${inside#no: })" ;;
esac
report "$(ok [ -x "$HELPER" ])" "helper installed ($HELPER)"

if [ "$failed" -eq 0 ]; then echo "check_patch: OK"; else echo "check_patch: FAILED"; fi
exit "$failed"
