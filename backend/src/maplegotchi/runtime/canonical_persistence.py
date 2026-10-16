"""Explicit isolated canonical persistence lifecycle, never default MapleService.

This owns one canonical snapshot and serialized persistence operations. It is
not a default heartbeat/Director engine and never constructs MapleState.
Proposals come from an authorized caller; D01 preflights compatibility
without installing them. The explicit step method supplies an isolated canonical life loop.
Checkpoint is a Save intent, not simulation advancement. Restore
accepts canonical Travel independently of Legacy presentation availability.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import replace
from datetime import datetime
from threading import RLock

from maplegotchi.core.activities import Activity
from maplegotchi.core.audit import ActionEventKind
from maplegotchi.core.behavior import BehaviorInputs
from maplegotchi.core.daytime import require_utc
from maplegotchi.core.parameters import GLOBAL_INTERACTION_WINDOW, CoreParameters
from maplegotchi.core.state import prune_interactions
from maplegotchi.core.tasks import LIBRARY_CATALOG, SourceRef, Tool, ToolOp, ToolRecord
from maplegotchi.core.timeline import GoalStarted
from maplegotchi.core.world.canonical_lifecycle import LifeFrame, LifeLoopBlocked, LifeStep
from maplegotchi.core.world.canonical_lifecycle import step as life_step
from maplegotchi.core.world.coordinates import Tile
from maplegotchi.core.world.legacy_projection import (
    DevelopmentWorld,
    LegacyProjection,
    PointRef,
    Presentation,
    project_point,
)
from maplegotchi.core.world.movement import EdgeStart
from maplegotchi.core.world.resolution import PointKey, ResolutionSnapshot
from maplegotchi.persistence.boundary import capture_life
from maplegotchi.persistence.legacy_admission import CompatibilityRefusal, project_eligible
from maplegotchi.persistence.life_record import CanonicalLife, Cell, life_fields
from maplegotchi.persistence.revision_snapshot import LifeReference
from maplegotchi.persistence.travel_codec import encode_travel_path
from maplegotchi.runtime.lifecycle import CallGate, RuntimeClosedError, admitted
from maplegotchi.storage.canonical_v11 import (
    CanonicalSnapshot,
    LifecyclePort,
    PersistenceError,
    load,
    save,
)
from maplegotchi.storage.repositories import encode_event


def checkpoint_image(snapshot: CanonicalSnapshot) -> CanonicalSnapshot:
    """Complete exact image for an explicit Save; only life revision increments.

    No tick, needs evolution, RNG draw, pruning, arrival or history is fabricated.
    Existing unprojectable Travel remains intact. Binding validates all facts.
    """
    life = capture_life(
        replace(
            snapshot.life,
            record=replace(snapshot.life.record, revision=snapshot.life.record.revision + 1),
        )
    )
    values = dict(life_fields(life.record))
    tables = tuple(
        (name, columns, (tuple(values[column] for column in columns),))
        if name == "life_state"
        else (name, columns, rows)
        for name, columns, rows in snapshot.tables
    )
    return CanonicalSnapshot(life, tables, snapshot.sequences)


def _presentation(life: CanonicalLife, facts: Presentation) -> None:
    r = life.record
    if (
        facts.activity != life.activity
        or facts.started_at != datetime.fromisoformat(r.activity_started_at)
        or facts.until != datetime.fromisoformat(r.activity_until)
        or facts.needs != life.needs
        or facts.reaction != life.reaction
        or facts.goal != life.active_goal
        or facts.task != life.task
    ):
        raise CompatibilityRefusal("presentation")


def _project(
    life: CanonicalLife, facts: Presentation, now: datetime, origin: PointRef | None
) -> LegacyProjection:
    _presentation(life, facts)
    document = life.layout.active.layout
    return project_eligible(
        DevelopmentWorld(document.world, document.catalog),
        PointRef(life.record.point_host, life.record.point_id),
        facts,
        now,
        travel=life.travel,
        origin=origin,
        from_activity=Activity(life.record.route_from_activity)
        if life.record.route_from_activity
        else None,
    )


def _transition(
    before: CanonicalLife, after: CanonicalLife, now: datetime, origin: PointRef | None
) -> None:
    """Continuity gate only; does not invent an activity/heartbeat algorithm."""
    require_utc(now)
    if (
        before.identity_row != after.identity_row
        or before.layout.revisions != after.layout.revisions
        or before.layout.active_revision != after.layout.active_revision
        or now < datetime.fromisoformat(before.record.last_updated_at)
        or now != datetime.fromisoformat(after.record.last_updated_at)
    ):
        raise CompatibilityRefusal("continuity")
    current: Tile | EdgeStart = Tile(before.record.tx, before.record.ty)
    if before.travel is not None:
        if now < before.travel.departed_at:
            raise CompatibilityRefusal("pending")
        if now >= before.travel.arrives_at:
            # Existing settle_movement requires MapleState and arrival audit.
            # Do not invent an alternative grid settle/event policy here.
            raise CompatibilityRefusal("unsettled")
        current = before.travel.current_at(now)
        if isinstance(current, EdgeStart):
            raise CompatibilityRefusal("mid_edge")
    if after.travel is None:
        if current != Tile(after.record.tx, after.record.ty):
            raise CompatibilityRefusal("continuity")
        # A genuine zero walk must not jump between different Legacy anchors.
        # Use the same accepted mapping; never invent a zero-duration route.
        document = after.layout.active.layout
        context = DevelopmentWorld(document.world, document.catalog)
        try:
            start = project_point(
                context, PointRef(before.record.point_host, before.record.point_id), before.activity
            )
            end = project_point(
                context, PointRef(after.record.point_host, after.record.point_id), after.activity
            )
            if start.id != end.id:
                raise CompatibilityRefusal("projection")
        except ValueError:
            raise CompatibilityRefusal("projection") from None
    elif after.travel.departed_at != now or after.travel.route.origin != current:
        raise CompatibilityRefusal("continuity")
    if (
        before.travel is None
        and after.travel is not None
        and origin != PointRef(before.record.point_host, before.record.point_id)
    ):
        raise CompatibilityRefusal("continuity")
    performed = (
        Activity(before.record.route_from_activity)
        if before.record.route_from_activity is not None and before.travel is not None
        else before.activity
    )
    if after.travel is not None and after.record.route_from_activity != performed.value:
        raise CompatibilityRefusal("continuity")


def _frame(life: CanonicalLife) -> LifeFrame:
    r = life.record
    return LifeFrame(
        life.needs,
        life.activity,
        datetime.fromisoformat(r.activity_started_at),
        datetime.fromisoformat(r.activity_until),
        datetime.fromisoformat(r.last_tick_at),
        datetime.fromisoformat(r.last_updated_at),
        datetime.fromisoformat(r.needs_at or r.last_tick_at),
        life.rng,
        r.action_counter,
        PointKey(r.point_host, r.point_id),
        Tile(r.tx, r.ty),
        life.travel,
        Activity(r.route_from_activity) if r.route_from_activity else None,
        life.priority,
        datetime.fromisoformat(r.critical_since) if r.critical_since else None,
        life.active_goal,
        life.suspended_goal,
        life.suspended_action,
        r.goal_counter,
        life.task,
    )


def _life_after(before: CanonicalLife, outcome: LifeStep, decision_id: int | None) -> CanonicalLife:
    f, old = outcome.frame, before.record
    document = before.layout.active.layout
    mask = DevelopmentWorld(document.world, document.catalog).mask
    reaction = before.reaction
    if reaction is not None and not reaction.is_active(f.updated_at):
        reaction = None
    ledger = tuple(
        row
        for row in before.ledger_rows
        if f.updated_at - datetime.fromisoformat(row[3]) < GLOBAL_INTERACTION_WINDOW
    )
    new_goals = tuple(event.goal for event in outcome.events if isinstance(event, GoalStarted))
    goal_rows = (
        *before.goal_rows,
        *(
            (
                g.id,
                old.maple_id,
                old.revision + 1,
                g.type.value,
                g.summary,
                g.source.value,
                decision_id,
                g.started_at.isoformat(),
                g.horizon_until.isoformat(),
            )
            for g in new_goals
        ),
    )
    record = replace(
        old,
        revision=old.revision + 1,
        mood=f.needs.mood,
        energy=f.needs.energy,
        curiosity=f.needs.curiosity,
        social=f.needs.social,
        activity=f.activity.value,
        activity_started_at=f.started_at.isoformat(),
        activity_until=f.until.isoformat(),
        last_tick_at=f.last_tick.isoformat(),
        last_updated_at=f.updated_at.isoformat(),
        needs_at=None,
        tick_counter=f.rng.tick_counter,
        decision_counter=f.rng.decision_counter,
        action_counter=f.action_id,
        action_priority=f.priority.value,
        critical_since=f.critical_since.isoformat() if f.critical_since else None,
        goal_counter=f.goal_counter,
        active_goal_id=f.goal.id if f.goal else None,
        suspended_goal_id=f.suspended_goal.id if f.suspended_goal else None,
        suspended_action=f.suspended_action.value if f.suspended_action else None,
        task_tool=f.task.tool.value if f.task else None,
        task_target=f.task.target if f.task else None,
        task_title=f.task.title if f.task else None,
        task_category=f.task.category if f.task else None,
        point_host=f.point.instance_id,
        point_id=f.point.point_id,
        tx=f.tile.tx,
        ty=f.tile.ty,
        route_path=encode_travel_path(f.travel, walkability=mask) if f.travel else None,
        route_departed_at=f.travel.departed_at.isoformat() if f.travel else None,
        route_arrives_at=f.travel.arrives_at.isoformat() if f.travel else None,
        route_from_activity=f.from_activity.value if f.from_activity else None,
        reaction_kind=reaction.kind.value if reaction else None,
        reaction_variant=reaction.variant if reaction else None,
        reaction_started_at=reaction.started_at.isoformat() if reaction else None,
        reaction_until=reaction.until.isoformat() if reaction else None,
    )
    return capture_life(
        replace(
            before,
            record=record,
            needs=f.needs,
            rng=f.rng,
            activity=f.activity,
            priority=f.priority,
            active_goal=f.goal,
            suspended_goal=f.suspended_goal,
            suspended_action=f.suspended_action,
            task=f.task,
            goal_rows=goal_rows,
            goals=(*before.goals, *new_goals),
            decisions=(*before.decisions, (decision_id, old.maple_id, record.revision))
            if decision_id is not None
            else before.decisions,
            travel=f.travel,
            reaction=reaction,
            ledger_rows=ledger,
            recent_interactions=prune_interactions(before.recent_interactions, f.updated_at),
            layout=replace(
                before.layout,
                life_reference=LifeReference(
                    old.maple_id, old.layout_revision, f.point.instance_id, f.point.point_id
                ),
            ),
        )
    )


def _step_image(before: CanonicalSnapshot, outcome: LifeStep) -> CanonicalSnapshot:
    """Append only existing v10 audit vocabulary. No world_event payload activation."""
    decision_id = (
        dict(before.sequences).get("decision", 0) + 1
        if outcome.minutes is not None and outcome.interruption is None
        else None
    )
    life = _life_after(before.life, outcome, decision_id)
    r, f = life.record, outcome.frame
    values = dict(life_fields(r))
    images = {name: (columns, rows) for name, columns, rows in before.tables}
    seq = dict(before.sequences)

    def append(name: str, fields: dict[str, Cell]) -> int:
        columns, rows = images[name]
        row_id = seq.get(name, 0) + 1
        seq[name] = row_id
        row: dict[str, Cell] = {column: None for column in columns}
        row.update(id=row_id, maple_id=r.maple_id, revision=r.revision)
        row.update(fields)
        images[name] = columns, (*rows, tuple(row[column] for column in columns))
        return row_id

    def wire(fields: dict[str, Cell]) -> str:
        return json.dumps(fields, sort_keys=True, separators=(",", ":"), allow_nan=False)

    document = life.layout.active.layout
    world = DevelopmentWorld(document.world, document.catalog)
    point = project_point(world, PointRef(r.point_host, r.point_id), life.activity)
    old_point = project_point(
        world,
        PointRef(before.life.record.point_host, before.life.record.point_id),
        before.life.activity,
    )
    for event in outcome.actions:
        # A late tick can arrive/start the old action and select/interrupt into a
        # new one together. Audit facts belong to the event's action, not the final frame.
        old_action = event.action_id == before.life.record.action_counter
        target = old_point if old_action else point
        payload: dict[str, Cell] = {"point": target.id, "furniture": target.furniture.value}
        if event.payload:
            payload = dict(event.payload)
        elif event.kind is ActionEventKind.DESTINATION_SELECTED:
            payload.update(
                activity=f.activity.value,
                duration_minutes=float(outcome.minutes) if outcome.minutes is not None else None,
            )
        elif event.kind is ActionEventKind.ACTIVITY_STARTED:
            payload.update(activity=before.life.activity.value if old_action else f.activity.value)
        elif event.kind is ActionEventKind.WALKING_STARTED:
            # Legacy audit distance remains Legacy geometry, not a grid-step alias.
            from maplegotchi.core.room import shortest_path

            _, distance = shortest_path(old_point.id, point.id)
            payload.update(arrives_at=f.started_at.isoformat(), distance=distance)
        elif event.kind is ActionEventKind.ACTIVITY_COMPLETED:
            payload = {"activity": before.life.activity.value}
        append(
            "action_event",
            dict(
                action_id=event.action_id,
                goal_id=event.goal_id,
                priority=event.priority.value if event.priority else None,
                kind=event.kind.value,
                at=event.at.isoformat(),
                payload=wire(payload),
            ),
        )
    for timeline_event in outcome.events:
        kind, at, payload_text = encode_event(timeline_event)
        append(
            "timeline_event",
            dict(
                kind=kind,
                at=at,
                payload=payload_text,
                tick_id=f.rng.tick_counter if kind == "downtime_gap" else None,
            ),
        )
    if decision_id is not None:
        if outcome.minutes is None:
            raise PersistenceError("invalid")
        actual_id = append(
            "decision",
            dict(
                at=f.updated_at.isoformat(),
                trigger="action_completed",
                director_kind="rule",
                director_name="canonical-mvp",
                director_version="1",
                context_summary="synthetic ordinary basic activity profile",
                proposed_goal_op=outcome.goal_op,
                proposed_goal_type=f.goal.type.value
                if outcome.goal_op == "new" and f.goal
                else None,
                proposed_goal_summary=f.goal.summary
                if outcome.goal_op == "new" and f.goal
                else None,
                proposed_horizon_minutes=(f.goal.horizon_until - f.goal.started_at).total_seconds()
                / 60
                if outcome.goal_op == "new" and f.goal
                else None,
                proposed_action=f.activity.value,
                proposed_duration_minutes=float(outcome.minutes),
                proposed_reason="MVP ordinary selection",
                verdict="accepted",
                executed_by="rule",
                executed_reason="MVP ordinary selection",
                goal_id=f.goal.id if f.goal else None,
                action_id=f.action_id,
                executed_action=f.activity.value,
                executed_point=point.id,
                executed_duration_minutes=outcome.minutes,
            ),
        )
        if actual_id != decision_id:
            raise PersistenceError("invalid")
    images["goal"] = images["goal"][0], life.goal_rows
    images["life_state"] = (
        images["life_state"][0],
        (tuple(values[c] for c in images["life_state"][0]),),
    )
    images["interaction_ledger"] = images["interaction_ledger"][0], life.ledger_rows
    return CanonicalSnapshot(
        life,
        tuple((name, *images[name]) for name, _, _ in before.tables),
        tuple(sorted(seq.items())),
    )


TaskEffects = Callable[[CanonicalSnapshot, CanonicalLife, datetime], tuple[ToolRecord, ...]]


def _task_records(
    before: CanonicalLife,
    after: CanonicalLife,
    now: datetime,
    records: tuple[ToolRecord, ...],
) -> tuple[ToolRecord, ...]:
    """Fail closed on missing/duplicate/foreign provenance from a task capability."""
    expected = [(before, False), (after, True)]
    expected = [(life, starting) for life, starting in expected if life.task is not None]
    if type(records) is not tuple or len(records) != len(expected):
        raise PersistenceError("invalid")
    for record, (life, starting) in zip(records, expected, strict=True):
        task = life.task
        if task is None or type(record) is not ToolRecord:
            raise PersistenceError("invalid")
        until = datetime.fromisoformat(life.record.activity_until)
        complete = now >= until
        at = now if starting or not complete else until
        goal_id = life.active_goal.id if life.active_goal else None
        if (
            record.task != task
            or record.action_id != life.record.action_counter
            or record.goal_id != goal_id
            or record.at != at
        ):
            raise PersistenceError("invalid")
        if starting:
            allowed = (
                (ToolOp.READ_STARTED, ToolOp.READ_FAILED)
                if task.tool is Tool.READER
                else (ToolOp.WRITE_STARTED,)
            )
        elif not complete:
            allowed = (ToolOp.READ_FAILED,) if task.tool is Tool.READER else (ToolOp.WRITE_FAILED,)
        else:
            allowed = (
                (ToolOp.READ_COMPLETED, ToolOp.READ_FAILED)
                if task.tool is Tool.READER
                else (ToolOp.WRITE_COMPLETED,)
            )
        failed = record.op in (ToolOp.READ_FAILED, ToolOp.WRITE_FAILED)
        if (
            record.op not in allowed
            or record.success == failed
            or (record.document is not None) != (record.op is ToolOp.WRITE_COMPLETED)
        ):
            raise PersistenceError("invalid")
    return records


def _with_tools(snapshot: CanonicalSnapshot, tools: tuple[ToolRecord, ...]) -> CanonicalSnapshot:
    images = {name: (columns, rows) for name, columns, rows in snapshot.tables}
    sequences = dict(snapshot.sequences)
    revision = snapshot.life.record.revision

    def append(name: str, fields: dict[str, Cell]) -> int:
        columns, rows = images[name]
        row_id = sequences.get(name, 0) + 1
        sequences[name] = row_id
        row: dict[str, Cell] = dict.fromkeys(columns)
        row.update(id=row_id, maple_id=snapshot.life.record.maple_id, revision=revision)
        row.update(fields)
        images[name] = columns, (*rows, tuple(row[c] for c in columns))
        return row_id

    for record in tools:
        doc = record.document
        document_id = None
        if doc is not None:
            document_id = append(
                "document",
                dict(
                    kind=doc.kind.value,
                    title=doc.title,
                    body=doc.body,
                    created_at=record.at.isoformat(),
                    action_id=record.action_id,
                    goal_id=record.goal_id,
                    sources=json.dumps(list(doc.sources)),
                ),
            )
        task = record.task
        append(
            "tool_use",
            dict(
                at=record.at.isoformat(),
                action_id=record.action_id,
                goal_id=record.goal_id,
                tool=task.tool.value,
                operation=record.op.value,
                target=task.target,
                title=task.title,
                category=task.category,
                status="success" if record.success else "failure",
                detail=record.detail,
                chars=record.chars,
                document_id=document_id,
            ),
        )
    return CanonicalSnapshot(
        snapshot.life,
        tuple((name, *images[name]) for name, _, _ in snapshot.tables),
        tuple(sorted(sequences.items())),
    )


class CanonicalPersistenceRuntime:
    """Single-owner opt-in lifecycle using existing CallGate and writer locking.

    No service, timer, API, environment or database-path discovery. An uncertain
    Save quarantines this instance; inspect by explicit new restore, never retry.
    """

    def __init__(
        self, port: LifecyclePort, snapshot: CanonicalSnapshot, schema_version: int
    ) -> None:
        if type(schema_version) is not int or schema_version != 11:
            raise PersistenceError("version")
        self._port = port
        self._snapshot = CanonicalSnapshot(snapshot.life, snapshot.tables, snapshot.sequences)
        self._version = schema_version
        self._calls = CallGate()
        self._lock = RLock()
        self._closed = False
        self._uncertain = False

    @classmethod
    def create(
        cls, port: LifecyclePort, initial: CanonicalSnapshot, *, schema_version: int
    ) -> CanonicalPersistenceRuntime:
        if type(schema_version) is not int or schema_version != 11:
            raise PersistenceError("version")
        try:
            port.create(initial, schema_version=schema_version)
            restored = load(port, schema_version=schema_version)
            if restored != initial:
                raise PersistenceError("invalid")
            return cls(port, restored, schema_version)
        except BaseException:
            port.close()
            raise

    @classmethod
    def restore(cls, port: LifecyclePort, *, schema_version: int) -> CanonicalPersistenceRuntime:
        try:
            return cls(port, load(port, schema_version=schema_version), schema_version)
        except BaseException:
            port.close()
            raise

    def _require_current(self) -> None:
        if self._closed:
            raise RuntimeClosedError("canonical runtime closed")
        if self._uncertain:
            raise PersistenceError("uncertain")

    @admitted
    def capture(self) -> CanonicalSnapshot:
        with self._lock:
            self._require_current()
            return self._snapshot

    @admitted
    def legacy(
        self, facts: Presentation, now: datetime, *, origin: PointRef | None = None
    ) -> LegacyProjection:
        with self._lock:
            self._require_current()
            return _project(self._snapshot.life, facts, now, origin)

    def _save(self, proposed: CanonicalSnapshot) -> CanonicalSnapshot:
        with self._calls.commit():
            try:
                save(
                    self._port,
                    proposed,
                    schema_version=self._version,
                    expected_revision=self._snapshot.life.record.revision,
                )
            except BaseException:
                # A writer can fail after COMMIT. Do not expose old state as current.
                self._uncertain = True
                raise
        self._snapshot = proposed
        return proposed

    @admitted
    def checkpoint(self) -> CanonicalSnapshot:
        with self._lock:
            self._require_current()
            return self._save(checkpoint_image(self._snapshot))

    @admitted
    def step(
        self,
        now: datetime,
        inputs: BehaviorInputs,
        params: CoreParameters,
        facts: Presentation,
        *,
        expected_revision: int,
        catalog: Sequence[SourceRef] = LIBRARY_CATALOG,
        task_effects: TaskEffects | None = None,
    ) -> CanonicalSnapshot:
        """Opt-in synthetic ordinary life loop. Refused/duplicate calls never save.

        Not the default service. Goals/tasks use shared rule semantics. Task
        effects require an explicit owned read-only capability; state/provenance
        save together. Unprojectable interrupt origins remain explicit blockers.
        """
        with self._lock:
            self._require_current()
            before = self._snapshot
            life = before.life
            if life.record.revision != expected_revision:
                raise PersistenceError("revision")
            _presentation(life, facts)
            if life.record.decision_due_since is not None:
                raise LifeLoopBlocked("reevaluation_policy")
            document = life.layout.active.layout
            outcome = life_step(
                _frame(life),
                ResolutionSnapshot(document.world, document.catalog),
                now,
                inputs,
                params,
                catalog,
            )
            if outcome is None:
                return before
            proposed = _step_image(before, outcome)
            if outcome.minutes is not None:
                f = outcome.frame
                _project(
                    proposed.life,
                    replace(
                        facts,
                        activity=f.activity,
                        started_at=f.started_at,
                        until=f.until,
                        needs=f.needs,
                        reaction=proposed.life.reaction,
                        goal=proposed.life.active_goal,
                        task=proposed.life.task,
                    ),
                    now,
                    PointRef(life.record.point_host, life.record.point_id)
                    if f.travel is not None
                    else None,
                )
            if outcome.frame.action_id != life.record.action_counter and (
                life.task is not None or proposed.life.task is not None
            ):
                if task_effects is None:
                    raise LifeLoopBlocked("task_effects")
                records = _task_records(
                    life, proposed.life, now, task_effects(before, proposed.life, now)
                )
                proposed = _with_tools(proposed, records)
            return self._save(proposed)

    @admitted
    def preflight_transition(
        self,
        proposed: CanonicalSnapshot,
        facts: Presentation,
        now: datetime,
        *,
        origin: PointRef | None = None,
    ) -> LegacyProjection:
        """Preflight one caller proposal without state, counter or history mutation.

        This does not certify simulation/audit semantics or install the proposal.
        ADR0027/0028 action facts and the canonical engine remain prerequisites
        for a future transition commit; no fallback or scheduling policy is added.
        """
        with self._lock:
            self._require_current()
            admitted_snapshot = CanonicalSnapshot(
                proposed.life, proposed.tables, proposed.sequences
            )
            _transition(self._snapshot.life, admitted_snapshot.life, now, origin)
            return _project(admitted_snapshot.life, facts, now, origin)

    def begin_shutdown(self) -> None:
        self._calls.stop()

    def close(self) -> None:
        self.begin_shutdown()
        self._calls.drain()
        with self._lock:
            if not self._closed:
                self._port.close()
                self._closed = True
