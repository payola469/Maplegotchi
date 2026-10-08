# ADR-0040: Room view transition, initial room set, and the default-switch acceptance gate

- **Status:** Accepted — FIXED design (CLAUDE.md D39). **NOT IMPLEMENTED.** Implementation is not yet authorized. Zoom levels, widths and budgets inherit the PROVISIONAL art/rendering values of ADR-0041.
- **Date:** 2026-10-08
- **Decided by:** owner, Maple Room review decisions **B1** (default view), **B2** (initial rooms), **B14** (acceptance gate), and **B13** (baseline A13), together with **B10** (staging).
- **Extends:** D2 / ADR-0002 (PixiJS renders only the room). **Related:** ADR-0035, ADR-0037, ADR-0041, M2 (the approved Phase 6 room).

## Context

The current 1000×600 room (Phase 6, milestone M2) works and is approved. The new 3/4 tile world is a large change in rendering, art and backend geometry. The owner wants the new architecture without removing the working room until the replacement is proven stable.

## Decision

### 1. Default view and feature flag (B1)
- **The current 1000×600 room remains the default view** behind a feature flag while the new 3/4 tile world is developed.
- The default switches **only** after all acceptance criteria in §4 are met.
- After R1b the old view is fed by the legacy projection (ADR-0037 §4).

### 2. Initial room set and rollout (B2)
- **R1b builds 5 functional rooms:** Central Hall, Bedroom, Living Room, Library and Work Studio.
- **Creation Room, System Room and Future Space** are architecturally reserved **closed placeholders**:
  - the full 8-room house structure is supported from the beginning;
  - placeholders need no production-complete art or behaviour;
  - opening one must not require redesigning the house (ADR-0035).
- **When placeholders open:**
  - the **Creation Room** when its creation/project capabilities are ready;
  - the **System Room** when System Investigator integration is ready;
  - **Future Space** remains intentionally undecided.
- **Art:** concept work may cover all 8 rooms now. Production art follows the phased rollout (ADR-0041).

### 3. Lighting and renderer responsibilities (A13)
- **Lighting layers:**
  - neutral base art;
  - a per-room multiply tint driven by the backend's day phase (D16) and room lighting presets;
  - separate additive light sprites;
  - emissive pixels (screens, LEDs) that stay bright at night.

  Nothing is baked into base art.
- **The renderer only draws** (ADR-0036 §6). Camera modes (Overview, Follow, Focus) are presentation: integer zoom, snapped translation, reduced-motion snapping. Final zoom steps are validated by the spike (ADR-0041).

### 4. Acceptance gate for making the new Room the default (B14)
The new 3/4 Room becomes the default **only after all of the following are true**:
1. **Functional parity** with the legacy view:
   - Maple's position and backend-route walking, with arrival matching `arrives_at`;
   - all activities with correct poses and 4-direction facing;
   - the five expressions via face overlays, with sleep using a closed-eye face;
   - Greet/Pet reactions ending exactly at `until`;
   - the speech bubble, informational hotspots and Inspector destination;
   - all four day phases, the stale/disconnected indicator and the late-heartbeat banner.
2. **Renderer truthfulness:**
   - API-driven only;
   - no invented state;
   - no duplicated backend rules or geometry in the new path;
   - frontend guard tests pass.
3. **Backend correctness:**
   - the deterministic 30-day simulation passes, with its digest updated deliberately;
   - property tests (no teleport, path validity, capability resolution) and legacy-projection tests pass;
   - the v11 migration rehearsal on a production-database copy passes.
4. **Seven consecutive days of production soak** after R1b, with:
   - no world, movement or backend failures;
   - no unresolvable action loops;
   - no unexpected recovery relocations;
   - no renderer crashes.
5. **Rendering quality:** pixel-perfect at the agreed integer zoom levels, and verified at desktop, tablet and phone widths (1440, 820 and 390 px, as for M2) with no horizontal scroll and within the texture-memory budget.
6. **Production art is complete** for:
   - the 5 open rooms;
   - Maple's required core animation set (idle and walk in 4 directions, `sit_write`, `sit_monitor`, `stand_read`, `stand_think`, `sit_rest`, `lie_sleep`);
   - the face overlays.

   All assets pass validation. Closed placeholders may use simple art.
7. **Accessibility parity:**
   - a DOM room summary that names Maple's room;
   - keyboard focus;
   - reduced motion;
   - colour is never the only signal.
8. **Security and CI remain green:**
   - CSP unchanged;
   - assets same-origin only;
   - the route-table test updated deliberately;
   - all checks pass.
9. **Rollback:** returning to the legacy view through the flag remains available for **at least one full release** after the default switch.
10. **Paolo performs the final visual review and explicitly signs off.**

- **Not required for this cutover:** Edit Mode / R4, opening placeholder rooms, representations, sound.
- **The old view must not be removed in the same change that makes the new view default.** It is removed, together with the legacy projection and the retired `front`/`back` facing values (ADR-0035 §5), in a later, separate change.

## Deferred
- Sound, music, ambient weather and polished outdoor backdrops (roadmap R6).
- Opening placeholders (see §2).
- Edit Mode (ADR-0038, roadmap R4).

## Consequences
- There is always a working Room view. The switch is a checklist, not a judgement call.
- The roadmap phase order is unchanged. R1 is staged internally (R1a/R1b, ADR-0037) without reordering phases.
