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
| Temperature | `psutil.sensors_temperatures()` (`/sys/class/hwmon`) | preferred chips `coretemp`, `k10temp`, `zenpower`, `cpu_thermal`, `soc_thermal`, `acpitz`; max current reading; the survey confirms the right chip |

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

Targets (`INTENDED_SERVICES`) are the D12 logical ids — `maplegotchi`,
`metrics_collector`, `grafana`, `lycan_watch`, `qbittorrent`, `jellyfin`,
`backup` — with **no unit names**. Verified unit names come from the survey
and will live in deployment config. No auto-discovery.

| Provider | Phase 3 behavior |
|---|---|
| `monitor_db` | reads only through `storage.external.interface.MetricsSource`. With no surveyed `SchemaExpectation`: `not_surveyed`. Otherwise `source_missing` / `source_unreadable` / `wrong_schema`, or `query_not_configured` until surveyed queries exist. |
| `systemd_dbus` | `ReadOnlySystemdClient` can send only `Manager.GetUnit(unit)` and `Properties.Get(org.freedesktop.systemd1.Unit, ActiveState)` to `org.freedesktop.systemd1`, for allowlisted units; everything else raises before reaching the transport. Reasons: `unit_not_configured`, `bus_unavailable`, `unit_not_loaded`, `dbus_error`, `unrecognized_state`. |

No D-Bus library is added yet: the concrete transport is added only if the
survey shows monitoring cannot supply service state. Until then the production
wiring reports `bus_unavailable`/`unit_not_configured`. CLAUDE.md allowed
`Properties.GetAll`; it is not needed, so the client is narrower and omits it.

Today, on any machine, every service therefore reads
`unknown: monitor_db:not_surveyed;systemd_dbus:unit_not_configured` — honest,
not inferred.

## External metrics datasource (D18, ADR-0019)

`maplegotchi.storage.external`:

| Module | Role |
|---|---|
| `interface.py` | `MetricsSource` protocol (`describe_schema`, `sample_rows`, `close`), schema report types, `SchemaExpectation`, `check_schema`, `ExternalSourceError`. No `sqlite3`. Sensors import only this. |
| `sqlite_metrics.py` | `SqliteMetricsSource`: `mode=ro` + `PRAGMA query_only = ON` (verified) + defensive + `trusted_schema=OFF`. Schema discovery and at most 5 newest rows of a *discovered* table. No arbitrary SQL, no write/schema/migration method. Missing file → `missing` (never created); non-database → `unreadable`. |
| `fake.py` | `FakeMetricsSource` for tests/dev. |

Separation from Maple's writable storage is enforced by import-linter in both
directions, and the AST scanner treats `storage/external` as a non-writer that
may import `sqlite3`. A test forbids write-SQL keywords in its string
constants. The real schema is not assumed; queries are added after the survey.

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
≈ **0.54 MB/day ≈ 196 MB/year**. Retention (e.g. downsampling old rows) is a
later phase; nothing is deleted now.

## paolo-core survey

`deploy/survey/README.md` and `deploy/survey/survey_paolo_core.py` — a
read-only, stdlib-only survey (no commands, no writes) plus optional
owner-run read-only commands and a findings template. Not yet run.
