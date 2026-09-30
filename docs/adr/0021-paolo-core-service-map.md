# ADR-0021: The paolo-core service map and sources, from the Stage A survey

- **Status:** Accepted — FIXED (CLAUDE.md D20). Refines ADR-0011/ADR-0012 for this deployment.
- **Date:** 2026-09-30
- **Decided by:** owner (Stage B locked decisions 5 and 7; the "by-design unknown"
  summary rule APPROVED in the Stage B review). The 660 s freshness window is a
  tunable implementation detail.

## Context
D11 assumed the existing monitoring database would supply service health. Stage A
found that `metrics.db` has one wide `metrics` row every ~300 s (`ts` in epoch
seconds) whose only service columns are legacy ollama/n8n/discord/docker flags —
none of D12's services. qBittorrent and Jellyfin do not exist on paolo-core, Grafana
runs in Docker, and Lycan Watch has no systemd unit.

## Decision
- Service map (code, `runtime/senses.py`): `maplegotchi` → `maplegotchi.service`;
  `metrics_collector` → `personal-ai-monitor.service` + `personal-ai-monitor.timer`;
  `backup` → `paolo-core-backup.service` + `paolo-core-backup.timer`;
  `grafana` → unknown (`not_observable:docker_container`); `lycan_watch` → unknown
  (`not_observable:no_systemd_unit`). qBittorrent and Jellyfin are not in this map.
- Unit state comes from the read-only systemd D-Bus provider. A timer-driven job
  reads `failed` if its last run failed, its running state while it runs, and
  otherwise the timer's state (`active` = scheduled).
- `metrics.db` contributes one fact: collector freshness (`MAX(ts)` within 660 s ⇒
  `metrics_collector` active). It is asked first; when stale or unreadable, D-Bus
  answers. The legacy flags are never read. psutil remains the host-metric source.
- `monitor-v2` is not Maple's collector.
- Observations whose reason starts with `not_observable:` (v0.1: Grafana, Lycan Watch)
  are shown as unknown but do not stop the server summary from being calm: they are
  a known limit of her senses, not a doubt about the present. Real failures, stale
  required data, D-Bus errors, missing required observations, and failed required
  services still make the summary unclear or troubled (APPROVED).

## Consequences
- No Docker socket, no new monitoring stack, no auto-discovery.
- Adding a service later is a reviewed code change to the map, which also widens
  the D-Bus unit allowlist.
