# ADR-0007: Deterministic simulation, persisted randomness

- **Status:** Accepted — FIXED (CLAUDE.md D7)
- **Date:** 2026-09-30
- **Decided by:** owner

## Context
Behavior needs some variety, but must be reproducible and coherent across restarts.

## Decision
Simulations use a fixed seed and are deterministic. Production randomness is controlled, and its seed/state is persisted.

## Consequences
- Proposed mechanism (CLAUDE.md §3.7): a persisted `life_seed` plus per-stream counters; each event's RNG is derived from `(life_seed, stream, counter)`, and counters are saved in the same transaction as state.
- `core` never imports `random` (enforced by the scanner).
