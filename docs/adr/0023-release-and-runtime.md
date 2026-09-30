# ADR-0023: Release model, uv-managed CPython 3.12, and rollback

- **Status:** Accepted — FIXED (CLAUDE.md D22)
- **Date:** 2026-09-30
- **Decided by:** owner (Stage B locked decisions 1, 11, 12, 13). Building the
  frontend on the trusted build machine is PROPOSED in Stage B.

## Context
paolo-core's system Python is 3.14; D1 fixes 3.12. Deployments must be tied to an
approved commit, reversible, and must never endanger Maple's database.

## Decision
- Runtime: uv-managed CPython **3.12** (pinned patch, 3.12.14) under
  `/opt/maplegotchi/python`; a per-release venv built from `uv.lock`
  (`--locked --no-dev --no-editable`). The project is not migrated to 3.14.
- A release is `/opt/maplegotchi/releases/<commit-sha>`, immutable after its
  `.complete` marker; `current` / `previous` symlinks; atomic switch by
  `activate_release.sh`.
- Bundles are built on the trusted build machine from `git archive <sha>`, with the
  frontend built there (`pnpm install --frozen-lockfile`). Files are covered by
  `SHA256SUMS`, and the bundle by a SHA-256 the owner checks. paolo-core needs no
  node/pnpm. Python wheels are installed on paolo-core from the hash-pinned lock.
- Rollback swaps code only. A release older than the database schema is refused; a
  release that migrates forward needs `--allow-migration` after a verified copy.
- All privileged steps are owner-run scripts; nothing requires Claude to hold sudo.

## Consequences
- The build backend is pinned (`hatchling==1.32.4`) so installs are reproducible.
- A schema migration's PR must state its rollback story.
