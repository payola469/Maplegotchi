# ADR-0011: Reuse paolo-core's existing monitoring data

- **Status:** Accepted — FIXED (CLAUDE.md D11)
- **Date:** 2026-09-30
- **Decided by:** owner

## Context
paolo-core already runs a metrics collector writing about every 5 minutes to `/data/monitor/metrics.db`, which Grafana reads.

## Decision
- Provider #1 for server/health information reuses this data where practical, read-only.
- Do not add Prometheus, node_exporter, Netdata, or any other monitoring stack.
- The database schema, cadence, permissions, and journal mode are runtime facts to be surveyed in Phase 3; nothing is guessed or hard-coded before then.
- Build and test against a fake provider first.

## Consequences
- The `monitor_db` provider opens the file with SQLite `mode=ro`, runs only fixed parameterized SELECTs, and checks staleness.
- `maple` gets read access only; the grant method is decided in the survey and must not give write access to `/data/monitor`.
