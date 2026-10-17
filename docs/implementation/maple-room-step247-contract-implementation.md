# STEP 247 — approved directions, local implementation and remaining gate

Owner STEP 247 explicitly reports STEP 246 approval of D01-A, separate opt-in
polling for D03, and a full integrated corpus for D05. This supersedes the earlier
direction-only OPEN labels; it does not approve new ordering/provenance semantics,
schema changes, digest pins, public API/SSE changes, publication or acceptance.

## D03 implemented boundary

The existing synthetic Local Alpha controller exposes the separate read-only
`GET /local-alpha/v1/state`. It is localhost-only on the existing controller port,
under the same exact Host check, no CORS and no-store response policy. No shipped
FastAPI route, DTO, SSE event or replay contract is changed.

`maple-canonical-poll.v1` identifies `opt_in_canonical` as its source. A successful
reply contains Maple identity/birth, life and layout revisions, committed UTC
timestamp, actual canonical feet, activity/phase, needs and counters from one
immutable committed capture. Legacy data is included only when the unchanged
pure admission succeeds with supplied presentation/provenance. Otherwise its
status is `unavailable`, with the stable refusal reason and no Legacy data.
Missing origin is not inferred from the destination or a rounded tile.

The controller executes an independently tracked read-only worker on every poll;
it restores and validates SQLite and the expected full-image digest. It does not
init, tick, install a new controller frame, retry a write or reset any state.
Errors return HTTP 503 with an unavailable envelope and no snapshot/display.
Renderer geometry and metadata come from that same worker capture. The UI checks
matching revisions/timestamps/needs/position/counters before accepting the frame.
Connection failure/unavailable marks the retained frame stale, removes Live and
current-save claims, disables mutation controls and reconnects read-only. A
changed session is refused; controller restart renews the mutation token without
replaying a command. The technical `/state` preview remains available separately.

This is a real opt-in synthetic integration, not activation of the shipped service
or proof of production migration/operational readiness.

## D01 affected implementation stopped at ordering gate

The existing resolver accepts `Tile` only (`core/world/resolution.py`,
`candidates_for`) and scores `1000 * room_tier + path_steps - 50 * sticky - 200 *
preference`. Equal scores draw from the seeded decision stream. The existing
mid-edge `reroute` compares exact remaining microseconds, turns and endpoint.
Those endpoint rules choose a path to a *given* target, not which capability
provider the urgent action should select.

At a genuine `EdgeStart`, applying the Tile resolver to the departure tile or
either endpoint would fabricate an origin. Replacing path_steps with elapsed
microseconds without scaling the other terms changes destination ordering.
Fractional-step cost, common-integer scaling, endpoint enumeration and urgent
tie RNG/counter ownership need an explicit interpretation before implementation.
The current urgent branch also refuses point ties; no guard is removed here.

Smallest proposed clarification: use existing reroute for each eligible provider;
preserve the existing weighted score in step units via exact common-integer
scaling, then use the existing seeded tie stream with explicit counter ownership.
This is **PROPOSED**, not selected by this implementation. Owner must approve or
identify an already binding rule for this case, including equal-time interruption
and persisted provenance validation. If existing schema/codec cannot retain the
required provenance, stop and propose the exact delta rather than change schema.

Critical/High mid-edge remains fail-closed; this is a mandatory R1B-04 blocker,
not a successful interruption or a silently queued transition. Existing ordinary,
stationary and known-arrival behavior remains unchanged.

## D05 full-corpus preparation

`tests/schema_v11/integrated_corpus.py` defines a repeatable **candidate input
manifest**, not a completed executor: two existing seeds (0 and 5), fixed UTC
clock, 300-second ordinary ticks, 8,640 ticks per seed for 30 days, and restart
cuts after transitions 1, 3, 288, 2016, 4320 and 8352. Mandatory scenarios explicitly
include Critical/High mid-edge, pending/Entry restart, late/ghost arrival, goal/task
suspend/resume/expiry, unavailable/reconnect and commit failures/uncertainty.

No mandatory scenario may be omitted and called PASS. Complete schedule details
for urgent inputs depend on D01 ordering; full committed-image comparisons,
native artifacts and actual proposed pin remain outstanding. Corpus acceptance
requires repeated continuous/restarted complete state, goals/tasks, history,
arrivals, revisions and RNG equality. Process/platform identity is provenance,
never a reason to normalize semantic state differences. No new normalization
or golden hash is chosen here. A 12/24-tick diagnostic is not 30-day acceptance.

Original and R17 fixtures/pins remain unchanged. Actual integrated pin and
intentional differences require a separate owner review after full native
evidence. R1B-04–07 are not automatically DONE; accepted progress remains 3/12.
