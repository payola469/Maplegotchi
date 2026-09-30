# ADR-0024: Maple's database in the nightly paolo-core backup

- **Status:** Accepted — FIXED (CLAUDE.md D23). The exact script diff is finalized in
  Stage C step 0, against the real `/usr/local/sbin/paolo-core-backup`.
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
  atomic rename to `$RUN_DIR/maple.db`, which is added to the restic inputs.
- Exit 3 means "not deployed" (`/data/maple` absent): skipped on purpose. Once Maple
  is deployed, any failure takes the script's existing fail-safe path.
- The existing backup system is not redesigned; its other inputs are untouched.

## Consequences
- The helper is covered by tests against a live database.
- Restores are verified with `maple-db-snapshot verify`.
