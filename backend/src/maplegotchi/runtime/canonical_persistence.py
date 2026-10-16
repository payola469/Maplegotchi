"""Explicit isolated canonical persistence lifecycle, never default MapleService.

This owns one canonical snapshot and serialized persistence operations. It is
not a default heartbeat/Director engine and never constructs MapleState.
Proposals come from an authorized caller; D01 preflights compatibility
without installing them. The explicit step method supplies only a bounded ordinary-life MVP.
Checkpoint is a Save intent, not simulation advancement. Restore
accepts canonical Travel independently of Legacy presentation availability.
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime
from threading import RLock

from maplegotchi.core.activities import Activity
from maplegotchi.core.audit import ActionEventKind
from maplegotchi.core.behavior import BehaviorInputs
from maplegotchi.core.daytime import require_utc
from maplegotchi.core.parameters import GLOBAL_INTERACTION_WINDOW, CoreParameters
from maplegotchi.core.state import prune_interactions
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
    )


def _life_after(before: CanonicalLife, outcome: LifeStep) -> CanonicalLife:
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
    life = _life_after(before.life, outcome)
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
        target = old_point if event.kind is ActionEventKind.ACTIVITY_COMPLETED else point
        payload: dict[str, Cell] = {"point": target.id, "furniture": target.furniture.value}
        if event.kind is ActionEventKind.DESTINATION_SELECTED:
            payload.update(
                activity=f.activity.value,
                duration_minutes=float(outcome.minutes) if outcome.minutes is not None else None,
            )
        elif event.kind is ActionEventKind.ACTIVITY_STARTED:
            payload.update(activity=f.activity.value)
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
                kind=event.kind.value,
                at=event.at.isoformat(),
                payload=wire(payload),
            ),
        )
    if outcome.changed_at is not None and outcome.previous is not None:
        append(
            "timeline_event",
            dict(
                kind="activity_changed",
                at=outcome.changed_at.isoformat(),
                payload=wire(dict(previous=outcome.previous.value, current=f.activity.value)),
            ),
        )
    if outcome.downtime_since is not None:
        append(
            "timeline_event",
            dict(
                kind="downtime_gap",
                at=f.updated_at.isoformat(),
                tick_id=f.rng.tick_counter,
                payload=wire(dict(since=outcome.downtime_since.isoformat())),
            ),
        )
    if outcome.minutes is not None:
        decision_id = append(
            "decision",
            dict(
                at=f.updated_at.isoformat(),
                trigger="action_completed",
                director_kind="rule",
                director_name="canonical-mvp",
                director_version="1",
                context_summary="synthetic ordinary basic activity profile",
                proposed_action=f.activity.value,
                proposed_duration_minutes=float(outcome.minutes),
                proposed_reason="MVP ordinary selection",
                verdict="accepted",
                executed_by="rule",
                executed_reason="MVP ordinary selection",
                action_id=f.action_id,
                executed_action=f.activity.value,
                executed_point=point.id,
                executed_duration_minutes=outcome.minutes,
            ),
        )
        life = capture_life(
            replace(life, decisions=(*life.decisions, (decision_id, r.maple_id, r.revision)))
        )
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
    ) -> CanonicalSnapshot:
        """Opt-in synthetic ordinary life loop. Refused/duplicate calls never save.

        Not the default service. Unsupported goals/tasks/priority transitions are
        explicit blockers; valid persisted states still Restore/checkpoint exactly.
        """
        with self._lock:
            self._require_current()
            before = self._snapshot
            life = before.life
            if life.record.revision != expected_revision:
                raise PersistenceError("revision")
            _presentation(life, facts)
            if (
                life.active_goal is not None
                or life.suspended_goal is not None
                or life.task is not None
                or life.priority.value != "normal"
                or life.record.critical_since is not None
            ):
                raise LifeLoopBlocked("goal_task_priority")
            document = life.layout.active.layout
            outcome = life_step(
                _frame(life),
                ResolutionSnapshot(document.world, document.catalog),
                now,
                inputs,
                params,
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
                    ),
                    now,
                    PointRef(life.record.point_host, life.record.point_id)
                    if f.travel is not None
                    else None,
                )
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
