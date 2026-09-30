# ADR-0013: Same-origin FastAPI + Tailscale Serve, no Caddy

- **Status:** Accepted — FIXED (CLAUDE.md D13)
- **Date:** 2026-09-30
- **Decided by:** owner

## Context
A separate web server adds moving parts that v0.1 does not need.

## Decision
- No Caddy initially.
- The frontend is built to static assets and served by FastAPI/Starlette, same origin as `/api`.
- FastAPI binds to localhost; Tailscale Serve exposes it to the tailnet; Funnel stays disabled.
- Required HTTP security headers are set in the application.

## Consequences
- No CORS configuration needed.
- Caddy can be added later in front of the same routes without app changes.
