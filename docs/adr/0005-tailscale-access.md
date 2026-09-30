# ADR-0005: Tailnet-only access

- **Status:** Accepted — FIXED (CLAUDE.md D5)
- **Date:** 2026-09-30
- **Decided by:** owner

## Context
The owner needs to view and interact with Maple remotely; Maple must not be on the public internet.

## Decision
Access is via Tailscale. The backend binds to localhost and is exposed only to the tailnet. No public exposure in v0.1.

## Consequences
- The tailnet is the v0.1 trust boundary. Interaction endpoints still check Origin/Host and rate limits.
- Mechanics are in ADR-0013.
