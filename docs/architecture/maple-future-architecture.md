# Maple future architecture: Room, Workspace, System Investigator

> **DRAFT · PROPOSED · FOR HUMAN REVIEW. NOT IMPLEMENTED.**
> - This document is an architecture proposal. None of the components, services, tables, endpoints, mounts, or units it describes exist in the code or on any host.
> - The current system is described by `CLAUDE.md` and `docs/*.md`.
> - Art values (tile 16 px, Maple frame 32×48, feet point (16, 47)) are **PROVISIONAL** until technical validation.

- **Status:** DRAFT for owner review. Every decision below is **[PROPOSED]**. Nothing here is FIXED until the owner accepts the matching ADR (§20).
- **Date:** 2026-10-08
- **Repository baseline:** branch `v0.2-development` @ `5be58c0`, schema v10.
- **Requirements source:** `docs/roadmap/maple-roadmap.md`, the product/capability roadmap. This document does not modify it.
- **Companion document:** `docs/architecture/maple-art-production-contract.md`, the art handoff contract (§10 summarises it).
- **Scope:** architecture and technical design only. This document contains no code, migrations, unit changes, permission changes, or deployment steps.

---

## 1. Executive summary

The roadmap asks for three linked subsystems:
- **Room:** a multi-room pixel world.
- **Workspace:** Maple creates, keeps, and runs real things.
- **System Investigator:** Maple explains problems on paolo-core.

The current codebase is a good base for all three. The base is not the room geometry or the frontend art. It is the *decision pipeline*:
- Director proposes.
- Core validates.
- One serialized writer commits one transaction.
- SSE publishes after the commit.
- The audit is append-only.

Every new capability in this document plugs into that pipeline as a new kind of proposal, validated transition, and stored record. None of them gets a side channel.

### Headline recommendations

| # | Recommendation | Why |
|---|---|---|
| 1 | **Turn the room from code into data.** A tile-grid world with a room graph, a release-shipped *object catalog* (engine metadata), and an owner-editable *layout* stored as immutable revisions in `maple.db`. | Today the room is a hard-coded 1000×600 side view in `core/room.py`. Furniture geometry exists only in the frontend, and activity→location is 1:1. None of that scales to many rooms, an editor, or growth. |
| 2 | **Use capability-based interaction resolution.** An activity needs capabilities. Interaction points on object instances provide them. A task can add requirements. Core picks among valid, reachable points with a seeded tie-break. | Satisfies the roadmap rule "no READ = bookshelf". New activities become data plus an enum migration, not new movement code. |
| 3 | **Use 4-direction movement on an integer grid with A\*.** | Manhattan costs are integers, so CLAUDE.md §5's deterministic-arithmetic rule holds without the declared-edge-length workaround used today. |
| 4 | **Workspace content as a content-addressed blob store** in a dedicated, fixed-size, `noexec` mount at **`/data/maple/workspace/`**. Metadata (projects, files, versions, artifacts) lives in `maple.db`. | Versioning, rollback, and "delete" (a tombstone) come for free. Maple never names a host path. The disk cap is enforced by the filesystem. A full workspace cannot starve `maple.db`. D19 ("`/data/maple` is the only writable path") stays literally true. |
| 5 | **Code execution in a separate, socket-activated, root-defined sandbox unit** (`maple-exec@.service`). It uses copy-in/copy-out over a Unix socket, has no network, no `/data`, a minimal root filesystem, and hard CPU/RAM/task/time/tmpfs limits. | The Maplegotchi backend keeps "no subprocess, no shell" (§4.1 #2) unchanged. The executor follows the same separate-boundary pattern as `maple-brain` (ADR-0025/0033). The caller cannot weaken the sandbox, because root defines it. |
| 6 | **A separate read-only `maple-observer` adapter service** for the data the main service must not see directly: process list, selected journald logs, wider `/proc`, Tailscale status. Closed-enum queries, bounded results, redaction *before* data leaves the adapter. | The main unit hides other processes (`ProtectProc=invisible`), has no journal access, and must not gain it. Raw logs and process command lines may contain secrets, so they should never reach `maple.db` or a model. |
| 7 | **The investigation engine is core rules plus runtime orchestration in the main backend.** Hypothesis catalog, evidence scoring, and confidence are computed by core. The Brain may only phrase explanations, which must cite stored evidence ids. | Keeps "Brain proposes, core decides" for diagnosis as well as action. Confidence is never model self-reported. |
| 8 | **Separate engine metadata from art metadata.** Footprint, collision, interaction points, capabilities, and slots are backend-authoritative (object catalog). Frames, anchors, layers, and animation timing are frontend presentation (art manifest). Both are joined by `object_type` id and cross-checked in CI. | Art can change without touching validation, and validation can change without re-exporting art. |
| 9 | **New FIXED decisions are needed** before implementation: about 12 ADRs (§20). Several current FIXED items need explicit owner amendments (§4.2). | Several roadmap items conflict with FIXED scope: inventory, code execution, owner mutations, modify/delete on the workspace. |

**No new microservice is proposed for the Room.** One process is added for the Workspace (the executor, only at W4), and one for the Investigator (the observer, at S1). Everything else stays in the existing backend.

---

## 2. Current architecture findings

This section describes the system as built (HEAD `5be58c0`), verified against the code, not only against the docs.

### 2.1 Process and service layout

| Service | Account | Listen | Writable | Network | Notes |
|---|---|---|---|---|---|
| `maplegotchi.service` | `maple-svc` (no shell/home/groups) | 127.0.0.1:8470 | `/data/maple` only (`TemporaryFileSystem=/data:ro` + `BindPaths=/data/maple`, `BindReadOnlyPaths=/data/monitor`) | `IPAddressAllow=localhost`, AF_UNIX/AF_INET | `MemoryMax=512M`, `TasksMax=64`, `MemoryDenyWriteExecute=yes`, `ProtectProc=invisible`, seccomp `@system-service` minus a long deny list, polkit denies all |
| `maple-brain.service` | `maple-brain-svc` | 127.0.0.1:8471 | `StateDirectory=maple-brain` (provider login) | outbound open (provider) | runs the provider CLI via `subprocess` (argv, no shell, scratch cwd, minimal env, timeout, refused auto-approve flags); MDWE deliberately unset (ADR-0033) |
| `maple-discord.service` | `maple-discord-svc` | none | none | outbound (Discord) | tokens via `LoadCredential`; calls Maple only on loopback; the only write is `POST /api/conversation/messages` (bearer token) |

The release layout follows D19/D22: `/opt/maplegotchi/releases/<sha>`, uv-managed CPython 3.12, root-owned, immutable. The backup is the nightly restic job; `maple.db` is staged through `maple-db-snapshot` (ADR-0024).

**Verified current runtime (2026-10-08):**
- All three services are active on paolo-core at release `160ed4fb9f2534a4609d826d9c4535cc7863ae3d`.
- The production database is at schema v10.
- The listeners are `127.0.0.1:8470` and `127.0.0.1:8471` only.

Also verified on the live host:
- `maplegotchi.service` hardening is loaded (`systemd-analyze security` 1.1 OK).
- `MAPLE_BRAIN`, `MAPLE_DIRECTOR` and `MAPLE_REPLIER` are `antigravity`, and `maple-brain` (`maple-brain-svc`) reports `provider=command`, `model=gemini-3.8-flash-medium`.
- Tailscale Serve and Funnel are tailnet-only.
- The nightly backup ran successfully on 2026-10-08, with the Maple DB snapshot staged (restic snapshot `8b7bea38`).

**Not verified:**
- the inside-service runtime boundary probe, which was not re-run (the verify scripts are not in the deployed release);
- restore.

See `docs/architecture.md` → Deployment state.

### 2.2 Backend layering (enforced)

- `core` is pure: an AST import allowlist and no I/O, clock, or randomness.
- `brain` is pure.
- `sensors` are read-only.
- `storage` is the only writer (the `DataDir` jail).
- `storage.external` is a read-only SQLite datasource.
- `api` talks to `runtime` and `core`.
- `runtime` wires the concrete implementations.

These rules are enforced by seven import-linter contracts plus the AST forbidden-API scanner (`tests/security/forbidden_apis.py`). The scanner forbids subprocess, pty, multiprocessing, `os.exec*/spawn*/fork/kill`, eval/exec/compile, `importlib.import_module`, `shutil.rmtree`, and `shell=True`. It forbids file writes outside `storage`.

### 2.3 Life loop and decisions

- `runtime/life.py:LifeRuntime` is the single writer.
  - One `threading.Lock` guards every transition.
  - Each transition is one `BEGIN IMMEDIATE` transaction guarded by an optimistic `revision`.
  - In-memory state is adopted only after the commit.
- `MapleService.step` (every 5 s): settle arrival → decide → heartbeat (every 300 s).
- **Decisions** (ADR-0026):
  1. The context is built under the lock.
  2. The Director is called *outside* the lock, with a hard deadline (default 15 s), and is never stacked.
  3. The result is re-validated against current state (`decide_proposal_committed`). A decision that is no longer due is recorded `stale`.
  - Verdicts: `accepted | clamped | rejected | fallback | stale`. Every non-accepted outcome falls back to rule direction in the same transition.
- **Replies** follow the same three-step pattern (`receive_message_committed` → unlocked `/reply` → `record_reply_committed`).
- **Finding (failure isolation):** the *journal* Brain (`ExternalHttpBrain`, `/generate`) is called from `_write_journal` **inside the writer lock**.
  - It uses a 30 s default timeout that is not configurable, with no redirect refusal and no response-size cap. The Director and Replier clients have both.
  - A slow companion can therefore stall every transition for up to 30 s when `MAPLE_BRAIN=antigravity`.
  - This predates the roadmap and is listed in §21 (R-01). The new subsystems must not copy this pattern.

### 2.4 Room (A1/A8, ADR-0027)

- **Geometry:** `core/room.py` defines one room as pure code.
  - Logical 1000×600 units, origin top-left, `FLOOR_Y=380`. It is a *front-elevation* view: back wall above, floor band below. It is not 3/4 top-down.
  - 9 `InteractionPoint`s (`id, location, x, y, facing, pose, allowed_actions`).
  - 7 `RoomLocation`s persisted in `life_state` (with CHECK constraints): `bed, desk, bookshelf, window, terminal, rug, sofa`.
  - Furniture identity comes from `FURNITURE_AT[location]`.
- **Navigation:** a fixed waypoint graph (5 lane nodes plus points) with **declared integer edge lengths**, so no runtime `sqrt` is needed. Dijkstra with a node-id tie-break. `WALK_SPEED=120` units/s.
- **Activity→place is effectively 1:1:**
  - `SPECS[activity].locations[0]` gives the location (`core/direction.py:429`).
  - A seeded draw among points happens only for `idle/walk` across the 3 open-area points.
- **Movement:** backend-modeled.
  - The `Route(departed_at, arrives_at, path, from_activity)` lives in `MapleState`. `activity_started_at == arrives_at`.
  - Phase is derived from `now`.
  - Mid-edge rerouting is supported.
  - The path is stored as JSON `[[x,y,distance,node],…]` in `life_state.route_path`.
- **API:** `GET /api/room` is static (it reads no state). Movement arrives per snapshot in `activity.{phase, point, furniture, pose, facing, position, route}`.
- **Frontend:**
  - PixiJS 8.21 with `antialias: true` and `resolution = min(DPR, 2)`.
  - A **fixed 1000×600 render target, CSS-scaled to the container**, so scaling is not integer.
  - **All art is procedural** (`Graphics` rectangles; Maple is a text-grid sprite composed into a canvas atlas at 24×28 px × `PIXEL=4` units).
  - No texture assets exist. `frontend/public/assets/` does not exist, and every `FURNITURE_ASSETS[*].texture` is unset.
  - No depth sort: Maple is always drawn above all furniture.
  - No camera or zoom. Pixi has no pointer interaction; hotspots are a DOM/SVG overlay.
  - Backend `facing` `front/back` and `activity.pose` are *ignored*. The frontend derives pose from `activity.kind` and facing from motion x-direction.
  - Furniture boxes, room size, anchors, and labels are duplicated in `frontend/src/room/layout/anchors.ts`.
  - Day/night is driven by backend `snapshot.day.phase`: a multiply darkness layer plus additive lamp and screen glow.

### 2.5 Persistence (schema v10)

- **Database:** one `maple.db`.
  - STRICT tables, WAL, `synchronous=FULL`, `trusted_schema=OFF`, defensive mode.
  - `application_id` `MAPL`; `user_version` = 10.
- **Migrations:** forward-only, one transaction each, optional in-transaction capture/verify.
  - From v4 on, an automatic verified `pre-migration/` copy is taken first. If that copy fails, nothing migrates.
  - Shipped migrations are frozen text. Enum lists are literal `CHECK (x IN (...))`, so adding an activity or location means a table rebuild (as v4 did).
- **Tables:**
  - Identity and immutables: `maple`.
  - Single-row state: `life_state` (plus the interaction ledger), `journal_state`.
  - Append-only: `timeline_event`, `observation`, `journal_entry` (+ refs), `goal`, `decision`, `action_event`, `document`, `tool_use`, `memory_event`, `daily_reflection`, `conversation_message`.
  - Mutable but undeletable: `memory`, with a fixed identity.
- **Workspace today (ADR-0029):**
  - The append-only `document` table: note/summary/reflection/research, title ≤ 80, body ≤ 4,000 chars.
  - A read catalog by id: 5 release `library:*` docs, Maple's 5 most recent documents, `journal:recent`, `server:status`, `memory:long_term`.
  - **No filesystem write path** beyond `maple.db`.
- `observation` grows about 0.54 MB/day with **no retention yet** ("retention is a later phase").

### 2.6 Senses

- **Host metrics:** psutil gives CPU (delta), memory %, disk % for `/` only, load averages, CPU count, and temperature (coretemp `Package id 0`).
- **Not collected:** swap, network, disk I/O, GPU, per-process data, logs.
- **Service health:** `runtime/senses.py:PAOLO_CORE_SERVICES`.
  - `maplegotchi`, `metrics_collector` (metrics.db freshness and D-Bus), and `backup` are observed via D-Bus `GetUnit` + `Get(ActiveState)`.
  - `grafana` (Docker) and `lycan_watch` (no unit) are `unknown` by design.
- **metrics.db:** has more than Maple reads, but Maple reads only `MAX(ts)`. D20 forbids using its legacy service flags. Available columns include swap, GPU, VRAM, data-disk, and uptime.
- **Other sources:** `/data/monitor-v2` (per-minute collector, schema unknown to this repo) exists but is hidden from Maple.
- **Attention:** `core/attention.py` gives a max-of-contributions score in [0,1], which drives priority signals.

### 2.7 Documentation drift found during this review

These items were found during this review. A documentation-only update on 2026-10-08 reconciled the docs and docstrings listed below. The current runtime on paolo-core has since been **verified** from owner-supplied live evidence and is recorded in `CLAUDE.md` and `docs/architecture.md`: `maplegotchi`, `maple-brain` and `maple-discord` are active at release `160ed4f…`, the schema is v10, and the listeners are 127.0.0.1:8470 and :8471. Hardening (loaded), the AI configuration, Tailscale and backup creation were verified later the same day. The Stage C authorization record, Phase 8, the inside-service boundary probe and restore stay unverified (OD-01, narrowed). No code behaviour was changed.

| Where | Drift |
|---|---|
| `docs/frontend.md` | Anchors table has no sofa; says "rest → rug"; describes 220 u/s presentation-only walking (the code now follows backend routes). |
| `docs/security-model.md` | Lists `runtime/life.py: require_rule_brain`. That function no longer exists; external Brains are accepted by `require_supported_brain`. |
| `brain/interface.py`, `runtime/life.py` docstrings | Say external brains are not implemented / are refused. |
| `api/stream.py` docstring | Lists 6 SSE kinds. `movement` and `life` are also published. |
| `docs/api.md` | "Three append-only stores", but its table lists seven. |
| `docs/sensors.md` | Says the survey has "not yet run". `deploy/survey/findings.md` records that it has. |
| `CLAUDE.md` status | Said Stage C / Phase 8 are not authorized while a deployment was running. **Reconciled 2026-10-08:** the current runtime is verified (all three services active at `160ed4f…`, schema v10). The 2026-09-30 authorization line is kept as history. Loaded hardening (1.1 OK), the AI switches, Tailscale tailnet-only and nightly backup creation are also verified. Stage C authorization, Phase 8, the inside-service boundary probe and restore remain unverified (OD-01). |

---

## 3. Existing components to reuse

| Component | Reuse as | Change needed |
|---|---|---|
| Director → core validate → commit pipeline (`core/proposal.py`, `runtime/service.py`) | The single path for every new Maple-initiated operation: move object, file edit, run job, investigation step | New proposal kinds; a versioned contract (`maple.decision.v2`, `maple.work.v1`) |
| Single writer + one-transaction commit (`runtime/life.py`, `repositories.commit`) | World, workspace metadata, investigation records | `commit` grows new record groups. Workspace blob writes happen *before* the commit (§7.6). |
| Append-only audit model (`decision`, `action_event`, `tool_use`, life-event envelope) | Provenance for world edits, file versions, jobs, evidence | New envelope stores: `world`, `work`, `investigation` |
| SSE `EventHub` + `/api/life-events` cursor | Live sync for world, work, and investigation | New SSE kinds; no new bus |
| Backend-modeled movement (route in state, phase from `now`, reroute from current position) | Kept as the movement *semantics* | Geometry changes from 1000×600 points to (room, tile) waypoints; 4-direction |
| Seeded RNG streams (`core/rng.py`) | Point choice, slot choice, tie-breaks | Possibly a new stream for `world` |
| Interaction point concept (ADR-0027) | Kept; generalised to object-instance points with capabilities and approach/occupy | Moves from code constants to catalog plus layout data |
| Task model (`core/tasks.py`: tool, target, title, category) | The "Task" of the roadmap's Activity/Task split | Extended target namespaces (`project:`, `file:`, `inv:`); capability hints |
| `DataDir` write jail | The workspace blob store writer | A second jail root (the workspace mount) |
| `storage.external` read-only datasource | Investigator history from metrics.db | Additional fixed SELECTs (needs a D20 amendment for which columns are trusted) |
| Read-only D-Bus client (D21) | Unit state for the investigator | Possibly more properties (`NRestarts`, `ActiveEnterTimestamp`) → ADR amendment of D21 |
| Companion pattern (`maple-brain`, `maple-discord`): separate account, loopback, hardened unit, owner-run install | Template for `maple-exec` and `maple-observer` | New units, accounts, contract tests |
| Brain Health (ADR-0034) aggregation-from-audit pattern | Health of executor and observer ("subsystem health") | Generalise to a subsystem health report |
| Pre-migration snapshot + forward-only migration (ADR-0028 R1–R8) | All new schema | Unchanged |
| Release bundle + `activate_release.sh --allow-migration` gate | All new releases | Bundle also ships the object catalog, art atlases, executor runner, observer |
| Backup staging (`maple-db-snapshot`, restic) | `maple.db` unchanged | Add the workspace blob directory as a restic path (an ADR-0024 amendment) |
| Frontend `visual.ts` pure snapshot→visual mapping, revision-gated store, DOM/Pixi split (D2) | Kept as the frontend pattern | Rebuilt renderer; new world store slice |
| `core/presence.py` bubble from real state | Kept | New bubble kinds (investigating, coding) |
| Discord read-only commands | Investigation reports, notifications (pull) | New GET endpoints; companion polling |

---

## 4. Gaps and conflicts

### 4.1 Gaps (missing today)

| Area | Missing |
|---|---|
| Room | Multi-room world, tile grid, collision, doors, room graph, object instances, object state, placement slots, layout persistence, editor, camera, y-sort, textures/atlases, 4-direction sprites, pixel-perfect rendering |
| Workspace | Mutable files, versions, projects, artifacts, quotas, library items with reading progress, execution, packages/toolchains |
| Investigator | Process data, logs, network/disk I/O, swap/GPU history, anomaly episodes, investigation records, evidence provenance, redaction, notifications |
| Cross-cutting | Data retention (observations already grow without bound), owner authentication beyond the tailnet + Origin check, subsystem health beyond the Brain |

### 4.2 Conflicts with current FIXED decisions

Each row needs an explicit owner decision or ADR amendment.

| Roadmap item | Conflicts with | Resolution proposed |
|---|---|---|
| R1: 3/4 top-down, multi-room, tile grid | D26 / ADR-0027 geometry (one 1000×600 front-view room, points in `core/room.py`) | New ADR (world model). Keep ADR-0027 *semantics*: walk-then-act, phase from `now`, reroute, Writing Desk ≠ Computer Desk. Supersede its geometry. |
| R2: capability-based furniture, new activities | `SPECS[activity].locations` 1:1; `RoomLocation` CHECK enums; D27 fixed activity set | Capability resolution; activities as a lookup table, not a CHECK; each new activity still needs owner approval (a FIXED set by policy, not by schema shape) |
| R3: "Inventory" | CLAUDE.md §2 out-of-scope "inventory, currency, shops…" (D3) | **Owner decision OD-02.** Proposed meaning: *storage of Maple's own creations and decorations not currently displayed*. No items to acquire, no currency. The term "Storage" is suggested to avoid the game-system connotation. |
| R4: owner editor (mutations) | D3/D31: the only mutations are Greet, Pet, and the Discord conversation; `test_route_table_is_exactly_the_approved_surface` | New ADR: owner edit endpoints with owner authentication (OD-03) |
| W1/W2: create/modify/delete files | ADR-0029 §1 ("workspace is a table, append-only, no new filesystem write path") | New ADR superseding ADR-0029 §1. `document` stays as Maple's immutable notes; files become versioned blobs. |
| W4: run code | §4.1 #2 (no subprocess/shell); §2 out-of-scope "code experimentation"; §8 ("separately sandboxed lab… never sharing privileges with the core service") | New ADR: `maple-exec` boundary. §4.1 #2 stays true for the Maplegotchi backend; the executor is a separate boundary as §8 anticipated. |
| W5: self-directed creation | §2 "learning, self-modification" out of scope | Self-modification stays forbidden: Maple can never touch its own code or config. W5 is creation inside the workspace only. Owner approval is still required to enable it. |
| S1: process list, logs | `ProtectProc=invisible`; no `systemd-journal` group (§4.3) | Separate `maple-observer` adapter; the main unit is unchanged |
| S1: Docker health | Docker socket inaccessible (= root-equivalent) | No Docker socket. Use container cgroup stats and `docker.service` state only. A Docker API proxy needs OD-09. |
| S1: metrics.db columns | D20: legacy service flags are not a source | Amend D20 to trust specific numeric columns (swap, GPU, data disk) as *historical* evidence. Flags stay excluded. |
| S3: process → service mapping | D12: no service auto-discovery | Mapping a PID to its unit via `/proc/<pid>/cgroup` is a read-only *lookup for evidence*. It never adds to the service-health allowlist. Needs explicit owner acknowledgement (OD-10). |
| R6: character sprite in the last phase | R1 needs 4-direction walk and the R2 activities need poses | Placeholder art in R1–R5 against the locked technical contract; final art in R6 (§18.3) |

---

## 5. Proposed target architecture

```
                       Browser (tailnet, Tailscale Serve, Funnel off)
                         │  REST + SSE (same origin)
┌────────────────────────▼──────────────────────────────────────────────────────────┐
│ maplegotchi.service  (maple-svc; loopback; NO subprocess; writes /data/maple only)│
│                                                                                   │
│  api ──► runtime/service ──► runtime/life (single writer, one txn per transition) │
│                │                    │                                             │
│                │             core (pure): needs · goals · direction · proposal    │
│                │               world/   (grid, room graph, A*, capabilities,      │
│                │                         placement & layout validation)           │
│                │               work/    (project/file/artifact rules, quotas,     │
│                │                         job requests, output validation)         │
│                │               investigate/ (anomaly, hypotheses, evidence        │
│                │                         scoring, confidence, report grounding)   │
│                │                                                                  │
│  runtime adapters (I/O, chosen here only):                                        │
│    brain clients ── HTTP loopback ──► maple-brain   (/decide /reply /work /explain)│
│    exec client   ── unix socket   ──► maple-exec@   (per-job sandbox, W4+)        │
│    observer client ─ unix socket  ──► maple-observer (read-only, S1+)            │
│    senses (psutil, D-Bus RO, metrics.db RO)                                       │
│  storage: maple.db  +  workspace blob store (/data/maple/workspace, noexec mount) │
└───────────────────────────────────────────────────────────────────────────────────┘
        ▲ GET only + POST conversation (token)        
  maple-discord (pulls notifications via GET)       
```

### Principles, restated as rules for every new component

1. **One authority.** Core validates; `runtime/life` commits. New subsystems never write `maple.db` themselves and never call each other directly. They exchange data through core transitions.
2. **Workers are capability-free by default.**
   - `maple-exec` can compute but cannot see anything it wasn't handed.
   - `maple-observer` can read but cannot write anything.
   - `maple-brain` can phrase but cannot act.
3. **Every external call is outside the writer lock**, has a deadline, is never stacked, and its result is re-validated against current state (the ADR-0026 three-step pattern). The §2.3 journal exception is not copied.
4. **Fail closed on capability, fail soft on life.** If a worker is down, the capability is unavailable (recorded, shown as `unknown`/`unavailable`). Maple's life continues on rule fallbacks.
5. **Derived over stored.** Visual state that can be computed from domain data (shelf fullness, monitor alert glow, project board contents) is derived, never stored twice.
6. **Data, not code, for world content.** Rooms, objects, and slots are versioned data validated by core. Adding a lamp needs no code change.

---

## 6. Maple Room architecture

### 6.1 Component boundaries

| Layer | Owns | Never does |
|---|---|---|
| **Object catalog** (release data, `maplegotchi/world_catalog/*.json`, root-owned) | Object *types*: footprint, collision mask, capabilities, interaction-point templates, slot templates, state machine, movability class, category | Instance placement, art frames |
| **core/world** (pure) | Grid model, walkability, room graph, A\*, capability resolution, placement/layout validation, object-state transitions, Maple position and route math | I/O, persistence, rendering |
| **runtime** | Loads catalog + active layout, passes them to core as frozen data, runs transitions under the writer lock, publishes `world` events | Validation rules |
| **storage** | Layout revisions, object instances, placements, world events | Any rules |
| **api** | `GET /api/world*`, owner edit endpoints (R4), DTO mapping | Rules, direct writes |
| **frontend store** | Latest world revision + snapshot; editor *draft* state | Authoritative state |
| **renderer (Pixi)** | Tile/object/character drawing, y-sort, lighting, camera, interpolation along the backend route | Pathfinding, collision, validation, choosing destinations |
| **art manifest** (frontend data) | Frames, anchors, layers, animation timing per `object_type`/state/orientation | Footprints or capabilities (read-only mirror for the editor overlay comes from the API) |

### 6.2 Source of truth

- **World structure** (rooms, doors, object instances, slots): the *active layout revision* in `maple.db`.
- **Object types:** the catalog in the running release. Catalog version and hash are recorded in each layout revision.
- **Maple's position and route:** `life_state` (as today), with the coordinates redefined.
- **Dynamic object state** (occupied, on/off, display contents): either derived from domain data or stored in `object_instance.state` with revision.
- **The renderer and editor draft are never authoritative.** The editor's "preview" asks the server.

### 6.3 Coordinate and room model

- **World unit:** 1 *art pixel* at 1× ("px").
- **Tile:** `T × T` px. Provisional `T = 16`, to be locked in the technical spike (art contract §B.2).
- **Grid coordinates:** integer `(tx, ty)` per room, origin at the room's north-west tile; x grows east and y grows south.
- **Room:** `id` (slug), `kind` (bedroom, living, library, studio, creation, system, hall, future), `size` (w×h tiles), `floor`/`wall` theme ids, a walkability base mask (derived from walls), and a `lighting` preset.
- **World position:** `(room_id, tx, ty)` plus, while walking, progress along the current route.
- **Room placement in the house:** each room has a `house_offset` (tile coordinates in a global house grid), used only for rendering and the overview camera. Pathfinding uses the room graph, not global coordinates, so rooms need not be physically adjacent in data. Validation still requires doors to line up visually: a door connects two rooms' wall tiles that are adjacent in house coordinates.
- **Doors:** a `room_connection` with `{a: (room, door tile, side), b: (room, door tile, side), width_tiles, state: open|closed|locked_by_owner}`. A door is walkable on both sides and is an edge in the room graph with integer cost.

### 6.4 Walkability, collision, pathfinding

- **Walkable grid per room** = floor tiles − wall tiles − the union of the `blocks` masks of placed object instances (catalog footprint mask, rotated by orientation) + door tiles.
- **Maple occupies one tile** (feet tile). There are no other agents in v1, so dynamic collision is not needed. The model leaves room for future entities via an `occupancy` layer.
- **4-direction A\*** on each room grid:
  - Integer cost: 10 per step, +1 per turn to prefer straight lines. This is deterministic and needs no `sqrt`.
  - Manhattan heuristic.
  - Tie-break on `(f, h, ty, tx)`.
  - **Cross-room pathfinding is hierarchical:**
    1. Dijkstra over the room graph. Nodes are doors; edge costs are the cached intra-room door-to-door distances.
    2. A\* within each room on the chosen corridor.
  - Results are cached by `(layout_revision, from, to)`. The cache is a pure function of the layout, so it is safe to recompute.
- **The route is stored compressed:** waypoints at corners and door transitions, as `[(room, tx, ty, cumulative_steps)]`.
- **Time and position:**
  - Travel time = `steps × ms_per_step` (tunable; replaces `WALK_SPEED`).
  - Position at `now` is linear between waypoints using only `+ - * /`, as today.
- **Door transitions:** the route crosses a door waypoint. The renderer may play a door animation; the backend models no extra state beyond optional `door_ms` added to travel time.
- **No teleport by default (roadmap R1):** a destination with no path makes the action invalid (`no_destination`, existing rejection code). Core never snaps across walls. The only snap is the recovery rule in §6.12.

### 6.5 Object model

**Object type** (catalog, immutable per release):

```jsonc
{
  "type": "furniture.writing_desk",          // stable id, never reused
  "category": "functional",                  // functional | decorative | creation_display | structural
  "geometry_version": 1,                     // bumps on any footprint/point change (art contract §B.15, §C.8)
  "footprint": {"w": 3, "h": 2},             // tiles, at orientation "south"
  "blocks": ["###", "###"],                  // collision mask rows (# blocks walking)
  "orientations": ["south", "east", "west", "north"],
  "capabilities": ["writing_surface", "seat"],
  "points": [                                // interaction point templates, object-local tiles
    {"id": "chair", "approach": {"tx": 1, "ty": 2, "facing": "north"},
     "occupy": {"px": [24, 30], "pose": "sit", "layer": "occupant"},
     "provides": ["writing_surface", "seat"], "capacity": 1}
  ],
  "slots": [{"id": "desktop", "accepts": ["creation.small", "project.active"], "capacity": 2}],
  "states": ["default"],                     // object state machine (e.g. lamp: off|on)
  "movable_by": ["owner"],                   // owner | maple | none
  "deletable_by": ["owner"],
  "placement": {"surface": "floor", "against_wall": "north_optional"}
}
```

**Object instance** (layout data):

```jsonc
{"id": "obj:12", "type": "furniture.writing_desk", "room": "studio",
 "tx": 4, "ty": 2, "orientation": "south", "state": "default",
 "owner": "paolo",                // paolo | maple (who placed it; governs who may move it)
 "link": null}                    // or {"kind": "project", "id": "project:7"}
```

The roadmap R2 metadata list maps fully onto this model:

| Roadmap field | Where it lives |
|---|---|
| ID | instance `id` |
| type | instance `type` |
| room | instance `room` |
| position | `tx`/`ty` |
| orientation | `orientation` |
| category | type `category` |
| capability tags | type `capabilities` |
| allowed activity | derived via capabilities (§6.6) |
| interaction point | type `points` |
| facing | point `facing` |
| state | instance `state` |
| linked project/file/creation | instance `link` |
| movable / deletable | type `movable_by` / `deletable_by` |
| owner | instance `owner` |

### 6.6 Capability model and activity/task relationship

The roadmap R2 principle is: **Activity** = broad behavior; **Task** = what Maple is actually doing; **Furniture** = the tool or place that supports it.

**Activity requirements** (core table, versioned with the activity set):

| Activity | Requires (any-of groups) | Notes |
|---|---|---|
| sleep | `sleep_spot` | |
| rest | `seat_soft` ∨ `sleep_spot` | sofa, armchair, bed |
| read | `reading_spot` | bookshelf front, armchair, sofa, library desk |
| write | `writing_surface` ∧ `seat` | Writing Desk |
| observe_server | `system_console` ∨ `computer` | Computer Desk, System Room console |
| think | `window_view` ∨ `quiet_spot` | window, plant corner |
| idle / walk | `open_floor` | any free walkable tile flagged by the room as open area, or an `open_floor` point |

**Resolution algorithm** (pure, in `core/world`):
1. `required` = activity requirements ∪ task requirements. Examples: task target `library:*` adds a preference (not a requirement) for `book_source` in a `library` room; task `investigate` adds `system_console`.
2. `candidates` = interaction points on placed instances whose `provides ⊇` one requirement group, whose instance state allows use (e.g. not `disabled`), whose capacity is free, and which are **reachable** from Maple's position.
3. Score each candidate with an integer score. Inputs: path cost, room kind affinity (activity ↔ room kind table), task preference, Maple preference memory (e.g. "I like reading on the sofa", from ADR-0030 accepted preferences), and a stickiness bonus for the current point.
4. Choose the best; ties are broken by a seeded draw (the existing `decision` RNG stream), never by set order.
5. No candidate → the activity is not allowed now. The Director context lists only activities with at least one reachable candidate (extending today's `allowed.actions`).

Consequences:
- **Writing Desk ≠ Computer Desk (D26)** is preserved: they are distinct types with disjoint capabilities.
- A new activity (e.g. `code`) is: an activity enum row, a requirement row, capabilities on the relevant types, and poses in the art manifest with fallbacks. No movement code changes.
- **Task** stays `core/tasks.py`'s `Task`. Its target namespace grows: `library:`, `document:`, `file:`, `project:`, `artifact:`, `inv:`. A task never names an object instance. The object is resolved by capability, and the chosen point is recorded on the action (`decision.executed_point` already exists).

### 6.7 Room state, object state, and Maple state

| State | Stored? | Source |
|---|---|---|
| Room lighting preset, theme | stored (layout) | owner edit |
| Day phase, ambient tint | derived | `core/daytime` + room preset |
| Lamp on/off | derived (day phase + room occupancy) or stored if Maple/owner toggles it later | object state machine |
| Bookshelf fullness | derived | count of library items assigned to that shelf (`slot` contents) |
| Monitor/console visual (calm/alert/investigating) | derived | server attention + open investigation |
| Project board contents | derived | projects in `planned` with a display link |
| Occupied seat | derived | Maple's current point at `now` |
| Creation on display | stored | `display_placement` (Maple or owner action) |
| Maple position/route | stored | `life_state` (§6.4) |

### 6.8 Persistent world state and growth

- The **layout revision** is an immutable, validated JSON document: rooms, connections, instances, owner-defined placement zones, theme, and lighting.
  - Each edit creates a new revision; the active pointer moves.
  - History gives audit and owner-level undo across saves.
- **Display placements** (Maple-controlled contents of slots) live in a separate, small, mutable table with append-only history.
  - Maple's frequent actions don't create whole-layout revisions.
  - Owner layout edits don't race Maple's shelf placements; a placement references `slot_id` on an instance id that survives revisions when the owner keeps the instance.
- **Growth mechanisms:**
  1. A creation or artifact gains a *representation* (§11.1).
  2. A slot accepting it becomes eligible.
  3. Maple may propose placing it.
  4. Core validates (slot accepts the category, capacity free, slot owner policy allows Maple).
  5. Commit → `world` event → renderer shows it.
- "Bookshelf fills up" is derived from library item counts, with no placement action.
- "Creation Room grows":
  - Owner-defined expansion: new layout revisions. The room `kind=future` is a placeholder room the owner converts.
  - Optionally, a **growth rule** (core, data-driven) that *unlocks* catalog object types or additional slots when milestones are reached (e.g. 10 completed projects → a second display shelf becomes available in storage).
  - Unlocking never places furniture by itself. Placement of functional furniture stays owner-only (roadmap R3: "Maple cannot move functional furniture at first").

### 6.9 Placement slots and validation

- **Slots are declared on object types** (shelf positions, desk top, wall hooks) and on **owner-defined placement zones** (rectangles of floor/wall tiles in a room where Maple may place freestanding decorations).
- **Layout-commit-time guarantee:** when the owner saves a layout, core validates that *every zone tile could be filled* without breaking anything:
  - door blocking,
  - path connectivity between all doors and all functional interaction approaches,
  - functional-object collision.

  A Maple placement therefore needs only *local* checks (slot accepts, capacity, not occupied, the item's footprint fits the zone). This makes Maple's validation cheap, total, and impossible to make pathfinding-breaking. It is the roadmap R3 rule ("no blocking doors, walkways, functional objects; do not break pathfinding") enforced structurally.
- **Full layout validation** (owner edits, R4), all in core and pure:
  1. Every instance type exists in the catalog; the orientation is supported; the footprint lies inside its room floor.
  2. No two blocking masks overlap; wall-mounted objects sit on wall tiles; floor objects on floor tiles.
  3. Every door tile and its approach tile are walkable.
  4. Every functional point's approach tile is walkable and reachable from every door (connectivity BFS).
  5. The room graph is connected (no orphan room), unless a room is marked `closed`.
  6. Every placement zone passes the commit-time guarantee above.
  7. Every existing display placement still has a valid slot. Otherwise it is moved to **storage**: listed in the validation result, never silently dropped.
  8. Maple's current position stays walkable. Otherwise the §6.12 recovery applies on commit and is shown in the preview.
  9. Size bounds: max rooms, max instances per room, max layout JSON size (DoS guard).

### 6.10 Live mode, edit mode, undo/redo

- **Live mode:** what exists today; the renderer follows snapshots and SSE.
- **Edit mode** (owner only, R4):
  - The frontend loads the active layout plus catalog and works on a local **draft**.
  - Grid overlay, drag/drop, snap to tile, rotate.
  - **Undo/redo** is a frontend command stack over the draft. It is ephemeral, persisted only per browser (localStorage, best-effort).
  - **Preview:** `POST /api/world/layout/preview` sends the draft and returns the validation result (errors with instance/tile references, storage moves, Maple relocation). It is debounced; no state change.
  - **Save:** `POST /api/world/layout` sends the draft plus `base_revision`. Core re-validates; on success the server commits a new revision.
    - A stale `base_revision` gives `409` with a diff, so the editor rebases. This protects against a concurrent Maple placement or a second tab.
  - **Revert:** `POST /api/world/layout/revert {revision}` creates a new revision copying an old one (history stays append-only).
- **Maple during an edit:** live life continues. A saved layout is applied as a transition:
  - Maple's route is replanned from the current position (the ADR-0027 reroute semantics).
  - If her current action's point vanished, the action is interrupted (`activity_interrupted`, reason `layout_changed`) and a decision becomes due.

### 6.11 APIs and events (proposed, additive)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/world` | active layout (rooms, connections, instances, zones), `layout_revision`, catalog version; ETag by revision |
| GET | `/api/world/catalog` | object types (engine metadata) for the running release; immutable per release, cacheable |
| GET | `/api/world/placements` | display placements |
| GET | `/api/world/history?limit` | layout revision list |
| POST | `/api/world/layout/preview` | owner, validate draft (no write) |
| POST | `/api/world/layout` | owner, save new revision |
| POST | `/api/world/layout/revert` | owner |
| — | `/api/room` | kept for one release as a compatibility view of the initial room, then removed (the route-table test is updated deliberately) |

- **Snapshot:** gains `world_revision`. `activity.position` becomes `{room, tx, ty, x_px, y_px}` (pixel position derived for the renderer), and `route.path` becomes room/tile waypoints.
- **SSE:** a new kind `world` (`{revision, layout_revision, changed: ["layout" | "placements" | "object_state"]}`). The frontend then refetches the relevant resource.
- **Life-event envelope:** new store `world` (`layout_saved`, `layout_reverted`, `object_placed`, `object_moved`, `object_stored`, `maple_relocated`).

### 6.12 Synchronization and failure behavior

| Situation | Behavior |
|---|---|
| Catalog type missing for an instance (release removed a type) | Release activation check refuses (an `activate_release.sh`-style gate). At runtime the instance is rendered as a placeholder and is non-functional; logged; never deleted. |
| Layout invalid under the new catalog version | The startup check fails loudly (same policy as a corrupt DB), with an owner-run fix. Alternatively the release's migration step transforms the layout deterministically and records a revision. |
| Maple stands on a now-blocked tile | Deterministic recovery: nearest walkable tile by BFS, tie-break `(ty, tx)`. A `maple_relocated` event with reason is recorded. This is the only allowed non-walking position change. |
| Path not found for a chosen action | Action invalid (`no_destination`) → rule fallback picks another. |
| Frontend asset missing | Placeholder sprite (art contract §C.10). Never blocks rendering. |
| World endpoint fails | The room shows the stale indicator (the existing §3.9 rule). Vitals and other panels keep working. |
| Editor save conflict | 409 + rebase. Never last-writer-wins. |

### 6.13 Day/night, ambient, sound (foundation only)

- Day phase stays backend-derived (`day.phase`, D16 offset). Lighting presets per room define tint and light-source behaviour per phase. The renderer interpolates.
- **Ambient visual state** (rain outside, etc.) is future work. If ever "real" (e.g. weather), it must come from a backend fact, never invented (§3.9). Purely decorative ambience (dust motes, idle animations) is allowed as animation.
- **Sound** (R6) is a frontend presentation layer:
  - Per-room ambient loops keyed by room kind and day phase.
  - SFX keyed by life events and animation frame events (footsteps).
  - Muted by default (browser autoplay rules), with a DOM control.
  - Sound assets go in the same manifest system (`sfx.*`, `amb.*`, `mus.*`).
  - No backend change beyond the events that already exist.

### 6.14 Migration from the current room

See §17, step M-R1. In short: the current 7 locations become object instances in one initial room (`living`) of a seed layout. The other rooms are added as layout revisions in R1. `life_state.location`/`point_id` are converted; enum CHECKs move to lookup tables.

---

## 7. Maple Workspace architecture

### 7.1 Evaluating the roadmap's `/data/maple/world/`

| Criterion | `/data/maple/world/` as plain directories | **Proposed: `/data/maple/workspace/` dedicated mount, blob store** |
|---|---|---|
| Name clarity | "world" collides with the Room's world model (layout and object state live in `maple.db`) | "workspace" is unambiguous |
| D19 (writable = `/data/maple` only) | holds | holds (a mount *under* `/data/maple`; `BindPaths` is recursive) |
| Disk exhaustion isolation | shares the filesystem with `maple.db`; a runaway workspace can stop Maple's commits | **fixed-size filesystem image or LV**: a hard cap, and `maple.db` is unaffected |
| Exec safety | files are executable on the host unless remounted | **`noexec,nodev,nosuid`**: nothing Maple writes can run on the host directly |
| Path traversal / symlink classes | must be defended on every operation | **eliminated**: Maple never names host paths; blobs are named by hash; logical paths are validated strings in the DB |
| Versioning / undo delete | needs a separate mechanism | inherent (immutable blobs + version rows) |
| Backup consistency | DB and tree can diverge mid-backup | blobs are immutable and written before the DB commit; garbage collection uses a grace period → the restic snapshot is consistent with any DB snapshot newer than the grace period |
| Owner browsing | easy | needs an owner-run export tool or a read-only API download (acceptable) |

**Recommendation:** `/data/maple/workspace/`, a dedicated `ext4` filesystem image (e.g. `/data/maple-workspace.img`) or LV, mounted `noexec,nodev,nosuid`. Proposed initial size: 10 GiB (OD-05). It is created and mounted by the owner via fstab or a mount unit, with `RequiresMountsFor=` added to the unit.

The roadmap's folders (`projects/`, `creations/`, `code/`, `library/`, `notes/`, `scratch/`) become **logical namespaces** in metadata, not host directories:

```
/data/maple/workspace/            (maple-svc:maple-svc 0700, separate fs, noexec,nodev,nosuid)
├── objects/ab/cdef…              immutable content blobs, name = SHA-256, mode 0400
├── staging/                      incoming blobs being hashed (same fs → atomic rename)
├── jobs/                         (W4) transient job bundles/results, cleaned after import
└── lost+found/
```

### 7.2 Ownership and accounts

| Actor | Access |
|---|---|
| `maple-svc` (main backend) | sole writer of the blob store via a `DataDir` jail rooted at `/data/maple/workspace`; reads blobs to build Brain contexts and job bundles |
| `maple-exec` jobs (W4) | **no access to the store at all**: they receive a copy over a socket (§7.5) |
| `maple-brain-svc` | none (`/data` inaccessible); sees only bounded excerpts in contexts |
| owner | owner-run export tool (read-only), restic restore |

### 7.3 Data model (metadata in `maple.db`)

- **project:** `id, slug, title, goal (≤240), status, created_at, updated_at, created_by (maple|paolo), budget, archived_at`.
  - Status lifecycle (roadmap W3): `idea → planned → active ⇄ paused → completed → archived`, plus `abandoned`.
  - Transitions are validated by core; history is in `project_event` (append-only).
- **workspace_file:** `id, project_id | namespace (notes, scratch, library, creations), logical_path, current_version_id, kind (text, code, data, image, pdf, binary), created_at, deleted (tombstone flag via version)`.
- **file_version** (append-only): `id, file_id, blob_sha256 | null (tombstone), size, media_type, created_at, author (maple | job:<id> | paolo), reason (≤200), decision_id/action_id`.
- **artifact:** `id, project_id, title, kind (document, program, dataset, image, report, experiment), file_version_ids, created_at, status (draft | final | archived), representation (§11.1)`.
- **library_item:** `id, file_id | catalog_id (library:*), title, kind (pdf, document, note, reference), status (unread | reading | completed | reference | archived), added_by`.
- **reading_progress:** `library_item_id, position (page/section/char offset), percent, updated_at` (mutable) plus `reading_session` (append-only).
- **project_task:** `id, project_id, title, status (todo | doing | done | dropped), order`.
- **execution_job** (W4): `id, project_id, toolchain_id, entrypoint, input_manifest_digest, status (queued | running | succeeded | failed | timed_out | killed | rejected), started_at, ended_at, exit_code, cpu_ms, max_rss, output_summary, stdout_blob, stderr_blob`. Append-only lifecycle via `job_event`.

The existing `document` table stays: Maple's immutable notes (ADR-0029). New writing that should be editable goes to `workspace_file`. A one-time optional import can mirror existing documents into a `notes` namespace as version 1. It is never mandatory and never deletes rows.

### 7.4 Operations and permission matrix

All operations are **core-validated transitions** proposed by the Director/work contract or rule direction:

| Operation | Inside workspace | Outside workspace |
|---|---|---|
| Read | ✅ any of Maple's files (bounded excerpt to the Brain) | only the existing allowlisted catalog (`library:*` release docs, journal, server status, memory) |
| Write / create | ✅ new file version (size, count, quota checks) | ❌ no code path exists |
| Modify | ✅ new version (full content or validated patch) | ❌ |
| Delete | ✅ tombstone version; content retained until retention purge | ❌ |
| Execute | ✅ only via `maple-exec` with an allowlisted toolchain and entrypoint (W4) | ❌ |

**Limits** (core tunables, enforced in core *and* by the filesystem):

| Limit | Default |
|---|---|
| Max file size | 1 MiB for text, 10 MiB for others |
| Max files per project | 500 |
| Max versions per file before compaction eligibility | 200 |
| Max projects in `active` | 3 |
| Max projects total (not archived) | 30 |
| Logical path grammar | `[a-z0-9][a-z0-9._-]{0,63}` segments, depth ≤ 6, no `.`/`..`, no leading dot, total ≤ 200 chars |
| Daily write budget | e.g. 50 MiB/day |

Accounting lives in `maple.db`. The hard ceiling is the mount size.

### 7.5 Execution sandbox (W4): `maple-exec`

**Mechanism (recommended):** a socket-activated, root-defined per-connection unit.

```
maple-exec.socket   ListenStream=/run/maple-exec/exec.sock  Accept=yes  MaxConnections=1
                    SocketUser=root SocketGroup=maple-svc SocketMode=0660
maple-exec@.service (one instance per job; definition root-owned, contract-tested)
  DynamicUser=yes            # fresh unprivileged uid per job; no persistent account state
  RootDirectory=/opt/maple-exec/rootfs/<toolchain-set>   # minimal root: toolchains only, no shell
  (fallback if RootDirectory impractical: ProtectSystem=strict + InaccessiblePaths for shells/compilers)
  TemporaryFileSystem=/work:size=256M,mode=0700          # job working dir; counts toward MemoryMax
  PrivateNetwork=yes  IPAddressDeny=any  RestrictAddressFamilies=AF_UNIX
  PrivateTmp=yes PrivateDevices=yes PrivateIPC=yes PrivateUsers=yes ProtectProc=invisible ProcSubset=pid
  InaccessiblePaths=/data /home /root /etc/maplegotchi /etc/maple-brain /etc/maple-discord /run/dbus /run/docker.sock
  NoNewPrivileges=yes CapabilityBoundingSet= AmbientCapabilities= RestrictSUIDSGID=yes
  SystemCallFilter=@system-service  SystemCallFilter=~@privileged @resources @mount @debug @raw-io @reboot @swap @module @clock @obsolete @cpu-emulation
  RestrictNamespaces=yes LockPersonality=yes MemoryDenyWriteExecute=yes (relax only per-toolchain with ADR, as for maple-brain)
  CPUQuota=100% CPUWeight=20 MemoryMax=512M MemorySwapMax=0 TasksMax=32 LimitNOFILE=256 LimitFSIZE=64M LimitCORE=0
  RuntimeMaxSec=120  Nice=10 IOWeight=10
  StandardInput=socket StandardOutput=socket
  ExecStart=/opt/maple-exec/runner/bin/maple-exec-runner   # small root-owned runner, part of the release
```

**Flow (copy-in / copy-out; no shared filesystem):**

1. Core validates the run request:
   - project status `active`;
   - toolchain id in the allowlist;
   - entrypoint is a logical path in the project;
   - argv from a closed template (e.g. `python -I <entry>`, `python -I -m unittest`);
   - job budget and daily execution budget not exceeded.
2. Runtime builds a **bounded bundle** outside the lock: a tar of selected file versions (≤ 32 MiB, no links, no special files) plus a JSON manifest. It connects to the socket.
3. systemd starts a fresh `maple-exec@N` with the fixed sandbox. The runner:
   - unpacks into `/work` and rejects absolute paths, `..`, links, devices, and oversize entries;
   - execs the toolchain argv without a shell;
   - captures stdout/stderr (capped, e.g. 256 KiB each);
   - streams back a result tar of `/work/out` (capped, same entry rules) plus a JSON status: exit code, signal, cpu ms, max RSS, wall time, truncation flags.
4. Runtime validates the result:
   - size, entry grammar, media types;
   - the output path allowlist (`out/**` only).

   Core then commits a transition: job record, output file versions (blobs written first, §7.6), artifacts if declared, and a `tool_use`-style provenance row.
5. Timeout or failure → job `timed_out`/`failed`/`killed` with the reason; Maple's life continues. The kill is enforced by `RuntimeMaxSec`, the cgroup, and connection close.

**Why this shape:**
- The caller (`maple-svc`) cannot widen the sandbox; only root-owned unit files define it.
- `maple-svc` never forks (§4.1 #2 holds for the backend).
- There is no shared writable path between Maple's data and job code.
- A per-job `DynamicUser` gives no persistent foothold.
- The tmpfs size gives a per-job disk quota.
- `MaxConnections=1` means one job at a time, so there is no cross-job interference.

**Alternatives considered:**

| Alternative | Rejected / deferred because |
|---|---|
| Docker / Docker socket | root-equivalent; Docker is explicitly inaccessible today |
| `systemd-run` transient units from `maple-svc` | needs polkit `manage-units`, and the caller chooses unit properties (could set `User=root`) |
| bubblewrap / unprivileged user namespaces inside a service | Ubuntu restricts unprivileged userns via AppArmor (`kernel.apparmor_restrict_unprivileged_userns`); needs a host policy change; viable as a secondary layer later |
| rootless podman | heavier; needs userns and subuid maps; reconsider if non-Python runtimes need images |
| gVisor / Firecracker | strongest isolation; operationally heavy for one home server; future option for untrusted network-enabled jobs |

The exact mechanism must be confirmed by a **spike on paolo-core** (OD-06): the systemd version (`PrivateUsers`, `RootDirectory`, `TemporaryFileSystem` size options, `PrivateIPC`), `DynamicUser` with `RootDirectory`, and building the toolchain rootfs.

**Runtime and dependency policy:**
- **Toolchains** are owner-installed, versioned, read-only bundles under `/opt/maple-exec/toolchains/<id>@<version>`. Initially `python312-stdlib`: CPython 3.12 standard library only.
- **No package installation by Maple.** No `pip`, no `npm`, no network.
  - Maple may *request* a package. The request is a recorded `toolchain_request` the owner reviews.
  - The owner builds a new toolchain version with a pinned, hashed wheel set (uv lock) and adds it to the allowlist through a release or config change. Maple can never change that config (§4.1 #5).
- **Shell:** none in the rootfs. No `sh`, `bash`, or `busybox`.
- **Subprocess inside a job:** allowed by the OS but bounded: `TasksMax=32`, no shell binary, no network, no writable path except `/work`. Fork bombs hit `TasksMax`; runaway CPU hits `CPUQuota`/`RuntimeMaxSec`.
- **JavaScript/Node:** deferred (OD-07). Node's JIT needs `MemoryDenyWriteExecute` relaxed, which would be an explicit per-toolchain ADR exception, like `maple-brain`.
- **Internet:** none for jobs (OD-08). A future "fetch" capability would be a separate, allowlisted, read-only fetcher, never raw sockets in jobs.

### 7.6 Write ordering, consistency, garbage collection

1. Blob write: stream to `staging/<random>`, fsync, hash, then `rename` to `objects/<h[:2]>/<h>` (no overwrite; if it exists, deduplicate), mode 0400.
2. Then the `maple.db` transaction references the hash.
3. A crash between 1 and 2 leaves an orphan blob. Garbage collection reclaims it.

**Garbage collection** runs as a runtime maintenance transition, not in the heartbeat. It deletes blobs that are (a) unreferenced by any version row *and* (b) older than the **grace period ≥ 2 × backup interval** (e.g. 72 h).

**Retention purge** of tombstoned or old versions: versions older than N days beyond the newest K per file become unreferenced. The rows stay as metadata with `blob_purged_at`. This makes the bytes eligible for GC; history metadata is never deleted.

### 7.7 Project and artifact lifecycle; archive; versioning

- **Projects:**
  - `archived` → read-only, excluded from the Brain context and the active limit.
  - Restore → `paused`.
- **Artifacts:** `draft → final → archived`.
  - Only `final` artifacts may gain a Room representation.
  - An artifact pins exact file versions, so later edits never change a displayed artifact.
- **Rollback:** "restore file to version N" = a new version with N's blob. "Restore project to date D" = a new version for each file whose current version differs from its version at D.

### 7.8 Brain involvement (`maple.work.v1`)

- **Today:** documents are composed by core templates (ADR-0029 §4). Coding needs generated content, so a new companion endpoint `POST /work` (contract `maple.work.v1`) is required:
  - **Context:** project goal, task list, a file tree of logical paths with sizes, ≤ N bounded excerpts, last job result summary (exit code, truncated stderr tail), budget remaining.
  - **Response:** a closed set of operations as data: `write_file {path, content ≤ 64 KiB}`, `patch_file {path, unified_diff ≤ 64 KiB}`, `delete_file {path}`, `run {toolchain, entry, args_template}`, `set_task_status`, `note {text}`, `complete_step {reason}`.
  - **Core validation:** grammar, quotas, project state, path existence, diff applies cleanly, ≤ M operations per step, no operation touches another project.
- **Work happens in bounded steps:** one `/work` call per step, outside the lock, with a deadline. Each step is one committed transition. Maple's `write`/`code` activity spans many steps, each re-validated, so an interrupt (critical signal, owner message) stops cleanly between steps.
- **No tools for the Brain.** It never executes, never reads files itself, never sees host paths. File content in contexts is untrusted data; prompt injection in files can at most influence *proposals*, which core bounds (§14, T-08).

### 7.9 Self-directed creation (W5)

- A **creation policy** (core, tunable, owner-configurable through release config) defines:
  - max new projects per week;
  - max active projects;
  - daily execution minutes;
  - project kinds allowed without approval (`notes`, `writing`, `small_program`);
  - kinds requiring owner approval (anything that needs a new toolchain, more than X MiB, or a run budget above the default).
- **Approval flow:**
  - A project in `idea` that needs approval enters `awaiting_approval`. The bubble kind `approval_required` already exists in `core/presence.py` and is unused today.
  - The owner approves or declines in the Inspector or via Discord (both owner-authenticated, OD-03).
  - No approval → the project never leaves `idea`.
- **Stop conditions:**
  - budget exhausted;
  - N consecutive failed runs → project `paused` with reason `stuck`;
  - no progress over K steps;
  - owner pause switch (`MAPLE_WORKSPACE_MODE=off|read_only|create|create_and_run`, release config, root-owned).

### 7.10 Audit logging

Every operation leaves an append-only row: `file_version`, `project_event`, `job_event`, `tool_use`. Each carries the `decision_id`/`action_id` that caused it. stdout/stderr are stored as capped blobs, shown in the Inspector with escaping (§14, T-14). No prompt or raw model output is stored, only the validated operations and the one-line reason (as ADR-0026).

### 7.11 Backup and recovery

- **`maple.db`:** unchanged ADR-0024 path.
- **Blob store:** add `/data/maple/workspace/objects` to the restic paths. The objects are immutable files, which is restic-friendly; the job runs as root and can read 0400.
- **Consistency:** the DB snapshot is taken at backup time, and every blob it references exists because blobs precede DB rows and GC respects the grace period.
- **Restore drill** (added to `deploy/install.md`): restore `maple.db` + `objects/`, then run the owner verification tool `maple-workspace-verify`, which checks every referenced blob exists and hashes correctly.
- **A lost workspace mount** (device failure) → workspace capability `unavailable`. Maple lives on, and files are restored from backup.

### 7.12 Integration with the Room

§11 covers the integration in detail. In short:
- Work Studio desks show active projects.
- The Library shows library items and reading progress.
- The Creation Room displays final artifacts.
- The System Room console is used by `observe_server`/`investigate`.

---

## 8. Maple System Investigator architecture

### 8.1 Components

```
 maple-observer (read-only adapter)            maplegotchi (main)
 ┌──────────────────────────────────┐          ┌───────────────────────────────────────────┐
 │ adapters (allowlisted, read-only)│  query   │ runtime/investigate (orchestrator, budgets)│
 │  proc · journald · net · diskio  │◄─────────│  ↑ uses core/investigate (pure):           │
 │  cgroup · tailscale(status)      │  result  │    anomaly episodes · hypothesis catalog · │
 │ redaction + bounding             │─────────►│    evidence scoring · confidence · report  │
 │ short in-memory ring buffers     │          │  storage: anomaly/investigation/evidence/  │
 └──────────────────────────────────┘          │    hypothesis/report (append-only)         │
   unix socket, closed-enum queries            │  senses (existing): psutil, D-Bus, metrics │
                                               └───────────────────────────────────────────┘
```

### 8.2 Allowlisted data adapters

| Source | Where read | Mechanism | Notes |
|---|---|---|---|
| CPU, load, RAM, temp, `/` disk | main (existing senses) | psutil | unchanged |
| swap, net I/O counters, disk I/O counters, `/data` disk usage | main senses (extend) | psutil (`swap_memory`, `net_io_counters`, `disk_io_counters`); `/data` usage via `statvfs` | `/data` is hidden by tmpfs in the main unit. Either bind-mount `/data` read-only *metadata only* (not possible; `statvfs` on the bind of `/data/maple` reports the same filesystem, which is enough when on the same device), or read `data_used_pct` from metrics.db history. OD-11. |
| History (5 min): cpu, temp, ram, swap, root/data disk, GPU | main `storage.external` | fixed SELECTs on `metrics` | amend D20: numeric columns trusted as historical evidence; `*_ok` flags stay excluded |
| History (1 min): monitor-v2 | main `storage.external` (new datasource) | read-only, fixed SELECTs | **schema unknown → read-only survey first** (CLAUDE.md §5 "don't guess") |
| Unit state, restarts, timestamps | main D-Bus client | add `Get` of `NRestarts`, `ActiveEnterTimestamp`, `ExecMainStatus`, `Result` for allowlisted units | amend D21's property allowlist; still no `GetAll`, no methods beyond `GetUnit`/`Get` |
| Process list + per-process CPU/RSS/IO | **observer** | `/proc` (`ProtectProc=default` in its unit) | names and units only by default; **cmdline redacted** (§8.4) |
| PID → unit | observer | `/proc/<pid>/cgroup` → `system.slice/<unit>` | lookup for evidence only (D12, OD-10) |
| Selected journald logs | **observer** | `sd_journal` read with `_SYSTEMD_UNIT` match for allowlisted units, bounded time window, priority ≤ configured | requires `systemd-journal` group for `maple-observer-svc` (OD-12) |
| Container resource usage | observer | cgroup v2 files under `system.slice/docker-<id>.scope` (cpu.stat, memory.current) | no Docker socket; container names via cgroup only, or unknown |
| Docker health | — | not available by default | needs a Docker API read proxy → OD-09 (default: no) |
| Tailscale status | observer | LocalAPI socket `/run/tailscale/tailscaled.sock`, `GET /localapi/v0/status` only | verify which LocalAPI reads need operator rights; read-only endpoints only; OD-13 |
| Backup status | main D-Bus (existing) + `ExecMainStatus`/`Result` | | already mapped (`backup`) |
| Maple / Brain / Discord health | main | own audit (ADR-0034 pattern), `maple-discord` unit state via D-Bus (add to map) | |
| GPU live | — | no GPU hardware recorded in the survey; metrics.db has GPU columns | evidence from history only, if non-null |

### 8.3 Read-only diagnostic interface and bounded query model

- **Transport:** a Unix socket `/run/maple-observer/observer.sock`, group `maple-svc`, 0660. Request and response are JSON, ≤ 64 KiB.
- **Query kinds are a closed enum**, each with typed parameters and hard bounds:

| Query | Params | Bound |
|---|---|---|
| `top_processes` | `by: cpu|rss|io`, `n ≤ 15` | names, pid, unit, %, rss; no cmdline unless redacted |
| `process_detail` | `pid` | state, start time, threads, unit, redacted cmdline (≤ 200 chars) |
| `process_history` | `name|unit`, `window ≤ 60 min` | from the observer's in-memory ring buffer (e.g. 30 s samples × 2 h) |
| `unit_logs` | `unit ∈ allowlist`, `window ≤ 2 h`, `priority ≤ warning|info`, `limit ≤ 50 lines` | redacted, line length ≤ 300 |
| `net_interfaces` | — | up/down, rx/tx rates, errors |
| `disk_io` | `window ≤ 15 min` | per device rates |
| `cgroup_usage` | `unit|scope ∈ allowlist` | cpu, memory |
| `tailscale_status` | — | backend state, self online, peer count (no peer names/IPs unless allowlisted) |

- **No free-form command, path, SQL, or regex** from Maple or the Brain.
- **The observer never executes binaries.** Everything is read from `/proc`, `/sys`, the journal API, and the LocalAPI socket. It keeps **no persistent writes** (no `StateDirectory`); ring buffers live in memory only.

### 8.4 Log redaction and secret protection

- **Layers:**
  1. **Source allowlist:** only allowlisted units' journals, never the whole journal.
  2. **Field allowlist:** `MESSAGE`, `PRIORITY`, `_SYSTEMD_UNIT`, `__REALTIME_TIMESTAMP` only. Never `_CMDLINE` or `_EXE` environment fields.
  3. **Pattern redaction:** key=value secrets (`password|passwd|token|secret|api[_-]?key|authorization|bearer|cookie|session`), JWT-like strings, long base64/hex runs (≥ 32 chars), PEM blocks, URLs with userinfo, email addresses, IPs outside a configured allowlist (configurable), Discord/OpenAI/GitHub-style key prefixes.
  4. **Length caps.**
  5. **Control-character stripping** (ANSI escapes, CR, NUL); log-injection defense.
  6. **Process cmdline:** argv[0] basename plus a redacted argument summary. Arguments that look like secrets are dropped; any argument following `--token`/`--password`-style flags is dropped.
- **Redaction happens in the observer**, so unredacted data never crosses into `maple-svc`, `maple.db`, a Brain context, or the UI.
- **Before any Brain call,** contexts get a second redaction pass in core (defense in depth). The **external-provider policy** is decided by the owner (OD-14): investigation contexts may be withheld from cloud providers entirely, in which case reports use rule wording only.
- **Redaction is tested** with a corpus of real-shaped secrets (§14 T-07). Redaction failures are treated as security bugs.

### 8.5 Anomaly detection (S2)

- **Input:** stored observations (existing, every 300 s) + metrics.db/monitor-v2 history + observer samples on demand.
- **Episode model:** an `anomaly` row has `metric/subject`, `kind` (threshold | baseline_deviation | rate | recurrence | state), `severity` (info | warning | critical), `opened_at`, `last_seen_at`, `closed_at`, `peak`, `baseline`, and `status` (`open | transient | escalated | closed`).
- **Rules** (core, data tables):
  - Thresholds reuse `core/attention.py`'s levels.
  - **Duration** (must persist ≥ N consecutive samples).
  - **Baseline** (median of the same hour over the last 7 days from history; deviation ≥ k × MAD, computed with rational arithmetic or integer quantiles so it is deterministic).
  - **Recurrence** (≥ R episodes in 24 h).
  - **Rate** (e.g. `NRestarts` delta, disk-fill rate → time-to-full).
- **False-positive protection:**
  - Hysteresis: a separate clear threshold.
  - Minimum duration.
  - Cooldown per metric/subject before reopening.
  - Warming-up suppression after boot or restart.
- **Outcome:** `transient` (closed before escalation) or `escalated` (opens an investigation if the budget allows).
- **Interaction with existing priorities:** a critical anomaly still maps to the critical signal (ADR-0026) and interrupts as today. The investigation is an additional *task* of the `observe_server`/`investigate` activity, never a heartbeat side effect (D6).

### 8.6 Investigation engine (S3)

- **Lifecycle:** `open → collecting → analyzing → concluded | inconclusive | aborted(budget|timeout|source_unavailable)`.
- **Hypothesis catalog** (core data, versioned). Per symptom kind, a list of candidate causes, each with the evidence queries it needs and the scoring rules. Example for `cpu_temp_high`:
  - `cpu_load_high` (needs `cpu_usage` window): supports if CPU ≥ X over the overlap.
  - `process_hog` (needs `top_processes by cpu`, `process_history`): supports if one process accounts for ≥ 50 % of CPU during ≥ 60 % of the episode.
  - `service_activity` (needs `pid→unit`, `unit_logs`): supports if the hog maps to a unit with log activity in the window.
  - `scheduled_job` (needs timer units' `ActiveEnterTimestamp`): supports if a timer fired at the episode start ± 2 min.
  - `cooling_or_ambient` (no CPU/process correlation, temp high at low load): residual hypothesis, never above `low` confidence without direct evidence.
- **Step loop** (runtime orchestrator, outside the lock):
  1. Core picks the next query from the open hypotheses' unmet evidence needs. The order is the deterministic catalog priority.
  2. The Brain may *suggest* the next query among the allowed ones, validated like a Director target (OD-15; default rule-only in S3).
  3. Runtime calls the observer or senses with a deadline.
  4. The result is stored as `evidence` (a committed transition).
  5. Core rescores the hypotheses.
- **Budgets** (per investigation):
  - depth (≤ 3 levels: symptom → resource → actor → context);
  - ≤ 12 queries;
  - ≤ 90 s wall time;
  - ≤ 2 concurrent investigations (normally 1);
  - a daily cap on investigations;
  - adapter-level rate limits.

  An exhausted budget → `inconclusive`, with "what to check next".

### 8.7 Correlation and confidence model

- **Evidence:** `id, investigation_id, source (adapter + query + params), window, as_of, summary (structured JSON, bounded), digest (sha256 of the canonical result), redacted (bool), status (ok | unavailable | error)`.
- **Correlation primitives** (core, pure, integer or rational math):
  - temporal overlap ratio;
  - share of resource;
  - lead/lag (cause precedes symptom ≤ Δ);
  - co-occurrence count across recurrences;
  - contradiction (evidence that rules a hypothesis out).
- **Confidence:**
  - Each hypothesis has rule-scored points: supporting − contradicting, capped per evidence kind.
  - Bands: `low` (< 40), `medium` (40–69), `high` (≥ 70, requires ≥ 2 independent evidence kinds *and* no contradiction).
  - **Only core sets confidence.** A model never raises it.
- **Symptom ≠ cause:** the report schema separates `symptom` (anomaly facts) from `probable_cause` (the top hypothesis, if ≥ medium). Otherwise the result is "undetermined" plus the next steps (roadmap S4: "do not assert without enough evidence").

### 8.8 Report (S4) and explanation

- **Report record:** `symptom, probable_cause (hypothesis code + band) | undetermined, supporting_evidence_ids, contradicting_evidence_ids, impact (core rule: affected services/resources), what_changed (diff of unit states/process set vs baseline window), next_checks (from unmet evidence needs), uncertainty (text from rules), created_at`.
- **Wording:**
  - The rule template is always available.
  - An optional Brain `POST /explain` (contract `maple.explain.v1`) receives *only* the structured report plus evidence summaries (redacted) and returns ≤ 800 chars of text in which **every factual sentence must cite evidence ids** (`[e12]`).
  - Core rejects text that mentions a process, unit, or number not present in the cited evidence. This is the journal grounding rule (`core.journal.accept_drafts`) generalised.
  - Rejection → rule wording.

### 8.9 Audit trail and notification rules

- **Audit:** anomaly, investigation, evidence, hypothesis_score, report, and notification rows are all append-only, with life-event envelope store `investigation`.
- **Notifications:**
  - **Channel:** Discord via **pull**. `maple-discord` polls `GET /api/notifications?after=<id>` (new, read-only, gateway-token-guarded). Maple keeps no outbound network.
  - **Rules:**
    - severity ≥ warning and the investigation concluded or inconclusive after the budget;
    - one notification per episode (dedupe), with updates only on severity escalation or conclusion;
    - quiet hours (owner local night) except critical;
    - ≤ N per day;
    - every notification links to the report id.
  - The **Inspector** shows the full history.

### 8.10 Failure behavior

| Failure | Behavior |
|---|---|
| Observer down / socket missing | Adapters `unavailable`. Investigations proceed with the main senses only, and are capped at `medium` confidence if key evidence is missing (recorded). Subsystem health → `degraded`. |
| Adapter timeout | Evidence `unavailable(timeout)`, counted against the budget |
| Redaction error | Drop the data (fail closed), evidence `error(redaction)` |
| History DB locked or stale | `unavailable(stale)`; never inferred |
| Brain `/explain` failure | rule wording |
| Too many anomalies (storm) | rate limit: escalate the highest severity only; others are recorded `suppressed` |

### 8.11 Future remediation: extension point only

- **Data:** `remediation_proposal` (`id, report_id, action_code from a closed catalog (e.g. restart_unit), target, rationale, status: proposed | declined | expired`). There is **no `approved`/`executed` state in the schema until a future ADR adds it.**
- **Explicitly not implemented:** any executor, endpoint, polkit rule, capability, or D-Bus method beyond reads.
- **A future design would require:**
  - owner approval per action with strong authentication;
  - a separate privileged agent with a per-action allowlist and its own unit and audit;
  - a dry-run;
  - rate limits;
  - a never-again switch;
  - its own threat model and an owner ADR.

### 8.12 System Room integration

- **Visual state is derived:**
  - console `calm | alert | investigating | reporting` from attention and open investigations;
  - wall display shows the last report band;
  - a history shelf for past investigations, as creation-like objects with links.
- **Activity:** an anomaly escalation makes `observe_server` (task `inv:<id>`) a candidate with a `system_console` requirement. The critical signal still interrupts as today.
- Maple walks to the System Room console; the investigation steps run while she "uses" it. The investigation itself is not paced by animation. Steps run on their own budget; the activity's duration spans them.

---

## 9. Art / visual technical architecture

The production rules are in `maple-art-production-contract.md`. This section covers the engine side.

### 9.1 Coordinate system

- **World space:**
  - 1 unit = 1 art pixel at 1×.
  - Tiles are `T×T` (provisional 16).
  - Each room has a tile grid; the house places rooms by a tile offset.
  - Depth is *not* a coordinate: draw order comes from y-sort.
- **Screen space:** world × integer zoom `Z ∈ {1, 2, 3, 4, 5, 6}` − camera offset, rounded to whole device pixels.
- **Backend:** speaks tiles (plus px offsets for occupy poses from the catalog). It never speaks screen pixels.
- **Pixel-perfect rules:**
  - nearest-neighbour sampling (`scaleMode: 'nearest'`);
  - `antialias: false`;
  - `roundPixels: true`;
  - integer zoom only for the world layer;
  - camera translation snapped to `1/Z` world units, i.e. whole screen pixels;
  - interpolated character positions rounded at render time (not in state);
  - canvas backing store = CSS size × DPR with an integer `Z × DPR` product. If DPR is fractional (e.g. 1.25), use `resolution = 1` and integer CSS-pixel zoom to avoid shimmer.

### 9.2 Render layers (Pixi scene graph)

```
stage
└── viewport (camera transform: integer zoom, snapped translation)
    ├── L0 backdrop        outside-window scenes (Digital Nature / Quiet City Edge), parallax
    ├── L1 floor           tilemap (per room, cached as RenderTexture chunks)
    ├── L2 floor_decals    rugs, floor marks (non-blocking flat objects)
    ├── L3 walls_back      north walls + wall-mounted decor on north walls
    ├── L4 shadows         contact/blob shadows (alpha), never baked
    ├── L5 entities        y-sorted: object parts + Maple + props   (sortableChildren, zIndex = sort key)
    ├── L6 occluders       wall tops / door lintels / "always-front" parts
    ├── L7 light_multiply  darkness tint per room (multiply)
    ├── L8 light_add       lamp glows, window light, monitor glow (additive sprites)
    ├── L9 emissive        screen/LED pixels that must not darken (drawn after L7)
    ├── L10 fx_world       particles, reaction glyphs anchored to world
    └── L11 editor_overlay grid, footprints, collision, slots, interaction points, validation marks
DOM overlay (outside Pixi, D2): text speech bubble, hotspots/labels, editor tool panels, panels
```

- **Sort key** = the world y of the part's ground line (the object footprint's south edge, plus the part's `sort_offset`; Maple's feet y).
- **Ties:** `layer_priority` (floor props < furniture < occupant < overlay), then a stable instance id.
- **Occupant overlays:** e.g. the bed blanket or a chair back drawn over a seated Maple. They are separate parts with `sort: "above_occupant"`.

### 9.3 Camera, zoom, viewport, modes

| Mode | Behavior |
|---|---|
| **Overview** | fit the house at the largest integer Z that fits; letterbox; if Z would be < 1, show a DOM minimap plus room list instead |
| **Follow** | centre on Maple with a dead-zone (e.g. 25 % of the viewport), eased with integer-snapped output; room transitions keep following |
| **Focus** | frame one room or one object (editor, Inspector "show me"), at the largest integer Z that fits |

- **Bounds:** the camera clamps to the house bounds.
- **Zoom:** user control steps through integer levels only.
- **Reduced motion:** snap the camera, no easing.

### 9.4 Hit areas, interaction, pathfinding boundary

- **Hit testing:**
  - Pixi `eventMode` on object parts with a **polygon hit area from the art manifest** (fallback: the footprint rectangle).
  - Live mode: hover/click shows info (DOM). It never commands Maple; D3/D31 are unchanged.
  - Edit mode: select, drag, rotate.
- **The renderer never pathfinds or validates.** It renders `route` waypoints over time (as today's `routeFrame`, now with tile waypoints and 4-direction facing derived from segment direction). Collision and slot overlays in edit mode are *drawn from backend data* (catalog masks + preview results).

### 9.5 Asset registry and manifest (engine side)

**Two registries, joined by `type`:**

1. **Object catalog** (backend, §6.5): engine metadata.
2. **Art manifest** (frontend):

```jsonc
{"type": "furniture.writing_desk", "art_revision": 3, "geometry_version": 1,
 "atlas": "studio", "orientations": {
   "south": {"parts": [
      {"part": "base",       "frame": "furniture.writing_desk--default--south", "anchor": [0, 47], "sort_offset": 0},
      {"part": "chair_back", "frame": "furniture.writing_desk--default--south--chair_back", "anchor": [0, 47],
       "sort": "above_occupant"}],
     "shadow": "shadow.rect_3x2", "hit": [[0,20],[48,20],[48,47],[0,47]],
     "light":  null, "emissive": null}},
 "states": {"default": {}}, "fallback": "placeholder.furniture_3x2"}
```

**CI cross-check:** every catalog type has a manifest entry. `geometry_version` must match, the footprint × T must be consistent with the frame floor area, and every state and orientation must be covered or explicitly fall back.

### 9.6 Performance

- **Atlases:**
  - One per room theme (`bedroom`, `living`, `library`, `studio`, `creation`, `system`, `hall`), plus `character_maple`, `shared_props`, `fx`, `ui_world`.
  - Max page 2048×2048 (safe for any WebGL2 device). Packed at build time by the frontend pipeline from individual delivered PNGs, with 2 px extrusion and power-of-two pages.
- **Loading:**
  - Boot: `character_maple` + the current room's atlas + shared.
  - Lazy: adjacent rooms when the camera or Maple's route enters a door, with idle prefetch of the rest.
  - Unload: rooms not visible for > N minutes may unload (Pixi `Assets.unload`).
- **Memory budget:** ≤ 48 MiB of GPU textures for a full house (about 12 pages of 2048² RGBA = 192 MiB if careless; budget enforced by an atlas-size CI check). Target ≤ 6 pages total at v1.
- **Floor tilemaps:** baked per room into cached chunks (RenderTexture), re-baked on layout revision.
- **Frame budget:** 60 fps on desktop; ≤ 300 sprites in view.
- **CSP:** assets are same-origin (`/assets/...`), so the existing CSP allows them. Atlas JSON is loaded by fetch; no eval (the existing `pixi.js/unsafe-eval` import stays).

### 9.7 Responsive behavior

- **Desktop-first:** room viewport plus DOM panels.
- **Tablet:** viewport on top, panels below; default Follow mode at Z = 2–3.
- **Phone:** Focus on Maple's current room at the largest integer Z; overview replaced by the DOM room list or minimap. Editor not offered below a minimum viewport (e.g. 900 px wide).
- **Room switching** in the UI is camera-only. It never moves Maple.

---

## 10. Art Production Contract (summary)

The full, standalone contract is in `docs/architecture/maple-art-production-contract.md`. It is written as a handoff for a separate Maple Art chat. It has three separated parts:

1. **Concept art rules:** freedom of style within the agreed direction. Not engine-bound, but avoids choices that make production impossible (e.g. baked dramatic lighting, perspective that isn't 3/4 top-down).
2. **Production asset rules:**
   - canvas and frames;
   - transparent PNG-32 with binary alpha on base sprites;
   - feet/footprint anchors;
   - tile alignment;
   - footprint drawn on the grid;
   - directions ordered `down, left, right, up`;
   - sheet layout (rows = directions, columns = frames);
   - separate layers for shadow, light, emissive, and overlay parts;
   - neutral lighting;
   - naming `category.name[.variant]--state--orientation[--part].png`;
   - delivery directory;
   - versioning (`art_revision` vs `geometry_version`);
   - no gutters (the pipeline extrudes);
   - integer scale only.
3. **Engine metadata requirements:** what each delivery must state (footprint, interaction points, slots, sort offsets, hit polygons, frame timings, loop modes, animation events), with examples for Maple, bed, desk, bookshelf, server console, wall decoration, and project object.

It lists **SAFE TO PRODUCE NOW** (style bible, concepts, moods, poses, lighting references) and **WAIT FOR TECHNICAL LOCK** (final tile size, sheet dimensions, footprints, collision, interaction coordinates, frame counts, door dimensions, export sizes, atlas packing).

Values are given as **provisional defaults** (T = 16 px, Maple frame 32×48 px, feet anchor (16, 47)) to be locked by the technical spike (§22).

---

## 11. Cross-system integration

### 11.1 Ownership and identifiers

| Entity | Owner (writer) | Id form | Stored in |
|---|---|---|---|
| Layout, rooms, instances, zones | core world (owner edits / Maple placements) | `room:<slug>`, `obj:<n>`, layout `rev:<n>` | `maple.db` |
| Object types | release catalog | `furniture.writing_desk` | release data |
| Projects, files, versions, artifacts | core work | `project:<n>`, `file:<n>`, `ver:<n>`, `artifact:<n>` | `maple.db` (+ blobs) |
| Library items | core work | `libitem:<n>`; release docs keep `library:<id>` | `maple.db` |
| Investigations, evidence, reports | core investigate | `inv:<n>`, `ev:<n>`, `report:<n>` | `maple.db` |
| Jobs | core work (executor runs them) | `job:<n>` | `maple.db` |
| Decisions, actions, goals | core (existing) | existing integer ids | `maple.db` |

**Representation rule:** a domain entity becomes visible in the Room only through a **representation**, which is core-derived from entity kind and state:

| Entity state | Representation | Eligible slots (`accepts`) |
|---|---|---|
| project `planned` | `project.card` | `project.board` (Work Studio board) |
| project `active` | `project.active_stack` | `project.active` (Work Studio desk) |
| project `paused` | `project.box` | `project.shelf` |
| project `completed`/artifact `final` | archetype by kind: `creation.book`, `creation.frame`, `creation.device`, `creation.plant`, `creation.trophy` | `creation.*` slots (Creation Room, display shelves, walls) |
| library item | `library.book` (spine colour by kind and status) | bookshelf `book_storage` slots (derived fill) |
| investigation report | `system.report_binder` | System Room history shelf |

**Object links** are *soft references*: `object_instance.link = {kind, id}`. A missing or archived target renders the object in an "archived" or "unlinked" variant and never fails the world load (failure isolation). Not every file is an object (roadmap R5): only projects, final artifacts, selected creations, library items (aggregated as shelf fill), and reports.

### 11.2 Events across subsystems

All events use the existing life-event envelope and SSE hub. **Subsystems never subscribe to each other.** Core derives cross-effects inside the same transition or in the next decision context:

- A work transition that marks an artifact `final` also, in the same transaction, makes a representation *eligible* (derived). No world write happens until Maple or the owner places it.
- An investigation transition opening `inv:<n>` makes the derived console state `investigating`, with no world write.

### 11.3 Flow 1: workspace project completes → Room

1. Maple's `write`/`code` work step proposes `complete_step` + `set_project_status completed` (`maple.work.v1`).
2. Core validates: all required artifacts are `final`, and there are no running jobs. Commit: project `completed`, `project_event`, `artifact.status=final`, life events (`work` store).
3. The representation becomes derived-eligible (`creation.device` for a program). The next decision context lists `place_creation` options (eligible slots with free capacity, Maple-allowed).
4. Director (or rule: "display new creations within a day") proposes the action `arrange` (a new activity, or a `walk`/`idle` with task `place:artifact:42→slot obj:31/shelf_2`).
5. Core validates: slot accepts the archetype, capacity is free, the slot policy allows Maple, the zone guarantee holds.

   Maple walks to the slot's approach point (backend route) and, on arrival + duration, commits the `display_placement` row + world event `object_placed`.
6. SSE `world` → the frontend refetches placements → the renderer shows the object (a slot sprite position from the catalog plus the archetype art).

**If any step fails** (slot taken meanwhile, path blocked, workspace unavailable): the action is rejected or interrupted with a reason. The artifact stays "in storage" (a derived list). Nothing is lost.

### 11.4 Flow 2: system anomaly → report

1. Heartbeat stores observations (existing). The anomaly rules (core, run in the heartbeat transition: pure, no external calls) open or extend an `anomaly` episode.
2. Escalation (duration/severity met, budget OK) → an `investigation` row (`open`). Decision becomes due with a candidate task `inv:<n>`. A critical anomaly additionally raises the existing critical signal.
3. Decision: `observe_server` with task `inv:<n>` → resolution needs `system_console` → Maple walks to the System Room console.
4. On arrival, the orchestrator runs steps outside the lock. Each observer/sense query → evidence committed → hypotheses rescored. Console state is derived `investigating`.
5. Conclusion → `report` committed (rule or validated `/explain` wording) → a notification row, if the rules allow.
6. `maple-discord` pulls `/api/notifications` → posts to Paolo. The Inspector shows the report with evidence. The System Room wall display shows the band.
7. **Observer down:** step 4 records `unavailable` evidence. The report says what could not be checked; confidence is capped.

### 11.5 Permission boundaries across the chain

```
Brain (no tools) ──proposals──► core (validates) ──commands──► workers
   maple-exec: compute on a copy, no network, no /data
   maple-observer: read allowlisted host facts, redact, no writes
   storage: only maple-svc writes, only /data/maple (+ workspace mount inside it)
Owner: edits layout, approves projects, installs toolchains (root, owner-run)
```

### 11.6 Failure isolation matrix

| Subsystem down | Room | Workspace | Investigator | Maple's life |
|---|---|---|---|---|
| Room world data invalid | stale/placeholder view | unaffected | unaffected | continues; activities needing unreachable capabilities are disallowed |
| Workspace mount missing/full | creation displays still render (pinned metadata); new placements of new artifacts not possible | `unavailable`/`read_only` | unaffected | continues (no write/code tasks) |
| `maple-exec` down | unaffected | edits allowed, runs `unavailable` | unaffected | continues |
| `maple-observer` down | console shows `degraded` | unaffected | reduced evidence, capped confidence | continues |
| `maple-brain` down | unaffected | rule-only (no code generation → coding tasks unavailable, notes still template-written) | rule wording | rule direction (existing) |
| `maple-discord` down | — | — | notifications queue in DB | continues |

---

## 12. Data model proposal (conceptual, not schema)

| Concept | Decision | Notes |
|---|---|---|
| room | **new** (inside the layout revision document) | not a separate mutable table; a layout is versioned as a whole |
| room_connection | **new** (inside the layout document) | |
| world_object (type) | **release data**, not DB | catalog version and hash recorded per layout revision |
| object_instance | **new** (inside the layout document) + `object_state` table for mutable per-instance state (only if a non-derived state is needed) | ids stable across revisions |
| placement_slot | catalog (type slots) + layout (owner zones) | not a DB table |
| display_placement | **new table** (mutable current) + world events (append-only) | Maple/owner placements |
| interaction_point | catalog | executed point keeps being recorded in `decision.executed_point` / `action_event` (existing) |
| world_state | **new single row**: active layout revision, catalog version | or columns on `life_state`; prefer a separate row to avoid rebuilding `life_state` again |
| world_layout_revision | **new append-only table**: id, created_at, author (paolo / migration), base_revision, catalog_version, document JSON, validation digest | |
| Maple position | **extend `life_state`**: `room_id, tx, ty`; route path format v2 | migration (rebuild, as v4) |
| activity / location enums | **migrate CHECKs → lookup tables** (`activity_kind`, FK) | future activities = row inserts, not rebuilds; `RoomLocation` retired in favour of instance points |
| project, project_event, project_task | **new** | |
| workspace_file, file_version | **new** | blobs on disk |
| artifact | **new** | pins versions |
| creation | **no separate entity**: an artifact with `kind` + representation | avoid duplication |
| library_item, reading_progress, reading_session | **new**; release `library:*` stays catalog | ADR-0029 catalog extended with `libitem:` ids |
| document | **reuse unchanged** (Maple's immutable notes) | |
| tool_use | **extend** with new operations (`file_write`, `file_delete`, `job_run`, `place`) or **new** `work_event` | prefer extending via a lookup-table enum |
| execution_job, job_event | **new** | |
| anomaly | **new** | |
| investigation, evidence, hypothesis_score, report | **new**, append-only | |
| system_event | **avoid**: covered by observation + anomaly + evidence | no duplicate generic event table |
| notification | **new** (append-only, with a delivery cursor per consumer) | |
| observation | **reuse**; add metrics (swap, net, diskio) via a lookup-table migration | **retention needed** (§15) |
| memory | **reuse**; new kinds (`project`, `investigation`) via enum migration | |
| subsystem_health | **derived** from audit (the ADR-0034 pattern) | no table |

**Schema strategy:**
- Continue forward-only numbered migrations with the pre-migration snapshot.
- Move from literal CHECK enums to lookup tables at the first rebuild that touches them (M-R1), so later capability growth avoids rebuilds.
- Every new history table is append-only by trigger.
- JSON documents (layout) are validated by core before insert and are size-capped by CHECK.

---

## 13. Process / service model

| Component | Placement | Purpose | Why (not) separate | Account | Filesystem | Network | API boundary | Failure isolation | Lifecycle |
|---|---|---|---|---|---|---|---|---|---|
| Room/world | **main backend** | world model, pathfinding, validation, editor endpoints | pure computation on Maple's own data; separation would only add consistency problems | `maple-svc` | `maple.db` | loopback | REST/SSE | world errors degrade the view only | release |
| Workspace metadata + blob store | **main backend** | single writer for files and metadata | one writer = consistent ordering (§7.6); D19 holds | `maple-svc` | `/data/maple/workspace` (mount, noexec) | — | internal | mount missing → `unavailable` | release; owner creates the mount |
| **maple-exec** (W4) | **socket-activated per-job sandbox** | run Maple's code | executes untrusted code; must not share the backend's uid, files, or network; backend must stay subprocess-free | `DynamicUser` per job | own tmpfs `/work`, minimal rootfs; no `/data` | none (`PrivateNetwork`) | Unix socket, bundle in/result out | job dies alone; `RuntimeMaxSec`, cgroup limits | socket always listening; instance per job |
| **maple-observer** (S1) | **long-running read-only adapter** | process, logs, net, cgroup, Tailscale reads | needs read privileges (`/proc` visibility, journal group) the main unit must not have; raw secrets stay out of the main process | `maple-observer-svc` (system, nologin, `systemd-journal` group only if OD-12 is approved) | read-only everywhere; no StateDirectory; `/data` inaccessible | `IPAddressDeny=any`; AF_UNIX only | Unix socket, closed-enum queries | down → capped investigations | release-bundled, owner-installed unit |
| Investigation engine | **main backend** | anomaly, hypotheses, scoring, reports | pure rules + orchestration; needs the single writer | — | — | — | internal | — | release |
| maple-brain | existing companion | + `/work`, `/explain` | unchanged rationale (ADR-0025/0033) | `maple-brain-svc` | unchanged | outbound (provider) | loopback HTTP | rule fallbacks | unchanged |
| maple-discord | existing companion | + notification pull, report commands | unchanged | `maple-discord-svc` | unchanged | outbound (Discord) | loopback HTTP to Maple | queue in DB | unchanged |
| Asset pipeline | **build time only** (trusted build machine) | pack atlases, validate assets | not runtime | — | — | — | — | build fails | `scripts/build_release.sh` |

**Not proposed:**
- No separate "world service".
- No "workspace service" in W1–W3.
- No job queue daemon (the socket with `MaxConnections=1` plus a DB `queued` state in core is the queue).
- No message broker.
- No container runtime.

---

## 14. Security / threat model

Legend: **C** = control, **V** = validation/test, **R** = residual risk.

| # | Threat | Impact | Control | Validation / test | Residual risk |
|---|---|---|---|---|---|
| T-01 | **Path traversal** in file ops (`../`, absolute, drive, device names) | write/read outside the workspace | logical paths are DB strings with a strict grammar; disk names are content hashes; `DataDir` jail on the workspace root; no API accepts host paths | grammar property tests; existing `test_datadir.py` cases extended to the workspace root; AST rule: no path-from-input joins outside `storage` | low |
| T-02 | **Symlink escape** (job outputs, bundles, the store) | read/write host files | blob store contains only regular files created by `maple-svc`; tar import rejects symlinks, hardlinks, devices, FIFOs, absolute paths, `..`; `DataDir` resolves `strict`; `nosuid,nodev` mount | fuzzed tar corpus (link, `..`, long names, sparse, zip-slip); `sandbox_probe` additions | low |
| T-03 | **Arbitrary execution** in the main backend | full `maple-svc` compromise | no subprocess/eval in backend (existing AST + ruff); workspace mounted `noexec`; executor is a separate unit | existing forbidden-API tests unchanged; unit contract test asserts `noexec` in the mount requirement docs; `check_boundaries` verifies mount flags | low |
| T-04 | **Malicious generated code** in the sandbox | escape, host damage, data theft | DynamicUser, no caps, NNP, seccomp, no network, minimal rootfs, `/data`/home inaccessible, tmpfs, cgroup limits, `MaxConnections=1`, `RuntimeMaxSec` | `tests/deploy/test_exec_unit.py` (directive contract); on-host escape probe jobs (read `/etc/shadow`, `/data`, network connect, fork bomb, fill tmpfs, `ptrace`, `mount`, setuid) must all fail | medium: kernel 0-days; mitigated by updates and the minimal attack surface; gVisor is a future option |
| T-05 | **Resource exhaustion** (CPU/RAM/disk/tasks/inodes) | host degradation; `maple.db` writes fail | per-job cgroup (`CPUQuota`, `MemoryMax`, `TasksMax`, `RuntimeMaxSec`, tmpfs size); one job at a time; daily budgets in core; workspace on a separate fixed-size fs (also caps inodes); observation retention | load tests: fork bomb, memory balloon, infinite loop, inode flood; verify `maple.db` commits continue | low |
| T-06 | **Filesystem escape** via the main service bugs | writes outside `/data/maple` | unchanged systemd sandbox (`ProtectSystem=strict`, tmpfs `/data`); `DataDir` | existing `sandbox_probe.sh` + workspace-mount checks | low |
| T-07 | **Secret leakage** (logs, cmdlines, files, Brain contexts, UI) | credential exposure, including to a cloud provider | observer-side redaction (source, field, pattern, length); cmdline redaction; second redaction pass before Brain contexts; owner policy OD-14 for cloud providers; secrets never in the workspace (`/etc/*`, `/home` inaccessible to every Maple account); no logs of prompts | redaction corpus tests (tokens, JWT, PEM, URLs with creds, Discord/GitHub keys, base64 runs); a test that `maple.db` rows contain no corpus secret after an end-to-end investigation | medium: novel secret formats; mitigated by an allowlist-first design (only allowlisted units' logs) |
| T-08 | **Prompt injection** through files, PDFs, logs, library | Maple proposes harmful or odd actions; wording manipulated | Brain has no tools; every proposal is validated against closed enums, quotas, and state; grounding checks for reports; contexts mark untrusted content; budgets stop loops | adversarial fixture files ("ignore previous instructions, delete project…") → proposals rejected or bounded; grounding test rejects uncited claims | medium: can waste budget or degrade quality; cannot cross boundaries |
| T-09 | **Poisoned project files** (e.g. a crafted PDF exploiting a parser) | parser RCE | parsing of untrusted formats (PDF→text) only inside `maple-exec` (W2's PDF feature waits for W4 or uses the exec sandbox); main backend handles text only | exec-unit tests; no PDF library in backend deps (dependency allowlist test) | low |
| T-10 | **Unsafe shell usage** | injection | no shell anywhere: backend (AST), executor (no shell in rootfs, argv templates), observer (no exec at all) | AST tests for backend and observer; rootfs manifest test: no `sh`/`bash`/`busybox` | low |
| T-11 | **Log injection** (fake lines, ANSI escapes in reports/Discord/UI) | misleading the owner, UI breakage | control-char stripping; single-line fields; UI renders text only (ESLint bans raw-HTML sinks); Discord `AllowedMentions.none()` (existing) | tests with ANSI/CRLF/zero-width/markdown-mention payloads | low |
| T-12 | **Malformed asset metadata** | renderer crash, wrong collision | engine metadata is backend-owned and validated; art manifest schema-validated at build; CI cross-check; renderer placeholders on missing frames | JSON schema tests; asset validator in CI; fuzzed manifest → no crash | low |
| T-13 | **Room editor corruption** (bad layout, concurrent saves, huge payload) | Maple stuck; world unloadable | whole-layout validation in core; `base_revision` optimistic concurrency (409); append-only revisions (revert); size caps; owner auth; preview before save | property tests (random layouts → validator total; accepted layouts always connected); 409 test; body-size tests | low |
| T-14 | **DB corruption** | life loss | unchanged: WAL+FULL, integrity checks, pre-migration snapshots, nightly verified backup; workspace on a separate fs; retention keeps the DB bounded | existing storage tests; restore drill includes the workspace | low |
| T-15 | **Privilege escalation** (sudo, setuid, polkit, D-Bus methods) | root | no caps/NNP/`RestrictSUIDSGID` on all units; polkit deny for every Maple account (`maple-svc`, `maple-observer-svc`, DynamicUser jobs via a `unix-user` range or a group rule); D-Bus method allowlist unchanged | `check_boundaries` per account; polkit rule tests; D-Bus allowlist test extended for new properties only | low |
| T-16 | **Service-account boundary failure** (a shared group or socket gives more than intended) | cross-service access | sockets 0660 with group `maple-svc` only; observer and exec have no write paths; no account in docker/adm/sudo/journal (except observer → journal, if approved) | `check_boundaries` asserts groups, socket modes, mount namespaces per unit | medium for the observer's journal group (reads all journals); mitigated by code-level unit filtering + redaction; alternative: journald namespaces for allowlisted units (OD-12) |
| T-17 | **Owner-endpoint abuse** (editor, approvals) from any tailnet device | layout tampering, approving risky projects | owner authentication (Tailscale identity header from Serve: `Tailscale-User-Login` matched against an allowlist; plus the existing Origin check); rate limits | header-spoof test (direct loopback requests without Serve must not be trusted unless from Serve; verify Serve strips client-supplied identity headers); route-table test updated | medium until OD-03 is resolved |
| T-18 | **Investigation DoS / feedback loop** (investigating its own load) | host load | budgets, rate limits, observer reads are cheap (`/proc`, bounded journal windows); the observer has its own `CPUQuota` | load test with an anomaly storm | low |

---

## 15. Persistence, backup, recovery

| Data | Location | Backup | Recovery |
|---|---|---|---|
| `maple.db` (all metadata incl. world, work, investigation) | `/data/maple/maple.db` | ADR-0024 (unchanged) | ADR-0024 restore / R6-style owner restore |
| Workspace blobs | `/data/maple/workspace/objects` | restic path (new, ADR-0024 amendment, owner-run patch) | restore + `maple-workspace-verify` |
| Pre-migration copies | `/data/maple/pre-migration` | as today | as today |
| Object catalog, art atlases, runner, observer code | release (`/opt/...`) | rebuildable from git | reinstall release |
| Toolchains | `/opt/maple-exec/toolchains` | rebuildable from pinned locks | owner rebuild |
| Observer ring buffers | memory | none (by design) | lost on restart; documented |

**Retention (needed now, before S1):**
- `observation` already grows ~0.54 MB/day. The proposal is to keep it 90 days raw, then downsample to hourly aggregates in a new `observation_hourly` table. Because the history is append-only, the "delete" must be an owner-approved, ADR-defined *compaction transition* that keeps aggregates and the audit of the compaction. This is a conscious exception to "append-only, never deleted" and needs owner approval (OD-16).
- Evidence summaries stay small (bounded JSON). Job stdout/stderr blobs fall under workspace retention.

**Restart semantics:**
- World, work, and investigation state all reload from `maple.db`.
- A job running at shutdown is recorded `killed(shutdown)` on the next start (detected by a `running` row without a live connection).
- An investigation in progress resumes or ends `aborted(restart)`. Recommendation: abort and re-escalate if the anomaly is still open. That is simpler and deterministic.

---

## 16. Failure, timeout, and fallback strategy

| Call | Timeout | Concurrency | On failure |
|---|---|---|---|
| Director `/decide` | existing 15 s | never stacked | rule direction |
| Replier `/reply` | existing | never stacked; `busy` | rule reply |
| Journal `/generate` | existing 30 s **inside the lock** | — | no wording. **Fix before roadmap work (R-01):** move outside the lock or reduce the timeout and add caps. |
| Work `/work` | 30 s (proposed) | one per step | step skipped; after N failures the task is paused; notes fall back to templates |
| Explain `/explain` | 15 s | one | rule wording |
| Exec job | `RuntimeMaxSec` 120 s + connect 2 s | `MaxConnections=1`; core queue | job failed/timed_out; Maple continues |
| Observer query | 3 s each, 90 s per investigation | ≤ 2 in flight | evidence `unavailable` |
| World preview/save | in-process (bounded by layout size caps) | owner only | 4xx with validation errors |
| Workspace blob I/O | fs | single writer | `unavailable` capability, recorded |

**General rules:**
- The heartbeat never makes an external call (D6). Heartbeat-time additions (anomaly rules, retention bookkeeping) are pure.
- Every worker result is re-validated after it returns, as `stale` handling does today.
- Subsystem health generalises ADR-0034: a read-only report per subsystem (`world`, `workspace`, `exec`, `observer`, `brain`) is computed from the audit plus a one-shot liveness probe. There is no polling and no new log.

---

## 17. Migration strategy

Every step is forward-only, preceded by the automatic verified pre-migration copy, gated by `activate_release.sh --allow-migration`, and changes the pinned simulation digest deliberately.

| Step | Migration | Content | Risk control |
|---|---|---|---|
| M-0 | none | docs drift fixes (§2.7); R-01 fix (journal Brain outside the lock), separate small PR | normal review |
| M-R1 | v11 (rebuild `life_state`, `timeline_event`, `journal_entry` as v4 did) | lookup tables for activity/location kinds; `life_state` position `room_id, tx, ty` + route v2; seed `world_layout_revision` #1 (the current 7 furniture pieces as instances in room `living`); `world_state` row; in-flight routes converted to zero-length at destination (as ADR-0027 did) | in-transaction verify: identity, counters, history counts; startup invariant check; v10 restore path documented (loses life since) |
| M-R1b | none or data-only | additional rooms as layout revisions (authored data in the release, applied by an owner-triggered or release migration step that creates revision #2) | revision history allows revert |
| M-R2 | v12 | `object_state` (if needed), `display_placement`, world events | additive |
| M-W1 | none in DB; host: workspace mount (owner-run) | `RequiresMountsFor` in the unit; `check_boundaries` mount flags | unit contract test |
| M-W2/W3 | v13 | project, workspace_file, file_version, artifact, library_item, reading_progress, project_event/task | additive |
| M-W4 | v14 | execution_job, job_event; new units `maple-exec.socket`/`@.service`; toolchain rootfs | owner-run install; contract tests |
| M-S1 | v15 | observation metric lookup additions; anomaly; investigation/evidence/hypothesis/report/notification; observer unit | additive; owner-run install |
| M-RET | v16 (with OD-16) | `observation_hourly` + compaction audit | owner approval; backup before the first compaction |

**API compatibility:**
- Additive fields first.
- `/api/room` is retained as a compatibility view for one release.
- `activity.location` is kept, derived as the instance type's legacy location where one exists, else `null`, until the frontend has migrated.
- The route-table test is updated in the same PR as each new endpoint.

---

## 18. Roadmap mapping

### 18.1 Per phase

| Phase | Reusable now | Architecture work | Schema | Service/process | Security | Art/asset | Depends on | Acceptance |
|---|---|---|---|---|---|---|---|---|
| **R1 Foundation** | movement semantics, route-in-state, RNG, DOM/Pixi split, day phase | tile grid, room graph, doors, A\* 4-dir, camera modes, layered renderer, pixel-perfect pipeline, catalog loader | M-R1 | none | none new (read-only additions) | **technical lock required** (tile, frame, anchors); placeholder art allowed | art spike (§22), ADR world model | Maple walks 4-dir between ≥ 3 rooms through doors, never teleports; deterministic replays; route renders identically from backend data; integer-scale rendering verified at Z=2,3,4 |
| **R2 Object / Activity** | interaction-point idea, task model, Director catalog | object catalog, capability resolution, instance points (approach/occupy), activity→capability table | lookup tables (in M-R1) | none | catalog validation | per-object metadata deliveries (contract §C) | R1 | no code path maps activity→object type directly (test); adding an object type with `reading_spot` makes it used without code change (test); Writing ≠ Computer Desk preserved |
| **R3 Persistence / Growth** | single writer, append-only audit, snapshot | layout revisions, display placements, zones with commit-time guarantee, storage list, growth unlock rules | M-R2 | none | OD-02 (inventory meaning) | creation archetypes, slot sprite positions | R2 | restart keeps world; Maple placements never break paths (property test); placements traceable to decisions |
| **R4 Editor** | Inspector (owner UI), store | edit mode, draft, preview/save/revert, 409 rebase, owner auth | none (uses revisions) | none | **owner auth (OD-03)**, new mutation endpoints | editor overlay assets, hit polygons | R3, ADR owner endpoints | invalid layouts impossible to save; undo/redo; concurrent save → 409; Maple reroutes after save |
| **R5 Project/Library/Creation** | document, library catalog, tool_use | representations, links, Library shelves (derived), Studio boards | uses W2/W3 tables | none | link resolution soft | project/library/creation archetype art | W3, R3 | every displayed object links to a real source; archived source → archived variant |
| **R6 Polish** | lighting layers | ambient, sound layer, micro-anims, outdoor backdrops | none | none | none | **final Maple sprites**, lighting assets, SFX | all | visual checklist; no backend state invented |
| **W1 Boundary** | `DataDir`, systemd sandbox, D19 | workspace mount, blob store, quotas, path grammar | none (host mount) | none | mount flags, `check_boundaries` | — | ADR workspace | `sandbox_probe`: workspace writable, `noexec`; disk-full in workspace doesn't stop `maple.db` commits |
| **W2 File / Library** | catalog reader, document table | file versions, library items, reading progress, text-only ingestion; owner intake path (OD-17) | M-W2 | none | T-01/T-02 | library book variants | W1 | CRUD via versions; delete = tombstone; restore works; quotas enforced |
| **W3 Projects** | goals, tasks, Director | project lifecycle, `maple.work.v1` (notes/writing first), steps | M-W3 | brain `/work` | T-08 | project representations | W2 | multi-day project resumes after restart; history complete |
| **W4 Coding Sandbox** | companion patterns | `maple-exec`, toolchains, bundle protocol, output validation | M-W4 | **new socket unit** | T-04/T-05/T-09/T-10 | coding pose (`sit_type`) | W3, **exec spike (OD-06)** | escape-probe suite passes on paolo-core; runaway jobs are killed; backend still has zero subprocess usage |
| **W5 Self-directed** | Director, daily intent, approval bubble | creation policy, approval flow, stop conditions | small | none | approval auth (OD-03) | — | W4 | budgets respected over a 30-day sim; approvals required where configured |
| **S1 Observability** | senses, D-Bus RO, storage.external, Brain Health pattern | observer adapter, query enum, redaction, new metrics, monitor-v2 survey | M-S1 (partial) | **new observer unit** | T-07/T-16, OD-09/12/13 | — | ADR observer; retention (OD-16) | queries bounded; redaction corpus passes; observer cannot write anywhere (`sandbox_probe`) |
| **S2 Anomaly** | attention, observations | episodes, baselines, hysteresis | M-S1 | none | — | — | S1 | replay of recorded history yields stable episodes; false-positive suite |
| **S3 Investigation** | decision pipeline | orchestrator, hypothesis catalog, budgets, evidence | M-S1 | none | T-18 | — | S2 | budgets enforced; every evidence row has provenance |
| **S4 Root cause** | journal grounding | scoring, confidence bands, report, `/explain` grounding | — | brain `/explain` | T-08 | — | S3 | uncited claims rejected; undetermined when evidence is weak |
| **S5 Room/Alert** | presence bubble, Discord | System Room derived states, notifications (pull), remediation *proposal record only* | notification | discord pull | no remediation capability (test asserts none) | console/alert/report art | S4, R3 | notifications deduped; quiet hours; no write path exists |

### 18.2 Phase order: original vs proposed

**Original:**

```
STEP 1–2   Room design spec, review architecture
STEP 3–5   R1, R2, R3
STEP 6–8   W1, W2, W3
STEP 9–10  R4, R5
STEP 11–12 W4, W5
STEP 13–17 S1–S5
STEP 18    R6
```

**Proposed** (the roadmap file is not modified; this is a recommendation for the owner):

```
STEP 0     Record missing verification evidence (OD-01); R-01 fix        (new, small; runtime state and docs drift already reconciled 2026-10-08)
STEP 1–2   Room Final Design Spec + this review                          (as original)
STEP 2a    Technical lock spike: tile size, frame sizes, pixel-perfect
           Pixi prototype, placeholder art pipeline → locks Art Contract  (new)
STEP 3–5   R1 (split R1a single-room grid migration, R1b multi-room), R2, R3
STEP 5a    Data retention ADR + implementation (observation compaction)   (moved earlier: prerequisite for S1 growth)
STEP 6–8   W1, W2 (text only), W3
STEP 9–10  R4, R5
STEP 10a   Exec sandbox spike on paolo-core (read-only checks + local VM) (new, before W4)
STEP 11–12 W4, W5
STEP 13–17 S1–S5   (S1 may run in parallel with W-phases; it is independent and read-only)
STEP 18    R6 (final art can be produced continuously from STEP 2a onward, integrated here)
```

**Why:**
1. Art production is starting now. Without a technical lock early, assets risk rework (R-04).
2. R1 bundles a risky DB migration with multi-room work; splitting it reduces the blast radius.
3. Observation retention is already overdue, and S1/S2 add data.
4. The executor mechanism depends on host facts (systemd features, AppArmor userns policy) that must be checked before W4 design is final.
5. S1 is low-risk, read-only, and independent of the workspace, so parallelism is safe if capacity exists. This is optional.

### 18.3 Roadmap conflicts summary

| # | Conflict |
|---|---|
| 1 | "Inventory" vs D3 (OD-02) |
| 2 | Owner editor vs the mutation surface (OD-03) |
| 3 | Workspace modify/delete vs ADR-0029 |
| 4 | Code execution vs §2/§4.1 (new boundary ADR) |
| 5 | Process/log access vs the main sandbox (observer) |
| 6 | Docker health vs the no-socket rule (OD-09) |
| 7 | Character art scheduled in R6 while R1/R2 need sprites (placeholders) |
| 8 | Path `/data/maple/world/` → proposed `/data/maple/workspace/` |
| 9 | metrics.db columns vs D20 |
| 10 | PID→unit vs D12 (OD-10) |

---

## 19. Open decisions (owner)

| # | Decision | Recommendation |
|---|---|---|
| OD-01 | *Narrowed 2026-10-08:* verified so far — the current runtime (main/Brain/Discord active at `160ed4f…`, schema v10, loopback 8470/8471), the loaded hardening (`systemd-analyze security` 1.1 OK), the AI switches = antigravity, Tailscale Serve and Funnel tailnet-only, and nightly backup creation (incl. the Maple DB snapshot). **Still open:** the Stage C authorization record; Phase 8 status; an inside-service runtime boundary probe (the verify scripts are not in the deployed release); a restore test. | owner records the authorization, ships or runs the boundary probe for the deployed release, and tests a restore before roadmap work |
| OD-02 | Meaning of "Inventory" (R3) | "Storage" of Maple's own creations and decorations not displayed; no acquisition, no currency |
| OD-03 | Owner authentication for editor and approvals | Tailscale Serve identity header (`Tailscale-User-Login`) allowlist + Origin; verify header stripping on the host |
| OD-04 | Initial room set and sizes | the 8 roadmap rooms; `future` as a closed placeholder; sizes in the design spec |
| OD-05 | Workspace capacity | 10 GiB image to start |
| OD-06 | Exec mechanism | socket-activated `maple-exec@` + `DynamicUser` + minimal `RootDirectory`; confirm with a spike |
| OD-07 | Runtimes | Python 3.12 stdlib only at W4; Node later with an explicit MDWE exception ADR |
| OD-08 | Internet for jobs | none; a future read-only fetcher as its own capability |
| OD-09 | Docker container health | no Docker socket; cgroup stats only |
| OD-10 | PID→unit lookup vs D12 | allow as evidence lookup only |
| OD-11 | `/data` disk usage source | metrics.db `data_used_pct` history + main senses for `/data/maple` |
| OD-12 | Journal access for the observer | `systemd-journal` group with code-level unit filtering; evaluate journald namespaces as a stricter alternative |
| OD-13 | Tailscale status | LocalAPI status read only, if confirmed read-only for a non-operator user |
| OD-14 | Sending workspace/investigation content to the cloud Brain provider | workspace: allowed (Maple's own content); investigation logs/process data: **not sent** by default (rule wording) |
| OD-15 | Brain suggesting investigation queries | rule-only in S3; revisit in S4 |
| OD-16 | Observation retention/compaction (append-only exception) | 90 d raw + hourly aggregates forever |
| OD-17 | How owner files (PDFs) enter the Library | owner upload endpoint (owner-auth) *or* a read-only owner inbox bind; prefer the upload endpoint with size/type caps |
| OD-18 | Tile size and character frame size | T = 16 px, Maple 32×48; lock in the spike |
| OD-19 | Where source art (`.aseprite`) lives | outside the release bundle; repo `art/` with Git LFS, or a separate art repo |
| OD-20 | W5 initial autonomy | approval required for every new project during the first month, then the policy table |

---

## 20. Recommended architecture decisions (ADRs to write)

Numbers are proposed. Each needs owner acceptance before code.

| ADR | Decision | Amends / supersedes |
|---|---|---|
| 0035 | World model: tile grid, room graph, doors, 4-dir A\*, (room, tile) position, hierarchical pathfinding, no teleport | supersedes ADR-0027 geometry (keeps its semantics) |
| 0036 | Object catalog (engine metadata) vs art manifest; capability-based interaction resolution; approach/occupy points | extends ADR-0027 §1; D26 preserved |
| 0037 | World persistence: layout revisions, display placements, zones with the commit-time guarantee; lookup-table enums | extends ADR-0028 schema policy |
| 0038 | Owner edit endpoints and owner authentication | amends D3/D31 mutation surface |
| 0039 | Workspace storage: `/data/maple/workspace` dedicated noexec mount, content-addressed blobs, metadata in `maple.db`, GC/retention | supersedes ADR-0029 §1 (document table stays) |
| 0040 | Projects, artifacts, library items, representations | — |
| 0041 | Execution boundary: `maple-exec` socket-activated sandbox; toolchain and package policy | scopes §4.1 #2 to the backend explicitly; realises §8 "lab" |
| 0042 | Brain contracts `maple.work.v1`, `maple.explain.v1` | extends ADR-0025/0033 |
| 0043 | Observer adapter service, query enum, redaction | amends §4.3 for a new account; D21 property allowlist; D20 columns |
| 0044 | Investigation model: anomaly, hypotheses, evidence, confidence, reports, notifications; remediation proposal-only | — |
| 0045 | Data retention and compaction | amends "append-only, never deleted" for observations only |
| 0046 | Art technical lock (tile, frames, anchors, layers, naming) | locks `maple-art-production-contract.md` |
| 0047 | Subsystem health generalisation | extends ADR-0034 |

---

## 21. Risks

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R-01 | Journal Brain called inside the writer lock (30 s, no caps) stalls all transitions | medium; **active in production** (`MAPLE_BRAIN=antigravity`, verified 2026-10-08) | high | fix in STEP 0 (outside-the-lock pattern) |
| R-02 | R1 migration of `life_state` again (rebuild) on irreplaceable data | low | high | v4-style in-transaction verify, pre-migration copy, owner snapshot gate |
| R-03 | Exec sandbox mechanism not viable on the host's systemd/AppArmor | medium | medium | spike before W4; fallback options listed |
| R-04 | Art produced before the technical lock needs rework | high if not locked | medium | Art Contract "WAIT FOR TECHNICAL LOCK" list; STEP 2a |
| R-05 | Observer journal group reads all logs | medium | medium | code-level filtering, redaction, journald namespaces alternative, OD-12 |
| R-06 | Redaction misses a secret and it reaches a cloud provider | low–medium | high | OD-14 default: no investigation data to the cloud; corpus tests |
| R-07 | Scope creep (game systems via "inventory", "growth") | medium | medium | OD-02; growth only unlocks displays/slots; no acquisition loop |
| R-08 | Determinism broken by new float math (baselines, scoring) | medium | medium | integer/rational rules, cross-platform digest tests (existing practice) |
| R-09 | `maple.db` growth from new audit tables | medium | medium | bounded payloads, retention ADR, size monitoring in Brain/subsystem health |
| R-10 | Owner auth via Tailscale header misconfigured (spoofable on loopback) | low | high | verify Serve header behavior; reject identity headers on non-Serve paths; tests |
| R-11 | Renderer rewrite regresses the current approved UI (M2) | medium | low–medium | keep `visual.ts` contract; feature flag; staged rollout (R1a single room) |
| R-12 | Too many new components for a single maintainer | medium | medium | only two new processes; strict phase gating |

---

## 22. Acceptance criteria before implementation

The owner should require all of the following before R1 code starts. Later subsystems have their own gates (listed below).

**Before R1:**
1. OD-01 resolved: an inside-service boundary probe and a restore test are recorded for the running release (hardening-loaded, Tailscale and backup creation are already verified), and the authorization status is clarified. §2.7 docs drift: done 2026-10-08. R-01 fixed or explicitly accepted.
2. Room Final Design Spec approved (roadmap STEP 1): room list, sizes, door positions, furniture list per room.
3. **Technical lock spike done** and ADR-0046 accepted:
   - tile size and Maple frame size locked;
   - a Pixi prototype demonstrates integer-scale, pixel-perfect rendering with y-sort, an occupant overlay, multiply and additive lighting, and camera modes on desktop, tablet, and phone widths;
   - placeholder art passes the asset validator.
4. ADR-0035/0036/0037 accepted; migration M-R1 design reviewed with its in-transaction verification list and restore path.
5. Boundary tests designed for R1 (determinism digest, no-teleport property, path validity property, catalog/manifest cross-check).

**Before W1/W4:**
- ADR-0039/0041 accepted.
- Workspace mount created by the owner.
- Exec spike report:
  - host systemd version and features;
  - AppArmor userns policy;
  - rootfs build;
  - escape-probe suite results in a VM.
- Threat model rows T-01…T-10 have concrete test names.

**Before S1:**
- ADR-0043/0044/0045 accepted.
- monitor-v2 read-only survey recorded.
- Redaction corpus agreed.
- OD-09/12/13/14 decided.
- Observer unit contract test and `sandbox_probe` extensions designed.

**Every phase (roadmap global rule 10):** design review + threat model delta + boundary tests before code.

---

## Appendix A: Evidence base (inspected)

- **Project docs:**
  - `CLAUDE.md`
  - `docs/roadmap/maple-roadmap.md`
  - `docs/autonomy.md`, `brain-contract.md`, `architecture.md`, `security-model.md`, `v0.2-review.md` (with sections of `frontend.md`, `persistence.md`, `api.md`, `sensors.md`, `deployment.md`)
  - ADR-0025, 0026 (via autonomy/brain-contract), 0027, 0028, 0029, 0033
- **Backend (via code survey):**
  - `core/room.py`, `movement.py`, `activities.py`, `direction.py`, `presence.py`, `tasks.py`, `proposal.py`, `attention.py`, `observations.py`
  - `storage/migrations.py`, `db.py`, `datadir.py`, `repositories.py`, `tool_rows.py`, `external/*`
  - `runtime/life.py`, `service.py`, `events.py`, `tasks.py`, `brain_factory.py`, `external_*.py`, `brain_health.py`, `senses.py`
  - `api/app.py`, `models.py`, `views.py`, `security.py`, `stream.py`
  - `backend/pyproject.toml` (import-linter, ruff)
  - `tests/security/forbidden_apis.py`
- **Frontend:**
  - `package.json`
  - `src/room/**` (`RoomScene.ts`, `anchors.ts`, `furniture.ts`, `manifest.ts`, `sprites.ts`, `atlas.ts`, `figure.ts`, `motion.ts`, `visual.ts`)
  - `src/ui/room/*`, `src/ui/inspector/Inspector.tsx`, `styles.css`
- **Deploy:**
  - `deploy/systemd/maplegotchi.service`
  - `deploy/brain/*`, `deploy/discord/*`, `deploy/etc/maplegotchi/maplegotchi.env`
  - `deploy/install/*.sh`, `deploy/backup/*`, `deploy/verify/*`
  - `deploy/survey/findings.md`
- **Companions:** `companion/brain/src/maple_brain/*`, `companion/discord/src/maple_discord/*`
