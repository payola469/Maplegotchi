# ADR-0037: World persistence, the R1b schema-v11 migration, and the legacy projection

- **Status:** Accepted — FIXED design (CLAUDE.md D36). **NOT IMPLEMENTED.** No migration is written. Implementation is not yet authorized. Exact table and column shapes are [PROPOSED] and are fixed in the migration PR, which must follow the ADR-0028 R1–R8 discipline.
- **Date:** 2026-10-08
- **Decided by:** owner, Maple Room review decisions **B10** (R1 staging and cutover), **B13** (baseline A10, A17), together with **B2** and **B8** (the initial house).
- **Extends:** ADR-0028 (schema policy, rollback/recovery), ADR-0023 (owner migration gate), ADR-0024 (backup). **Related:** ADR-0035, ADR-0036, ADR-0038, ADR-0039, ADR-0040.

## Context

The world must survive restarts and deploys (roadmap R3), and the renderer must not be the source of truth. Today `life_state` stores `activity`, `location` (CHECK enum `RoomLocation`), `point_id`, and a route as `[[x, y, distance, node], …]` in the 1000×600 space. Enum lists are literal CHECK constraints, so adding a value means rebuilding the table, as v4 did. Production runs schema v10 with an irreplaceable `maple.db`.

## Decision

### 1. Persistence model (A10)
- **Layout revisions** are immutable, validated documents covering rooms, doors, object instances, room themes and lighting presets.
  - They live in an append-only table with `id`, `created_at`, `author` (`paolo | migration`), `base_revision`, catalog version/hash, the document, and a validation digest.
  - A small `world_state` row points to the active revision.
  - Every owner edit creates a new revision. Revert = a new revision copying an old one (ADR-0038).
- **Display placements** live in a separate small table (current placements, with append-only history in world events), so Maple's slot placements and the owner's layout edits do not collide (ADR-0039).
- **Visual state is derived where possible:**
  - shelf fullness;
  - occupied seats;
  - lamp on/off by day phase;
  - console state.

  Only true state is stored.
- **Maple's position** lives in `life_state` as `(tx, ty)` on the house grid, plus the route waypoints (ADR-0035). The room is derived from the region.

### 2. Lookup tables instead of CHECK enums (A17)
The R1b v11 migration replaces literal CHECK enums for activity kinds and location/room kinds with **lookup tables plus foreign keys**. Future activities or room kinds then become row inserts, not table rebuilds. `RoomLocation` is retired in favour of instance points; legacy values stay derivable (§4).

### 3. Staging and the single production cutover (B10)
- **R1a: engine first. No production world change.**
  - Build the house grid, object catalog, capability resolution, deterministic A\*, the new renderer behind the feature flag, the art pipeline and validator, and placeholder/test art.
  - Exercise them only with development data, fixtures and the deterministic simulation.
- **R1b: one production cutover.**
  1. **Rehearse** schema v11 on a **copy of the production database** (owner-taken snapshot), with in-transaction verification and the restore path.
  2. Run **one production migration directly into the final initial house** (B2/B8): all 8 room regions reserved; 5 functional rooms open (Central Hall, Bedroom, Living Room, Library, Work Studio) with today's furniture as instances; 3 closed placeholders (Creation Room, System Room, Future Space).
  3. Maple's backend movement switches to the grid at that point.
- **Production never passes through a temporary single-room tile layout.**
- **v11 verification and safety, unchanged from ADR-0028:**
  - forward-only;
  - one `BEGIN IMMEDIATE` transaction;
  - in-transaction verification (identity, `born_at`, seed, counters, history counts and max ids, `foreign_key_check`);
  - the converted state must load through core invariants;
  - an automatic verified `pre-migration/` copy, and the **owner snapshot gate** (`activate_release.sh --allow-migration` only after `maple-db-snapshot stage`);
  - no fabricated timeline events. A route in flight at migration becomes a zero-length plan at its destination's new point, as ADR-0027 did for v4.
- **Determinism:** the pinned 30-day simulation digest and location-specific tests are updated deliberately in the same change.
- **Recovery:** forward-fix is preferred. Returning to a v10 release is an owner-run restore of the pre-migration copy, which loses life lived since then (ADR-0028 R5/R6).

### 4. Legacy projection (B10)
- While the old 1000×600 view remains the default (ADR-0040), the backend keeps emitting the legacy fields (`activity.location`, a legacy `position`, legacy `point`/`facing` where applicable). They come from a **deterministic projection** of the new world: each object instance or capability maps to the corresponding legacy anchor (e.g. any Writing Desk instance → `desk`; the Hall's open floor → `rug`).
- The old view uses its existing fallback walker between projected anchors.
- The legacy view is a **transitional, simplified projection of the same backend truth**. It is never a separate state.
- The projection is pure and unit-tested. It is removed only together with the old view, in a separate change at least one full release after the default switch (ADR-0040).

## PROVISIONAL / [PROPOSED]
- Exact table names, columns and JSON document schema.
- The layout document size cap.
- The legacy-projection mapping table.
- `GET /api/world*` DTO shapes. Additive APIs: `/api/room` remains as a compatibility view during the transition, and the route-table test is updated deliberately.

## Deferred
- Stored object state set by Maple.
- Representation contents (project / library / creation / report objects). The `link` field and slot `accepts` exist as hooks only.
- Data retention for world history (covered by a future retention ADR).

## Consequences
- The world survives restart and deploy. The renderer is never authoritative.
- Production `maple.db` changes exactly once for the new world, after a rehearsal.
- **Future compatibility:** soft `link`s on instances and placements can later point at projects, library items or investigation reports without changing this persistence model.
