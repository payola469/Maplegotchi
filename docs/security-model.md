# Security model

`CLAUDE.md` §4 is the source of truth. This file will record the concrete
evidence behind it as phases land (test names, systemd unit review, the
Phase 3 paolo-core survey, and `check_boundaries.py` output).

## Enforced today (Phases 0–1)

| Control | Where |
|---|---|
| No subprocess / shell / exec / eval / process-kill APIs in `backend/src` | `backend/tests/security/test_forbidden_apis.py` (AST scanner, self-tested) |
| `core` has no I/O, clock, randomness, or concurrency imports | same scanner, core rules |
| `core` imports only allowlisted stdlib modules (`__future__`, `collections`, `dataclasses`, `datetime`, `enum`, `hashlib`, `math`, `types`, `typing`) and `maplegotchi.core.*` | `test_core_imports_only_allowlisted_modules` (Phase 1) |
| Heartbeat cannot invoke a Brain (no Brain parameter) | `tests/core/test_heartbeat.py::test_heartbeat_takes_no_brain` (Phase 1) |
| Only Greet/Pet exist; D14 limits fixed and restart-safe | `tests/core/test_interactions.py`, `tests/core/test_state.py` (Phase 1) |
| Banned APIs flagged while editing | ruff `TID251` + `S` rules (`backend/pyproject.toml`) |
| Layer dependency rules (CLAUDE.md §3.3) | import-linter contracts (`backend/pyproject.toml`) |
| No `eval` / `new Function` / raw HTML sinks in the UI | `frontend/eslint.config.js` |
| All of the above in CI on every push/PR | `.github/workflows/ci.yml` |
