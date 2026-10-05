# ADR-0026: AI Director — goals, actions, priorities, and the decision transition

- **Status:** Accepted — FIXED (CLAUDE.md D25)
- **Date:** 2026-10-05
- **Decided by:** owner (2026-10-05: AI decisions become their own transition;
  Director is a separate protocol; out-of-range durations are clamped and recorded;
  Greet/Pet stay non-interrupting; decision and action audit in separate tables).
  Details marked [PROPOSED] may still be adjusted in review.
- **Amends:** ADR-0010 (behavior is no longer exclusively a core rule; core stays
  the validator/executor), ADR-0025 (the External Brain companion gains a decision
  endpoint). **Preserves:** ADR-0006 (an ordinary heartbeat never invokes an
  External Brain), ADR-0007 (determinism), ADR-0003 (Greet and Pet only).
- **Related:** ADR-0027 (room and movement), ADR-0028 (activity set v2, event
  model, schema v4, rollback/recovery).

## Context

Until now Maple's behavior has been chosen only by core's seeded utility scoring
(`core/behavior.py`), invoked inside the heartbeat. The owner wants Antigravity,
reached through the loopback External Brain boundary of ADR-0025, to become the
primary source of Maple's short-term goal and next action, while core keeps the
final say and the existing rule behavior remains a complete fallback.

Constraints carried over unchanged:
- `maplegotchi.brain` is pure: no I/O, no network, no handles.
- The AI never writes state, the database, files, or runs anything.
- An ordinary heartbeat never invokes an External Brain (D6).
- Any transition must be reproducible from stored inputs plus `life_seed` (D7).
- Raw model chain-of-thought is never persisted.

## Decision

### 1. Roles
- **Director** proposes: a short-term goal (or keep/complete/resume/abandon the
  current one) and the next action with a duration and a concise reason.
- **Core** validates and executes: it accepts, clamps, or rejects the proposal,
  resolves the destination (ADR-0027), and produces every state change and event.
- **Rule direction** — core's own behavior engine, extended with goals — is always
  available and is used whenever no Director is configured or the Director fails,
  times out, or is rejected. It is core logic, not a Brain.

### 2. A separate `Director` protocol
- New pure module `maplegotchi.brain.director` defines
  `Director(Protocol)`: `kind: DirectorKind ("rule" | "external")`, `name`,
  `version`, `propose_decision(context: DecisionContext) -> DecisionProposal | None`.
- The journal `Brain` protocol (`compose_journal`) is **unchanged**. The two are
  wired independently by `runtime`; one object may implement both, but neither
  protocol depends on the other.
- Configuration [PROPOSED]: `MAPLE_DIRECTOR = rule | antigravity` (default
  `rule`), `MAPLE_DIRECTOR_TIMEOUT_SECONDS` (default 15, allowed 1–30). The
  Director uses the same loopback-only `MAPLE_BRAIN_URL` validation as ADR-0025.
- As with the journal Brain, a non-built-in Director claiming `kind="rule"` is
  refused at startup.
- `runtime/external_brain.py` implements `propose_decision` by `POST /decide` to
  the companion with a versioned JSON contract (`maple.decision.v1`): request =
  serialised `DecisionContext`; response = one proposal object. The companion
  must add this endpoint (it lives outside this repository). Maplegotchi sends no
  free-form prompt for decisions; prompt construction belongs to the companion.

### 3. The decision transition
A **decision** is a third kind of life transition, next to heartbeat and
interaction, serialized by the same single writer (`runtime/life`).

- **Due** when, at `now`: the current action has completed (`now >= until`); or a
  high-priority signal requested re-evaluation (§6); or there is no action plan
  (first start after migration).
- **Flow** (mirrors how senses are read today):
  1. Under the lock: read `(state, revision)`; core builds a `DecisionContext`.
  2. Outside the lock: call the Director with the timeout (via
     `asyncio.to_thread` from the life loop; at most one decision in flight).
  3. Under the lock: `decide_committed(proposal, based_on_revision)`. Core
     re-validates against the **current** state. If a decision is no longer due
     (a heartbeat or interrupt already handled it), the proposal is recorded as
     `stale` and dropped. Otherwise it is accepted, clamped, or rejected (§5); a
     rejection, timeout, transport error, or `None` uses rule direction in the same
     transition.
  4. One SQLite transaction writes: state, the `decision` audit row, goal and
     action events (ADR-0028); then SSE publishes them.
- The **heartbeat never calls a Director.** It keeps its existing duties (needs,
  observations, journal triggers) and two safety duties, both pure rule logic:
  - **critical interrupts** are executed by core immediately in the transition that
    detects them (§6), without waiting for any Director;
  - **overdue fallback**: if a decision has been due for longer than
    `decision_grace` [PROPOSED: 120 s] — e.g. the companion is hung — the heartbeat
    applies rule direction, so Maple's life never stalls on the AI.
- The AI call is never made while holding the writer lock, so Greet/Pet are never
  blocked by Director latency.

### 4. DecisionContext (built by core, frozen, serialisable)
Contains only plain values: Maple's name; local hour and day phase; needs; current
goal and suspended goal (type, summary, started/horizon); current action, phase
(walking/performing) and remaining time; pending signals with priorities; a
reduced server view (attention level, problem service ids — facts from
observations only); the allowed goal types; the allowed actions **at this moment**
(after hard rules) with their duration ranges; the last few decision verdicts.
Never DB handles, paths, config, sensor objects, raw observation rows, or journal
text. Size-bounded.

### 5. DecisionProposal and validation (`core.direction.validate_proposal`)
Proposal shape (parsed strictly by the runtime adapter; unknown keys reject):
- `goal`: one of `keep`; `new {type, summary, horizon_minutes}`; `complete`;
  `resume`; `abandon {reason_code}`.
- `action`: `{kind, duration_minutes}`.
- `reason`: one printable line, 1–240 characters (same structural rules as journal
  text). This is the only free text stored from the AI.

Validation, in order; the first failure rejects with a closed-enum reason code:
| Check | On failure |
|---|---|
| Shape, types, enums parse | reject `malformed` / `unknown_goal_type` / `unknown_action` |
| `summary` 1–120 chars, `reason` passes text rules | reject `text_invalid` (rejected text is not stored) |
| Goal operation legal in this state (e.g. `resume` needs a suspended, unexpired goal) | reject `goal_operation_invalid` |
| Action allowed by hard rules (energy ≤ 10 → only `sleep`; energy < 25 → only `sleep`/`rest`; a critical response in progress cannot be replaced) | reject `action_not_allowed` |
| A destination exists for the action (ADR-0027) | reject `no_destination` |
| `duration_minutes` numeric but outside the action's range | **clamp** to range, verdict `clamped`, original value recorded |
| `horizon_minutes` numeric but outside 30–120 | **clamp**, verdict `clamped`, original recorded |
| Non-numeric / non-finite duration or horizon | reject `malformed` |

Transport-level outcomes are recorded with codes `timeout`, `transport_error`,
`no_proposal`, `stale`. Every reject or transport failure falls back to rule
direction; the audit row records both the proposal (if any) and the fallback.

Goal type and action are **not** cross-validated: goal type is semantic intent only,
and no goal type implies a fixed action sequence.

### 6. Goals
- Goal types (v1, closed enum): `learn`, `create`, `recover`, `reflect`, `monitor`,
  `socialize`, `explore`, `organize`, `maintain`, `practice`, `plan`, `wait`
  (wait / anticipate), `play` (play / relax), `help`, `investigate`, `remember`.
- A goal has: id, type, summary, source (`rule`|`external`), originating decision
  id, `started_at`, `horizon_until` (30–120 min after start).
- At most one **active** and one **suspended** goal.
- A goal ends when: the Director's accepted `complete` → `goal_completed`; the
  horizon passes → `goal_completed` with reason `horizon_reached`; or it is
  abandoned with an explicit reason code (`expired`, `superseded`,
  `no_longer_relevant`, `director_abandoned`, `replaced_on_interrupt`).
- Rule direction creates goals from a small deterministic rule table [PROPOSED]
  (e.g. low energy → `recover`, server attention → `monitor`, high curiosity →
  `learn`, otherwise a seeded draw among `reflect`, `play`, `create`, `organize`).

### 7. Priority and interruption
Core classifies signals (`core.priority`) into four levels:

| Level | v1 sources | Effect |
|---|---|---|
| critical | newly observed serious server problem (a required service failed, or the existing server-problem trigger at its severe level) | Interrupts **immediately** in the detecting transition. Core chooses the response action (`observe_server`) by rule; no Director wait. |
| high | energy ≤ 10 (existing forced-sleep rule, unchanged); reserved for future owner messages (Paolo/Discord) | Interrupts the current action and makes a decision due now; the existing forced sleep is kept as the hard response. |
| normal | e.g. curiosity ≥ 75, mild social need | Never interrupts; offered to the next decision as a pending signal. |
| low | small mood/curiosity changes | Never interrupts; context only. |

- Greet and Pet are unchanged: reaction only, never an interruption, no new
  priority. Future real chat messages may be classified `high` by their own ADR.
- **On interrupt:** the action ends with `activity_interrupted`; the active goal
  becomes **suspended** (a previously suspended goal is abandoned as
  `superseded`). After the interrupting action completes, the next decision
  either **resumes** the suspended goal (allowed only before its horizon) or
  **abandons** it with an explicit reason. The Director may propose either; core
  enforces the horizon rule. Rule direction resumes if the horizon has not passed
  and the interrupting condition has cleared, otherwise abandons as `expired` /
  `no_longer_relevant`.

### 8. Audit, not chain-of-thought
Each decision transition writes exactly one `decision` row (schema in ADR-0028):
core-generated context summary, proposed goal/action/duration/horizon, the AI's
concise reason, verdict (`accepted`|`clamped`|`rejected`|`fallback`|`stale`),
reason code, clamped originals, the executed goal/action/destination, and
director kind/name/version. No prompt, no raw response, no model reasoning is
stored or logged.

### 9. Determinism
- Rule direction draws from `RngStream(life_seed, "decision", decision_counter)`;
  `decision_counter` persists with state (schema v4).
- An accepted external proposal is a stored input: replaying a decision uses the
  `decision` row, not the AI. Ticks remain reproducible from stored inputs + seed.
- `maplegotchi simulate` uses rule direction only, so it stays deterministic; its
  pinned digest is updated deliberately once in ADR-0028's change.

## Schema v4 and rollback

This ADR's persistent additions (`decision` table, goal tables/columns,
`decision_counter`) ship in the single schema-v4 migration defined in
**ADR-0028**, whose rollback/recovery strategy is normative for them: forward-only
migration, no down-migration code, a verified automatic pre-migration snapshot plus
the owner's `maple-db-snapshot` copy, one-transaction migration with in-transaction
verification, and owner-run restore of the v3 snapshot as the only path back to a
pre-v4 release (losing life lived since). Disabling the Director
(`MAPLE_DIRECTOR=rule`) is the first-line, zero-data-loss remedy for AI
misbehavior and needs no rollback.

## Consequences
- Behavior becomes Director-led but core-bounded; every outcome remains valid
  under core invariants.
- The heartbeat path is unchanged in cadence and never touches the network.
- The companion service needs a `/decide` endpoint and must be hardened before
  `MAPLE_DIRECTOR=antigravity` is enabled in production (as ADR-0025 requires).
- CLAUDE.md §3.4/§3.6, `docs/architecture.md`, and `docs/journal.md` must be
  updated with the implementation; import-linter contracts gain
  `maplegotchi.brain.director` (pure) and keep `runtime` as the only wiring place.
- Known, out of scope here: the journal Brain call still runs inside the writer
  lock with a 30 s timeout (ADR-0025 implementation); moving it out is a separate
  change.
