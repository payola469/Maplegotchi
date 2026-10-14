"""Explicit isolated canonical persistence lifecycle, never default MapleService.

This owns one canonical snapshot and serialized persistence operations. It is
NOT a replacement heartbeat/Director engine and never constructs MapleState.
Proposals come from an authorized caller; D01 preflights compatibility
without installing them. Grid engine/action-audit integration is not supplied.
Checkpoint is a Save intent, not simulation advancement. Restore
accepts canonical Travel independently of Legacy presentation availability.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from threading import RLock

from maplegotchi.core.activities import Activity
from maplegotchi.core.daytime import require_utc
from maplegotchi.core.world.coordinates import Tile
from maplegotchi.core.world.legacy_projection import (
    DevelopmentWorld,
    LegacyProjection,
    PointRef,
    Presentation,
    project_point,
)
from maplegotchi.core.world.movement import EdgeStart
from maplegotchi.persistence.boundary import capture_life
from maplegotchi.persistence.legacy_admission import CompatibilityRefusal, project_eligible
from maplegotchi.persistence.life_record import CanonicalLife, life_fields
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
