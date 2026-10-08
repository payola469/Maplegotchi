# Sensors and observations (Phase 3)

Status: implemented and approved (2026-09-30). Choices here are **[PROPOSED]**
unless they follow directly from a FIXED decision (noted inline).

## Overview

```
HostProbe (psutil | fake) ──► sensors/host.py ──┐
                                                ├─► observe_paolo_core() ──► ObservationSnapshot
ServiceHealthProvider chain ─► get_service_health() ┘            │
  1. monitor_db   (via storage.external read-only interface, D18) │
  2. systemd_dbus (read-only client, gaps only, D4)               ├─► core.attention ─► BehaviorInputs.server_attention
  3. fake         (dev/tests)                                     └─► stored with the heartbeat (observation table, v2)
```

Runtime (`runtime/senses.py`) is the only place concrete probes/providers are
chosen. Sensors never import `sqlite3`, `subprocess`, file-writing APIs, or
Maple's writable storage (AST tests + import-linter).

## Observation schema (`core/observations.py`)

Observations are facts only (D8): no interpretation, mood, or prose.

| Field | Meaning |
|---|---|
| `metric` | `cpu_usage`, `memory_usage`, `disk_usage`, `load_1m`, `load_5m`, `load_15m`, `cpu_count`, `temperature`, `service_state` |
| `subject` | what was measured: `cpu`, `memory`, a mount such as `/`, `system`, or a service id |
| `status` | `available` / `unavailable` / `unknown` / `error` |
| `value` | number, only when available (range-checked per metric) |
| `state` | systemd ActiveState, only for an available `service_state` |
| `unit` | derived from the metric: `percent`, `celsius`, `load`, `count`, `state` |
| `observed_at` | UTC timestamp of the snapshot |
| `source` | producer: `psutil`, `fake`, `monitor_db`, `systemd_dbus`, `service_health`, `host` |
| `reason` | reason code, required unless available, e.g. `no_temperature_sensors`, `monitor_db:not_surveyed;systemd_dbus:unit_not_configured` |

Status semantics:

| Status | When |
|---|---|
| `available` | a valid, in-range value was measured |
| `unavailable` | the metric does not exist here (platform/hardware lacks it; no probe) |
| `unknown` | it exists but cannot be determined now (not configured, not surveyed, source missing) |
| `error` | a source raised, or returned an invalid/out-of-range value (`invalid_value`) |

Value ranges: percentages 0–100, load 0–10 000, CPU count 1–4096,
temperature −40–150 °C. Out-of-range, NaN, infinity, booleans, and non-numbers
become `error`/`invalid_value` — never stored as facts.

## Host sensors

`sensors/interface.py: HostProbe` (raw readings; raise `MetricUnavailable` for
honest gaps). `sensors/system.py: PsutilHostProbe`:

| Metric | Source | Notes |
|---|---|---|
| CPU usage | `psutil.cpu_times()` deltas | busy share since the previous reading (≈ the 5-min heartbeat); first reading is `unavailable: warming_up` |
| Memory | `psutil.virtual_memory().percent` | |
| Disk | `psutil.disk_usage(mount)` | mounts configured (default `/`) |
| Load 1/5/15 | `psutil.getloadavg()` (`/proc/loadavg`) | Linux only; elsewhere `unavailable: not_supported_on_platform` (psutil would emulate with early zeros) |
| CPU count | `psutil.cpu_count()` | used to judge load per CPU |
| Temperature | `psutil.sensors_temperatures()` (`/sys/class/hwmon`) | preferred chips `coretemp`, `k10temp`, `zenpower`, `cpu_thermal`, `soc_thermal`, `acpitz`; within the chosen chip the `Package id 0` reading (paolo-core: coretemp, Stage A), else the hottest reading; none → `unavailable` |

No subprocess, shell, writes, privileged calls, or network for host metrics.

## Partial-failure semantics

- Each metric is read in its own guard. `MetricUnavailable` → `unavailable`;
  any other exception → `error: provider_error:<exception type>`; invalid value
  → `error: invalid_value`. Other metrics are unaffected.
- The three load windows come from one read and share its outcome.
- Each service-health provider is called once per pass in its own guard; a
  raising provider becomes a reason (`<source>:provider_error_<type>`) and the
  next provider is still asked.
- No host probe at all → every host metric `unavailable: no_host_probe`.
- A snapshot is always produced; it may contain any mix of statuses.

## Service health (D4, D12)

`get_service_health(targets, providers, now)` is provider-independent:
for each service, providers are asked in priority order; the first
`available` answer wins; otherwise the service is `unknown` with every
provider's reason joined by `;`. There is no shell/`systemctl` fallback.

`INTENDED_SERVICES` keeps the D12 intent (logical ids, no unit names). The
production map is `runtime/senses.py:PAOLO_CORE_SERVICES`, verified by the
Stage A survey (`deploy/survey/findings.md`, ADR-0021). No auto-discovery.

| service_id | Target | How it is observed |
|---|---|---|
| `maplegotchi` | `maplegotchi.service` | systemd D-Bus |
| `metrics_collector` | `personal-ai-monitor.service`, timer `personal-ai-monitor.timer` | `metrics.db` freshness first, then systemd D-Bus |
| `backup` | `paolo-core-backup.service`, timer `paolo-core-backup.timer` | systemd D-Bus |
| `grafana` | `unobservable="docker_container"` | none: `unknown`, `not_observable:docker_container` |
| `lycan_watch` | `unobservable="no_systemd_unit"` | none: `unknown`, `not_observable:no_systemd_unit` |

qBittorrent and Jellyfin were not found on paolo-core and are not in the map.
A target with `unobservable` set is reported without asking any provider.
Such `not_observable:*` gaps are shown as `unknown` but do not stop the server
summary from being calm (they are a known limit of Maple's senses; owner-approved
rule, ADR-0021). Every other gap still counts: stale collector data, D-Bus
errors, missing units or required observations make it "unclear", and a failed
service makes it troubled.

| Provider | Behavior |
|---|---|
| `monitor_db` | Answers only for `metrics_collector`, through `storage.external.interface.MetricsSource`: schema must have `metrics.ts`; `MAX(ts)` (Unix epoch seconds) no older than 660 s (two 300 s cadences + 60 s) → `active`. Otherwise `unknown` with `stale_data`, `no_rows`, `timestamp_in_future`, `invalid_timestamp`, `wrong_schema`, `source_missing`, `source_unreadable` (includes a hot rollback journal, which read-only SQLite refuses to replay). Every other target: `not_recorded`. The legacy `ollama_ok`/`n8n_ok`/`discord_bot_ok`/`docker_ok` columns are never read. |
| `systemd_dbus` | `ReadOnlySystemdClient` sends only `Manager.GetUnit(unit)` and `Properties.Get(org.freedesktop.systemd1.Unit, ActiveState)` to `org.freedesktop.systemd1`, for units on the allowlist derived from the map; everything else raises before reaching the transport. Timer-driven targets: service `failed` → failed; service running → its state; service `inactive` → the timer's state. Reasons: `unit_not_configured`, `bus_unavailable`, `unit_not_loaded`, `permission_denied`, `dbus_timeout`, `unexpected_reply`, `unrecognized_state`, `call_refused`, `dbus_error`. |

The transport (`dbus_transport.py`, dbus-fast, ADR-0022) re-checks the same
two-call allowlist, sets `NO_AUTO_START`, uses a 2 s timeout and one short-lived
connection per call, and turns every failure into a `DbusCallError`. CLAUDE.md
allowed `Properties.GetAll`; it is not needed, so neither layer permits it.
On Windows (development) `dbus_fast.aio` cannot load, so the provider reports
`bus_unavailable`.

## External metrics datasource (D18, ADR-0019)

`maplegotchi.storage.external`:

| Module | Role |
|---|---|
| `interface.py` | `MetricsSource` protocol (`describe_schema`, `sample_rows`, `max_value`, `close`), schema report types, `SchemaExpectation`, `check_schema`, `ExternalSourceError`. No `sqlite3`. Sensors import only this. |
| `sqlite_metrics.py` | `SqliteMetricsSource`: `mode=ro` + `PRAGMA query_only = ON` (verified) + defensive + `trusted_schema=OFF`. Schema discovery, at most 5 newest rows of a *discovered* table, and `MAX(column)` of a *discovered* table and column (identifiers validated against the schema, then quoted). No arbitrary SQL, no write/schema/migration method. Missing file → `missing` (never created); non-database → `unreadable`. |
| `fake.py` | `FakeMetricsSource` for tests/dev. |

Separation from Maple's writable storage is enforced by import-linter in both
directions, and the AST scanner treats `storage/external` as a non-writer that
may import `sqlite3`. A test forbids write-SQL keywords in its string
constants. The only production query is `MAX(ts)` of `metrics` (Stage A schema).

## server_attention derivation (`core/attention.py`)

Observations stay canonical; `server_attention` is derived, bounded to 0–1,
capability-free, and only biases the `observe_server` score.

| Fact (available only) | Threshold → contribution |
|---|---|
| CPU usage | ≥ 75 % → 0.3; ≥ 90 % → 0.6 |
| Memory usage | ≥ 80 % → 0.3; ≥ 90 % → 0.6 |
| Disk usage (any mount) | ≥ 85 % → 0.4; ≥ 95 % → 0.8 |
| Temperature | ≥ 75 °C → 0.4; ≥ 85 °C → 0.8 |
| 1-min load ÷ CPU count | ≥ 1.0 → 0.25; ≥ 2.0 → 0.5 |
| A service `failed` | 0.8 (inactive/activating: 0 — timers are often inactive) |

Result = **maximum** contribution (never a sum). Unavailable/unknown/error data
contributes nothing, so gaps never create concern. Deterministic and
order-independent; each crossed threshold is named in `reasons`
(e.g. `disk_usage:/>=95`) for later use by the Journal.

## Persistence (migration v2)

A dedicated append-only `observation` table (not `timeline_event`), written in
the **same transaction** as the heartbeat that used the snapshot, keyed by
`tick_id`, `UNIQUE (tick_id, metric, subject)`, with CHECKs mirroring the core
invariants and triggers forbidding UPDATE/DELETE.

Storage growth (measured): 15 observations per heartbeat (8 host with one mount
+ 7 services) × 288 heartbeats/day = 4 320 rows/day ≈ 124 bytes/row incl. index
≈ **0.54 MB/day ≈ 196 MB/year**. That measurement predates the Stage A map.

The production map (D20) has 5 services, so production writes 8 + 5 = 13 rows per
heartbeat, about 0.46 MB/day at the same row size. Retention (e.g. downsampling old
rows) is a later phase; nothing is deleted now, so the table grows without bound.
A retention ADR is proposed in `docs/architecture/maple-future-architecture.md` §15
(PROPOSED).

## paolo-core survey

`deploy/survey/README.md` and `deploy/survey/survey_paolo_core.py` — a
read-only, stdlib-only survey (no commands, no writes) plus optional
owner-run read-only commands and a findings template. **Run on 2026-09-30
(Phase 7 Stage A)**; results are in `deploy/survey/findings.md` and led to
the production service map (D20, ADR-0021), the D-Bus transport (D21) and the
psutil host-metric choice.

## What Maple does not observe today

These gaps are documented and intentional for v0.1/v0.2:
- **Not collected:**
  - swap, network interfaces and I/O, disk I/O;
  - GPU;
  - `/data` disk usage (only `/` is configured, and `/data` is hidden by the unit's tmpfs);
  - per-process data (psutil `Process` is unused, and the unit sets `ProtectProc=invisible`);
  - logs or journald (no journal access, and the account has no `systemd-journal` group);
  - Docker state (no Docker socket).
- **metrics.db:** it records more than Maple reads (swap, GPU, data disk, uptime), but Maple reads only `MAX(ts)`.
- **monitor-v2:** `/data/monitor-v2` exists on paolo-core but is hidden from Maple.

A read-only System Investigator that would widen this is **DRAFT / PROPOSED / FOR
HUMAN REVIEW** only (`docs/architecture/maple-future-architecture.md` §8). It needs
its own ADRs and amendments to D12, D20 and D21 before any change.
