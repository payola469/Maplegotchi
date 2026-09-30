# ADR-0001: Tech stack

- **Status:** Accepted — FIXED (CLAUDE.md D1)
- **Date:** 2026-09-30
- **Decided by:** owner

## Context
Maple runs as a long-lived service on paolo-core (Ubuntu) with a browser UI, and is developed on Windows.

## Decision
Backend: Python 3.12, FastAPI, SQLite, psutil. Frontend: TypeScript, Vite, PixiJS.

## Consequences
- One Python process owns Maple's state; SQLite (WAL) is the durable store in `/data/maple`.
- psutil gives cross-platform host metrics, so development works on Windows.
- Tooling: uv, ruff, mypy strict, pytest, import-linter; pnpm, eslint, tsc strict, vitest.
