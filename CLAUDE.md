# CLAUDE.md — Maplegotchi

This file guides Claude Code (and humans) working in this repository. Read it fully before changing anything.

> **Status: Phases 0-3 complete (2026-09-30). Phase 4+ NOT authorized.**
> Do not start the next phase until the owner approves it.
> Items marked **[FIXED]** are owner decisions — do not change them without owner approval.
> Items marked **[PROPOSED]** are implementation details that may still be adjusted.
> Every FIXED decision has an ADR in `docs/adr/`.

---

## 0. Decision log [FIXED]

| # | Date | Decision | ADR |
|---|---|---|---|
| D1 | 2026-09-30 | Stack: Python 3.12 + FastAPI + SQLite + psutil; TypeScript + Vite + PixiJS. | 0001 |
| D2 | 2026-09-30 | PixiJS renders **only** the Maple Room / sprite layer. Vitals, journal, timeline, observations, service health are normal DOM UI components. | 0002 |
| D3 | 2026-09-30 | v0.1 has exactly two owner interactions: **Greet** and **Pet**. They update real backend state, produce a short visible reaction, and are cooldown/rate-limited. No feeding, inventory, currency, shops, gifts, or other game systems. | 0003 |
| D4 | 2026-09-30 | Service Health is **required** in v0.1. No subprocesses, no `systemctl`, no shell fallback. Core sees only a provider-independent `get_service_health()`. Provider order: (1) existing paolo-core monitoring data, (2) narrowly scoped read-only systemd D-Bus sensor, only for what (1) cannot supply. | 0004 |
| D5 | 2026-09-30 | Access model is **Tailscale**. Backend is localhost-only; exposed only to the tailnet. Never exposed to the public internet in v0.1. | 0005 |
| D6 | 2026-09-30 | Production heartbeat interval is **300 s**, configurable. Tests/simulations use injected fake time. An ordinary heartbeat never invokes an External Brain / LLM. | 0006 |
| D7 | 2026-09-30 | Simulations deterministic with fixed seed. Production randomness is controlled; seed/RNG state is persisted so restarts stay coherent. | 0007 |
| D8 | 2026-09-30 | **Observation** = factual machine/world event data. **Journal** = Maple's interpretation / life record. Separate in model, storage, API, and UI. v0.1 journal text from RuleBrain/templates. | 0008 |
| D9 | 2026-09-30 | 72-hour trial run is required before declaring v0.1 **stable**; it does not block earlier milestones or local visual testing. | 0009 |
| D10 | 2026-09-30 | Replaceable Brain interface as in §3.6. RuleBrain is the v0.1 default. No external LLM yet; adding one later must not change Maple's identity or core state model. | 0010 |
| D11 | 2026-09-30 | paolo-core's existing monitoring (a collector writing ~every 5 min to `/data/monitor/metrics.db`, also read by Grafana) is provider #1. **Do not add** Prometheus, node_exporter, Netdata, or any other monitoring stack. Its schema and unit names are runtime facts to be **surveyed in Phase 3**, not guessed. | 0011 |
| D12 | 2026-09-30 | v0.1 service allowlist (intent): Maplegotchi itself, the existing metrics collector, Grafana, Lycan Watch / Lycan updates, qBittorrent, Jellyfin, relevant backup / integrity-check timers or services. **No service auto-discovery.** Verified unit names are recorded in deployment config after the Phase 3 survey. Unknown/unavailable is shown as `unknown`, never inferred. | 0012 |
| D13 | 2026-09-30 | Web layer: **no Caddy in v0.1.** Frontend built to static assets and served by FastAPI/Starlette (same origin as API). FastAPI binds localhost; **Tailscale Serve** exposes it to the tailnet; **Funnel disabled**. Required HTTP security headers are set in the app. Keep compatible with adding Caddy later. | 0013 |
| D14 | 2026-09-30 | Interaction limits: Greet 60 s cooldown, Pet 30 s cooldown, global 10 interactions / 10 min. Cooldown and rate-limit state is persisted; restart cannot reset it. | 0014 |
| D15 | 2026-09-30 | Phase 3 includes an explicit **read-only survey** of the real paolo-core runtime before choosing/configuring the final service-health provider. Fake sensors/providers come first so development never depends on paolo-core access. | 0015 |
| S1 | 2026-09-30 | Security principles in §4.1. | 0016 |
| D16 | 2026-09-30 | paolo-core local time is **Asia/Bangkok (UTC+07:00, no DST)**; core's production default `utc_offset` is +07:00. The offset stays injectable for tests/simulations; core never reads the system timezone database. | 0017 |
| D17 | 2026-09-30 | Greet/Pet reactions are **transient**: each has an explicit `until` (v0.1: 8 s after the interaction). Presentation (active reaction, expression) is derived from a supplied `now`, so a reaction ends at `until` without a heartbeat, scheduler, or timer. | 0018 |
| D18 | 2026-09-30 | `sqlite3` stays inside the storage/data-access boundary. The external `/data/monitor/metrics.db` is read through a narrowly scoped **read-only external datasource** in `maplegotchi.storage.external` (read-only connection; SELECT-only API; no write, schema, or Maple-repository methods), fully separate from Maple's writable database. Service-health sensors depend on that datasource's read API and never import `sqlite3`. No sqlite3 exception for `sensors`. | 0019 |

---

## 1. What this project is

**Maplegotchi** hosts **Maple**, a digital being living in a Tamagotchi-style 2D room.

- Maple has its own **state**, **activities**, **heartbeat**, **journal**, **observations**, and **life timeline**.
- Maple **observes** its host, **paolo-core** (Ubuntu server), through **read-only** sensors, including service health.
- Maple **never modifies** external systems.
- The owner can **greet** and **pet** Maple.
- The UI is a window into Maple's real life: **what the UI shows must be what the backend state is.**

Maple's identity (name, persona parameters, history, memories) belongs to Maple's data — not to any code module and not to any LLM provider.

---

## 2. Fixed v0.1 scope [FIXED]

### In scope
1. **Maple Room** — PixiJS 2D room rendering Maple, the current activity, and interaction reactions.
2. **Character state** — needs/mood/energy/affection etc., persisted, with defined ranges and decay rules.
3. **Heartbeat** — periodic tick (300 s in production) that advances Maple's life.
4. **Behavior engine** — selects Maple's next activity from state + observations; deterministic given seed.
5. **Owner interactions** — Greet and Pet only, with cooldowns and rate limits.
6. **Journal** — Maple's interpretation of its life, generated by RuleBrain/templates.
7. **Observations** — factual records derived from sensor data.
8. **Life timeline** — append-only record of significant life events.
9. **Read-only paolo-core monitoring** — host metrics and **service health** for the allowlisted services, from existing monitoring data where practical.

### Out of scope for v0.1 (do not build, do not stub in a way that grants capability)
- GPT-style / free-form chat with Maple.
- Any external LLM / network Brain call.
- Feeding, inventory, currency, shops, gifts, mini-games, or any interaction other than Greet and Pet.
- Learning, self-modification, code experimentation, model training / fine-tuning.
- Any write, restart, kill, or config action against paolo-core or any other external system (including `/data/monitor`).
- Subprocesses and shell execution of any kind (including `systemctl`).
- Adding monitoring stacks (Prometheus, node_exporter, Netdata, …); service auto-discovery.
- Caddy or any other extra web server; multi-user accounts; public internet exposure (including Tailscale Funnel).

If a task seems to need something out of scope, **stop and ask** — do not add it "just a little".

---

## 3. Architecture

### 3.1 Tech stack
- **Backend [FIXED]:** Python 3.12, FastAPI (Starlette also serves static frontend), SQLite (WAL mode), psutil.
  **[PROPOSED]:** Pydantic v2, uvicorn, stdlib `sqlite3` with hand-written migrations, `dbus-fast` for the D-Bus provider (added only if the Phase 3 survey shows it is needed).
- **Frontend [FIXED]:** TypeScript, Vite, PixiJS for the room layer only. **[PROPOSED]:** Preact for DOM panels.
- **Transport [PROPOSED]:** REST for snapshots and interactions; Server-Sent Events (SSE) for live updates.
- **Runtime [FIXED]:** systemd service on paolo-core under dedicated unprivileged user `maple`; FastAPI on localhost; Tailscale Serve to the tailnet.
- **Tooling [PROPOSED]:** `uv`, `ruff` (lint + format), `mypy --strict`, `pytest`, `import-linter`, AST-based forbidden-API tests; `pnpm`, `eslint`, `tsc --strict`, `vitest`.

### 3.2 Repository layout
Packages marked (P0) exist as empty scaffolding after Phase 0; module files listed are created in the phase that implements them.
```
Maplegotchi/
├── CLAUDE.md  README.md
├── .github/workflows/ci.yml
├── scripts/check.sh                  # runs every local check CI runs
├── docs/
│   ├── architecture.md
│   ├── security-model.md
│   └── adr/                          # ADR per FIXED decision
├── backend/
│   ├── pyproject.toml  uv.lock
│   ├── src/maplegotchi/
│   │   ├── core/          (P1)       # pure domain logic, no I/O
│   │   │   state.py activities.py behavior.py heartbeat.py interactions.py        (P1)
│   │   │   timeline.py identity.py rng.py daytime.py parameters.py simulation.py (P1)
│   │   │   observations.py attention.py                                      (P3)
│   │   │   journal.py                                                        (Phase 4)
│   │   ├── brain/         (P0)       # interface.py, rule_brain.py
│   │   ├── sensors/       (P3)       # interface.py, system.py (psutil), fake.py, host.py, observe.py
│   │   │   └── service_health/ (P3)  # interface.py (get_service_health), monitor_db.py (#1),
│   │   │                             #   systemd_dbus.py (#2), fake.py
│   │   ├── storage/       (P2)       # datadir.py (write jail), db.py (open/birth), migrations.py,
│   │   │   │                         #   repositories.py, errors.py  — Maple's own writable DB
│   │   │   └── external/  (P3)       # interface.py (no sqlite3), sqlite_metrics.py (read-only),
│   │   │                             #   fake.py — for /data/monitor/metrics.db (D18); never writes
│   │   ├── runtime/       (P2/P3)    # clock.py, life.py (single writer), senses.py (wiring);
│   │   │                             #   scheduler loop with `run` later
│   │   ├── api/           (P0)       # app.py, routes_read.py, routes_interact.py, stream.py,
│   │   │                             #   static.py (serves built frontend), headers.py
│   │   ├── config.py                 # frozen settings + policy loaded at startup
│   │   └── cli.py                    # simulate (P1, fake time); run, migrate, check-config later
│   └── tests/
│       ├── unit/  security/  core/  storage/  runtime/  sensors/
│       └── (api/ as phases add it)
├── frontend/
│   ├── package.json  pnpm-lock.yaml
│   └── src/
│       ├── api/           (P0)       # typed client derived from backend OpenAPI
│       ├── room/          (P0)       # PixiJS only
│       └── ui/            (P0)       # DOM components
├── assets/                           # sprites, room art (Phase 6)
└── deploy/                           # Phase 7
    ├── systemd/maplegotchi.service
    ├── etc/maplegotchi/              # settings.toml, policy.toml templates (incl. verified unit names)
    ├── tailscale/serve.md            # Tailscale Serve setup; Funnel explicitly off
    ├── polkit/                       # defense-in-depth deny rule for user `maple`
    ├── survey/        (P3)           # read-only survey script + procedure; findings.md after running
    ├── verify/check_boundaries.py
    └── install.md
```

### 3.3 Components and dependency rules
```
  Browser (tailnet) ──HTTPS──► Tailscale Serve ──► FastAPI on 127.0.0.1 ──┬─ static frontend (same origin)
                                                                          └─ /api/*
                                                                                │
          ┌─────────────────────────── runtime/life (single writer) ────────────┤
          │                                                                     │
  sensors (read-only) ──readings──►  core (pure)  ◄── brain interface ── RuleBrain
  + service_health providers           │
     │  └─ systemd D-Bus (RO)          ▼
     ▼                             storage ──► MAPLE_DATA_DIR (/data/maple)   (Maple-owned, writable)
  storage.external (RO datasource) ──► /data/monitor/metrics.db               (external, read-only)
```

Dependency rules (enforced by import-linter + AST tests in CI):
- `core` imports nothing from `sensors`, `storage`, `api`, `runtime`, `config`, `cli`, and no I/O / clock / randomness modules. Time and RNG are injected.
- `core` depends on the `brain` **interface** only; `brain` implementations depend on `core` models only.
- `sensors` only read; they never import `api`, `runtime`, `brain`, Maple's writable storage, or `sqlite3`. From `storage` they may import only `maplegotchi.storage.external.interface` (D18; import-linter + AST tests).
- `maplegotchi.storage.external` never imports Maple's writable storage modules (`db`, `repositories`, `migrations`, `datadir`, `errors`) and vice versa (import-linter).
- `storage` is the only module that opens files for writing, and only inside `MAPLE_DATA_DIR`.
- `api` never mutates state directly; interactions are submitted to `runtime/life`. `api` does not import `sensors`.
- `runtime` is the only place concrete implementations (clock, sensors, providers, brain) are chosen.

### 3.4 The life loop, heartbeat, and interactions
All state mutations go through **one serialized writer** (`runtime/life`), so heartbeats and interactions never race.

**Heartbeat tick** (every `heartbeat_interval_s`, default **300**):
1. Collect `SensorReading`s and `get_service_health()` (per-source timeout; failure → `status="unavailable"` / `unknown`, never crashes the tick).
2. `observations.derive(readings, recent_history) -> [Observation]` — factual only.
3. `heartbeat.tick(state, observations, now, rng, brain)` — decay needs, advance activity, choose next activity, decide journal triggers.
4. Journal text comes from the **local** brain (RuleBrain). An ordinary heartbeat never calls an external Brain; `runtime` refuses to start if the heartbeat brain is not `local`.
5. Persist state, observations, journal entries, timeline events, and RNG counters in **one SQLite transaction**; then publish the snapshot over SSE.

**Missed ticks:** the gap is recorded on the timeline; catch-up is bounded (capped decay, no mass replay). Maple is never "killed" by downtime.

**Interactions** (Greet, Pet) [FIXED limits]:
- `POST /api/interactions/greet` and `/pet`; closed-enum action, no free-text payload.
- Processed immediately by `core.interactions.apply_interaction(state, kind, now, params)` → updated state, a transient `Reaction` (kind, variant, started_at, until), a timeline event.
- Reactions depend on real state (e.g. greeting a sleeping Maple yields a sleepy reaction) and are part of the backend snapshot.
- **Reactions are transient [FIXED, D17]:** active only while `started_at <= now < until` (8 s in v0.1). `state.expression_at(now)` / `state.active_reaction(now)` derive presentation from the supplied time, so the reaction ends without waiting for a heartbeat. The heartbeat only drops ended reactions as housekeeping.
- **Greet 60 s cooldown, Pet 30 s cooldown, global 10 interactions / 10 min.** Stored in core state and persisted; restart cannot reset them. Rejections return `429` with `retry_after`. [PROPOSED] repeated interactions have diminishing effect.

**Time:** `Clock` is injected. Production uses `SystemClock`; tests and `cli simulate` use `FakeClock` and advance instantly. No test sleeps for a heartbeat.

### 3.5 Service health
- Core-facing, provider-independent interface:
  `get_service_health() -> ServiceHealthReport` containing `[ServiceHealth(service_id, state: active|inactive|failed|activating|unknown, since, source, as_of)]`.
- `service_id` is a stable logical name (e.g. `grafana`); the mapping to verified systemd unit names and to monitoring-DB identifiers lives in root-owned deployment config, filled in after the Phase 3 survey.
- **Intended services** (D12): maplegotchi, metrics collector, grafana, lycan-watch/updates, qbittorrent, jellyfin, backup/integrity timers or services. No auto-discovery.
- **Provider order** (per service, no shell fallback):
  1. **Existing monitoring** — the sensor reads through the **read-only external datasource** `maplegotchi.storage.external.monitor_metrics` (D18, ADR-0019), which alone touches `/data/monitor/metrics.db`: SQLite URI `mode=ro` (plus `PRAGMA query_only = ON`), fixed parameterized SELECTs only, no INSERT/UPDATE/DELETE/DDL/ATTACH or write-capable method, short busy timeout, staleness check against the collector's ~5 min cadence. It does not reuse Maple's `LifeRepository` or `DataDir`. Schema is **not** assumed; queries are written only after the Phase 3 survey documents it.
  2. **`systemd_dbus`** — only for services/fields existing monitoring cannot supply. Uses only `org.freedesktop.systemd1.Manager.GetUnit` and `org.freedesktop.DBus.Properties.Get` of `org.freedesktop.systemd1.Unit.ActiveState` for allowlisted units (`GetAll` is permitted by this rule but not needed, so the client omits it). The concrete bus transport is added only if the survey shows it is needed. No `LoadUnit`, `Start*`, `Stop*`, `Restart*`, `Reload*`, `Kill*`, `Enable*`, `Set*`, or anything else. A test asserts no other method name can be sent.
  3. **`fake`** — dev/tests only; production config refuses it. Built first (D15).
- Missing/stale/unreadable data → `unknown`, visible in the UI. Never inferred.
- Implementation details, observation schema, status semantics, partial-failure rules, and the `server_attention` derivation: `docs/sensors.md` [PROPOSED].
- Host metrics (CPU, memory, disk, load, uptime, network, temps) may likewise come from the external monitoring datasource where practical, with `psutil` as the local read-only source otherwise. Decided after the survey.

### 3.6 External Brain boundary
- `Brain` protocol (e.g. `suggest_activity(ctx)`, `compose_journal(ctx)`, `compose_reaction(ctx)`) plus `kind: "local" | "external"`.
- The context passed to a Brain is an explicit, serialisable `BrainContext` built by `core` — never DB handles, file paths, sensor objects, or config.
- Brain output is **advisory**: `core` validates it and may ignore it. A Brain cannot write state, files, or call tools.
- Maple's identity lives in Maple's data and is passed *to* the Brain. Replacing the Brain must not change identity, state schema, or history.
- v0.1 ships only `RuleBrain` (`kind="local"`). No network calls, no API keys.

### 3.7 Randomness and determinism
- At Maple's birth a 256-bit `life_seed` is generated and stored in Maple's data.
- Randomness is derived per event from `(life_seed, stream, counter)` (e.g. `stream="tick"`, counter=`tick_id`). Counters persist in the same transaction as state.
- Restart resumes the same random sequence; any tick is reproducible from stored inputs.
- Simulations and tests use a fixed seed and `FakeClock`.

### 3.8 Observation vs Journal
| | Observation | Journal entry |
|---|---|---|
| Nature | Fact about the machine/world | Maple's interpretation / life record |
| Author | `core.observations` from sensor data | Brain (RuleBrain in v0.1) |
| Shape | kind, subject, value, threshold, source, observed_at | text + mood + `refs` to observation/event ids |
| Mutability | Immutable | Append-only |
| UI | Neutral "system facts" styling | Maple's voice / diary styling |

Journal entries may cite observations; observations never depend on journal text. Facts in the UI always come from observations.

### 3.10 Persistence and restart [PROPOSED — details in `docs/persistence.md`]
- One SQLite database, `MAPLE_DATA_DIR/maple.db` (production `/data/maple/maple.db`); STRICT tables, CHECK constraints, WAL + `synchronous=FULL`, foreign keys on; schema version = `PRAGMA user_version`, file marked with `application_id`.
- Canonical state = exactly the fields of `MapleState`; derived values (expression, active reaction, age) are never stored.
- One logical transition = one transaction (state row + interaction ledger + timeline events), guarded by an optimistic `revision`.
- `runtime/life.py` is the single writer: heartbeats and Greet/Pet share one lock; memory adopts a new state only after its commit succeeds.
- Birth happens once: the first life is built in a temporary file in rollback-journal (DELETE) mode, committed, closed, verified self-contained (no sidecars, non-WAL header), and only then published as `maple.db` with a non-overwriting link; WAL is enabled afterwards on the canonical file. Identity/seed are immutable (DB triggers); timeline is append-only (DB triggers).
- Restart loads and continues; downtime is one bounded catch-up heartbeat with a `DowntimeGap` event.
- Corrupt, empty, foreign, or too-new databases fail loudly and are never repaired or replaced automatically.
- Only `maplegotchi.storage` may write files or import `sqlite3` (AST-enforced); every write path goes through the `DataDir` guard. The external monitoring DB is read through `maplegotchi.storage.external` only (D18).
- Schema v2 adds an append-only `observation` table: each heartbeat's snapshot is stored in the same transaction as the heartbeat (~0.54 MB/day measured; retention is a later phase).

### 3.9 UI truthfulness
- The frontend holds no authoritative state; it renders the latest backend snapshot (REST on load, SSE thereafter).
- Animation/interpolation is allowed; inventing state is not.
- Interaction buttons show the server-reported cooldown; a reaction appears only once the backend returns one, and the UI stops showing it at the backend-provided `until`.
- Every snapshot carries `tick_id` and `as_of`. Silent SSE past keep-alive, or no tick for > 2 heartbeat intervals → visible stale/disconnected indicator.

---

## 4. Security model

### 4.1 Principles [FIXED]
1. External system access is **read-only** (this includes `/data/monitor/metrics.db` and systemd).
2. **No subprocesses and no shell** — no `subprocess`, `os.system`, `os.popen`, `os.exec*`, `os.spawn*`, `pty`, `multiprocessing`, `eval`/`exec`; no `systemctl`.
3. Maple's writable area in production is **`/data/maple` only**.
4. **Runtime code and Maple-owned writable data are separated.** Maple cannot write to its own code.
5. **Maple cannot modify its own security boundaries** — code, config, policy, service allowlist, systemd unit, Tailscale/polkit config.
6. The Brain is untrusted input; output is validated, never executed.
7. **Tailnet-only access.** App bound to localhost; Tailscale Serve only; Funnel off; no public exposure.

### 4.2 Filesystem layout on paolo-core [PROPOSED]
| Path | Owner / mode | Maple access | Purpose |
|---|---|---|---|
| `/opt/maplegotchi/` | `root:root` 0755, files 0644 | read | Backend code, venv, built frontend |
| `/etc/maplegotchi/` | `root:maple` 0750, files 0640 | read | settings.toml, policy.toml (service map, limits) |
| `/etc/systemd/system/maplegotchi.service` | `root:root` 0644 | none | Sandbox definition |
| `/etc/polkit-1/rules.d/50-maple-deny.rules` | `root:root` 0644 | none | Deny systemd management actions to `maple` |
| `/data/monitor/metrics.db` | existing owner (survey) | **read only** | Existing monitoring data (D11) |
| `/data/maple/` | `maple:maple` 0750 | read/write | Maple's DB, logs, backups |

How `maple` gets read access to `metrics.db` (group membership, ACL) and whether read-only open of its journal mode works without write access to `/data/monitor` are **Phase 3 survey items**; the chosen method must not grant `maple` any write access there.

### 4.3 Process sandbox (systemd) [PROPOSED]
`User=maple`, no login shell, no sudo, not in `docker`/`adm`/`sudo`/`systemd-journal`/any privileged group. Unit hardening, at minimum:
`NoNewPrivileges=yes`, `ProtectSystem=strict`, `ReadWritePaths=/data/maple`, `ReadOnlyPaths=/data/monitor`, `ProtectHome=yes`, `PrivateTmp=yes`, `PrivateDevices=yes`, `ProtectKernelTunables=yes`, `ProtectKernelModules=yes`, `ProtectControlGroups=yes`, `CapabilityBoundingSet=`, `AmbientCapabilities=`, `RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6`, `IPAddressDeny=any`, `IPAddressAllow=localhost`, `RestrictSUIDSGID=yes`, `LockPersonality=yes`, `MemoryDenyWriteExecute=yes`, `SystemCallFilter=@system-service`, `SystemCallFilter=~@privileged @resources`, `UMask=0027`.

### 4.4 In-process controls
- `storage/datadir.py` resolves every path and rejects writes outside `MAPLE_DATA_DIR` (incl. `..` and symlink escapes).
- The external monitoring datasource (`storage/external`, D18) opens only the configured path with `mode=ro` + `query_only`, exposes only SELECT-backed read methods, and has no write, schema, or Maple-repository API. Phase 3 adds an AST rule forbidding write SQL keywords and write methods in `storage/external`.
- D-Bus wrapper exposes only the three read calls in §3.5.
- Settings/policy load once at startup into frozen models; no code path writes them.
- Interaction endpoints: closed-enum actions, no body text, JSON `POST` only, `Origin`/`Host` check against the configured tailnet hostname, backend-enforced persisted cooldowns and global limit.
- App-layer security headers (minimal set): `Content-Security-Policy` (self only), `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `X-Frame-Options: DENY` / `frame-ancestors 'none'`, `Permissions-Policy` (deny all), `Cache-Control: no-store` on API responses.
- No secrets in the repo; v0.1 needs none.

### 4.5 Network exposure
- uvicorn binds `127.0.0.1:<port>` only and serves both `/api/*` and the built frontend (same origin).
- `tailscale serve` publishes that port to the tailnet over HTTPS. **Funnel is never enabled.** No public-interface listeners.
- The tailnet is the v0.1 trust boundary. Caddy may be added later without changing app code (same routes, headers movable).

### 4.6 Verifying the boundary
CI / tests:
- Forbidden-API AST tests over `backend/src` (subprocess/shell/exec/eval/process-kill APIs), plus stricter purity rules for `core` (no I/O, clock, or randomness). The scanner itself is unit-tested.
- Ruff security rules (`S`) + banned-API list.
- Import-linter contracts for §3.3.
- ESLint bans `eval`, `new Function`, `innerHTML`-style sinks in the frontend.
- Later phases add: path-jail tests; D-Bus method allowlist test; external monitoring datasource read-only tests (write attempts fail, API has no write methods); heartbeat external-Brain guard; cooldown persistence tests.

On paolo-core, `deploy/verify/check_boundaries.py` asserts §4.2, unit hardening, listening sockets (localhost only + Tailscale Serve), Funnel off, and that `maple` cannot write outside `/data/maple` (explicitly including `/data/monitor`).

---

## 5. Coding rules

- **Pure core.** No `datetime.now()`, `time`, `random`, file, network, env, or `asyncio` in `core/`.
- **Typed everything.** Pydantic models at boundaries; `mypy --strict` backend; `tsc --strict` frontend.
- **Fake time in tests.** `FakeClock` + fixed seeds; never sleep for a heartbeat. A simulated 30 days must run in seconds.
- **Don't guess external facts.** Monitoring schema, unit names, and file permissions on paolo-core come from the Phase 3 survey and are recorded in `deploy/survey/` and deployment config.
- **Schema-first data.** SQLite changes only via numbered migrations. Never edit a shipped migration.
- **Append-only history.** Observations, journal, timeline rows are never updated or deleted by runtime code.
- **Fail soft.** Failing sensors/providers, malformed Brain output, or missed ticks degrade gracefully and are recorded.
- **UTC timestamps**, ISO-8601 with timezone; localisation only in the UI. Core computes day/night from a caller-supplied `utc_offset` (production default +07:00, Asia/Bangkok, [FIXED, D16]); it never reads timezone databases.
- **Tuning constants are tunable, not architecture.** Need rates, behavior scores, thresholds, and durations may be retuned (with the pinned simulation digest updated deliberately). FIXED values (D14 limits, 300 s heartbeat default, 8 s reaction, activity/expression sets) are not tuning.
- **Deterministic arithmetic in core.** Only `+ - * /` on floats (no `exp`/`log`/`pow` with float exponents), which IEEE 754 rounds identically everywhere, so replays match across Windows and Linux. Iterate tuples/enums, never sets, when order affects RNG draws.
- **PixiJS for the room only**; panels and controls are DOM components.
- **Dev ports [PROPOSED]:** backend on `127.0.0.1:8470`; Vite dev server on `127.0.0.1` (Vite default port 5173) proxies `/api` to `8470` (`frontend/vite.config.ts`). The production port is set in deployment config (Phase 7) and is also localhost-only.
- **Config** via `MAPLE_CONFIG` and `MAPLE_DATA_DIR`. Dev defaults: `./var/config.toml`, `./var/maple-data/` (git-ignored). Dev profile may use a short heartbeat and fake sensors/providers; production config rejects fake providers. Code runs on Windows (dev) and Linux (prod) — use `pathlib`.
- **No speculative capability.** No hooks, flags, or stubs for chat, LLMs, learning, training, code execution, or extra game systems.
- **Line endings:** LF everywhere (`.gitattributes`).
- **Small, reviewable changes.** One concern per PR; update `docs/`, ADRs, and this file when architecture changes.

### Commands
Run from the repo root (Git Bash on Windows, bash on Linux/CI):
```
scripts/check.sh              # everything below

# backend (cd backend)
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run ruff check --config pyproject.toml ../deploy/survey          # survey script: same rules
uv run ruff format --check --config pyproject.toml ../deploy/survey
uv run mypy                                                         # src, tests, and ../deploy/survey (strict)
uv run lint-imports
uv run pytest
uv run maplegotchi simulate --days 30   # fake-time core simulation, prints JSON report + digest

# on paolo-core only, read-only (see deploy/survey/README.md)
python3 deploy/survey/survey_paolo_core.py > survey.json

# frontend (cd frontend)
pnpm install --frozen-lockfile
pnpm lint
pnpm typecheck
pnpm test
pnpm build
```

---

## 6. Development phases

The 72-hour trial run (Phase 8) gates only the **stable** v0.1 release.

| Phase | Goal | Exit criteria | Milestone |
|---|---|---|---|
| **0. Foundations** | Scaffolding, tooling, CI, ADRs, security checks, test scaffolding | All checks green on skeleton | — |
| **1. Core being** | state, activities, behavior, heartbeat, interactions (D14 limits), rng, identity — pure code | 30-day `FakeClock` sim deterministic for fixed seed; values in range; cooldown logic tested | — |
| **2. Persistence** | SQLite schema, migrations, repositories, write jail, single-writer life loop | Restart resumes state + RNG counters + cooldowns; downtime gap on timeline | — |
| **3. Senses** | (a) psutil sensors, observation derivation, `get_service_health()` + fake providers; (b) **read-only paolo-core survey**: `metrics.db` schema/cadence/permissions/journal mode, actual unit names for D12 services, what monitoring cannot supply; (c) read-only `storage.external` monitoring datasource + provider (D18), and `systemd_dbus` only for gaps | Fakes work without paolo-core; survey recorded in `deploy/survey/`; provider tests incl. read-only + method allowlists; `unknown` handled | — |
| **4. Inner life** | Journal (RuleBrain), timeline events, Brain interface, `local`/`external` guard | Journal cites observations/events; Brain swappable; guard test passes | — |
| **5. API** | Read REST, SSE, Greet/Pet endpoints, Origin check, security headers, static serving | OpenAPI schema; frontend types derived; 429 + `retry_after` tested; headers tested | **M1: headless Maple lives locally** |
| **6. Maple Room** | PixiJS room + sprites + activity/reaction animations; DOM panels; interaction buttons; staleness indicator | Every visible element traceable to an API field; local visual testing with fakes | **M2: local playable build** |
| **7. paolo-core deploy** | systemd unit, Tailscale Serve, polkit rule, verified service map, install doc, boundary verification | Runs sandboxed as `maple`; tailnet-only; `check_boundaries.py` passes | **M3: `v0.1.0-rc`** |
| **8. Trial run** | 72 h continuous run on paolo-core | DoD (§7) satisfied | **`v0.1.0` stable** |

---

## 7. Definition of Done — v0.1 stable

**Functional**
- [ ] Maple runs continuously on paolo-core as a systemd service under user `maple`.
- [ ] Heartbeat every 300 s (configurable); each tick persisted atomically with a `tick_id`.
- [ ] Character state evolves by documented rules; values always within defined ranges.
- [ ] Behavior engine selects activities from state + observations; any tick reproducible from stored inputs + `life_seed`.
- [ ] Greet and Pet work end-to-end: real state change, short state-dependent reaction, persisted cooldowns (60 s / 30 s) and global limit (10 / 10 min).
- [ ] No other interaction or game system exists.
- [ ] Host observations come from real paolo-core data (existing monitoring where practical, psutil otherwise).
- [ ] Service Health shown for the verified D12 service set, from `metrics.db` or the read-only D-Bus provider for gaps; `unknown` shown honestly.
- [ ] Journal entries (RuleBrain) reference the observations/events they interpret; observations and journal visibly distinct.
- [ ] Life timeline records birth, activity milestones, interactions, notable observations, downtime gaps; append-only.
- [ ] Maple Room (PixiJS) and DOM panels show Maple, activity, reactions, vitals, service health, journal, observations, timeline — all from the API.
- [ ] UI shows a clear stale/disconnected state when the backend is unreachable or ticks stop.
- [ ] Restart resumes Maple's life, RNG sequence, and cooldowns without data loss or reset.

**Security**
- [ ] No code path writes outside `MAPLE_DATA_DIR`; path-jail tests pass.
- [ ] No subprocess/shell/eval usage (tests + lint enforced); no `systemctl`.
- [ ] `metrics.db` opened read-only; `maple` has no write access to `/data/monitor`.
- [ ] D-Bus (if used) limited to the three read calls.
- [ ] No code path writes code, config, policy, or allowlists.
- [ ] Heartbeat never invokes an external Brain; guard test passes.
- [ ] App bound to localhost; served same-origin; security headers present; reachable only via Tailscale Serve; Funnel off; no public ports.
- [ ] `check_boundaries.py` passes on paolo-core.

**Quality**
- [ ] CI green: ruff, mypy strict, import contracts, forbidden-API tests, pytest; eslint, tsc strict, vitest, build.
- [ ] Deterministic 30-day `FakeClock` simulation passes with a fixed seed.
- [ ] 72-hour trial run on paolo-core: no crash, no unbounded memory/disk growth, SQLite integrity check passes, heartbeat cadence within tolerance.
- [ ] `docs/`, ADRs, `deploy/install.md`, `deploy/survey/`, and this file match what was built.

**Explicitly not required for v0.1:** chat, external LLM integration, learning, code experimentation, training/fine-tuning, extra game systems, extra monitoring stacks, Caddy, any action on external systems.

---

## 8. Future directions (not v0.1 — orientation only)
- External (LLM) Brain implementations behind the existing `Brain` interface, used only outside the ordinary heartbeat path.
- A separately sandboxed "lab" for learning / code experiments / model training with its own writable area and isolation, never sharing privileges with the core service.
- Caddy (or similar) if routing/web-serving needs grow.
- Richer owner interactions; per-user authorization (e.g. Tailscale identity).

Each requires its own design, security review, and explicit owner approval before any code is written.
