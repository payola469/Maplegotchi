# ADR-0024: Maple's database in the nightly paolo-core backup

- **Status:** Accepted — FIXED (CLAUDE.md D23). Patch finalized against the reviewed
  structure of the real `/usr/local/sbin/paolo-core-backup` (2026-09-30).
- **Date:** 2026-09-30
- **Decided by:** owner (Stage B locked decision 9)

## Context
`/usr/local/sbin/paolo-core-backup` (root, 03:30 daily, restic) does not include
`/data/maple`. `maple.db` is a live WAL database, so a byte copy is unsafe.

## Decision
- A stdlib helper, `/usr/local/sbin/maple-db-snapshot` (from
  `deploy/backup/maple_db_snapshot.py`), stages a copy: read-only source → SQLite
  online backup API → `$RUN_DIR/maple.db.partial` (0600) → `journal_mode=DELETE` →
  `integrity_check == ok`, Maplegotchi `application_id`, migrated schema → fsync →
  atomic rename to `$RUN_DIR/maple.db`.
- Exact patch (two insertions, no existing line changed): the block in
  `deploy/backup/maple-block.bash` after the `metrics.db` staging step, and
  `${MAPLE_DB_STAGED:+"$MAPLE_DB_STAGED"} \` among the explicit paths of the
  final `restic … backup` command, so Maple's file is passed only when staged.
- `/data/maple/maple.db` absent (not deployed): skipped on purpose, job unchanged.
  Present but not stageable: the helper fails as a plain command, so
  `set -Eeuo pipefail` fails the whole job through its existing ERR/exit
  handling (the script has no `fail()` function), and restic does not run.
- `check_patch.sh` proves on the host that the diff is exactly these insertions.
- The existing backup system is not redesigned; its other inputs are untouched.

## Consequences
- The helper is covered by tests against a live database.
- Restores are verified with `maple-db-snapshot verify`.
