# Frontend — Maple's Room (Phase 6)

The room is a **view** of the backend. It has no behaviour engine: activity,
location, needs, expression, reactions, interaction availability, cooldowns,
server health, day phase and journal text all come from the API
(`docs/api.md`). The UI maps those values to pictures and words, and times
purely presentational things (walking, lighting fades, the end of a reaction
bubble, countdown text).

Stack: TypeScript, Vite, Preact for DOM, PixiJS 8 for the room canvas only
(ADR 0002).

## Layout

```
frontend/src/
├── api/          client.ts (snapshot + Greet/Pet), sse.ts (fetch-based SSE), types.ts (DTO mirror)
├── state/        store.ts (single state, revision rule), live.ts (snapshot + SSE sync),
│                 interactions.ts (Greet/Pet flow), presentation.ts (formatting helpers)
├── room/
│   ├── visual.ts         THE mapping: snapshot -> VisualState (pure, total, tested)
│   ├── layout/anchors.ts room size, named anchors, furniture boxes
│   ├── animation/motion.ts walking between anchors, eased values
│   ├── objects/furniture.ts vector furniture (temporary art)
│   ├── maple/figure.ts   vector Maple (temporary art): poses, faces, reaction bubbles
│   ├── assets/manifest.ts asset list + replacement contract
│   └── scene/RoomScene.ts Pixi application, layers, one ticker
├── ui/           App.tsx, panels.tsx, room/RoomView.tsx, interactions/InteractionBar.tsx, hooks.ts
├── styles.css    all styling (no inline style attributes: CSP style-src 'self')
└── main.tsx      wiring: Store + API + LiveConnection + lazily loaded scene
```

The Pixi scene is injected into `App` as a factory (`createScene`), so DOM
tests use a recording fake and never load Pixi. `main.tsx` loads the scene
with a dynamic import so the panels appear before the canvas is ready.

## Scene structure

`RoomScene` creates one `Application` (logical 1000 × 600, auto-density, resolution
≤ 2) and never recreates it; snapshots call `update(visual)`. Layers, back to
front:

1. sky (window pane colour, mixed toward the phase's sky colour)
2. walls, floor, window frame
3. furniture (texture if the manifest names one, otherwise vector drawing)
4. Maple
5. darkness overlay (alpha from lighting)
6. lamp glow and screen glow (additive, soft stacked rings)

A single ticker advances motion, animates Maple and eases lighting. A
`ResizeObserver` fits the canvas width to its container. `destroy()`
disconnects the observer, removes the ticker and destroys the app with its
children and textures. The canvas is `aria-hidden`; a DOM text summary
(`describeRoom`) describes the room instead.

## Anchors

Logical units; `(x, y)` is where Maple's feet go. Names are the backend's
logical locations.

| Location | Anchor (x, y) | Furniture there |
|---|---|---|
| `bed` | (150, 455) | bed |
| `bookshelf` | (330, 500) | bookshelf |
| `window` | (500, 470) | window, lamp |
| `desk` | (640, 470) | desk + chair |
| `terminal` | (840, 470) | computer desk + monitor |
| `rug` | (480, 545) | rug (neutral fallback anchor) |

## Mapping (`room/visual.ts`)

`toVisual(snapshot, serverNowMs)` is pure and deterministic. It is total:
unknown values fall back and set `recognised = false`. The DOM then adds
"Some of Maple's state is new to this display."

| Backend activity | Pose | Typical location (backend decides) |
|---|---|---|
| `idle` | stand (breathing) | rug / window |
| `walk` | walk | any |
| `sleep` | sleep (lying on the bed, "z z", sleepy face) | bed |
| `read` | read (book prop) | bookshelf |
| `write` | sit_write (pen prop) | desk |
| `observe_server` | sit_monitor | terminal |
| `rest` | rest (sitting) | rug |
| unknown | stand | — |

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

- **Walking is presentation only.** When the anchor changes, Maple walks at
  220 units/s in the walk pose, then takes the backend pose. A new target
  mid-walk redirects from the current position. Logical state is never
  changed by the walk.
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

## Panels

- **Maple:**
  - name, age, activity and expression;
  - mood, energy, curiosity and social as `<meter>` bars with numbers.
- **Journal:** newest first.
- **Server:**
  - sensor freshness badge and summary sentence;
  - CPU, RAM, Disk (`/`) and temperature;
  - allowlisted services.
- **Timeline:** newest first; collapsed by default.
- **Runtime:** connection, last update, heartbeat and Brain; collapsed by
  default.

Missing readings say `no data`, and failed ones say `unavailable (reason)` or
`unknown`. The UI never shows a made-up healthy value.

## Responsive behaviour

- **Wider than 960 px:** the room on the left (flexible) and panels in a
  340 px column.
- **960 px and below:** the room on top, with panels in auto-fit columns
  (two on a tablet).
- **600 px and below:** one column, tighter padding, and buttons at least
  52 px tall.

The canvas scales by width with a fixed 5:3 aspect ratio. `overflow-x` is
hidden, and every grid track uses `minmax(0, …)`. Verified at 390 × 844 and
820 × 1180 with no horizontal scroll.

## Accessibility

- Real `<button>`s with a visible `:focus-visible` outline; hints are linked
  with `aria-describedby`.
- Semantic headings: `h1` for the room, `h2` for each panel.
- `role="status"` on the feedback line and the connection badge.
- `role="alert"` on the disconnected and late-heartbeat banners.
- A DOM room summary replaces the decorative canvas.
- Reduced motion is supported as described above.

## Assets and how to replace them

All v0.1 art is **original and temporary**: furniture and Maple are drawn as
vectors in code (`room/objects/furniture.ts`, `room/maple/figure.ts`).
`room/assets/manifest.ts` lists every piece.

- **Furniture:**
  1. Put a transparent PNG under `frontend/public/assets/room/`, drawn at 2×
     the layout box in `layout/anchors.ts` `FURNITURE`.
  2. Set `texture: "/assets/room/<name>.png"` for that piece in
     `FURNITURE_ASSETS`.
  3. The scene draws the image in the same box. Anchors and mapping are
     unchanged.
- **Maple:**
  - one image per pose (`MAPLE_POSES`), a face overlay per expression
    (`MAPLE_FACES`), and a bubble per reaction symbol (`REACTION_SYMBOLS`);
  - origin is between Maple's feet; size is about 90 × 100 logical units.
  - `figure.ts` is the only file to change. The mapping, anchors and tests
    stay as they are.
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

## Tests (`pnpm test`)

| File | Covers |
|---|---|
| `room/visual.test.ts` | all activities, locations, expressions and reactions; expiry at `until`; unknown fallbacks; day/night; room text |
| `room/animation/motion.test.ts` | walk, speed, mid-walk redirect, snap, eased lighting |
| `api/sse.test.ts`, `api/client.test.ts` | SSE parsing (chunking, CRLF, comments), `Last-Event-ID`, close; 200/429/403/network |
| `state/store.test.ts` | revision monotonicity, server-clock estimate |
| `state/live.test.ts` | coalescing, in-flight events, resync frame, late old snapshot, reconnect with backoff and last id, stale detection, offline, stop |
| `state/interactions.test.ts` | Greet success, Greet cooldown, Pet success, 403/network rejection, no optimism, double click |
| `state/presentation.test.ts` | countdown, formatting, honest unknowns |
| `ui/App.test.tsx` | explicit states, one scene per mount, reaction expiry without heartbeat, reduced motion, availability and countdown, feedback, panels, mobile smoke |
| `guards.test.ts` | no backend rule constants in UI code, no raw-HTML or inline styles, reduced-motion and mobile CSS present, manifest completeness |

The tests don't compare pixels. Visual checks were done manually with
headless-Edge screenshots (see the Phase 6 report).
