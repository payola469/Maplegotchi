# API, live state, and owner interactions (Phase 5)

Status: implemented and approved (2026-09-30). Choices here are **[PROPOSED]**
unless they follow directly from a FIXED decision (noted inline).

## Layers

```
HTTP (FastAPI routes, api/app.py)          thin: parse, call the service, map to DTOs
  └─ MapleService (runtime/service.py)     assembly + freshness; rules come from core
       ├─ LifeRuntime (runtime/life.py)    the single writer (Phase 2): heartbeats + Greet/Pet
       ├─ Senses (runtime/senses.py)       read outside the writer lock
       ├─ EventHub (runtime/events.py)     bounded live-event buffer for SSE
       └─ Clock (runtime/clock.py)         the only source of "now"
```

Routes never compute Maple rules. Expression, active reaction, cooldown
availability (`core.interactions.check_limits`), server summary
(`core.reflection.server_summary`), attention (`core.attention`), and day/night
(`core.daytime`) are all core functions evaluated by the service.

## Routes

All under `/api`. Responses are explicit Pydantic models (`api/models.py`);
no rows or domain objects are returned.

| Method | Path | Response | Notes |
|---|---|---|---|
| GET | `/api/health` | `{status}` | liveness only |
| GET | `/api/snapshot` | `SnapshotOut` | everything the UI needs (below) |
| GET | `/api/maple` | `MapleOut` | identity, age, needs, activity, location, expression, reaction, interaction availability |
| GET | `/api/status` | `StatusOut` | revision, freshness, brain label |
| GET | `/api/server` | `ServerOut` | summary, attention, service health, host readings, counts by status |
| GET | `/api/room` | `RoomOut` | room size, furniture labels, interaction points (ADR-0027); static per release |
| GET | `/api/decisions?limit=1..100` | `DecisionOut[]` | decision audit, most recent, oldest first (ADR-0026 §8) |
| GET | `/api/life-events?after_revision=N&limit=1..500` | `LifeEventsOut` | every life event after revision N, whole revisions only; continue from `last_revision` |
| GET | `/api/observations/latest` | `ObservationOut[]` | the snapshot stored with the latest observed heartbeat |
| GET | `/api/journal?limit=1..100` | `JournalEntryOut[]` | most recent, oldest first (default 20) |
| GET | `/api/timeline?limit=1..100` | `TimelineEventOut[]` | most recent, oldest first (default 20) |
| GET | `/api/events` | `text/event-stream` | SSE, read-only |
| POST | `/api/interactions/greet` | `InteractionOut` | 200 accepted / 429 rejected |
| POST | `/api/interactions/pet` | `InteractionOut` | 200 accepted / 429 rejected |
| GET | `/api/docs`, `/api/openapi.json` | | **development mode only** |

There is no other mutating route: no generic action or command endpoint, no
free text, no admin/debug surface. A test compares the app's full route table
against this list.

## Snapshot contract (`GET /api/snapshot`)

```jsonc
{
  "revision": 42,                       // commits so far; strictly increasing
  "generated_at": "…Z",                 // server time the snapshot describes
  "maple": {
    "revision": 42, "generated_at": "…Z",
    "identity": {"name": "Maple", "born_at": "…Z", "age_seconds": 1234.5, "ticks_lived": 4},
    "needs": {"mood": 64.0, "energy": 79.1, "curiosity": 60.3, "social": 62.0},
    "activity": {"kind": "write", "location": "desk", "started_at": "…Z", "until": "…Z",
                 // additive (ADR-0027): movement is backend state
                 "phase": "walking|performing", "point": "writing_desk.chair",
                 "furniture": "writing_desk", "pose": "walk|sit_write|…", "facing": "back",
                 "position": {"x": 412.5, "y": 520.0},          // at generated_at
                 "route": {"departed_at": "…Z", "arrives_at": "…Z",  // == started_at
                           "from_activity": "read",
                           "path": [{"x": 330, "y": 500, "distance": 0, "node": "bookshelf.front"}, …]}
                          | null},
    "expression": "happy",              // at generated_at
    "reaction": {"kind": "greet_happy", "variant": 1, "started_at": "…Z", "until": "…Z"} | null,
    "interactions": [
      {"kind": "greet", "available": false, "reason": "cooldown", "retry_after_seconds": 51.2},
      {"kind": "pet",   "available": true,  "reason": null,       "retry_after_seconds": null}
    ],
    // additive (ADR-0026)
    "goal": {"id": 3, "type": "learn", "summary": "Learn something new", "source": "rule",
             "started_at": "…Z", "horizon_until": "…Z"} | null,
    "suspended_goal": GoalOut | null,   // paused by an interruption
    "action_priority": "critical|high|normal|low"
  },
  "day": {"local_time": "2026-01-01T07:05:00+07:00", "local_hour": 7.0833, "phase": "morning",
          "is_night": false, "timezone": "Asia/Bangkok", "utc_offset_minutes": 420},
  "server": {"observed_at": "…Z" | null, "sensor_status": "fresh|stale|none",
             "summary": "calm|unclear|troubled_earlier|still_troubled|no_data",
             "attention_level": 0.0, "attention_reasons": [], "counts": {"available": 8, "unknown": 7},
             "services": [{"service_id": "jellyfin", "status": "unknown", "state": null,
                           "source": "service_health", "reason": "…", "observed_at": "…Z"}],
             "host": [ObservationOut…]},
  "journal":  [JournalEntryOut…],       // 10 most recent, oldest first
  "timeline": [TimelineEventOut…],      // 10 most recent, oldest first
  "freshness": {…},                     // below
  "brain": {"kind": "rule", "name": "rule_brain", "version": "1"},
  "director": {"kind": "rule", "name": "rule_director", "version": "1"}  // additive (ADR-0026)
}
```

The UI shows only these values: Maple's state is never invented client-side.
A reaction carries its `until`, so the UI can stop showing it at that moment
without waiting for an event; the next read confirms it (expression reverts
to the state-derived value).

## Consistency guarantees

**One coherent snapshot.** `MapleService.snapshot()` calls
`LifeRuntime.read_view()`, which (under the runtime lock, so the shared
connection is never used by two threads at once) runs
`LifeRepository.read_view()`: a single SQLite read transaction (`BEGIN` …
`COMMIT`) that reads the life state and its revision, the journal state, the
latest observations, the recent journal, and the recent timeline. With WAL, a
read transaction sees exactly one committed database state, so the persisted
parts of a snapshot always belong to the same revision. A transition that
commits concurrently appears either entirely before or entirely after — never
mixed. This holds even against a writer on another connection (proved in
`tests/api/test_consistency.py`, including a negative control that disables
the read transaction and observes the mixture it prevents). The snapshot is
assembled only from that view; derived-at-read values (`generated_at`,
expression, active reaction, availability, freshness) use the current clock
and never write.

**SSE describes committed transitions only.**
- `heartbeat_committed` / `interact_committed` return the result, the revision
  it committed, and the journal entries written — exactly, even under
  concurrency.
- The service publishes after the runtime call returns: after the durable
  commit, with the writer lock released. Publication is not part of the
  database transaction; a failing hub is swallowed and can never block or roll
  back a transition.
- A transition that fails or rolls back publishes nothing.
- Journal/timeline events carry exactly the rows with that revision.
- A client that receives an event with revision N and then reads a snapshot
  sees a revision ≥ N.
- An interaction response's `revision` is that interaction's own committed
  revision (current revision if rejected) and matches its `interaction` event;
  `maple.revision` in the same response is read afterwards and may be higher.

## Freshness semantics

| Field | Meaning |
|---|---|
| `server_time` | time the response describes |
| `last_heartbeat_at`, `next_heartbeat_due_at`, `heartbeat_interval_seconds`, `heartbeat_age_seconds` | heartbeat timing (300 s in production, D6) |
| `heartbeat_status` | `fresh` while `server_time ≤ next_due + 60 s`; `overdue` after that (connected, but Maple's life loop is late) |
| `life_loop_running`, `life_loop_error` | background loop alive; last error type if a step failed (the loop keeps retrying) |
| `sensor_status` | `none` (never observed), `fresh` (latest observations ≤ interval + 60 s old), `stale` (older) |
| `observations_at` | time of the latest stored observations |
| `sse_keepalive_seconds` | the stream sends at least a keepalive this often |

The client can therefore distinguish:
- **connected and fresh**: SSE open, `heartbeat_status = fresh`;
- **connected but overdue**: SSE open, `heartbeat_status = overdue`;
- **disconnected / stale**: no SSE traffic (not even a keepalive) for longer than
  `sse_keepalive_seconds` plus a margin, or a fetch failure; the last data must
  then be shown as stale;
- **sensor data unavailable**: `sensor_status = none|stale`, or individual
  observations with status `unavailable` / `unknown` / `error` and a reason.

## Interaction semantics

- `POST /api/interactions/greet` and `/pet` only. Body: empty or `{}`; anything
  else → 400. The action is the path, from a closed set.
- Each call goes through `LifeRuntime.interact` — the same lock as heartbeats —
  so cooldowns (Greet 60 s, Pet 30 s) and the global 10 per 10 min (D14) apply
  exactly, including across restarts.
- `200` accepted / `429` rejected (with a `Retry-After` header, whole seconds
  rounded up). Both return `InteractionOut`:
  `{interaction, accepted, reason, retry_after_seconds, reaction, revision, maple}`.
  A rejection changes nothing and is not persisted (revision unchanged).
- `maple.interactions` in every read tells the client each interaction's
  availability, so it never has to guess cooldowns.

## Origin and CORS rules

- **No CORS at all.** There is no CORS middleware and no
  `Access-Control-Allow-Origin` header, so no other origin can read responses.
  v0.1 is same-origin (D13): in production FastAPI serves the built frontend;
  in development the Vite dev server (port 5173) proxies `/api` to the backend
  (port 8470), which the browser sees as same-origin.
- **Mutations require a trusted `Origin`.** Greet/Pet require an `Origin` header
  exactly equal to one in `MAPLE_ALLOWED_ORIGINS` (exact `scheme://host[:port]`,
  no wildcards, no paths). Missing, `null`, or any other origin → 403, with no
  side effects. Development default: `http://127.0.0.1:5173`,
  `http://localhost:5173`, `http://127.0.0.1:8470`, `http://localhost:8470`.
  Production: must be set explicitly (e.g. the Tailscale Serve https origin).
- **Bind:** loopback only (`127.0.0.1`, `::1`, `localhost`); anything else is a
  settings error (D5, D13). Tailscale Serve is Phase 7.
- **Bodies:** a declared `Content-Length` over 1024 bytes, or a chunked body
  without a length, is refused with 413 before routing.
- **Headers on every response:** CSP (`default-src 'self'`, `frame-ancestors
  'none'`, …), `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`,
  `X-Frame-Options: DENY`, COOP/CORP `same-origin`, a restrictive
  `Permissions-Policy`, no `Server` header; `/api` responses are `no-store`.
- **Production mode** disables `/api/docs` and `/api/openapi.json`.

## SSE event contract (`GET /api/events`)

```
retry: 3000

id: <boot>-<seq>
event: <kind>
data: <one line of JSON>

: keepalive
```

| Event | When | Data |
|---|---|---|
| `snapshot` | on connect, and whenever the client cannot be caught up | full `SnapshotOut` |
| `heartbeat` | after each heartbeat | `revision`, `tick_id`, `activity`, `location`, `needs`, `last_heartbeat_at` |
| `observations` | after each observed heartbeat | `revision`, `observed_at`, `counts` |
| `interaction` | after an accepted Greet/Pet | `revision`, `kind`, `reaction` |
| `movement` | when an arrival or a decision changed where Maple is going | `revision`, `activity`, `location`, `point` |
| `life` | after every commit that wrote life events | `revision`, `events: LifeEventOut[]` (below) |
| `journal` | when entries were written | `revision`, `entries: JournalEntryOut[]` |
| `timeline` | when lifecycle events were written | `revision`, `events: TimelineEventOut[]` |

- Ids are `<boot>-<seq>`: `boot` changes on every process start; `seq` is
  strictly increasing. Events are delivered in order.
- **Reconnect:** send `Last-Event-ID`. A valid id from this process within the
  buffer → the missed events are replayed. Absent, malformed, from an earlier
  process, from the future, or older than the buffer → a `snapshot` event, then
  live events. The client never silently misses a change.
- **Bounded:** the hub keeps the last 512 events. Publishing only appends and
  wakes waiters; it never waits for a client. A slow client that falls behind
  is resynced with a snapshot.
- **Read-only:** the stream accepts no input; other methods on `/api/events`
  are refused. Waiting clients hold no lock; Maple's life never waits for them.

## Static frontend serving

With `MAPLE_STATIC_DIR` (or `--static-dir`) set to the built frontend (`frontend/dist`):

- `/api/...` is never served by the frontend; unknown API paths are JSON 404.
- existing files are served (`/assets/*` cached as immutable; others `no-cache`);
  only regular files inside the resolved static root, so traversal and symlink
  escapes are refused;
- a missing path with a file extension (e.g. `/missing.js`) is 404;
- any other path falls back to `index.html` (SPA routing).
- a static dir without `index.html` is a startup error.

## Running locally (milestone M1)

```bash
cd backend
mkdir -p ../var/maple-data                        # Maple's data dir must already exist
uv run maplegotchi run --data-dir ../var/maple-data --senses fake \
    --static-dir ../frontend/dist                 # http://127.0.0.1:8470
```

Settings come from the environment (`MAPLE_*`, see `maplegotchi/config.py`);
the flags above override them.

## Life events: one model for Web, iOS and Discord (ADR-0028 §2)

Three append-only stores, one envelope:

| Store | Types |
|---|---|
| `timeline` (significant life events) | `born`, `activity_changed`, `interaction_accepted`, `downtime_gap`, `goal_started`, `goal_suspended`, `goal_resumed`, `goal_completed`, `goal_abandoned` |
| `action` (action lifecycle) | `destination_selected`, `walking_started`, `walking_cancelled`, `arrived`, `activity_started`, `activity_completed`, `activity_interrupted`, `activity_resumed`, `needs_attention` |
| `decision` (audit) | `goal_proposed` (a new goal was proposed), `decision_made`, `decision_rejected` (rejected or stale proposal) |

```jsonc
{"id": "action:42", "type": "walking_started", "at": "…Z", "revision": 310,
 "goal_id": 7, "action_id": 55, "priority": null,
 "payload": {"point": "writing_desk.chair", "furniture": "writing_desk",
             "arrives_at": "…Z", "distance": 400.0}}
```

- Ordering: by revision, then decision → timeline → action, then row id.
- Live: the SSE `life` event carries the envelopes of one commit. Catch-up or
  polling (iOS, Discord gateway): `GET /api/life-events?after_revision=<last seen>`;
  a page never ends part-way through a revision.
- `DecisionOut` holds core's `context_summary`, the proposal (with the
  proposer's single concise `reason`), the verdict and reason code, clamped
  originals, and what was executed. No prompt, raw model output, or model
  reasoning is stored or served.

