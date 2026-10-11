# R1A-10 — New Room backend/API contracts

**Status:** REVIEW / OWNER ACCEPTED FOR INTEGRATION / MERGE PENDING / STEP 123. Commit, normal push, PR and CI inspection authorized; no merge or production activation.
**Baseline:** `efba67e7602c7cc70964a36f61b1734d58e22c28`, verified PR #9 merge.
**Branch:** `codex/r1a-10-world-api-contracts`.

## Binding inputs and dependencies

Locked ADR-0041 values → accepted ADR-0035–0040 rules → [Final Spec](../architecture/maple-room-final-design-spec.md) → proposed Future Architecture §6.11. [Master Plan](maple-room-r1a-plan.md) R1A-10/15 governs staging. R1A-02–09 are merged; the R1A-09 [pre-cutover gate](maple-room-r1a-09-legacy-projection.md#step-120--owner-acceptance-and-r1b-pre-cutover-integration-gate) remains. No accessible original design conversation is claimed.

## Implementation checkpoints

1. **Boundary and contract:** define frozen DTOs and explicit source labels. Normal `create_app` registers only GET `/api/world`, `/api/world/catalog`, `/api/world/placements`, returning documented 503 until authoritative world activation is separately authorized. No flag or dependency injection can enable fixtures there. Completion: exact route-table and unchanged legacy schema tests.
2. **Synthetic handoff:** separate fixture-only app factory, without MapleService, DB, scheduler, static frontend or SSE. Require actual Settings enums: development, fake senses, rule providers, exact local DEV_ORIGINS, no gateway/static frontend. Reconstruct Settings to validate forged/mutated profiles. This is a programmatic local fixture tool, never CLI/server wiring. Completion: default-deny and production-shaped negative tests.
3. **Serialization:** reuse runtime readers and validated canonical values. Stable ID/row-major ordering; explicit API-only content hashes for layout/catalog (not persisted v11 revision IDs). Backend provides structural classifications, lighting zones, resolved points/slots and walkable cells. Derived pixels use canonical FEET_IN_TILE and Travel. No frontend geometry authority.
4. **Examples and schemas:** derive idle/walking/empty/display examples from canonical data and existing placement validation. Export reviewable JSON and OpenAPI; derive new TypeScript contracts from that schema reproducibly, leaving existing handwritten legacy DTOs untouched. Completion: byte-for-byte regeneration and DTO round trips.
5. **Regression and review:** world/Oracle/rehearsal/API/runtime/storage/security regressions, original simulation pin, Ruff, configured strict mypy, frontend type/lint/tests/build, ten import contracts and documentation consistency. Completion: record actual results and REVIEW, no claim of native CI.

## Candidate API semantics

Three read-only GETs; no history/mutation/auth endpoints. 503 uses existing `{"detail": ...}` convention and no world payload. Successful fixture responses always carry `source: development_fixture`, `status: synthetic`, contract version and content identities. They never describe live Maple. Snapshot extension is a separate fixture snapshot nested in world output; production SnapshotOut and SSE serialization remain byte-compatible.

Tile coordinates are integer tx/ty; rectangles use half-open x/y/w/h. Structural cells are row-major and doors override bands explicitly. Point approaches are absolute tiles; occupy offsets are anchor-relative pixels, not stored Maple position. Compressed route waypoints carry cumulative steps and exact UTC departure/arrival; current position distinguishes a tile from a fractional edge instead of rounding state. Facing uses down/left/right/up with explicitly derived legacy front/back compatibility. Null route means stationary; no fabricated path. Metadata source/time is fixed synthetic input, never a current clock.

Type art IDs are soft references, not URLs or shipped art claims; geometry_version stays canonical. Slot sprite anchors and representation art are unresolved art delivery inputs, not invented coordinates. API hashes/DTO shape are workstream candidates, not an amendment fixing ADR-0037 DB columns. Tuning remains provisional. No ETag/cache relaxation: existing no-store policy wins over proposed future caching.

## SSE decision and scope

No live world transitions exist in R1a fixture handoff. R1A-15 may consume labeled fixture JSON/read-only fixture responses. `world` SSE deferred to R1b or a separately authorized demonstrated need; EventHub and existing messages remain unchanged. No projection caller, old renderer/anchors/walker, Director, schema/migration or production configuration change. R1A-11–20 remain TODO.

## Acceptance matrix

Positive: 44×26, eight regions (five open/three closed), seven doors, four open edges, 28 instances, 17 points, 12 slots, 431 connected walkable cells, 1,144 lighting cells; exact canonical references and Oracle regressions; idle/valid walking/display/empty examples; deterministic output and regeneration.
Negative: production/default normal app always 503; invalid/non-enum/production-shaped fixture profiles reject; no unsafe switches; no POST/PUT/PATCH/DELETE; no CORS or security-header change; no leaked internal paths/config/history; no mutation or events on reads; v10 startup and rehearsal/projection isolation unchanged. Frontend consumes backend geometry and never executes world rules.

## Evidence

3,695 distinct backend cases / 0 unresolved failures: full suite 3,692 PASS, followed by 108 focused API/security passes including three added default-deny cases (82 new R1A-10 cases total). Frontend 208 PASS (four new), TypeScript/ESLint/build PASS. Ruff lint/format PASS (seven Python files); configured strict Linux/Windows-target mypy PASS (228 each); ten import contracts kept. Five fixture JSON exports, OpenAPI and generated TypeScript reproduce exactly. Original simulation pin unchanged/PASS. Native platform CI not claimed.

Full backend command: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:. pytest -q -p no:cacheprovider` — 3,692 PASS in 61.47 s. Final review adds three fake-profile/no-state/no-event checks; 108 focused API/security cases PASS, covering 82 new cases. Counts are distinct cases, not sums of repeat runs. Full suite includes original simulation, world/Oracle/Harness, rehearsal, storage, runtime/API/SSE and security. Original digest: `458d6cb4035329a008105f8f2055d5f35b61cc1f537df3e04eabfcfe52d25917`, 8,640 ticks; pin/source unchanged.

Configured `mypy --platform linux` and `--platform win32` each check 228 files in strict mode. Ruff checks the seven changed/new Python files. Frontend TypeScript, ESLint, 208 Vitest tests and Vite build PASS using existing installed dependencies. pnpm dependency preflight refused the shared node_modules symlink; script tools still ran successfully and were verified directly with installed binaries (no dependency/lockfile changes). Build outputs remain ignored. No native Ubuntu/Windows CI claim. Final documentation checks: 67 local links valid; 25-file scoped manifest; checklist 20 total / 10 TODO / 1 REVIEW / 9 DONE; original worklog byte prefix preserved; tracked and untracked patch whitespace PASS. Earlier worktrees remain clean, local-only `40f0eb7` unchanged, no staged files.

Legacy proof: independently instantiated pre-R1A-10 and current apps with identical temporary fake lives. Existing OpenAPI paths and transitively referenced schemas, plus exact JSON bytes of `/api/snapshot`, `/api/room`, `/api/maple` and `/api/status`, match. New surface is exactly three GETs; existing approved mutation set unchanged. No event publication/state mutation on world reads. Fixture app exposes no live snapshot/events/room/mutation paths.

Five fixture exports validate/round-trip through their DTOs. Exported schemas equal actual normal-app world schemas and regenerate byte-for-byte with TypeScript. Geometry counts and references match canonical data; existing Oracle comparisons all pass without changes. Catalog version and layout content identities agree across endpoints/scenarios; display example has one explicit synthetic eligible existing item in bedside/top, validated by existing active-placement rules; initial/empty state has no items/displays/Storage.

## Consolidated review and remaining gates

PASS for local R1A-10 scope. No binding conflict found. Production startup has no fixture import, flag, loader or live canonical snapshot; only the unavailable GET router is added. Existing settings, Director, storage/migrations, core, accepted ADRs/Spec/Oracle/Harness/simulation pin and old UI/anchors/walker are unchanged. R1A-09 pre-cutover rejected-route strategy remains mandatory before R1b projection use. No live world activation, persistence IDs, owner authentication/editing, world events, renderer or artwork is implemented. Production schema remains v10. API field names are candidate workstream contracts under review; proposed DB shapes remain provisional.

R1A-11 can consume the labeled fixtures and generated contracts after its own authorization. Render passage cells over the uncarved wall map; use resolved points/slots rather than deriving transforms. Slot approaches are interaction tiles, not invented sprite anchors. Production art/slot sprite anchors and colors remain art delivery responsibilities. World SSE can be reconsidered only with a demonstrated integration need. Native CI and repository integration remain later authorized steps. Owner acceptance pending; no commit/push/PR/merge/deployment.

## Changed-file manifest

- Backend: `api/app.py` (two additive lines), new `api/world_models.py`, `api/world_routes.py`, `api/world_fixtures.py`; deliberate route-table update in `tests/api/test_api_security.py`; new `tests/api/test_world_api.py`, `tests/api/world_contract_export.py`.
- Frontend: new `src/api/world.generated.ts`, `src/api/world-contracts.test.ts`. No application consumer/wiring change.
- Generated handoff: `docs/api/world-openapi.json`; five `docs/fixtures/maple-room/r1a-10/*.json` examples. These are intentional reviewed contract artifacts, not runtime authoritative data or Oracle snapshots.
- Documentation: this plan, checklist, Master Plan, append-only worklog, R1A-09 current completion pointer, `docs/api.md`, `docs/architecture.md`, `docs/security-model.md`, `docs/frontend.md`, `CLAUDE.md`.

## STEP 123 — Owner acceptance for GitHub integration

2026-10-11: owner accepts STEP 122 implementation and local evidence for commit, normal push and PR against `v0.2-development`. Baseline remains `efba67e7602c7cc70964a36f61b1734d58e22c28`; reviewed scope is 25 files. Focused API/security verification: 108 passed; OpenAPI, generated TypeScript and five JSON fixtures reproduce exactly. Documentation links, counters, append-only history, unrelated worktrees and patch whitespace verified. Existing 3,695 distinct backend / 208 frontend evidence is retained without repeating unrelated suites. Production safety and legacy byte-compatibility gates remain PASS. Native CI is pending GitHub execution; no merge, deployment, production access, schema-v11 activation or R1A-11 authorization.
