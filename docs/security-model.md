# Security model

`CLAUDE.md` §4 is the source of truth. This file will record the concrete
evidence behind it as phases land (test names, systemd unit review, the
Phase 3 paolo-core survey, and `check_boundaries.py` output).

## Enforced today (Phases 0–2)

| Control | Where |
|---|---|
| No subprocess / shell / exec / eval / process-kill APIs in `backend/src` | `backend/tests/security/test_forbidden_apis.py` (AST scanner, self-tested) |
| `core` has no I/O, clock, randomness, or concurrency imports | same scanner, core rules |
| `core` imports only allowlisted stdlib modules (`__future__`, `collections`, `dataclasses`, `datetime`, `enum`, `hashlib`, `math`, `types`, `typing`) and `maplegotchi.core.*` | `test_core_imports_only_allowlisted_modules` (Phase 1) |
| Heartbeat cannot invoke a Brain (no Brain parameter) | `tests/core/test_heartbeat.py::test_heartbeat_takes_no_brain` (Phase 1) |
| Only Greet/Pet exist; D14 limits fixed and restart-safe | `tests/core/test_interactions.py`, `tests/core/test_state.py` (Phase 1) |
| Only `maplegotchi.storage` writes files or imports `sqlite3`/`shutil`/`tempfile` | scanner "write-outside-storage" rules (Phase 2) |
| Every Maple-owned write resolves inside `MAPLE_DATA_DIR` (`..`, absolute, drive, UNC, device names, symlink/junction escapes rejected) | `storage/datadir.py`, `tests/storage/test_datadir.py` (Phase 2) |
| Identity and life seed immutable; timeline append-only; one birth; revisions advance by one; RNG counters never decrease | SQLite triggers + unique index (migration 1), `tests/storage/test_database.py` (Phase 2) |
| Corrupt / foreign / empty / too-new databases fail loudly, never replaced | `storage/db.py`, `tests/storage/` (Phase 2) |
| SQLite hardening: `trusted_schema=OFF`, defensive mode | `storage/db.py` (Phase 2) |
| Birth is published only from a self-contained rollback-journal file (no WAL/sidecar dependency) | `storage/db.py`, `tests/storage/test_birth_publication.py` (Phase 2) |
| `sqlite3` only inside storage; external monitoring DB read via read-only `storage.external` datasource, never from sensors (D18) | scanner rules now; datasource + read-only rules + narrowed import contracts in Phase 3 |
| Banned APIs flagged while editing | ruff `TID251` + `S` rules (`backend/pyproject.toml`) |
| Layer dependency rules (CLAUDE.md §3.3) | import-linter contracts (`backend/pyproject.toml`) |
| No `eval` / `new Function` / raw HTML sinks in the UI | `frontend/eslint.config.js` |
| All of the above in CI on every push/PR | `.github/workflows/ci.yml` |
