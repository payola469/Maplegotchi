# Architecture Decision Records

Each FIXED decision in `CLAUDE.md` §0 has an ADR here. ADRs are immutable once
accepted; a changed decision gets a new ADR that supersedes the old one.

| ADR | Decision |
|---|---|
| [0001](0001-tech-stack.md) | Tech stack (D1) |
| [0002](0002-pixijs-room-only.md) | PixiJS renders only the room (D2) |
| [0003](0003-owner-interactions.md) | Greet and Pet only (D3) |
| [0004](0004-service-health-interface.md) | Service health interface, no subprocess (D4) |
| [0005](0005-tailscale-access.md) | Tailnet-only access (D5) |
| [0006](0006-heartbeat.md) | Heartbeat 300 s, fake time, no external Brain (D6) |
| [0007](0007-determinism.md) | Deterministic simulation, persisted randomness (D7) |
| [0008](0008-observation-vs-journal.md) | Observation vs Journal (D8) |
| [0009](0009-release-gating.md) | 72 h trial gates stable only (D9) |
| [0010](0010-brain-boundary.md) | Replaceable Brain, RuleBrain default (D10) |
| [0011](0011-existing-monitoring-source.md) | Reuse existing monitoring data (D11) |
| [0012](0012-service-allowlist.md) | Service allowlist, no auto-discovery (D12) |
| [0013](0013-web-layer.md) | Same-origin FastAPI + Tailscale Serve (D13) |
| [0014](0014-interaction-limits.md) | Interaction limits (D14) |
| [0015](0015-phase3-survey.md) | Phase 3 paolo-core survey (D15) |
| [0016](0016-security-principles.md) | Security principles (S1) |
| [0017](0017-timezone.md) | Home timezone Asia/Bangkok, UTC+07:00 (D16) |
| [0018](0018-transient-reactions.md) | Transient interaction reactions (D17) |
| [0019](0019-external-monitoring-datasource.md) | Read-only external monitoring datasource in the storage boundary (D18) |
| [0020](0020-production-account-and-layout.md) | Service account `maple-svc`, layout, namespace sandbox (D19) |
| [0021](0021-paolo-core-service-map.md) | paolo-core service map and sources from Stage A (D20) |
| [0022](0022-systemd-dbus-transport.md) | systemd D-Bus transport with dbus-fast (D21) |
| [0023](0023-release-and-runtime.md) | Release model, CPython 3.12 via uv, rollback (D22) |
| [0024](0024-maple-database-backup.md) | Maple's database in the nightly backup (D23) |
| [0025](0025-external-brain-runtime-boundary.md) | External Brain via localhost runtime boundary (D24) |
| [0026](0026-ai-director.md) | AI Director, goals, priorities, decision transition (D25) |
| [0027](0027-room-interaction-points-and-movement.md) | Room interaction points, backend-modeled movement (D26) |
| [0028](0028-activity-set-v2-events-and-schema-v4.md) | Activity set v2, life events, schema v4 rollback/recovery (D27) |
| [0029](0029-reader-writer-tools.md) | Real reading/writing: approved sources, workspace in maple.db, provenance (D28) |
| [0030](0030-memory.md) | Memory tiers, relevant retrieval, preferences by evidence (D29) |
| [0031](0031-daily-reflection.md) | Daily Reflection: day summary, memory candidates, tomorrow intent (D30) |
| [0032](0032-discord-conversation.md) | Discord conversations with the same Maple (D31) |
| [0033](0033-brain-companion-packaging.md) | The Maple Brain companion, version-controlled and reproducible (D32) |
| [0034](0034-brain-health-observability.md) | Brain Health / Observability v1: companion model, reply latency (schema v10), read-only `/api/brain-health` (D33) |
| [0035](0035-world-model.md) | Maple Room world model: one house grid, derived room graph, flat 4-direction A\*, direction vocabulary, provisional feet-in-tile (D34; accepted design, not implemented) |
| [0036](0036-object-catalog-and-capabilities.md) | Object catalog, capability-based interaction, approach/occupy points, backend owns geometry (D35; accepted design, not implemented) |
| [0037](0037-world-persistence-v11-migration-and-legacy-projection.md) | World persistence, R1a/R1b staging, single schema-v11 cutover, legacy projection (D36; accepted design, not implemented) |
| [0038](0038-owner-edit-mode-and-owner-authentication.md) | Owner Edit Mode and defense-in-depth owner authentication (D37; accepted design, not implemented; Tailscale header spike pending) |
| [0039](0039-storage-and-maple-slot-placement.md) | Storage (not an inventory) and Maple's slot-only placement autonomy (D38; accepted design, not implemented) |
| [0040](0040-room-view-transition-and-acceptance-gate.md) | Legacy room stays default behind a flag; 5 open + 3 placeholder rooms; default-switch acceptance gate (D39; accepted design, not implemented) |
| [0041](0041-art-technical-contract.md) | Art technical contract rule set; face overlays; art file and palette locations; numeric values provisional (D40; accepted rules, values pending spike) |

## Template

```
# ADR-NNNN: Title
- **Status:** Proposed | Accepted | Superseded by ADR-XXXX
- **Date:** YYYY-MM-DD
- **Decided by:**
## Context
## Decision
## Consequences
```
