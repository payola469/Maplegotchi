# Frontend — Maple's Room (Phase 6)

> **STEP 156 current authorization/status — 2026-10-12:** R1A-01–19 DONE / OWNER ACCEPTED / MERGED; baseline `6e861f2c199827098f3603e6952d44e87e8eff0a`. Owner ACCEPTS the STEP 155 audit and authorizes STEP 156 final review, fresh checks, documentation commit, normal push, PR into `v0.2-development` and CI inspection. R1A-20 **REVIEW / OWNER ACCEPTED / MERGE PENDING**; **19 DONE / 1 REVIEW / 0 TODO = 95%**. No merge, deployment, production/paolo-core access, schema-v11 activation, Legacy default switch, R1b or B14 authorization. Historical hardware/DPR/Linux evidence remains historical; actual new PR CI will be recorded separately. [Acceptance evidence](implementation/maple-room-r1a-20-acceptance-gate.md). Earlier dated records below are historical.

The room is a **view** of the backend. It has no behaviour engine: activity,
location, needs, expression, reactions, interaction availability, cooldowns,
server health, day phase and journal text all come from the API
(`docs/api.md`), as do Maple's position and walking route since v0.2 (ADR-0027).
The UI maps those values to pictures and words, and times purely presentational
things: animating along the backend's route, lighting fades, the end of a reaction
bubble, and countdown text.

Stack: TypeScript, Vite, Preact for DOM, PixiJS 8 for the room canvas only
(ADR 0002).

## R1A-09 isolated compatibility preparation (STEP 119)

The backend now has an explicit development/fixture-only pure [legacy projection](implementation/maple-room-r1a-09-legacy-projection.md), DONE / OWNER ACCEPTED / MERGED (PR #9, verified STEP 122). Production continues emitting its native legacy snapshot. No API/SSE, anchors, `toVisual`, `routeFrame`, fallback walker or default renderer wiring changed. Projection preserves caller-supplied pose classes as metadata; it does not claim that this existing activity-derived renderer can display new classes such as `sit_read`. Collapsed-anchor and unmappable mid-edge walks reject explicitly rather than inventing movement. The owner accepts the 40 collapsed-anchor pair rejections and ambiguous mid-edge rejection and prioritizes the new Room. Old-view compatibility expansion is deferred. Before R1b uses the projection, an explicitly validated integration strategy must prevent unsafe or misleading behavior; the linked plan tracks that pre-cutover concern. No new compatibility implementation is authorized.

## Layout

```
frontend/src/
├── api/          client.ts (snapshot + Greet/Pet), sse.ts (fetch-based SSE), types.ts (DTO mirror)
├── state/        store.ts (single state, revision rule), live.ts (snapshot + SSE sync),
│                 interactions.ts (Greet/Pet flow), presentation.ts (formatting helpers)
├── room/
│   ├── visual.ts         THE mapping: snapshot -> VisualState (pure, total, tested)
│   ├── layout/anchors.ts room size, fallback anchors, furniture boxes (frontend-only geometry)
│   ├── animation/motion.ts routeFrame (backend route interpolation), snap/fallback Motion, eased values
│   ├── objects/furniture.ts vector furniture (temporary art)
│   ├── maple/            pixel Maple: pixels.ts (art), sprites.ts (mapping), atlas.ts, figure.ts
│   ├── assets/manifest.ts asset list + replacement contract
│   └── scene/RoomScene.ts Pixi application, layers, one ticker
├── ui/           App.tsx, panels.tsx, room/RoomView.tsx, interactions/InteractionBar.tsx, hooks.ts,
│                 layout/AppShell.tsx (page shell: header, section navigation, grid areas)
├── styles.css    all styling and design tokens (no inline style attributes: CSP style-src 'self')
└── main.tsx      wiring: Store + API + LiveConnection + lazily loaded scene
```

The Pixi scene is injected into `App` as a factory (`createScene`), so DOM
tests use a recording fake and never load Pixi. `main.tsx` loads the scene
with a dynamic import so the panels appear before the canvas is ready.

## Scene structure

`RoomScene` creates one `Application` (logical 1000 × 600, `antialias: true`,
auto-density, resolution ≤ 2) and never recreates it; snapshots call
`update(visual)`. The canvas keeps that render size and is scaled by CSS to the
container width (a non-integer scale; no camera, zoom, or pan). There is no depth
sorting: Maple is always drawn above all furniture. Layers, back to front:

1. walls and floor:
   - cream wall with a pixel dot pattern, ceiling shade and a garland;
   - dark green wainscot with a wooden rail;
   - plank floor with a contact shadow at the wall;
   - wall decor: a framed picture and a small shelf.
2. sky: the window pane in pixel bands around the mapped sky colour, a pixel
   sun with clouds (day) or crescent moon with stars (night), and horizon
   hills and trees tinted by the sky.
3. window frame, sill and orange curtains.
4. furniture (texture if the manifest names one, otherwise vector drawing)
5. Maple
6. vignette (static edge shading for depth)
7. night: a navy `multiply` layer with alpha = darkness, plus a navy wash
   with alpha = darkness × 0.4
8. lamp glow (amber) and screen glow (teal) (additive, soft stacked rings)

The room art (`objects/furniture.ts`) is a cozy pixel-art style:
- blocky shapes on a 4-unit grid with dark 2-unit outlines;
- warm wood, dark green and warm orange accents, navy for depth;
- shared colours in `PALETTE`.

Every piece is drawn inside its unchanged `FURNITURE` box. The art is
decorative only: no clocks, dates or anything that could read as state.

A single ticker advances motion, animates Maple and eases lighting. A
`ResizeObserver` fits the canvas width to its container. `destroy()`
disconnects the observer, removes the ticker and destroys the app with its
children and textures. The canvas is `aria-hidden`; a DOM text summary
(`describeRoom`) describes the room instead.

## Anchors

Logical units; `(x, y)` is where Maple's feet go. Names are the backend's
logical locations. Since v0.2 (ADR-0027) the backend is the source of Maple's
position: interaction points come from `GET /api/room` (`core/room.py`), and each
snapshot carries `activity.position` and `activity.route`. The anchors below
(`layout/anchors.ts`) are only **fallbacks** for a snapshot that lacks a position
or route; each equals the backend's canonical point for that location.

| Location | Fallback anchor (x, y) | Furniture there (backend point id) |
|---|---|---|
| `bed` | (150, 455) | bed (`bed.side`) |
| `sofa` | (150, 560) | sofa (`sofa.seat`) |
| `bookshelf` | (330, 500) | bookshelf (`bookshelf.front`) |
| `window` | (500, 470) | Window / Plant Corner (`window.view`) |
| `desk` | (640, 470) | Writing Desk + chair (`writing_desk.chair`) |
| `terminal` | (840, 470) | Computer Desk + monitor (`computer_desk.chair`) |
| `rug` | (480, 545) | Open Area (`open_area.center`; the backend also uses `open_area.west` (400, 550) and `open_area.east` (580, 550)); neutral fallback anchor |

Known duplication (current state, not yet removed):
- Room size (`ROOM_WIDTH`, `ROOM_HEIGHT`, `FLOOR_Y`), the fallback anchors, and the furniture labels are repeated in the frontend.
- The furniture boxes (`FURNITURE`) exist **only** in the frontend; the backend has no furniture geometry.
- `GET /api/room` is used only by `ui/room/RoomOverlay.tsx` (hotspots and the SVG `viewBox`); the Pixi scene uses the frontend constants.

## Mapping (`room/visual.ts`)

`toVisual(snapshot, serverNowMs)` is pure and deterministic. It is total:
unknown values fall back and set `recognised = false`. The DOM then adds
"Some of Maple's state is new to this display."

| Backend activity | Pose | Location (activity set v2, ADR-0028; the backend decides) |
|---|---|---|
| `idle` | stand (breathing) | rug (Open Area) |
| `walk` | walk | rug (Open Area) |
| `sleep` | sleep (lying on the bed, "z z", sleepy face) | bed |
| `read` | read (book prop) | bookshelf |
| `write` | sit_write (pen prop) | desk (Writing Desk) |
| `observe_server` | sit_monitor | terminal (Computer Desk) |
| `rest` | rest (sitting) | sofa |
| `think` | think (drawn with the `stand` frame) | window (Window / Plant Corner) |
| unknown | stand | — |

How the frontend picks pose and facing:
- **Pose** comes from `activity.kind` via `ACTIVITY_POSE`. The backend's `activity.pose` field is not read.
- **Walking:** while the backend phase is `walking`, the walk pose is shown.
- **Facing** is horizontal only, taken from the x-direction of the current route segment (or of the last movement). The backend's `facing` values `front` and `back` are not used by the renderer.

Expressions `calm`, `happy`, `curious`, `sleepy` and `focused` are drawn as-is;
an unknown expression is drawn as `calm`.

| Reaction | Symbol | Text |
|---|---|---|
| `greet_happy` | wave ("Hi!") | waves hello |
| `greet_sleepy` | sleepy_wave | mumbles a sleepy hello |
| `pet_happy` | heart | enjoys the pat |
| `pet_sleepy` | sleepy_heart | smiles in their sleep |
| unknown | sparkle | reacts |

A reaction is shown while `serverNow < reaction.until`. The UI arms one
timeout for `until`, hides the bubble at that moment without waiting for a
heartbeat, and then asks for a fresh snapshot so that the expression that
follows comes from the backend. A malformed `until` shows no bubble.

The location maps to an anchor of the same name; an unknown location maps to
`rug`.

## Day/night

Lighting depends only on `snapshot.day.phase`. For an unknown phase it falls
back to `is_night`. The UI never reads the local clock to decide it.

| Phase | Darkness | Lamp | Window sky |
|---|---|---|---|
| morning | 0 | off | pale blue |
| afternoon | 0 | off | blue |
| evening | 0.22 | 0.55 | orange |
| night | 0.5 | 1.0 | deep navy |

Values ease toward the target at about 1.5/s, so phase changes fade smoothly.
Under reduced motion they snap.

## Animation rules

- **Walking follows the backend (v0.2, ADR-0027).**
  - Movement is backend state. A snapshot's `activity.route` (`departed_at`, `arrives_at`, `path`) is interpolated along the path by `routeFrame`.
  - The clock is the estimated server time (`Date.now()` plus the snapshot's clock offset).
  - Speed and travel time are fixed by the backend (`WALK_SPEED = 120` units/s in `core/room.py`).
  - From `arrives_at` the backend pose applies.
  - Rerouting is a backend decision; the next snapshot carries the new route.
- **Otherwise Maple snaps** to the backend position (`restPosition`): the route's last point, else `activity.position`, else the fallback anchor.
  - The older presentation-only `Motion` walker (220 units/s between anchors) still exists in `animation/motion.ts`.
  - `RoomScene.update` always calls it with `snap = true`, so in practice it never walks on its own.
- **The first placement snaps** (no walk across the room on page load).
- **Idle loops are small:** breathing, a walk bob, sleep rise and fall, a
  small sit and read motion.
- **Reduced motion** (`prefers-reduced-motion: reduce`, followed live):
  - motion amplitude is 0 and positions and lighting snap;
  - CSS transitions and animations are disabled;
  - pose, face, bubble and text still change, so no information is lost.

## Live state and revisions (`state/live.ts`, `state/store.ts`)

1. **Start:** fetch `GET /api/snapshot` and open the SSE stream in parallel.
2. **Events:**
   - A `snapshot` frame (the backend's resync) is applied directly.
   - Any other frame with a revision newer than the shown one triggers a
     refresh. Frames with a revision already shown are ignored.
3. **Refreshes are coalesced:** at most one request is in flight, plus at most
   one queued follow-up, however many events arrive. Events that arrive
   during a fetch are covered by the follow-up. There is no polling loop.
4. **Revision rule:** the store ignores any snapshot or interaction result
   older than the displayed revision, so a slow response can never roll the
   view back.
5. **Liveness:**
   - Any bytes on the stream, including `: keepalive` comments, count as
     activity. This is why SSE is fetch-based: `EventSource` hides comments.
   - If there is silence for 2 × keepalive + 5 s, the status becomes
     **stale** and the stream is closed and reopened.
6. **Reconnect:**
   - backoff of 1 s, 2 s, 5 s, then 10 s, sending `Last-Event-ID`;
   - after any drop, a fresh snapshot is fetched once the stream reopens;
   - the backend replays missed events, or sends a `snapshot` resync for an
     unknown or old id (for example after a restart).

| Status | Meaning | Shown as |
|---|---|---|
| loading | no snapshot yet | "Waking Maple up…" screen |
| live | stream active | "● Live" badge |
| reconnecting | stream dropped, retrying | badge + "Not connected — showing Maple as last seen at …" banner; room greyed |
| stale | stream silent too long | same banner; room greyed |
| offline | API unreachable before any snapshot | "Can't reach Maple" screen, retrying |

A late heartbeat (`freshness.heartbeat_status` other than `fresh`) shows its
own banner, even while the connection is live. Every status is shown as
text; colour is never the only signal.

## Interaction flow (Greet/Pet)

1. Buttons are enabled only when the backend reports `available` **and** the
   connection is live. When the connection isn't live, availability may be
   out of date.
2. A click marks that button pending ("Waiting for Maple…") and POSTs.
   Nothing else changes: there is no optimistic reaction.
3. Accepted (200) and rejected (429) responses both carry the backend's
   `maple`. It is applied under the revision rule, and the feedback line
   shows the backend's result:
   - "Maple waves hello." (accepted);
   - "Maple needs a moment. Try again in 42 s." (cooldown);
   - rate-limit and forbidden messages;
   - network failures read "Couldn't reach Maple. Nothing changed."
4. A refresh follows, so the journal and timeline update. SSE also announces
   the change.
5. **Countdowns** ("Ready in 23 s"):
   - counted down from `retry_after_seconds` relative to the snapshot's
     `generated_at`, using the estimated server clock;
   - at 0 the UI asks the backend for a new snapshot instead of enabling the
     button itself.

There are no other interactions.

## Page layout (`ui/layout/AppShell.tsx`)

A cozy dashboard: warm cream background, soft rounded cards, dark green as the
primary colour and a warm orange accent. The colours, radii, shadows and type
are design tokens on `:root` in `styles.css`. The page is light only.

`AppShell` is layout only. It holds no Maple state and shows no backend value
of its own. `App` renders each existing component **exactly once** and passes
it to a slot; the shell only places it in a grid area:

| Area (id) | Component |
|---|---|
| header | name + "'s room" (`h1`), connection badge |
| banners | disconnected / late-heartbeat banners |
| `#room` | `RoomView` (canvas + room summary) |
| `#status` | `StatusPanel` |
| interactions | `InteractionBar` (Greet / Pet + feedback line) |
| `#journal` | `JournalPanel` |
| `#activity` | `TimelinePanel` ("Recent Activity") |
| `#system` | `ServerPanel` + `RuntimePanel` |

There is exactly one `RoomView` and one `InteractionBar`. Nothing is
unmounted by navigation: the Pixi scene is never recreated by a layout change.

**Section navigation:**
- One `<nav aria-label="Sections">` holding in-page links to the five areas
  (Room, Status, Journal, Activity, System). It is a sidebar on wide screens
  and a fixed bottom bar on phones. This is done with CSS only, so the same
  element serves both.
- The current section is marked with `aria-current="location"`. It is
  derived from the scroll position: the section whose top has passed a third
  of the viewport, or the last one at the end of the page. The last link
  clicked wins ties between side-by-side areas.
- This is presentation only: local state in `AppShell`, one rAF-throttled
  scroll/resize listener, and nothing at all when `requestAnimationFrame` is
  missing. The highlight is a light pill plus an accent bar, so it is shape as
  well as colour.

## Panels

- **Maple** (status card):
  - name;
  - age, activity ("Doing") and expression ("Feeling") as small fact tiles;
  - mood, energy, curiosity and social as `<meter>` bars with numbers. Meter
    colours come from the meter's own low/high/optimum state, and the number
    is always shown.
- **Greet / Pet:**
  - Greet is the green button and Pet the orange one, each with a decorative
    icon (`aria-hidden`; the label stays the button's name);
  - disabled buttons are dashed and muted and still show their hint or
    countdown;
  - the feedback line keeps its height whether or not a message is shown, so
    nothing jumps;
  - the line is tinted by outcome (accepted, waiting, error), and the text
    always says what happened.
- **Journal:** newest first. Entries are written in a serif "diary" face
  (Maple's voice). `importance=notable` entries get a stronger accent and bold
  text.
- **Recent Activity** (the timeline): newest first, **open by default**. Each
  event is a dot on a vertical line, with the time above the text. Dot styles
  differ by kind (accepted interactions filled orange, downtime gaps dashed);
  the text says what happened.
- **Server:**
  - sensor freshness badge (with a symbol: ● fresh, ◐ stale);
  - summary sentence, with a left bar tinted by summary;
  - CPU, RAM, Disk (`/`) and temperature as tiles;
  - allowlisted services, each with its state word and a small dot (filled
    for active and failed, hollow otherwise).
- **Runtime:** connection, last update, heartbeat and Brain; **collapsed by
  default**.

Collapsible panels (Journal, Recent Activity, Server, Runtime) are still
`<details>`/`<summary>`. Classes such as `service__state--active` exist for
styling only.

Missing readings say `no data`, and failed ones say `unavailable (reason)` or
`unknown`. The UI never shows a made-up healthy value.

## Responsive behaviour

| Width | Layout |
|---|---|
| > 1180 px | sidebar (208 px); room, Greet/Pet and Journal in the middle; status card with Recent Activity directly under it on the right (320 px); System below |
| ≤ 1180 px | sidebar becomes an icon rail (76 px, labels under icons); right column 300 px; server readings in 2 columns |
| ≤ 960 px | room and Greet/Pet full width; Status + Recent Activity side by side; Journal and System full width |
| ≤ 760 px | navigation becomes a fixed bottom bar (safe-area aware; the page is padded so nothing hides behind it); System panels stack |
| ≤ 600 px | one column: **room, compact status, Greet/Pet**, then Journal, Recent Activity, System; needs in two columns with the meter under each label; buttons at least 56 px tall |

The canvas scales by width with a fixed 5:3 aspect ratio. `overflow-x` is
hidden, and every grid track uses `minmax(0, …)`. Verified at 1440 × 1000,
820 × 1180 and 390 × 844 with no horizontal scroll.

## Accessibility

- Real `<button>`s with a visible `:focus-visible` outline; hints are linked
  with `aria-describedby`. Navigation items are links (at least 44 px tall,
  56 px in the bottom bar) with their own focus ring that stays visible on
  the green background.
- Semantic headings: `h1` for the room, `h2` for each panel.
- `role="status"` on the feedback line and the connection badge.
- `role="alert"` on the disconnected and late-heartbeat banners.
- A DOM room summary replaces the decorative canvas; all icons are
  `aria-hidden`.
- No state is shown by colour alone. Badges, dots and tints always sit next
  to the word they describe.
- Reduced motion is supported as described above, and it also turns off
  smooth scrolling for the navigation.
- Fonts are system fonts (`style-src`/`default-src 'self'`: no web-font
  CDN).

## Assets and how to replace them

> **Current state only.** A future tile-based, multi-room asset system and an art
> handoff contract are **DRAFT / PROPOSED / FOR HUMAN REVIEW, not implemented**:
> `docs/architecture/maple-future-architecture.md` §9 and
> `docs/architecture/maple-art-production-contract.md`. Their numbers (tile 16 px,
> Maple frame 32×48, feet point (16, 47), 1× delivery) are **PROVISIONAL** until
> technical validation and do not apply to the current renderer described here.

All art is **original** and drawn in code, with no image files.
`frontend/public/` holds only `favicon.svg`, and no furniture `texture` is set in
the manifest.
- the furniture is pixel-style vector drawing (`room/objects/furniture.ts`);
- Maple is pixel art stored as text grids (`room/maple/`).

`room/assets/manifest.ts` lists every piece.

- **Furniture:**
  1. Put a transparent PNG under `frontend/public/assets/room/`, drawn at 2×
     the layout box in `layout/anchors.ts` `FURNITURE`.
  2. Set `texture: "/assets/room/<name>.png"` for that piece in
     `FURNITURE_ASSETS`.
  3. The scene draws the image in the same box. Anchors and mapping are
     unchanged.
- **Maple** (pixel/chibi: short black hair, dark brown eyes, black glasses,
  orange headphones, dark green hoodie):

  | File | Role |
  |---|---|
  | `maple/pixels.ts` | palette + art as text grids (one character per pixel, `.` transparent): head, face overlays, body parts, book, bubble glyphs, sleep "z" |
  | `maple/sprites.ts` | **the one mapping** (pure, tested): frame layouts, pose → frames (`POSE_FRAMES`), the fallback rules, bubble glyph per symbol, the list of frames the atlas needs |
  | `maple/atlas.ts` | paints every frame once into a single canvas; one `CanvasSource` with `scaleMode: "nearest"`, sliced into sub-textures |
  | `maple/figure.ts` | the Pixi figure (same API as before: `apply`, `animate`, `destroy`) |

  - **Frames:**
    - 24 × 28 pixels at 4 logical units per pixel (96 × 112 units, on the
      room's 4-unit grid);
    - origin between the feet;
    - poses: `stand`, `walk` (two leg frames, alternating while walking),
      `sleep`, `read` (open book), `sit_write` (pencil), `sit_monitor`
      (typing, teal screen light), `rest` (mug); `think` (v0.2) reuses the
      `stand` frame;
    - seated frames keep the feet on the bottom row;
    - `sleep` is its own lying-down frame (40 × 18): the head on the pillow
      and a green quilt over the body. Its origin (under the head, on the
      mattress line) is held at a fixed point relative to the bed anchor, so
      the anchor and its meaning are unchanged.
  - **Fallback rules:**
    - `sleep` always shows the closed-eye face, whatever the expression (as
      before, where a sleeping Maple was always drawn sleepy);
    - every other pose shows all five expressions;
    - unknown backend values are still resolved by `room/visual.ts`
      (`stand`, `calm`, `sparkle`), so the figure only ever sees known values.
  - **Bubbles:** same meaning as before, drawn as pixel glyphs in a
    stepped-corner bubble:
    - `wave` "Hi!"
    - `heart` ♥
    - `sleepy_wave` "…hi"
    - `sleepy_heart` ♥ z
    - `sparkle` ✦
  - **Crisp pixels:**
    - only Maple's atlas samples with `nearest`, and its sprites use
      `roundPixels`;
    - the canvas, room, glows and lighting are unchanged.
  - **Idle loops:** they move in whole steps (breathing bob, walk step,
    seated/reading bob, sleep rise and fall) instead of stretching or tilting
    the art. Under reduced motion they are still.
  - **Responsive size** (`mapleUnitsPerPixel`, presentation only):
    - the scene reports the room's on-screen scale to the figure on every
      resize;
    - a full-size room (scale ≥ 0.8, desktop) draws Maple at exactly 4 units
      per pixel;
    - a smaller room draws Maple a little larger: about 1.125× on tablets and
      1.25× on phones;
    - the size is snapped to whole canvas pixels when that stays within 10% of
      the target, so the art stays even;
    - anchors, logical coordinates and furniture are unchanged. Maple grows
      from its origin (feet, or the pillow point when sleeping), so every
      activity stays on its anchor.
  - **To change the art:** edit the grids in `pixels.ts` (`sprites.test.ts`
    checks sizes, palette and coverage). The mapping in `room/visual.ts`, the
    anchors and the motion stay as they are.
- Assets are served from the same origin (`img-src 'self'`); no external
  URLs are allowed.

## Performance and cleanup

- The scene is created once per mount.
- There is one Pixi ticker.
- Timers are single and re-armed: stale, reconnect, reaction end, and a
  one-second display tick that runs only while a reaction or countdown is
  showing. There are no `setInterval`s.
- `LiveConnection.stop()` (on `pagehide`) clears its timers and closes the
  stream.
- The room component destroys the scene on unmount.

## v0.2 room UX (Phase A8)

Concepts taken from Pixel Agents, adapted to one persistent Maple (no "one
session = one character", no terminals):

- **Live activity**: the room follows backend routes and poses (ADR-0027); the
  activity label and the speech bubble say *what* Maple reads or writes when the
  backend's `activity.task` says so.
- **Interactive furniture** (`ui/room/RoomOverlay.tsx`): an SVG layer over the canvas
  (positions as SVG attributes in room units, so no inline styles under the CSP)
  with one focusable hotspot per furniture from `GET /api/room`, describing what
  the furniture is for and marking the piece in use. Hotspots explain; there are no
  furniture actions.
- **Speech bubble**: `maple.bubble` from the backend (`core/presence.py`):
  needs attention, thinking, reading, writing, waiting for Paolo
  (`approval_required` is reserved and never sent in v0.2). Hidden while walking.
- **Backend-driven events** (`ui/feed.tsx`, "What Maple is doing"): the shared life
  events (SSE `life`, initial `GET /api/life-events`), kept in the store (last 60,
  deduplicated) and worded for people. Nothing is inferred from animations.
- **Maple Inspector** (`ui/inspector/Inspector.tsx`): a separate owner view opened
  from the header — current goal, action/phase/task, destination, the latest
  decision's reason, recent decisions with verdicts and codes, action history,
  interruptions and rejections, memory candidates and the last reflection's
  intent, and the Brain/Director identity. GET endpoints only (`api/read.ts`).
- **Brain Health** (Inspector card, ADR-0034; never in the living room): `GET
  /api/brain-health` on open and on each new revision — status badge (Healthy /
  Degraded / Offline / Unknown), provider and model as reported by the companion
  (model id shown with spaces and capitals only), last success, and per Director /
  Replier: mode, last call latency and time (with its fallback code if it fell back),
  fallbacks and timeouts in the current Maple day. Anything unavailable reads
  `Unknown`; nothing is inferred. Quota/credits are out of scope.

## Tests (`pnpm test`)

| File | Covers |
|---|---|
| `ui/inspector/brainhealth.test.tsx` | Brain Health card: healthy, degraded (fallback code), offline (provider/model Unknown, never guessed), unknown (no calls; endpoint failure; unrecognised status), latency/model formatting, fetched by the Inspector |
| `room/visual.test.ts` | all activities, locations, expressions and reactions; expiry at `until`; unknown fallbacks; day/night; room text |
| `room/maple/sprites.test.ts` | pixel grids rectangular and in-palette; frame parts fit; every pose × expression composes a full frame with hair, headphones, hoodie and glasses and feet on the bottom row; expressions distinct while awake; sleep falls back to the closed-eye face; dedicated lying sleep frame (head left on the origin, quilt to the right, no shoes); two walk frames; atlas covers every frame once; a distinct bubble glyph per symbol; responsive scale exact on desktop, slightly larger (never smaller) on small rooms, snapped to whole canvas pixels |
| `room/animation/motion.test.ts` | backend route interpolation (`routeFrame`), the fallback walker (speed, mid-walk redirect, snap), eased lighting |
| `ui/roomux.test.tsx` | v0.2 room UX: furniture hotspots from `/api/room`, speech bubble, Inspector |
| `api/sse.test.ts`, `api/client.test.ts` | SSE parsing (chunking, CRLF, comments), `Last-Event-ID`, close; 200/429/403/network |
| `state/store.test.ts` | revision monotonicity, server-clock estimate |
| `state/live.test.ts` | coalescing, in-flight events, resync frame, late old snapshot, reconnect with backoff and last id, stale detection, offline, stop |
| `state/interactions.test.ts` | Greet success, Greet cooldown, Pet success, 403/network rejection, no optimism, double click |
| `state/presentation.test.ts` | countdown, formatting, honest unknowns |
| `ui/App.test.tsx` | explicit states, one scene per mount, reaction expiry without heartbeat, reduced motion, availability and countdown, feedback, panels, section navigation (existing targets only, one current section), one room and one Greet/Pet bar, Recent Activity open / Runtime collapsed, mobile smoke |
| `guards.test.ts` | no backend rule constants in UI code, no raw-HTML or inline styles, reduced-motion and mobile CSS present, manifest completeness |

The tests don't compare pixels. Visual checks were done manually with
headless-Edge screenshots (see the Phase 6 report, and the v0.1 visual
refresh at 1440, 820 and 390 px wide using DevTools device emulation).

## R1A-11 handoff from R1A-10 (STEP 122)

[API contract/evidence](implementation/maple-room-r1a-10-world-api-contracts.md), [OpenAPI](api/world-openapi.json), [derived types](../frontend/src/api/world.generated.ts), [idle](fixtures/maple-room/r1a-10/world-idle.json), [walking](fixtures/maple-room/r1a-10/world-walking.json), [catalog](fixtures/maple-room/r1a-10/catalog.json), [empty displays](fixtures/maple-room/r1a-10/placements-empty.json), [synthetic display](fixtures/maple-room/r1a-10/placements-display.json). These are explicit synthetic inputs, never live v10 Maple. Backend owns structure, passage overrides, lighting zones, points/slots and walkable cells. No frontend pathfinding/geometry/placement authority. Read exact server route timing and position kind; do not round an edge into state. No new SSE subscription, store, client fetch activation, feature flag or renderer implementation in STEP 122. Legacy types/client/renderer remain unchanged. Slot artwork anchors, asset availability, phase tints and visual quality remain later authorized work; no sprite positions or production art are invented here. Reproduce using the test-only exporter documented in API docs.

## R1A-11 development renderer shell (STEP 125)

Legacy `room/` and its DOM panels remain the default. Run `pnpm dev` from `frontend/`, then explicitly open `/?room=fixture`. Only Vite development accepts this entry; production builds remove its import and fixtures. It constructs no legacy API/store/SSE connection. Fixture disclosure, scenario/time controls, status/error text and accessible room list stay in DOM. Vite's file allowlist adds only the accepted `docs/fixtures/maple-room/r1a-10` directory outside frontend. No dependency or lockfile changes.

`src/world-room/` contains generated-DTO consumers, presentation helpers, scoped test-art resources, a Pixi 8.21.0 scene and a Preact preview. Scene ownership: one application/ticker/observer per mount, abort-safe async initialization and idempotent disposal. Locked device-pixel renderer options and nearest/no-mipmap sources are local to this path. Integer Overview fit and a narrow DOM fallback provide shell support; Follow/Focus and camera interactions remain R1A-12. Backend geometry stays authoritative; no frontend navigation/placement/capability rules.

[R1A-11 evidence](implementation/maple-room-r1a-11-pixi-renderer-shell.md) preserves shell history. STEP 128 adds [R1A-14 validated atlases](implementation/maple-room-r1a-14-asset-pipeline.md): source PNG/sidecars in `art/export`, palette in `art/palette`, offline tooling in `frontend/tools/art`, ignored outputs in `frontend/src/world-room/generated`. `pnpm assets:build` validates and packs; `pnpm assets:test` tests rules, hashes, budgets and bundle boundaries. Normal dev/test/typecheck/build regenerate first. Builds never author or repair source assets; `make-placeholders.mjs` is an explicit one-time authoring tool that refuses existing exports.

`world-room/atlas.ts` loads Vite-hashed page URLs with embedded Pixi metadata. Serialized reference-counted leases share sheets and unload after the final release; errors/aborts free owned resources. Nearest sampling, no mipmaps, original canvases and declared anchors survive trimming. Base/occupant/emissive parts share the canonical object anchor; only declared light/shadow centres differ. These parts provide metadata/position primitives, not R1A-13 lighting. Production JavaScript excludes preview/fixtures; the build emits processed pages for release verification. No raw PNG source, sidecars or palette reaches `dist`.

STEP 131 merged-tree evidence: 423 Vitest cases, 65 asset/bundle cases, TypeScript/ESLint/build PASS. PR #12 merged at `7b45af4`; its native Windows PNG/metadata/generated-index reproduction and build passed in historical run `38144587116`. R1A-14 DONE / OWNER ACCEPTED / MERGED; R1A-11 atlas dependency RESOLVED and REVIEW / OWNER ACCEPTED / CLOSURE VERIFIED / MERGE PENDING (STEP 132; closure documentation integration pending). [Closure matrix](implementation/maple-room-r1a-11-pixi-renderer-shell.md#step-131--formal-closure-verification) separates shell requirements from camera/lighting/live coexistence and final-art/device gates. Placeholder colors, shapes and 12×6 face size remain provisional; R1A-13 owns lighting. Legacy default is unchanged.


### R1A-12 — owner-accepted camera implementation (STEP 135)

`world-room/camera.ts` provides pure CSS/device/world coordinate transforms, validated backing size, locked L1–L4 zoom, fitting, supplied-region bounds, Follow dead-zone/easing/clamping and oversize Focus. `scene.ts` applies them on the existing ticker, checks DPR every draw and keeps Pixi resolution1/nearest/no-mipmap and atlas lifecycle unchanged. Hidden/zero-size hosts pause safely. Integer output and a continuous easing accumulator prevent rounding stalls; reduced motion snaps. Geometry is supplied by R1A-10; camera navigation never moves Maple.

Development-only preview has native DOM mode/zoom/region controls and one canonical room list with current-room/open/closed labels. Overview fallback visually replaces the canvas while retaining measured dimensions and DOM focus. Desktop host is capped near806×484; narrower panels derive fit honestly. Follow L2 is explicitly a provisional configurable test setting, never a product default. [Detailed evidence](implementation/maple-room-r1a-12-camera-zoom-dpr.md) records 511 frontend, 65 asset and 237 backend passes, native DPR2/emulated DPR1 observations and STEP134B browser closure: explicit DPR1/1.25/1.5/2/3 × L1–L4, reduced-motion snap, nearest atlas sampling and first-frame live CDP DPR updates PASS. Physical-device/performance QA remains deferred. R1A-12 REVIEW / OWNER ACCEPTED / MERGE PENDING; R1A-11/14 DONE / OWNER ACCEPTED / MERGED. Production default, fixture isolation, API/SSE and schema unchanged. R1A-13 lighting and R1A-15 live coexistence remain separate workstreams.


### R1A-13 — lighting implementation (STEP137 CONTINUE)

Fixture scene consumes supplied zone rectangles and typed day phases. Replaceable provisional presets drive eight multiply zones,four window/two lamp additive atlas parts and one Computer Desk emissive part,after neutral scene/depth. Atlas partPosition preserves approved anchors;camera/ticker/disposal ownership is unchanged. The synthetic phase selector never modifies live state or canonical fixture JSON. Production bundle excludes preview/raw sources. R1A-12 is DONE / MERGED via PR14;R1A-13 REVIEW / OWNER ACCEPTED / MERGE PENDING (STEP138). Owner-approved original placeholder skin/shirt/hair palette substitutions resolve the initial contrast blocker,including hair against doorway wall bands. [Detailed evidence](implementation/maple-room-r1a-13-lighting-zones.md) records measured ratios,549 frontend/66 asset/237 backend passes,five-DPR zone coverage,actual additive/emissive pixels and deterministic atlas hashes. Native Windows reproduction is required on the R1A-13 PR;final artwork/colors/strengths and hardware/L21 acceptance remain deferred. R1A-15 is not implemented.

## R1A-15 — development coexistence (STEP 140 CONTINUE)

R1A-10 through14 are merged at baseline `a85f226fb664056482baf8f27389870fce14fd45`. R1A-15 is REVIEW / OWNER ACCEPTED / MERGE PENDING (STEP141);14/20 DONE=70%,eventual acceptance+merge15/20=75%. [Implementation,owner clarification and fresh Windows evidence](implementation/maple-room-r1a-15-coexistence.md).

`main.tsx` calls the extracted `ui/legacy.tsx` bootstrap in production. In development only it imports `dev/RoomSwitcher.tsx`: Legacy is the initial default; one exact `?room=fixture` selects the existing fixture preview. Duplicate/unknown/off flags fall back to Legacy. The persistent accessible DOM selector switches without reloading and retains keyboard focus; Return to legacy restores focus. Rollback is selecting Legacy or removing the fixture query and reloading. Existing Legacy App,panels,RoomView and Pixi scene remain unchanged. Explicit owner clarification preserves Legacy Pixi; only the new-world renderer stays uninitialized while disabled.

Switching unmounts the old view,stops its live connection and removes its bootstrap/history listeners;the new renderer retains AbortSignal,ticker/ResizeObserver,camera and atlas lease cleanup. An unresolved preview import cannot mount after rollback. Returning to Legacy creates a fresh Store and reads the backend normally;there is no fixture-to-live state adapter or mutation. Fixture-only mode starts no live API/SSE connection.

Existing fixture controls and description stay DOM. The canonical human-readable current-room summary uses the actor's world region and supplied open/closed status,independent of camera focus;its polite announcement changes with room/status only. Legacy business panels cannot safely consume WorldOut (no vitals,journal or interaction availability),so they remain with Legacy;no synthetic SnapshotOut is invented. Production JavaScript and source-map modules exclude development controls,fixtures and new-world rendering;bundle tests reject leaks and preserve hashed processed atlases. No API/SSE,Director,schema,CSP/Origin or deployment change. R1A-19 performance/soak,R1A-20 consolidation and the B14 production-default gate remain separate.


STEP140B closes the fractional-DPR browser gap: Playwright1.62.1/Chrome154.0.8037.98 reports actual DPR1/1.25/1.5/2/3 across desktop/tablet/phone15/15 PASS on measured WebGL2 ANGLE NVIDIA RTX3060 D3D11. Legacy/new round trips,focus,camera/backing,phases/atlas,cleanup and clean console/layout PASS;3 actual local production query/direct-route bypass checks remain Legacy. Fresh586+69 tests,lint,typecheck/build PASS; no application/dependency changes. R1A-15 remains REVIEW,ready for owner acceptance. [Full matrix and limits](implementation/maple-room-r1a-15-coexistence.md).


STEP141 owner accepts the implementation and STEP140B QA for commit,normal push,PR and CI inspection. R1A-15 remains REVIEW / OWNER ACCEPTED / MERGE PENDING;14/20 DONE=70%,75% only after confirmed merge. Browser QA above is accepted historical evidence,not a fresh STEP141 rerun. Production default and all API/SSE/security/schema boundaries remain unchanged;no B14,merge,deployment or production access authorization.


## R1A-19 measured renderer budgets — STEP 152

The integrated development-flagged New Room with the full 44×26 house and accepted placeholder atlases passes all six L20/L21 budgets on Windows/Chrome 154 hardware ANGLE RTX 3060: maximum actual draw submissions 4/40; worst synchronous Pixi render p95 2.0/4 ms desktop (including soak), 3.4/8 ms DPR-3 phone EMULATED at actual CDP 4× CPU throttle; zero >33 ms intervals in each of two ≥60-second desktop windows; 621,924 bytes retained JS heap growth over 631.946 seconds; conservative resident texture/render-target bound 12,656,568/33,554,432 bytes. The bound includes actual atlas/utility textures, backing buffers and Pixi's retained 1×1 capability framebuffer, not compressed PNG sizes.

CPU timing wraps the synchronous render invocation, separate from update/compositing/GPU completion. Every measured outlier is retained. Six Legacy/New round trips dispose the replaced renderer and preserve selector focus; post-GC DOM/listener counts remain stable. Phone Overview correctly uses the existing integer-zoom fallback and contributes no hidden cheap samples to its CPU gate. Runtime code, geometry, atlas bytes, Legacy default and production flag/API/SSE/security boundaries remain unchanged. Production query/direct-route isolation is freshly verified locally.

R1A-19 REVIEW / pending owner acceptance; 18 DONE / 1 REVIEW / 1 TODO = 90%. Physical devices, final production art, native Linux performance and seven-day production soak remain separate B14 work; R1A-20 is TODO. [Method, full scenario matrix, raw-evidence hashes, corrected allocation accounting and fresh tests](implementation/maple-room-r1a-19-performance-soak.md).

STEP 153: R1A-19 REVIEW / OWNER ACCEPTED / MERGE PENDING; 18 DONE / 1 REVIEW / 1 TODO = 90%. Hardware numbers above are accepted STEP 152 evidence. Fresh integration checks and deterministic harness/archive validation are recorded in the R1A-19 evidence document and PR; hosted CI does not measure RTX 3060 timing budgets.
