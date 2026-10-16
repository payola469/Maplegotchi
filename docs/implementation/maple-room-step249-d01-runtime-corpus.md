# STEP 249 — approved exact urgency and integrated evidence

Owner STEP249 explicitly approves STEP248's formula, tie-only decision RNG,
ordering and fail-closed boundaries. This record does not authorize publication,
accept workstreams, change a golden pin or activate the shipped runtime.

## D01 implementation

The existing capability/provider admission filters are shared by ordinary and
urgent resolution. Ordinary Tile scores/ordering remain unchanged. Urgent
resolution enumerates eligible providers without substituting a guessed Tile
for the current EdgeStart, then calls existing `reroute` for each target.

Scores are exact integers:
`S * (1000*tier - 50*sticky - 200*preference) + N*S + E`.
Mid-edge stickiness is zero. The existing per-target endpoint choice still uses
duration, turns and endpoint coordinates; turn penalty is not added again.
Tile-only scores are the original scores multiplied by the same positive S.

Only equal best provider scores consume one `decision(C+1)` draw, offset zero,
after stable PointKey ordering. The successful urgency transition persists C+1
only when that draw occurred. Duration keeps its existing tick RNG stream. This
is Core urgency, so no Director decision row is fabricated. Action counter,
state revision and tick counter advance once in the successful transaction.

Due arrivals settle once before urgency; otherwise the prior walking plan is
cancelled, its goal suspended, and its task ended through the existing shared
rules. The new Travel stores the exact Entry and inherits movement speed.
`route_from_activity` preserves the existing performed-activity provenance
(Legacy `performed_activity` uses the prior route's from_activity while moving),
not the cancelled plan's destination activity. The stored Tile remains the
route-origin endpoint required by the existing codec; actual position always
comes from Travel/Entry, not that Tile or a rounded pixel coordinate.

Canonical admission, revision/ownership checks and the atomic writer remain
mandatory. Approved canonical urgency can persist when Legacy projection cannot
represent it. Pure Legacy refusal stays intact; polling returns unavailable.
Legacy-only audit distance is null while its origin is unprojectable, rather
than a fictitious distance from the cancelled destination. Existing nullable
JSON scalar vocabulary is used; no world-event payload or public API is enabled.

Equal-time new interrupts, outstanding reevaluation, ambiguous provenance and
uncertain commit outcomes remain fail-closed. A refused transition is neither
queued nor reported as a successful heartbeat. These boundaries are not silently
declared supported by the new mid-edge implementation.

## D03 integration

The existing saved-layout S14 gate admits only the named Sleep/Observe providers.
Positive tie selection/counter tests therefore use isolated pure resolution
specimens. A negative saved-layout test proves an added urgent provider still
rejects under S14; no fictitious Legacy anchor or weakened validator is used to
manufacture a positive persisted-tie case. Enabling additional persisted urgent
providers would require a separate S14/mapping/audit contract clarification.
This does not block the approved single-provider MVP or its 30-day corpus.

The separate `maple-canonical-poll.v1` read contract and Local Alpha endpoint
remain unchanged. Actual post-urgency persisted Entry snapshots drive canonical
position/activity/needs, with consistent life/layout revisions and timestamp.
Legacy projection returns unavailable. Existing renderer Entry handling supports
both directions, and browser polling never supplies a movement origin to core.
Read-side mutation, stale-as-live frames and implicit recreation stay prohibited.

## Corpus and diagnostics

The candidate manifest remains 30 days, seeds 0 and 5, 300-second ordinary input
cadence, 8,640 inputs per seed and restart cuts 1,3,288,2016,4320,8352. The first
selected movement additionally receives the approved critical input at +100,000
microseconds. An ordinary input not due after that urgent tick is a no-op; it
must not fabricate a revision or duplicate history.

`tests/schema_v11/full_semantic_corpus.py` executes the existing pure engine for
the full duration twice per seed, comparing every full frame/action/life-event
prefix and final frame. It covers all eight activities. It explicitly does not
claim SQLite commit/restart proof or include dynamic stored-document effects.

`tests/schema_v11/durable_corpus.py` executes actual SQLite writes and the real
runtime/task catalog at every applicable input. Independent continuous and
restarted roots are compared at every input digest and final exact typed image.
Writer processes fully exit before successor readers/writers. The first action
cut exercises a persisted urgent Entry. Four independent roots/process streams
may run concurrently; they never share a database. Cancellation/error terminates
only tracked children and waits before returning; failed owned evidence is
retained, not automatically repaired, restored or retried.

```sh
cd backend
PYTHONPATH=src .venv/bin/python -B -m tests.schema_v11.durable_corpus --output NEW.json
```

On Windows use the already configured compatible interpreter/uv and equivalent
environment syntax. `--inputs N` is a partial harness check only; default is the
full manifest. Each child has a hard timeout and bounded stdout. Full diagnostics
are computationally expensive with the existing complete admission path; no
validation, ownership or transaction guard is reduced to accelerate them.

Separate real-process tests cover High urgency, both existing Entry directions,
old destination cancellation, D03 committed reads, no ghost/duplicate arrivals,
before/after-COMMIT interruption and unchanged unsupported-boundary refusals.
The short native diagnostic format is v2 because D01 now persists exact Entry;
this is not an original/R17 simulation-pin update.

The long durable run exposed a real shared-catalog serialization bug when Maple
read its own document: `WriteKind` escaped as a category where v11 requires an
exact TEXT scalar. `TaskWorker.catalog` now supplies the enum's existing string
value. This preserves selection order, RNG, public JSON values and the strict
record guard. A fresh owned-document regression protects this boundary.

Final run conclusions, source SHA and raw evidence are recorded in the STEP249
delivery packet. A started run, partial prefix or pure-only trace is not a full
durable PASS. Original/R17 pins remain unchanged; an integrated golden pin and
Owner acceptance require separate review. Native Windows evidence must come
from that actual platform at the published candidate, never Linux or win32 typing.
