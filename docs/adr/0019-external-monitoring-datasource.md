# ADR-0019: Read-only external monitoring datasource inside the storage boundary

- **Status:** Accepted — FIXED (CLAUDE.md D18)
- **Date:** 2026-09-30
- **Decided by:** owner
- **Refines:** ADR-0004, ADR-0011 (where the monitoring provider lives and how it reads)

## Context
Phase 3 will read paolo-core's existing monitoring database, `/data/monitor/metrics.db` (ADR-0011). Phase 2 made `sqlite3` usable only inside `maplegotchi.storage`. Letting sensors import `sqlite3` would spread database access across layers and blur the line between Maple's own writable database and an external system Maple must never modify.

## Decision
- `sqlite3` remains confined to the storage/data-access boundary. There is **no** `sqlite3` exception for `sensors`.
- The external database is read through a narrowly scoped **read-only external datasource** in `maplegotchi.storage.external` (e.g. `monitor_metrics.py`).
- That datasource:
  - opens a read-only SQLite connection (`mode=ro`, plus `PRAGMA query_only = ON`);
  - exposes only SELECT-backed read methods, and no INSERT/UPDATE/DELETE, schema, ATTACH, or other write-capable API;
  - does not reuse or extend Maple's writable repository (`LifeRepository`) or the Maple data-directory guard (`DataDir`);
  - is configured with the external path from root-owned deployment config, separate from `MAPLE_DATA_DIR`.
- Service-health (and host-metric) sensors depend on that datasource's read API and never import `sqlite3` themselves.

## Consequences
- In Phase 3 the import-linter contracts change:
  - `sensors` may import `maplegotchi.storage.external` and nothing else from `storage`;
  - `storage.external` and Maple's writable storage modules may not import each other.
- In Phase 3 the AST security scanner gains read-only rules for `storage/external`: no write SQL keywords and no write methods.
- The external database is also protected at the OS level: the `maple` user gets read access only, and systemd sets `ReadOnlyPaths=/data/monitor` (Phase 7).
- Nothing is implemented in Phase 2; the schema remains unknown until the Phase 3 survey (ADR-0015).
