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
