# Maplegotchi

Home of **Maple**, a digital being living in a Tamagotchi-style 2D room on the
Ubuntu server **paolo-core**. Maple has its own state, heartbeat, activities,
journal, observations, and life timeline, and watches its host through
strictly read-only sensors.

> Status: **Phase 0 — Foundations.** No Maple behavior is implemented yet.

- Architecture, scope, security boundaries, and rules: [`CLAUDE.md`](CLAUDE.md)
- Decisions: [`docs/adr/`](docs/adr/)

## Layout

| Path | What |
|---|---|
| `backend/` | Python 3.12 · FastAPI · SQLite · psutil (managed with `uv`) |
| `frontend/` | TypeScript · Vite · PixiJS (room) · Preact (panels) (managed with `pnpm`) |
| `docs/` | Architecture notes, security model, ADRs |
| `scripts/check.sh` | Runs every check CI runs |

## Development

Prerequisites: [`uv`](https://docs.astral.sh/uv/) (installs Python 3.12 for you), Node 24, pnpm 12.

```bash
cd backend && uv sync          # Python deps
cd frontend && pnpm install    # JS deps
scripts/check.sh               # lint, types, import contracts, security tests, unit tests, build
```

Dev ports (localhost only): backend `127.0.0.1:8470`; Vite dev server `127.0.0.1:5173`,
which proxies `/api` to the backend.
