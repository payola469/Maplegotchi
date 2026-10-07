"""Explicit response models. The API returns these, never rows or domain objects."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _Out(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class BrainOut(_Out):
    kind: str
    name: str
    version: str


class IdentityOut(_Out):
    name: str
    born_at: datetime
    age_seconds: float
    ticks_lived: int


class NeedsOut(_Out):
    mood: float
    energy: float
    curiosity: float
    social: float


class PositionOut(_Out):
    x: float
    y: float


class PathPointOut(_Out):
    x: float
    y: float
    distance: float
    node: str | None


class RouteOut(_Out):
    departed_at: datetime
    arrives_at: datetime  # the activity begins here
    from_activity: str  # what Maple was doing before setting off
    path: list[PathPointOut]


class TaskOut(_Out):
    tool: str  # reader | writer
    target: str  # catalog id (reader) or workspace:<kind> (writer)
    title: str
    category: str


class ActivityOut(_Out):
    kind: str
    location: str
    started_at: datetime  # while walking: the planned start, i.e. arrival
    until: datetime
    # Additive (ADR-0027): movement is backend truth; the UI only renders it.
    phase: str  # walking | performing
    point: str  # interaction point id
    furniture: str
    pose: str  # the point's pose; "walk" while walking
    facing: str
    position: PositionOut  # at generated_at
    route: RouteOut | None
    task: TaskOut | None  # what is being read/written (ADR-0029); null for other actions


class InteractionPointOut(_Out):
    id: str
    location: str
    furniture: str
    x: float
    y: float
    facing: str
    pose: str
    allowed_actions: list[str]


class FurnitureOut(_Out):
    id: str
    label: str
    location: str


class RoomOut(_Out):
    width: int
    height: int
    floor_y: int
    walk_speed: float  # logical units per second
    furniture: list[FurnitureOut]
    points: list[InteractionPointOut]


class ReactionOut(_Out):
    kind: str
    variant: int
    started_at: datetime
    until: datetime


class BubbleOut(_Out):
    # needs_attention | thinking | reading | writing | waiting_for_paolo | approval_required
    kind: str
    text: str


class GoalOut(_Out):
    id: int
    type: str  # one of the 16 goal types (ADR-0026 §6)
    summary: str
    source: str  # rule | external
    started_at: datetime
    horizon_until: datetime


class InteractionAvailabilityOut(_Out):
    kind: str
    available: bool
    reason: str | None
    retry_after_seconds: float | None


class MapleOut(_Out):
    revision: int
    generated_at: datetime
    identity: IdentityOut
    needs: NeedsOut
    activity: ActivityOut
    expression: str  # at generated_at
    reaction: ReactionOut | None  # active at generated_at, else null
    interactions: list[InteractionAvailabilityOut]
    # Additive (ADR-0026): Maple's short-term goal and how the current action began.
    goal: GoalOut | None
    suspended_goal: GoalOut | None  # paused by an interruption
    action_priority: str  # critical | high | normal | low
    bubble: BubbleOut | None  # what the speech bubble says, from real state (A8)


class DayOut(_Out):
    local_time: str  # ISO-8601 with the Asia/Bangkok offset
    local_hour: float
    phase: str
    is_night: bool
    timezone: str
    utc_offset_minutes: int


class ObservationOut(_Out):
    id: int
    tick_id: int
    metric: str
    subject: str
    status: str
    value: float | None
    state: str | None
    unit: str
    source: str
    reason: str | None
    observed_at: datetime


class ServiceHealthOut(_Out):
    service_id: str
    status: str
    state: str | None
    source: str
    reason: str | None
    observed_at: datetime


class ServerOut(_Out):
    observed_at: datetime | None
    sensor_status: str  # fresh | stale | none
    summary: str  # calm | unclear | troubled_earlier | still_troubled | no_data
    attention_level: float
    attention_reasons: list[str]
    counts: dict[str, int]  # by observation status
    services: list[ServiceHealthOut]
    host: list[ObservationOut]


class JournalEntryOut(_Out):
    id: int
    revision: int
    tick_id: int | None
    created_at: datetime
    category: str
    trigger: str
    topic: str
    text: str
    importance: str
    brain: BrainOut
    activity: str
    expression: str
    observation_ids: list[int]


class TimelineEventOut(_Out):
    id: int
    revision: int
    tick_id: int | None
    kind: str
    at: datetime
    details: dict[str, str]


class FreshnessOut(_Out):
    server_time: datetime
    last_heartbeat_at: datetime
    next_heartbeat_due_at: datetime
    heartbeat_interval_seconds: float
    heartbeat_age_seconds: float
    heartbeat_status: str  # fresh | overdue
    life_loop_running: bool
    life_loop_error: str | None
    sensor_status: str  # fresh | stale | none
    observations_at: datetime | None
    sse_keepalive_seconds: int


class SnapshotOut(_Out):
    revision: int
    generated_at: datetime
    maple: MapleOut
    day: DayOut
    server: ServerOut
    journal: list[JournalEntryOut]
    timeline: list[TimelineEventOut]
    freshness: FreshnessOut
    brain: BrainOut  # who words the journal
    director: BrainOut  # who proposes goals and actions (additive, ADR-0026)


class StatusOut(_Out):
    revision: int
    freshness: FreshnessOut
    brain: BrainOut
    director: BrainOut


class InteractionOut(_Out):
    interaction: str
    accepted: bool
    reason: str | None  # cooldown | rate_limit when rejected
    retry_after_seconds: float | None
    reaction: ReactionOut | None  # the reaction showing now
    revision: int  # this interaction's own committed revision (current revision if rejected)
    maple: MapleOut  # state read after the commit; maple.revision >= revision


class DirectorOut(_Out):
    kind: str  # rule | external
    name: str
    version: str


class ProposalOut(_Out):
    goal_op: str | None
    goal_type: str | None
    goal_summary: str | None
    horizon_minutes: float | None
    abandon_reason: str | None
    action: str | None
    duration_minutes: float | None
    reason: str | None  # the proposer's concise, validated reason (never model reasoning)


class ExecutedOut(_Out):
    by: str  # rule | external
    reason: str
    goal_id: int | None
    action_id: int
    action: str
    point: str
    duration_minutes: int


class DecisionOut(_Out):
    """One decision transition's audit (ADR-0026 §8)."""

    id: int
    revision: int
    at: datetime
    trigger: str
    priority: str | None
    director: DirectorOut
    context_summary: str  # written by core, not by a Director
    proposal: ProposalOut | None
    verdict: str  # accepted | clamped | rejected | fallback | stale
    reason_code: str | None
    clamped: dict[str, float]  # field -> the original, out-of-range value
    executed: ExecutedOut | None
    latency_ms: int | None


class LifeEventOut(_Out):
    """One envelope for every life event, for Web, iOS and Discord (ADR-0028 §2)."""

    id: str  # "<store>:<id>": timeline|action|decision|tool|memory|reflection|conversation
    type: str  # e.g. goal_started, walking_started, arrived, decision_rejected
    at: datetime
    revision: int
    goal_id: int | None
    action_id: int | None
    priority: str | None
    payload: dict[str, str | int | float | None]


class LifeEventsOut(_Out):
    events: list[LifeEventOut]  # by revision, then decision -> timeline -> action -> tool
    last_revision: int  # pass back as `after_revision` to continue


class DocumentSummaryOut(_Out):
    id: int
    kind: str  # note | summary | reflection | research
    title: str
    created_at: datetime
    chars: int
    action_id: int
    goal_id: int | None


class DocumentOut(DocumentSummaryOut):
    body: str
    sources: list[str]  # catalog ids it drew on


class MemoryOut(_Out):
    id: int
    kind: str
    tier: str  # short_term | long_term | archive
    status: str  # active, or candidate | accepted | rejected for preferences
    text: str
    key: str | None
    source: str | None
    importance: float
    evidence_days: list[str]
    created_at: datetime
    last_seen_at: datetime


class MemoryCandidateOut(_Out):
    memory_id: int
    text: str
    reason: str


class ReflectionOut(_Out):
    """One Daily Reflection (ADR-0031)."""

    day: str  # the Maple day (local 06:00 to 06:00)
    created_at: datetime
    recovered: bool  # written late, after a restart/failure/oversleep
    summary: str
    learned: list[str]
    moments: list[str]
    memory_candidates: list[MemoryCandidateOut]
    promoted: list[int]  # at most one memory id
    preference_candidates: list[list[str]]  # [key, text]
    intent: GoalIntentOut


class GoalIntentOut(_Out):
    type: str
    summary: str


class ConversationIn(BaseModel):
    """A message from Paolo, relayed by the local gateway (ADR-0032)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    message_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    channel: Literal["discord"]
    speaker: Literal["paolo"]
    text: str = Field(min_length=1, max_length=2000)


class ConversationOut(_Out):
    reply: str
    revision: int
    duplicate: bool
    replier: dict[str, str]  # {"kind": "rule|external", "name": ...}
    fallback_code: str | None
    activity: str
    goal: str | None


class ConversationMessageOut(_Out):
    id: int
    at: datetime
    channel: str
    speaker: str  # paolo | maple
    text: str
    reply_to: int | None
    replier: str | None
    fallback_code: str | None


class HealthOut(_Out):
    status: str


class AiCallOut(_Out):
    at: datetime
    ok: bool  # a usable answer (decision accepted/clamped; reply not a fallback)
    code: str | None  # decision reason_code or reply fallback_code
    latency_ms: int | None


class CallerHealthOut(_Out):
    mode: str  # rule | external
    name: str
    last_call: AiCallOut | None  # latest external call (stale decisions excluded)
    last_success_at: datetime | None
    fallbacks_today: int
    timeouts_today: int  # timeouts or transport errors


class CompanionOut(_Out):
    probed: bool  # false when no external mode is configured
    reachable: bool | None
    error: str | None  # timeout | unreachable | http_status | invalid_response


class BrainDayOut(_Out):
    day: str  # the Maple day (local 06:00 to 06:00), YYYY-MM-DD
    start: datetime
    end: datetime


class BrainHealthOut(_Out):
    """Read-only Brain Health (ADR-0034). Unknown values are null, never guessed."""

    as_of: datetime
    status: str  # healthy | degraded | offline | unknown
    status_reason: str
    provider: str | None
    model: str | None
    companion: CompanionOut
    journal_brain: str  # rule | external
    director: CallerHealthOut
    replier: CallerHealthOut
    last_success_at: datetime | None
    today: BrainDayOut


class ErrorOut(_Out):
    detail: str
