# First playable canonical preview (STEP 243)

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
