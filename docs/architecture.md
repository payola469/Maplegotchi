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
| 6. Maple Room UI | Complete, approved (see `frontend.md`) — milestone M2 |
| 7. paolo-core deploy | Stage A (read-only survey) complete — `deploy/survey/findings.md`; Stage B (local preparation) complete — `deployment.md`; Stage C (owner-run install):
- the services **are installed and active** on paolo-core at release `160ed4f…` (verified current runtime, see "Deployment state" below);
- verified on the live service: the systemd hardening is loaded, Tailscale Serve and Funnel are tailnet-only, and nightly backup creation works (including the Maple DB snapshot);
- **authorization:** the install of release `160ed4f…` was retroactively authorized by the owner on 2026-10-09 (status clarification only);
- **Stage C stays open** until the inside-service boundary probe and a restore test pass; M3 is not claimed |
| 8. Trial run | **Owner decision 2026-10-09:** not authorized, not started; deferred until Stage C is closed (boundary probe and restore test pass). Blocks neither R1a nor R1b; gates only the stable-release label (ADR-0009). |

### v0.2 (branch `v0.2-development`, pushed; schema v10)

| Work | Status |
|---|---|
| v0.2 autonomy A1–A10 (ADR-0026..0033) | Implemented, merged into `v0.2-development` (`docs/v0.2-review.md`, `docs/autonomy.md`) |
| Brain Health / Observability v1 (ADR-0034) | Implemented, merged |
| Discord chat polish + read-only status commands (ADR-0032 amendment 2026-10-07) | Implemented, merged |
| Room / Workspace / System Investigator roadmap | `docs/roadmap/maple-roadmap.md` (product roadmap). Architecture in `docs/architecture/` is **DRAFT / PROPOSED / FOR HUMAN REVIEW**; nothing is implemented. |

### Service relationships (current code)

```
browser ──Tailscale Serve──► maplegotchi (maple-svc, 127.0.0.1:8470) ◄── maple-discord (maple-discord-svc)
                                   │  loopback HTTP, only if MAPLE_BRAIN /       GETs for slash commands;
                                   │  MAPLE_DIRECTOR / MAPLE_REPLIER=antigravity POST /api/conversation/messages
                                   ▼                                             (gateway token)
                             maple-brain (maple-brain-svc, 127.0.0.1:8471) ──► provider CLI (outbound)
```

How the services connect:
- Maple calls the Brain companion only:
  - `/decide` and `/reply` outside the writer lock, with a deadline, never stacked, and re-validated afterwards;
  - `/generate` (the journal) inside the lock — a known limitation, not fixed;
  - `/health` for `GET /api/brain-health`.
- Maple never calls Discord. The Brain companion never calls Maple.
- Details are in `docs/security-model.md` → "Services and trust relationships".

## Deployment state (recorded 2026-10-08)

### VERIFIED CURRENT RUNTIME — paolo-core (owner-supplied live evidence)

| Item | Verified value |
|---|---|
| Services | `maplegotchi` **active**, `maple-brain` **active**, `maple-discord` **active** |
| Main release (`current`) | `/opt/maplegotchi/releases/160ed4fb9f2534a4609d826d9c4535cc7863ae3d` |
| Brain release (`current`) | `/opt/maple-brain/releases/160ed4fb9f2534a4609d826d9c4535cc7863ae3d` |
| Discord release (`current`) | `/opt/maple-discord/releases/160ed4fb9f2534a4609d826d9c4535cc7863ae3d` |
| Production database | `PRAGMA user_version = 10` (schema v10) |
| Listeners | `127.0.0.1:8470` (Maple), `127.0.0.1:8471` (Brain companion); loopback only. `maple-discord` listens on nothing. |
| Activation (local +07) | `maplegotchi` Wed 2026-10-07 17:33:45; `maple-brain` Wed 2026-10-07 17:37:12; `maple-discord` Wed 2026-10-07 18:22:18 |
| `maplegotchi.service` hardening (loaded properties) | `User=maple-svc`, `Group=maple-svc`; `ProtectSystem=strict`, `ProtectHome=yes`, `NoNewPrivileges=yes`, `PrivateTmp=yes`, `PrivateDevices=yes`, `ProtectProc=invisible`, `RestrictNamespaces=yes`, `RestrictAddressFamilies=AF_INET AF_UNIX`; `IPAddressDeny=::/0 0.0.0.0/0`, `IPAddressAllow=127.0.0.0/8 ::1/128`; `MemoryHigh=402653184` (384 MiB), `MemoryMax=536870912` (512 MiB), `TasksMax=64` |
| `systemd-analyze security` | "Overall exposure level for maplegotchi.service: **1.1 OK**" |
| AI switches (Maple env) | `MAPLE_BRAIN=antigravity`, `MAPLE_DIRECTOR=antigravity`, `MAPLE_REPLIER=antigravity` |
| Brain companion | runs as `maple-brain-svc`; port 8471 belongs to the `maple_brain` process; `/health` → `status=ok`, `provider=command`, `model=gemini-3.8-flash-medium` |
| Backup creation | `paolo-core-backup.timer` active, daily at 03:30. Latest observed run (2026-10-08) finished 0/SUCCESS: integrity checks passed for `n8n.sqlite`, `grafana.db` and `metrics.db`; the Maple DB snapshot was staged; restic snapshot `8b7bea38` saved; `BACKUP COMPLETED` logged. |
| Tailscale | Serve: tailnet-only, `/` → `http://127.0.0.1:8470`. Funnel status: tailnet-only (no public exposure). |

- All three `current` symlinks point to the same release, commit `160ed4f`: "merge: polish Maple chat and add Discord status commands".
- The only later commit on `v0.2-development`, `5be58c0`, adds `docs/roadmap/maple-roadmap.md`. The deployed code is therefore the current branch code.
- The documentation-only changes made on 2026-10-08 are not in the deployed release. They change no behaviour.

### HISTORICAL AUTHORIZATION / TEST EVIDENCE — still UNVERIFIED

The runtime evidence above shows what is running and configured. It does not prove any of the following:

| Item | Status |
|---|---|
| Stage C owner authorization | **Recorded 2026-10-09 (owner decision):** the Stage C install of release `160ed4fb9f2534a4609d826d9c4535cc7863ae3d` is retroactively authorized. Stage C is **not complete**: it stays open until the inside-service boundary probe and the restore test (below) pass, and M3 is not claimed. The 2026-09-30 "not authorized" line in `CLAUDE.md` is kept as history. |
| Phase 8 (72 h trial) | **Status clarified 2026-10-09 (owner decision):** not authorized, not started, deferred until Stage C is closed (boundary probe and restore test pass). It blocks neither R1a nor R1b and gates only the stable-release label (ADR-0009). |
| Inside-service runtime boundary probe | **Not re-run for this release.** `deploy/verify/check_boundaries.py` and `deploy/verify/sandbox_probe.sh` exist in the repository but are not present in the deployed release. The hardening controls are verified as *loaded*; the resulting namespace and runtime behaviour has **not** been re-verified end to end. That behaviour covers: writes only to `/data/maple`, `/data` siblings and homes hidden, Docker socket inaccessible, process credentials (caps, no_new_privs, seccomp), and the listening sockets as seen from inside the service. |
| Restore verification | **Unverified.** No restore from restic (including `maple.db` at schema v10) has been tested. |

Notes on this evidence:
- Backup *creation* is verified. A direct `restic snapshots` listing as user `paolo` failed because of repository permissions; that is an access restriction, not a backup failure.
- With `MAPLE_BRAIN=antigravity` in production, the known journal-Brain-inside-the-writer-lock limitation (`docs/security-model.md` → Known limitations) applies to the live service.
- Background from repository documents: before v0.2, paolo-core ran a schema-v3 Maplegotchi with a hand-made Brain bridge on 127.0.0.1:8471 (`docs/v0.2-review.md` §6, ADR-0033 context, `deploy/brain/README.md`). Port 8471 now belongs to the packaged `maple_brain` process.

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
