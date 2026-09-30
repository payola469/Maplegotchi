# paolo-core survey findings — 2026-09-30 (Phase 7 Stage A)

Recorded from the owner-run, read-only Stage A: `survey_paolo_core.py`
(`survey.json`) plus `owner_checks.sh` (systemctl/ls/ss/tailscale output), both
run as the owner's normal user at 2026-09-30 18:42 +07. The raw outputs stay out
of the repository (they list unrelated services, containers, and listeners); the
facts Maple depends on are below. These findings are the source of truth for
Phase 7; where they differ from earlier intent (D12), the difference is recorded
in ADR-0021.

## Host
- Ubuntu 26.04.1 LTS, kernel 7.0.0-31-generic, x86_64, 12 logical CPUs, 11.0 GiB RAM.
- System Python **3.14.4** (Maple does NOT use it; D1 keeps 3.12 via uv-managed CPython,
  ADR-0023). SQLite 3.46.1. `psutil` not installed system-wide (it will live only in
  Maple's venv). `uv` not installed; node v22.22.1 present, `pnpm` absent. git 2.53.0.
- Timezone: `/etc/localtime -> Asia/Bangkok` (`/etc/timezone` absent) — matches D16.
- `/data` is `/dev/sda`, **ext4**, local (WAL is safe for Maple's database); 59.5 % free.
- `/data/maple` does not exist yet. No `maple-svc` account yet.

## Monitoring database (`/data/monitor/metrics.db`)
- Owner `paolo:paolo` (1000:1000), mode **0644**; `/data/monitor` is `paolo:paolo` 0755.
  World-readable, so `maple-svc` needs **no** group or ACL grant; it never gets write access
  (the systemd unit also binds `/data/monitor` read-only).
- **journal_mode = delete** (rollback journal, not WAL); no `-wal`/`-shm`/`-journal` sidecar
  at survey time. `user_version = 0`, `application_id = 0`. Opened with `mode=ro` +
  `query_only` successfully by an unprivileged user.
  A hot rollback journal cannot be replayed read-only: Maple reports `unknown` (tested).
- Tables: `metrics` (8952 rows), `ai_requests` (53 rows, not used by Maple), `sqlite_sequence`.
- `metrics`: one **wide row about every 300 s**; `ts INTEGER NOT NULL` = **Unix epoch seconds**
  (index `idx_metrics_ts`). Newest rows 300 s apart (1790767741, …8041, …8341).
  Columns: `cpu_usage, cpu_temp, gpu_usage, gpu_temp, vram_used_mb, vram_total_mb,
  ram_used_mb, ram_total_mb, swap_used_mb, swap_total_mb, root_used_gb, root_total_gb,
  root_used_pct, data_used_gb, data_total_gb, data_used_pct, ollama_ok, n8n_ok,
  discord_bot_ok, docker_ok, uptime_seconds`.
- Service flags cover only **legacy ollama / n8n / discord bot / docker** — none of Maple's
  allowlisted services. They are **not** a service-health source for Maple.
- Writer: `personal-ai-monitor.service` (oneshot, `User=paolo`,
  `/usr/bin/python3 /home/paolo/services/monitor/collect_metrics.py`) triggered by
  `personal-ai-monitor.timer` (`OnBootSec=2min`, `OnUnitActiveSec=5min`, `Persistent=true`).

**Use in v0.1:** psutil stays the live source for CPU/RAM/disk/load/temperature. From
`metrics.db` Maple reads exactly one fact: `MAX(ts)` of `metrics`, i.e. whether the
collector wrote recently (fresh ≤ 660 s = two cadences + 60 s slack).

## Service allowlist (D12) — verified names
| service_id | unit(s) | source | v0.1 result |
|---|---|---|---|
| maplegotchi | `maplegotchi.service` (created in Stage C) | systemd_dbus | state of the unit |
| metrics_collector | `personal-ai-monitor.service` + `personal-ai-monitor.timer` | monitor_db freshness, then systemd_dbus | active if fresh; else unit state |
| backup | `paolo-core-backup.service` + `paolo-core-backup.timer` (daily 03:30, `Persistent=true`, oneshot as root, `ConditionPathIsMountPoint=/data`) | systemd_dbus | unit state |
| grafana | Docker container `grafana` (grafana/grafana:latest, host port 3000) — no systemd unit | none (no Docker socket for Maple) | `unknown` (`not_observable:docker_container`) |
| lycan_watch | no dedicated unit found (`/data/lycan-watch` exists; `ai_requests` rows come from `lycan_updates`) | none | `unknown` (`not_observable:no_systemd_unit`) |
| qbittorrent | **not found** | — | removed from this deployment's map |
| jellyfin | **not found** | — | removed from this deployment's map |

Not Maple's collector: `monitor-v2-collector.{service,timer}` (every minute, user
`monitor-v2-svc`, `/data/monitor-v2`, "proposed") and `monitor-v2-grafana-publish`.
`ai-metrics-logger.service` (a `paolo` user service) is unrelated to `metrics.db`.

## systemd over D-Bus
- `org.freedesktop.systemd1` is on the system bus and readable by an ordinary user
  (`busctl --system list`); `GetUnit` + `Properties.Get(ActiveState)` need no polkit
  authorization. → provider #2 is implemented (dbus-fast, ADR-0022).

## Temperatures
- hwmon chips: `coretemp` (`Package id 0` 49 °C, Core 0–5), `acpitz`, `nvme`,
  `pch_cannonlake`, `iwlwifi_1`; thermal zones include `x86_pkg_temp`.
- Maple uses psutil's `coretemp` **`Package id 0`** (falls back to the hottest reading of the
  first preferred chip present; `unavailable` if there is none — never invented).

## Network / exposure
- Nothing listens on **8470**. Existing public listeners (0.0.0.0): 22, 139/445 (Samba),
  3000 (Grafana), 5678 (n8n) — outside Maple's scope, noted only.
- Tailscale up (node `paolo-core`). **No Serve config, no Funnel config.**
- Docker present (grafana, n8n). The owner is in `docker`; `maple-svc` will not be.

## Backup
- `paolo-core-backup.service` runs `/usr/local/sbin/paolo-core-backup` as root daily at
  03:30; last run succeeded (status 0). It does **not** back up `/data/maple` yet.
  `/data/monitor/backup_alert_state.json` (root, 0644) suggests alert-state handling.
  The script's contents were **not** captured in Stage A; the exact patch is finalized
  against it in Stage C (deploy/backup/README.md).

## /data siblings Maple must not see
`archive, atlas, backups, downloads, logs, lost+found, lycan-watch, media, monitor-v2,
pre-reinstall-backup, private, raw, research-worker, sources` — several are world-readable
(0755), so the systemd mount namespace (`TemporaryFileSystem=/data:ro` + binds) is the
control that hides them, verified by `deploy/verify/sandbox_probe.sh`.
