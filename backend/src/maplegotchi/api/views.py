"""Domain/runtime objects -> response models. Pure mapping; no rules live here."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from datetime import datetime

from maplegotchi.api.models import (
    ActivityOut,
    BrainOut,
    BubbleOut,
    DayOut,
    DecisionOut,
    DirectorOut,
    DocumentOut,
    DocumentSummaryOut,
    ExecutedOut,
    FreshnessOut,
    FurnitureOut,
    GoalIntentOut,
    GoalOut,
    IdentityOut,
    InteractionAvailabilityOut,
    InteractionOut,
    InteractionPointOut,
    JournalEntryOut,
    LifeEventOut,
    MapleOut,
    MemoryCandidateOut,
    MemoryOut,
    NeedsOut,
    ObservationOut,
    PathPointOut,
    PositionOut,
    ProposalOut,
    ReactionOut,
    ReflectionOut,
    RoomOut,
    RouteOut,
    ServerOut,
    ServiceHealthOut,
    SnapshotOut,
    StatusOut,
    TaskOut,
    TimelineEventOut,
)
from maplegotchi.core import presence
from maplegotchi.core import room as room_model
from maplegotchi.core.audit import DecisionRecord, Verdict
from maplegotchi.core.daily import DailyReflection
from maplegotchi.core.goals import Goal
from maplegotchi.core.interactions import Accepted, Rejected
from maplegotchi.core.memory import Memory
from maplegotchi.core.observations import Metric, ObservationSnapshot
from maplegotchi.core.proposal import DirectorLabel
from maplegotchi.core.room import Pose, Route
from maplegotchi.core.state import MapleState, Reaction
from maplegotchi.core.timeline import (
    ActivityChanged,
    Born,
    DowntimeGap,
    GoalAbandoned,
    GoalCompleted,
    GoalResumed,
    GoalStarted,
    GoalSuspended,
    InteractionAccepted,
)
from maplegotchi.runtime.life import LifeRecords
from maplegotchi.runtime.service import (
    SSE_KEEPALIVE_SECONDS,
    BrainLabel,
    InteractionResult,
    LiveSnapshot,
)
from maplegotchi.storage.audit_rows import StoredDecision
from maplegotchi.storage.repositories import StoredEvent, StoredJournalEntry, StoredObservation
from maplegotchi.storage.tool_rows import StoredDocument

TIMEZONE = "Asia/Bangkok"  # D16


def brain(label: BrainLabel) -> BrainOut:
    return BrainOut(kind=label.kind.value, name=label.name, version=label.version)


def director(label: DirectorLabel) -> BrainOut:
    return BrainOut(kind=label.kind, name=label.name, version=label.version)


def reaction(value: Reaction | None) -> ReactionOut | None:
    if value is None:
        return None
    return ReactionOut(
        kind=value.kind.value, variant=value.variant, started_at=value.started_at, until=value.until
    )


def needs(state: MapleState) -> NeedsOut:
    n = state.needs
    return NeedsOut(mood=n.mood, energy=n.energy, curiosity=n.curiosity, social=n.social)


def route(value: Route | None) -> RouteOut | None:
    if value is None:
        return None
    return RouteOut(
        departed_at=value.departed_at,
        arrives_at=value.arrives_at,
        from_activity=value.from_activity.value,
        path=[PathPointOut(x=p.x, y=p.y, distance=p.distance, node=p.node) for p in value.path],
    )


def activity(state: MapleState, now: datetime) -> ActivityOut:
    point = state.point
    walking = state.walking_at(now)
    x, y = state.position_at(now)
    return ActivityOut(
        kind=state.activity.value,
        location=state.location.value,
        started_at=state.activity_started_at,
        until=state.activity_until,
        phase="walking" if walking else "performing",
        point=point.id,
        furniture=point.furniture.value,
        pose=Pose.WALK.value if walking else point.pose.value,
        facing=point.facing.value,
        position=PositionOut(x=x, y=y),
        route=route(state.route),
        task=(
            TaskOut(
                tool=state.task.tool.value,
                target=state.task.target,
                title=state.task.title,
                category=state.task.category,
            )
            if state.task
            else None
        ),
    )


def memory(m: Memory) -> MemoryOut:
    if m.id is None:  # pragma: no cover - only stored memories are served
        raise ValueError("memory is not stored")
    return MemoryOut(
        id=m.id,
        kind=m.kind.value,
        tier=m.tier.value,
        status=m.status.value,
        text=m.text,
        key=m.key,
        source=m.source,
        importance=m.importance,
        evidence_days=[d.isoformat() for d in m.evidence_days],
        created_at=m.created_at,
        last_seen_at=m.last_seen_at,
    )


def reflection(r: DailyReflection) -> ReflectionOut:
    return ReflectionOut(
        day=r.day.isoformat(),
        created_at=r.created_at,
        recovered=r.recovered,
        summary=r.summary,
        learned=list(r.learned),
        moments=list(r.moments),
        memory_candidates=[
            MemoryCandidateOut(memory_id=c.memory_id, text=c.text, reason=c.reason)
            for c in r.memory_candidates
        ],
        promoted=list(r.promoted),
        preference_candidates=[list(p) for p in r.preference_candidates],
        intent=GoalIntentOut(type=r.intent_type.value, summary=r.intent_summary),
    )


def document_summary(doc: StoredDocument) -> DocumentSummaryOut:
    return DocumentSummaryOut(
        id=doc.id,
        kind=doc.kind.value,
        title=doc.title,
        created_at=doc.created_at,
        chars=len(doc.body),
        action_id=doc.action_id,
        goal_id=doc.goal_id,
    )


def document(doc: StoredDocument) -> DocumentOut:
    return DocumentOut(
        **document_summary(doc).model_dump(), body=doc.body, sources=list(doc.sources)
    )


def room() -> RoomOut:
    return RoomOut(
        width=room_model.ROOM_WIDTH,
        height=room_model.ROOM_HEIGHT,
        floor_y=room_model.FLOOR_Y,
        walk_speed=room_model.WALK_SPEED,
        furniture=[
            FurnitureOut(
                id=furniture.value,
                label=room_model.FURNITURE_LABEL[furniture],
                location=location.value,
            )
            for location, furniture in room_model.FURNITURE_AT.items()
        ],
        points=[
            InteractionPointOut(
                id=p.id,
                location=p.location.value,
                furniture=p.furniture.value,
                x=p.x,
                y=p.y,
                facing=p.facing.value,
                pose=p.pose.value,
                allowed_actions=[a.value for a in p.allowed_actions],
            )
            for p in room_model.POINTS
        ],
    )


def maple(snap: LiveSnapshot) -> MapleOut:
    state = snap.state
    return MapleOut(
        revision=snap.revision,
        generated_at=snap.now,
        identity=IdentityOut(
            name=state.identity.name,
            born_at=state.identity.born_at,
            age_seconds=state.age(snap.now).total_seconds(),
            ticks_lived=state.ticks_lived,
        ),
        needs=needs(state),
        activity=activity(state, snap.now),
        expression=snap.expression.value,
        reaction=reaction(snap.reaction),
        interactions=[
            InteractionAvailabilityOut(
                kind=a.kind.value,
                available=a.available,
                reason=a.reason.value if a.reason else None,
                retry_after_seconds=a.retry_after.total_seconds() if a.retry_after else None,
            )
            for a in snap.interactions
        ],
        goal=goal(state.goal),
        suspended_goal=goal(state.suspended_goal),
        action_priority=state.action_priority.value,
        bubble=_bubble(state, snap.now),
    )


def _bubble(state: MapleState, now: datetime) -> BubbleOut | None:
    found = presence.bubble(state, now)
    return BubbleOut(kind=found.kind.value, text=found.text) if found else None


def goal(value: Goal | None) -> GoalOut | None:
    if value is None:
        return None
    return GoalOut(
        id=value.id,
        type=value.type.value,
        summary=value.summary,
        source=value.source.value,
        started_at=value.started_at,
        horizon_until=value.horizon_until,
    )


def observation(stored: StoredObservation) -> ObservationOut:
    o = stored.observation
    return ObservationOut(
        id=stored.id,
        tick_id=stored.tick_id,
        metric=o.metric.value,
        subject=o.subject,
        status=o.status.value,
        value=o.value,
        state=o.state.value if o.state else None,
        unit=o.unit.value,
        source=o.source,
        reason=o.reason,
        observed_at=o.observed_at,
    )


def server(snap: LiveSnapshot) -> ServerOut:
    view = snap.server
    services = [s for s in view.observations if s.observation.metric is Metric.SERVICE_STATE]
    host = [s for s in view.observations if s.observation.metric is not Metric.SERVICE_STATE]
    return ServerOut(
        observed_at=view.observed_at,
        sensor_status=snap.freshness.sensor_status.value,
        summary=view.summary.value,
        attention_level=view.attention.level,
        attention_reasons=list(view.attention.reasons),
        counts=dict(Counter(s.observation.status.value for s in view.observations)),
        services=[
            ServiceHealthOut(
                service_id=s.observation.subject,
                status=s.observation.status.value,
                state=s.observation.state.value if s.observation.state else None,
                source=s.observation.source,
                reason=s.observation.reason,
                observed_at=s.observation.observed_at,
            )
            for s in services
        ],
        host=[observation(s) for s in host],
    )


def journal_entry(stored: StoredJournalEntry) -> JournalEntryOut:
    e = stored.entry
    return JournalEntryOut(
        id=stored.id,
        revision=stored.revision,
        tick_id=e.tick_id,
        created_at=e.created_at,
        category=e.category.value,
        trigger=e.trigger.value,
        topic=e.topic,
        text=e.text,
        importance=e.importance.value,
        brain=BrainOut(kind=e.brain_kind.value, name=e.brain_name, version=e.brain_version),
        activity=e.activity.value,
        expression=e.expression.value,
        observation_ids=list(stored.observation_ids),
    )


def timeline_event(stored: StoredEvent) -> TimelineEventOut:
    event = stored.event
    details: dict[str, str]
    if isinstance(event, Born):
        kind, at, details = "born", event.at, {"name": event.name}
    elif isinstance(event, ActivityChanged):
        kind, at = "activity_changed", event.at
        details = {"previous": event.previous.value, "current": event.current.value}
    elif isinstance(event, InteractionAccepted):
        kind, at = "interaction_accepted", event.at
        details = {"kind": event.kind.value, "reaction": event.reaction.value}
    elif isinstance(event, DowntimeGap):
        kind, at, details = "downtime_gap", event.until, {"since": event.since.isoformat()}
    elif isinstance(event, GoalStarted):
        goal = event.goal
        kind, at = "goal_started", event.at
        details = {
            "goal_id": str(goal.id),
            "goal_type": goal.type.value,
            "summary": goal.summary,
            "source": goal.source.value,
            "horizon_until": goal.horizon_until.isoformat(),
        }
    elif isinstance(event, GoalSuspended):
        kind, at = "goal_suspended", event.at
        details = {
            "goal_id": str(event.goal_id),
            "goal_type": event.goal_type.value,
            "cause": event.cause,
        }
    elif isinstance(event, GoalResumed):
        kind, at = "goal_resumed", event.at
        details = {"goal_id": str(event.goal_id), "goal_type": event.goal_type.value}
    elif isinstance(event, GoalCompleted | GoalAbandoned):
        kind = "goal_completed" if isinstance(event, GoalCompleted) else "goal_abandoned"
        at = event.at
        details = {
            "goal_id": str(event.goal_id),
            "goal_type": event.goal_type.value,
            "reason": event.reason.value,
        }
    else:  # pragma: no cover - the union is closed
        raise TypeError(f"unknown timeline event {event!r}")
    return TimelineEventOut(
        id=stored.id,
        revision=stored.revision,
        tick_id=stored.tick_id,
        kind=kind,
        at=at,
        details=details,
    )


def decision(stored: StoredDecision) -> DecisionOut:
    r = stored.record
    p = r.proposal
    x = r.executed
    return DecisionOut(
        id=stored.id,
        revision=stored.revision,
        at=r.at,
        trigger=r.trigger,
        priority=r.priority.value if r.priority else None,
        director=DirectorOut(
            kind=r.director_kind, name=r.director_name, version=r.director_version
        ),
        context_summary=r.context_summary,
        proposal=ProposalOut(
            goal_op=p.goal_op,
            goal_type=p.goal_type.value if p.goal_type else None,
            goal_summary=p.goal_summary,
            horizon_minutes=p.horizon_minutes,
            abandon_reason=p.abandon_reason.value if p.abandon_reason else None,
            action=p.action.value if p.action else None,
            duration_minutes=p.duration_minutes,
            reason=p.reason,
        )
        if p
        else None,
        verdict=r.verdict.value,
        reason_code=r.reason_code,
        clamped=dict(r.clamped),
        executed=ExecutedOut(
            by=x.by,
            reason=x.reason,
            goal_id=x.goal_id,
            action_id=x.action_id,
            action=x.action.value,
            point=x.point,
            duration_minutes=x.duration_minutes,
        )
        if x
        else None,
        latency_ms=r.latency_ms,
    )


def _decision_type(record: DecisionRecord) -> str:
    if record.verdict in (Verdict.REJECTED, Verdict.STALE):
        return "decision_rejected"
    if record.proposal is not None and record.proposal.goal_op == "new":
        return "goal_proposed"
    return "decision_made"


def life_events(records: LifeRecords) -> list[LifeEventOut]:
    """The three stores as one ordered envelope stream (ADR-0028 §2)."""
    keyed: list[tuple[tuple[int, int, int], LifeEventOut]] = []
    for d in records.decisions:
        r = d.record
        x = r.executed
        payload: dict[str, str | int | float | None] = {
            "verdict": r.verdict.value,
            "reason_code": r.reason_code,
            "trigger": r.trigger,
            "director": r.director_kind,
            "proposed_reason": r.proposal.reason if r.proposal else None,
            "executed_reason": x.reason if x else None,
            "action": x.action.value if x else None,
            "point": x.point if x else None,
        }
        keyed.append(
            (
                (d.revision, 0, d.id),
                LifeEventOut(
                    id=f"decision:{d.id}",
                    type=_decision_type(r),
                    at=r.at,
                    revision=d.revision,
                    goal_id=x.goal_id if x else None,
                    action_id=x.action_id if x else None,
                    priority=r.priority.value if r.priority else None,
                    payload=payload,
                ),
            )
        )
    for e in records.timeline:
        out = timeline_event(e)
        goal_id = out.details.get("goal_id")
        keyed.append(
            (
                (e.revision, 1, e.id),
                LifeEventOut(
                    id=f"timeline:{e.id}",
                    type=out.kind,
                    at=out.at,
                    revision=e.revision,
                    goal_id=int(goal_id) if goal_id is not None else None,
                    action_id=None,
                    priority=None,
                    payload=dict(out.details),
                ),
            )
        )
    for t in records.tools:
        tr = t.record
        keyed.append(
            (
                (t.revision, 3, t.id),
                LifeEventOut(
                    id=f"tool:{t.id}",
                    type=tr.op.value,
                    at=tr.at,
                    revision=t.revision,
                    goal_id=tr.goal_id,
                    action_id=tr.action_id,
                    priority=None,
                    payload={
                        "tool": tr.task.tool.value,
                        "target": tr.task.target,
                        "title": tr.task.title,
                        "category": tr.task.category,
                        "status": "success" if tr.success else "failure",
                        "detail": tr.detail,
                        "chars": tr.chars,
                        "document_id": t.document_id,
                    },
                ),
            )
        )
    for sr in records.reflections:
        day = sr.reflection
        keyed.append(
            (
                (sr.revision, 5, sr.id),
                LifeEventOut(
                    id=f"reflection:{sr.id}",
                    type="daily_reflection",
                    at=day.created_at,
                    revision=sr.revision,
                    goal_id=None,
                    action_id=None,
                    priority=None,
                    payload={
                        "day": day.day.isoformat(),
                        "recovered": int(day.recovered),
                        "summary": day.summary,
                        "intent_type": day.intent_type.value,
                        "intent_summary": day.intent_summary,
                        "promoted": len(day.promoted),
                    },
                ),
            )
        )
    for me in records.memory:
        keyed.append(
            (
                (me.revision, 4, me.id),
                LifeEventOut(
                    id=f"memory:{me.id}",
                    type=f"memory_{me.event.kind.value}",
                    at=me.event.at,
                    revision=me.revision,
                    goal_id=None,
                    action_id=None,
                    priority=None,
                    payload={
                        "memory_id": me.memory_id,
                        "kind": me.memory_kind.value,
                        "tier": me.tier.value,
                        "text": me.memory_text,
                        "detail": me.event.detail,
                    },
                ),
            )
        )
    for a in records.actions:
        ev = a.event
        keyed.append(
            (
                (a.revision, 2, a.id),
                LifeEventOut(
                    id=f"action:{a.id}",
                    type=ev.kind.value,
                    at=ev.at,
                    revision=a.revision,
                    goal_id=ev.goal_id,
                    action_id=ev.action_id,
                    priority=ev.priority.value if ev.priority else None,
                    payload=dict(ev.payload),
                ),
            )
        )
    return [out for _, out in sorted(keyed, key=lambda item: item[0])]


def freshness(snap: LiveSnapshot) -> FreshnessOut:
    f = snap.freshness
    return FreshnessOut(
        server_time=snap.now,
        last_heartbeat_at=f.last_heartbeat_at,
        next_heartbeat_due_at=f.next_heartbeat_due_at,
        heartbeat_interval_seconds=f.heartbeat_interval.total_seconds(),
        heartbeat_age_seconds=(snap.now - f.last_heartbeat_at).total_seconds(),
        heartbeat_status=f.heartbeat_status.value,
        life_loop_running=f.life_loop_running,
        life_loop_error=f.life_loop_error,
        sensor_status=f.sensor_status.value,
        observations_at=f.observations_at,
        sse_keepalive_seconds=SSE_KEEPALIVE_SECONDS,
    )


def snapshot(snap: LiveSnapshot) -> SnapshotOut:
    return SnapshotOut(
        revision=snap.revision,
        generated_at=snap.now,
        maple=maple(snap),
        day=DayOut(
            local_time=snap.local_time.replace(tzinfo=None).isoformat(timespec="seconds")
            + _offset(snap),
            local_hour=round(snap.local_hour, 4),
            phase=snap.day_phase.value,
            is_night=snap.is_night,
            timezone=TIMEZONE,
            utc_offset_minutes=int(snap.utc_offset.total_seconds() // 60),
        ),
        server=server(snap),
        journal=[journal_entry(e) for e in snap.journal],
        timeline=[timeline_event(e) for e in snap.timeline],
        freshness=freshness(snap),
        brain=brain(snap.brain),
        director=director(snap.director),
    )


def _offset(snap: LiveSnapshot) -> str:
    minutes = int(snap.utc_offset.total_seconds() // 60)
    sign = "+" if minutes >= 0 else "-"
    return f"{sign}{abs(minutes) // 60:02d}:{abs(minutes) % 60:02d}"


def status(snap: LiveSnapshot) -> StatusOut:
    return StatusOut(
        revision=snap.revision,
        freshness=freshness(snap),
        brain=brain(snap.brain),
        director=director(snap.director),
    )


def interaction(result: InteractionResult, kind: str) -> InteractionOut:
    outcome = result.outcome
    rejected = outcome if isinstance(outcome, Rejected) else None
    return InteractionOut(
        interaction=kind,
        accepted=isinstance(outcome, Accepted),
        reason=rejected.reason.value if rejected else None,
        retry_after_seconds=rejected.retry_after.total_seconds() if rejected else None,
        reaction=reaction(result.snapshot.reaction),
        revision=result.revision,
        maple=maple(result.snapshot),
    )


def _get[T](data: Mapping[str, object], key: str, kind: type[T]) -> T:
    value = data.get(key)
    if not isinstance(value, kind):
        raise TypeError(f"live event field {key!r} is not {kind.__name__}")
    return value


def live_event(kind: str, data: Mapping[str, object]) -> dict[str, object]:
    """JSON payload for a hub event (see docs/api.md, SSE contract)."""
    revision = data.get("revision")
    if kind == "heartbeat":
        state = _get(data, "state", MapleState)
        return {
            "revision": revision,
            "tick_id": data["tick_id"],
            "activity": state.activity.value,
            "location": state.location.value,
            "needs": needs(state).model_dump(),
            "last_heartbeat_at": state.last_tick_at.isoformat(),
        }
    if kind == "life":
        records = _get(data, "records", LifeRecords)
        return {
            "revision": revision,
            "events": [e.model_dump(mode="json") for e in life_events(records)],
        }
    if kind == "movement":
        state = _get(data, "state", MapleState)
        return {
            "revision": revision,
            "activity": state.activity.value,
            "location": state.location.value,
            "point": state.point.id,
        }
    if kind == "observations":
        snap = _get(data, "snapshot", ObservationSnapshot)
        return {
            "revision": revision,
            "observed_at": snap.observed_at.isoformat(),
            "counts": dict(Counter(o.status.value for o in snap.observations)),
        }
    if kind == "interaction":
        out = reaction(_get(data, "reaction", Reaction))
        return {
            "revision": revision,
            "kind": str(data["kind"]),
            "reaction": out.model_dump(mode="json") if out else None,
        }
    if kind == "journal":
        entries = _get(data, "entries", tuple)
        return {
            "revision": revision,
            "entries": [journal_entry(e).model_dump(mode="json") for e in entries],
        }
    if kind == "timeline":
        events = _get(data, "events", tuple)
        return {
            "revision": revision,
            "events": [timeline_event(e).model_dump(mode="json") for e in events],
        }
    raise ValueError(f"unknown live event kind {kind!r}")
