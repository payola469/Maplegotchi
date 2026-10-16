# STEP 247 — versioned committed polling

The Room UI now reads `/local-alpha/v1/state` on this same localhost controller.
The opt-in `maple-canonical-poll.v1` response includes identity, life/layout
revision and committed timestamp from a fresh validated SQLite read. Legacy
projection refusal is explicit unavailable; it never becomes fake Legacy data.
Disconnected/unavailable UI frames are marked stale and controls are disabled.
The technical `/state` transport is retained. Existing public API/SSE is unchanged.

After updating this checkout, stop/start the existing controller with the commands
below to load the new endpoint; do not run init again. This implementation batch
does not restart or inspect the owner's retained session automatically. The
persistent alpha remains Linux-only, and R1B-04 still has a mandatory mid-edge
interrupt ordering gate. See
[implementation status](../../../docs/implementation/maple-room-step247-contract-implementation.md).

# Persistent synthetic Local Alpha (STEP 244)

On the Linux development host, from the repository root:

```sh
# First use ONLY: create an exclusive, new synthetic session and start it.
./frontend/tools/life-preview/alpha.sh init
# Ctrl+C stops the entire controller, retaining state.
# Every later start: restore only, never create/reset/repair.
./frontend/tools/life-preview/alpha.sh start
# From another terminal: pause, verify the owned session, and stop the controller.
./frontend/tools/life-preview/alpha.sh stop
```

Open **http://127.0.0.1:8474/**. This localhost belongs to the machine running the
command (the current Codex host is `paolo-ubuntu`), not an unrelated owner's
computer. If already authorized SSH access exists from another machine:
`ssh -N -L 8474:127.0.0.1:8474 USER@HOST`, then open the same URL there. No public
listener, Tailscale Serve, production service or paolo-core configuration is used.
Owner access has not been confirmed until the owner actually tries it.

The launcher uses the existing backend venv, or `uv run --locked`; install the
existing locked frontend dependencies first if needed. `MAPLE_ALPHA_PYTHON` can
explicitly select an already-installed compatible interpreter.

Data stays in this checkout's ignored `var/maple-local-alpha`. Do not delete,
move, copy, change permissions or re-run init to reset it. Existing directories
are refused by init, and missing/foreign/corrupt/incompatible data is refused by
start. Failed initialization is retained for explicit inspection, never repaired
or overwritten automatically. Closing the browser does not stop the controller;
use Ctrl+C in its terminal or the `stop` command above. Starting a second
controller is refused. After starting again, reload the browser page to obtain
the new controller's security token before using its controls.

This persistent mode has separate development ownership admission: a root created
exclusively by init, private Linux owner/permissions, immutable root/database
identity, synthetic session marker and an exclusive controller lock. Workers
receive a parent-bound capability and inherit the lock until exit, protecting
in-flight work even if the controller is abruptly killed. Existing temporary
OwnedRoot guards are unchanged. SQLite schema, codecs, complete state admission,
atomic/CAS writer and canonical life rules are the same existing implementation.
No arbitrary existing user/test/production database is adopted.

Restart begins paused and does not advance clock, revision or actions. Compare
`/state` before/after for controller PID, database identity, session, digest,
revision, RNG counters and history. Then click Live heartbeat to continue. The
existing UI is unchanged. This alpha is Linux-only; other platforms fail closed
until their ownership/locking implementation is validated. It is not R1B-04
completion, a D01/D03/D05 resolution, production migration or default activation.

---

# Temporary canonical preview (STEP 243)

This is an **isolated synthetic preview**, not the shipped Room, production
runtime, public API/SSE contract, or a resolution of D01/D03/D05.

## Open it

Install the existing locked frontend dependencies in this checkout:

```sh
cd frontend
pnpm install --frozen-lockfile
cd ../backend
uv sync --locked
PYTHONPATH=src uv run python -B -m tests.schema_v11.playable_preview --port 8473
```

Open **http://127.0.0.1:8473/** in a browser. Keep the controller terminal open.
The server binds only to `127.0.0.1`. No production services/configuration,
external network, API credentials or existing database path are required.

On the current development host, the already-installed Python can also run it:

```sh
cd /tmp/Maplegotchi-step238-life-loop/backend
PYTHONPATH=src /home/paolo-ubuntu/GitHub/Maplegotchi/backend/.venv/bin/python -B -m tests.schema_v11.playable_preview --port 8473
```

Use another free local port if this preview is already running. Never start a
second controller and expect it to adopt the first controller's database.

## Try the life loop

1. The initial real rule decision selects WRITE using a deterministic synthetic
   seed. Maple starts walking from the Hall to the Writing Desk. The controller
   initially pauses so the owner can inspect the first saved frame.
2. **Live heartbeat** advances the supplied preview clock by one second per
   completed heartbeat. Each tick uses the existing canonical needs/action/
   movement rules and atomic SQLite writer. Needs and grid position update.
3. After arrival, **Next activity** advances to activity completion, then lets
   the same rule engine choose the next action. It cannot skip an ordinary walk.
   The clock jump is explicit; it is not a client-side demo animation.
4. **Pause**, inspect the saved-state evidence, then **Restart runtime**. A new
   actual Python process restores the same owned SQLite state. Digest, revision,
   action and tick remain unchanged; PID changes. Click Live heartbeat to continue.

The preview deliberately runs each runtime command in a distinct, tracked
interpreter. The writer saves, exits completely and is waited for before a new
worker starts. The parent owns the private temporary root for this execution;
GET `/state` only displays the last successful saved frame. The client does not
simulate movement or needs. PixiJS (the existing pinned dependency) renders the
canonical layout, route and backend-derived feet coordinates with placeholder art.

## Session and failure boundaries

**Restart runtime preserves state within the current controller session.** The
controller/UI remains running while workers stop/restart. This demonstrates real
cross-process durability; it is not a claim about restarting the entire app,
rebooting the computer or resuming an old temporary directory.

Ctrl+C ends the controller session and cleans only its fresh registered synthetic
root on a normal exit. Starting a new controller starts a new synthetic Maple.
No arbitrary existing root/database is accepted. On a writer failure the preview
pauses, retains its owned artifacts and refuses automatic retry/reset. The last
saved display is explicitly marked stopped/stale.

Critical/high mid-movement interruption, point ties and persisted reevaluation
remain fail-closed limitations. There are no real sensors/owner interactions,
production data, live public DTO/SSE integration or default switches. Placeholder
art and one-second saved frames are preview presentation, not final renderer parity.
R1B-04 is **not complete**. Windows native validation of this new preview is pending.

## Focused validation

From `backend`:

```sh
PYTHONPATH=src uv run pytest tests/schema_v11/test_playable_preview.py
```

This checks real position/needs changes, actual worker PIDs/exit order, unchanged
SQLite bytes after restart, arrival/action continuation and local HTTP mutation
admission (host/origin/token/body/transfer-encoding). Existing core/world/extended
life and frontend regressions stay separate. No production migration is executed.

## Maple Room UI v1 (STEP 245)

`alpha.sh start` now builds the isolated Room UI from the existing processed atlas
and restores the same session. Open `/` for Room UI and `/technical` for the
unchanged technical controls. Start and Stop commands above are unchanged.
Existing locked Node/frontend dependencies are required. No raw art is served.
Backend-only runs without a UI build retain the technical transport fallback.

The Room uses the accepted Final Design Spec geometry, ADR-0040/0041 integer
pixel zoom and existing warm UI tokens. It reuses the original programmer atlas
(`art/README.md`); art/palette/faces remain provisional. There are no new art
assets, final-art claims or day-phase tint decisions. On narrow screens Overview
falls back to room buttons and a focused view, without fractional shrinking.

Read-only polling reconnects automatically after a controller restart. Mutation
controls refresh the new controller token before the next user command; failed
commands are never replayed automatically. A different session freezes the
view. Browser refresh/close never initializes a life. The main page has heartbeat
and pause; clock advance, worker restore and state diagnostics stay in Development
tools. Face overlays are neutral placeholder art (sleep has the sleep overlay),
not a newly inferred expression/mood policy. Mood bars are the actual saved needs.

Validation: `pnpm lint`, `pnpm typecheck`, `pnpm test`, `pnpm build`, followed by
`pnpm exec tsc -p tools/room-ui/tsconfig.json` and
`pnpm exec vite build --config tools/room-ui/vite.config.mjs`.
