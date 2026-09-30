# Security model

`CLAUDE.md` §4 is the source of truth. This file will record the concrete
evidence behind it as phases land (test names, systemd unit review, the
Phase 3 paolo-core survey, and `check_boundaries.py` output).

## Enforced today (Phase 0)

| Control | Where |
|---|---|
| No subprocess / shell / exec / eval / process-kill APIs in `backend/src` | `backend/tests/security/test_forbidden_apis.py` (AST scanner, self-tested) |
| `core` has no I/O, clock, randomness, or concurrency imports | same scanner, core rules |
| Banned APIs flagged while editing | ruff `TID251` + `S` rules (`backend/pyproject.toml`) |
| Layer dependency rules (CLAUDE.md §3.3) | import-linter contracts (`backend/pyproject.toml`) |
| No `eval` / `new Function` / raw HTML sinks in the UI | `frontend/eslint.config.js` |
| All of the above in CI on every push/PR | `.github/workflows/ci.yml` |
