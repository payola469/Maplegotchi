# Brain companion contract (ADR-0025, ADR-0026)

Maplegotchi never runs a model, a provider CLI, or a shell. It talks to a
separate **Maple Brain companion** over loopback HTTP (`MAPLE_BRAIN_URL`,
default `http://127.0.0.1:8471`). The companion owns provider execution and its
own security boundary: `companion/brain` and `deploy/brain/` (ADR-0033).

Both endpoints are advisory: whatever comes back is parsed and validated by core
and may be ignored. A failing, slow, or misbehaving companion never stops Maple.

## `POST /generate` — journal wording (ADR-0025)

Request: `{"prompt": "<text built by ExternalHttpBrain>"}`
Response: `{"response": "<text>"}` whose text is a JSON array of
`{"trigger_index": int, "text": str, "importance": "low|normal|high",
"template_id": str}`. Drafts are validated by `core.journal.accept_drafts`.

## `POST /decide` — goal and next action (`maple.decision.v1`, ADR-0026)

Used only when `MAPLE_DIRECTOR=antigravity`. Timeout: `MAPLE_DIRECTOR_TIMEOUT_SECONDS`
(default 15, allowed 1–30), enforced as a hard deadline by the service.

Request (built by `core/proposal.py:build_context`; no seed, paths, config,
journal text, or raw observation rows):

```jsonc
{"contract": "maple.decision.v1",
 "context": {
   "contract": "maple.decision.v1",
   "maple": {"name": "Maple"},
   "time": {"now": "…Z", "local_hour": 14.08, "day_phase": "afternoon"},
   "trigger": "action_completed|re_evaluate|no_plan|overdue|critical",
   "needs": {"mood": 64.0, "energy": 71.2, "curiosity": 58.3, "social": 47.0},
   "current": {"activity": "read", "walking": false, "point": "bookshelf.front",
               "furniture": "bookshelf", "minutes_remaining": 0, "priority": "normal"},
   "goal": {"id": 3, "type": "learn", "summary": "…", "minutes_left": 40} | null,
   "suspended_goal": {"id": 2, "type": "create", "summary": "…", "minutes_left": 12,
                      "interrupted_activity": "write"} | null,
   "must_resolve_suspended_goal": false,
   "signals": [{"kind": "curious", "priority": "normal"}],
   "server": {"attention": 0.0, "reasons": []},
   "allowed": {"goal_ops": ["keep", "new", "complete", "resume", "abandon"],
               "goal_types": ["learn", "…16 types"],
               "horizon_minutes": [30, 120],
               "actions": [{"kind": "read", "min_minutes": 20, "max_minutes": 60,
                            "furniture": "bookshelf"}, …],   // after core's hard rules
               "end_reasons": ["director_abandoned", "no_longer_relevant", "superseded", "expired"]},
   "intent": {"type": "create", "summary": "Write about what I read"} | null,  // yesterday's reflection
   "memories": [{"kind": "reading", "tier": "short_term", "text": "I read Maple's room: …"}],  // ≤ 5
   "recent_decisions": [{"at": "…Z", "verdict": "accepted", "action": "write", "by": "rule"}]}}
```

Response (exactly these keys; anything else is refused):

```jsonc
{"contract": "maple.decision.v1",
 "proposal": {
   "goal":   {"op": "keep"}
           | {"op": "new", "type": "<goal type>", "summary": "<1-120 chars, one line>",
              "horizon_minutes": 30..120}
           | {"op": "complete"} | {"op": "resume"}
           | {"op": "abandon", "end_reason": "<optional end reason>"},
   "action": {"kind": "<activity>", "duration_minutes": <number>,
              "target": "<optional: a read_sources id for read, a write_kinds value for write>"},
   "reason": "<one concise line, 1-240 chars>"} | null}
```

Core's handling (`core/proposal.py`):

| Case | Verdict | What happens |
|---|---|---|
| valid and legal now | `accepted` | executed as proposed (source `external`) |
| duration/horizon within ×0.5–×2 of its range | `clamped` | executed with the clamped value; the original is recorded |
| further out of range | `rejected` (`duration_out_of_range`) | rule direction |
| unknown keys/enums, wrong types, multi-line text | `rejected` (`malformed`, `unknown_action`, `unknown_goal_type`, `text_invalid`) | rule direction |
| illegal now (e.g. `keep` without a goal, action forbidden by low energy) | `rejected` (`goal_operation_invalid`, `action_not_allowed`) | rule direction |
| `target` not in the approved catalog / not a document kind | `rejected` (`unknown_target`) | rule direction |
| timeout, HTTP/transport error, wrong contract, oversized, `null` | `fallback` (`timeout`, `transport_error`, `no_proposal`) | rule direction |
| answer arrives after the decision stopped being due | `stale` | recorded, nothing executed |

## `POST /reply` — conversation replies (`maple.reply.v1`, ADR-0032)

Used only when `MAPLE_REPLIER=antigravity`. Request: `{"contract": "maple.reply.v1",
"context": {...}}` with `maple`, `local_hour`, `activity`, `walking`, `task`, `goal`,
`priority`, `expression`, `needs`, `server`, `memories` (≤ 5), `conversation` (≤ 6 recent
turns), and `message` (`text`, `language`: `en|th`). Response: exactly
`{"contract": "maple.reply.v1", "reply": "<1-1500 printable chars>"}`. Anything else,
a timeout, or an error → Maple's rule reply (recorded with a fallback code). The reply
must use only facts from the context.

Only the `reason` line is stored as text from the companion. The companion must
not return or log hidden reasoning; Maplegotchi would not store it anyway.
