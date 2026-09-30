# ADR-0012: v0.1 service allowlist, no auto-discovery

- **Status:** Accepted — FIXED (CLAUDE.md D12)
- **Date:** 2026-09-30
- **Decided by:** owner

## Context
Only services the owner cares about should be watched.

## Decision
Intended set: Maplegotchi itself, the existing metrics collector, Grafana, Lycan Watch / Lycan updates, qBittorrent, Jellyfin, and relevant backup / integrity-check timers or services. No service auto-discovery.

## Consequences
- Core uses stable logical ids; the mapping to real unit names lives in root-owned deployment config.
- Real unit names are discovered in the Phase 3 survey and recorded there.
- Unknown or unavailable status is shown as `unknown`, never inferred.
