"""Explicit response models. The API returns these, never rows or domain objects."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


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
    brain: BrainOut


class StatusOut(_Out):
    revision: int
    freshness: FreshnessOut
    brain: BrainOut


class InteractionOut(_Out):
    interaction: str
    accepted: bool
    reason: str | None  # cooldown | rate_limit when rejected
    retry_after_seconds: float | None
    reaction: ReactionOut | None  # the reaction showing now
    revision: int  # this interaction's own committed revision (current revision if rejected)
    maple: MapleOut  # state read after the commit; maple.revision >= revision


class HealthOut(_Out):
    status: str


class ErrorOut(_Out):
    detail: str
