# ADR-0003: Owner interactions: Greet and Pet only

- **Status:** Accepted — FIXED (CLAUDE.md D3)
- **Date:** 2026-09-30
- **Decided by:** owner

## Context
A purely view-only v0.1 would feel inert, but game systems would expand scope.

## Decision
Exactly two interactions: **Greet** and **Pet**. Each updates real backend state and produces a short, state-dependent visible reaction. Both are cooldown/rate-limited (limits in ADR-0014). No feeding, inventory, currency, shops, gifts, or other game systems.

## Consequences
- Two write endpoints exist in v0.1, with closed-enum actions and no free-text input.
- Reactions are part of the backend snapshot; the UI never invents them.
