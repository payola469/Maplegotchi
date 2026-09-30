# Architecture

`CLAUDE.md` §3 is the source of truth for architecture while v0.1 is being
built; this file collects longer-form notes as each phase lands.

## Phase status

| Phase | Status |
|---|---|
| 0. Foundations | Complete |
| 1. Core being | Complete |
| 2. Persistence + restart recovery | Complete (see `persistence.md`) |
| 3. Sensors + observations | Complete (see `sensors.md`) |
| 4. Journal + reflection + Brain | Complete (see `journal.md`) |
| 5. API + live state + owner interactions | Complete (see `api.md`) — milestone M1 |
| 6. Maple Room UI | Implemented, awaiting review (see `frontend.md`) — milestone M2 |
| 7–8 | Not started |

## Core (Phase 1)

All of `maplegotchi.core` is pure: no I/O, clock, randomness, or concurrency.
Time and randomness come from the caller.

| Module | Responsibility |
|---|---|
| `state.py` | `MapleState`, `Needs`, interaction ledger, reactions; every invariant checked on construction; `expression` derived, never stored |
| `activities.py` | The 7 fixed activities, logical room locations, per-activity durations and need rates |
| `behavior.py` | Utility scoring + hard rules (exhaustion → sleep, low energy → sleep/rest), seeded weighted choice |
| `heartbeat.py` | `heartbeat(state, now, inputs, params)`: evolve needs, expire reactions, prune ledger, bounded catch-up, maybe change activity. No Brain parameter. |
| `interactions.py` | `apply_interaction`: Greet/Pet, D14 cooldowns and global limit, diminishing returns, drowsy reactions |
| `rng.py` | `RngState` (persisted seed + counters) and `RngStream` (keyed BLAKE2b over seed, stream, counter, draw) |
| `timeline.py` | Life events: `ActivityChanged`, `InteractionAccepted`, `DowntimeGap` |
| `identity.py` | Maple's name and birth time |
| `daytime.py` | UTC enforcement, local hour, day phases (night 22:00–06:00) |
| `parameters.py` | FIXED interaction limits; tunable `CoreParameters` (heartbeat 300 s, UTC offset, catch-up cap, reaction duration) |
| `simulation.py` | Fake-time multi-day simulation with a reproducibility digest |

### Needs model
- **energy**: activity rate per hour (sleep +12, rest +5, walk −6, …).
- **curiosity**: builds while idle/walking/resting, satisfied by reading (−8/h) and observing the server (−10/h).
- **social**: relaxes toward a floor of 20 when alone; Greet/Pet raise it.
- **mood**: relaxes toward `20 + 0.35·energy + 0.45·social`, plus small per-activity effects; Greet/Pet raise it.

Relaxation uses the rational form `target + (value − target) / (1 + rate·hours)`,
not `exp`, to keep float results bit-identical across platforms.

### Expression priority
`state.expression_at(now)`: sleepy (asleep or energy < 20) → happy (a happy
reaction active at `now`) → focused (write / observe_server) → curious or
focused (read, by curiosity ≥ 60) → happy (mood ≥ 70) → curious
(curiosity ≥ 75) → calm.

### Transient reactions (D17, ADR-0018)
A Greet/Pet reaction is active while `started_at <= now < until`, with
`until = started_at + 8 s`. Expression is derived from the supplied `now`, so
the reaction ends exactly at `until` with no heartbeat or timer. The heartbeat
drops ended reaction records as housekeeping only.

## Tuning notes (non-blocking)
Tuning constants are adjustable, not architecture. Observations to revisit
once observations (Phase 3) and the Room UI (Phase 6) exist:

- **2026-09-30, Phase 1 baseline:** the 30-day demo simulation spends 1,870 of
  8,640 ticks (~156 h, ~22%) writing. Do not retune yet; reassess overall
  activity balance later.
