"""Isolated canonical lifecycle and prospective D01; no default service or tick."""

from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any

import pytest

from maplegotchi.core.activities import Activity
from maplegotchi.core.daytime import DayPhase
from maplegotchi.core.room import Pose
from maplegotchi.core.state import Expression
from maplegotchi.core.world.coordinates import Tile
from maplegotchi.core.world.legacy_projection import DevelopmentWorld, PointRef, Presentation
from maplegotchi.core.world.movement import EdgeStart, Entry, Travel
from maplegotchi.core.world.pathfinding import find_route
from maplegotchi.persistence.legacy_admission import CompatibilityRefusal, project_eligible
from maplegotchi.runtime.canonical_persistence import CanonicalPersistenceRuntime, checkpoint_image
from maplegotchi.runtime.lifecycle import RuntimeClosedError
from maplegotchi.storage.canonical_v11 import CanonicalSnapshot, PersistenceError
from tests.schema_v11 import owned_store as store
from tests.schema_v11.canonical_binding import OwnedBinding, admit, image_of
from tests.schema_v11.restart_worker import (
    advanced_snapshot,
    birth_snapshot,
    life_changes,
    resources,
)
from tests.schema_v11.test_canonical_boundary import scope as scope
from tests.world.test_legacy_projection import CASES, payload, ref, travel_between


@pytest.fixture(scope="module")
def context() -> DevelopmentWorld:
    _, _, document = resources()
    return DevelopmentWorld(document.world, document.catalog)


@pytest.mark.parametrize("source", CASES)
@pytest.mark.parametrize("destination", CASES)
def test_d01_exact_existing_pair_matrix(
    context: DevelopmentWorld,
    source: tuple[Activity, str, str],
    destination: tuple[Activity, str, str],
) -> None:
    from_activity, origin, start_anchor = source
    activity, target, end_anchor = destination
    travel = travel_between(context, origin, target)
    before = (context, travel, travel.route, travel.entry)
    facts = payload(activity, travel.arrives_at)
    if travel.duration_us > 0 and start_anchor == end_anchor:
        with pytest.raises(CompatibilityRefusal) as error:
            project_eligible(
                context,
                ref(target),
                facts,
                travel.departed_at,
                travel=travel,
                origin=ref(origin),
                from_activity=from_activity,
            )
        assert error.value.args == ("collapsed_anchor",)
    else:
        result = project_eligible(
            context,
            ref(target),
            facts,
            travel.departed_at,
            travel=travel,
            origin=ref(origin),
            from_activity=from_activity,
        )
        assert result.route is None if travel.duration_us == 0 else result.route is not None
        if result.route is not None:
            assert (result.route.departed_at, result.route.arrives_at) == (
                travel.departed_at,
                travel.arrives_at,
            )
    assert before == (context, travel, travel.route, travel.entry)


def port(scope: store.OwnedRoot, **kwargs: Any) -> OwnedBinding:
    catalog, validation, _ = resources()
    return OwnedBinding(scope, "maple.db", (catalog,), ((1, validation),), **kwargs)


def facts(snapshot: CanonicalSnapshot) -> Presentation:
    life = snapshot.life
    return Presentation(
        life.activity,
        datetime.fromisoformat(life.record.activity_started_at),
        datetime.fromisoformat(life.record.activity_until),
        life.needs,
        life.reaction,
        Expression.CALM,
        Pose.STAND,
        DayPhase.EVENING,
        "isolated-synthetic",
        life.active_goal,
        life.task,
    )


def initial(binding: OwnedBinding) -> CanonicalSnapshot:
    return admit(birth_snapshot(), binding.catalogs, binding.contexts)


def movement_proposal(
    binding: OwnedBinding,
    *,
    base: store.Snapshot | None = None,
    target: PointRef | None = None,
    activity: Activity = Activity.WRITE,
) -> CanonicalSnapshot:
    """Explicit synthetic proposal; never presented as an engine-generated tick."""
    target = PointRef("desk.writing", "chair") if target is None else target
    base = birth_snapshot() if base is None else base
    old = store.validate(base, binding.catalogs, binding.contexts)
    _, _, document = resources()
    world = DevelopmentWorld(document.world, document.catalog)
    point = next(
        p
        for p in world.catalog.points
        if (p.instance_id, p.template.id) == (target.instance_id, target.point_id)
    )
    destination = Tile(point.template.approach.x, point.template.approach.y)
    route = find_route(world.mask, Tile(old.record.tx, old.record.ty), destination).route
    assert route is not None
    now = datetime.fromisoformat(old.record.last_updated_at) + timedelta(seconds=1)
    travel = Travel(route, now)
    from maplegotchi.persistence.travel_codec import encode_travel_path

    image = life_changes(
        base,
        revision=old.record.revision + 1,
        activity=activity.value,
        point_host=target.instance_id,
        point_id=target.point_id,
        last_updated_at=now.isoformat(),
        activity_started_at=travel.arrives_at.isoformat(),
        activity_until=(travel.arrives_at + timedelta(minutes=15)).isoformat(),
        route_path=encode_travel_path(travel, walkability=world.mask),
        route_departed_at=now.isoformat(),
        route_arrives_at=travel.arrives_at.isoformat(),
        route_from_activity=old.activity.value,
    )
    return admit(image, binding.catalogs, binding.contexts)


def test_explicit_create_checkpoint_close_restore(scope: store.OwnedRoot) -> None:
    binding = port(scope)
    birth = initial(binding)
    runtime = CanonicalPersistenceRuntime.create(binding, birth, schema_version=11)
    saved = runtime.checkpoint()
    assert saved.life.record.revision == 2
    assert image_of(saved).sequences == image_of(birth).sequences
    assert store.old_history(image_of(saved)) == store.old_history(image_of(birth))
    runtime.close()
    runtime.close()
    with pytest.raises(RuntimeClosedError):
        runtime.capture()
    reopened = CanonicalPersistenceRuntime.restore(port(scope), schema_version=11)
    assert store.exact(image_of(reopened.capture())) == store.exact(image_of(saved))
    reopened.close()
    with pytest.raises(PersistenceError, match="ownership"):
        CanonicalPersistenceRuntime.create(port(scope), birth, schema_version=11)


def test_projectable_preflight_does_not_install_unaudited_transition(
    scope: store.OwnedRoot,
) -> None:
    binding = port(scope)
    runtime = CanonicalPersistenceRuntime.create(binding, initial(binding), schema_version=11)
    proposed = movement_proposal(binding)
    now = datetime.fromisoformat(proposed.life.record.last_updated_at)
    result = runtime.preflight_transition(
        proposed, facts(proposed), now, origin=PointRef("idle.hall_center", "idle")
    )
    assert result.route is not None
    assert runtime.capture() == initial(binding)
    runtime.close()
    restored = CanonicalPersistenceRuntime.restore(port(scope), schema_version=11)
    assert restored.capture() == initial(binding)
    restored.close()


def test_failed_admission_no_write_no_state_rng_or_history_mutation(scope: store.OwnedRoot) -> None:
    binding = port(scope)
    runtime = CanonicalPersistenceRuntime.create(binding, initial(binding), schema_version=11)
    before = runtime.capture()
    # Same-anchor positive movement from one bookshelves provider to another is
    # covered exhaustively above. Here exercise a typed runtime continuity refusal.
    proposed = movement_proposal(binding)
    now = datetime.fromisoformat(proposed.life.record.last_updated_at)
    for _ in range(2):
        with pytest.raises(CompatibilityRefusal, match="continuity"):
            runtime.preflight_transition(
                proposed, facts(proposed), now, origin=PointRef("idle.hall_west", "idle")
            )
        assert runtime.capture() is before
        assert store.exact(image_of(binding.load(schema_version=11))) == store.exact(
            image_of(before)
        )
    runtime.close()


@pytest.mark.parametrize("mode", ["stationary", "walking", "pending", "entry_a", "entry_b"])
def test_existing_canonical_state_remains_loadable_without_legacy(
    scope: store.OwnedRoot, mode: str
) -> None:
    binding = port(scope)
    store.create(scope, binding.name, birth_snapshot(), binding.catalogs, binding.contexts)
    specimen = advanced_snapshot(birth_snapshot(), mode)
    store.save(
        scope,
        binding.name,
        specimen,
        expected_revision=1,
        catalogs=binding.catalogs,
        contexts=binding.contexts,
    )
    runtime = CanonicalPersistenceRuntime.restore(binding, schema_version=11)
    old = runtime.capture()
    if mode.startswith("entry"):
        with pytest.raises(CompatibilityRefusal, match="mid_edge"):
            runtime.legacy(
                facts(old),
                datetime.fromisoformat(old.life.record.last_updated_at),
                origin=PointRef("idle.hall_center", "idle"),
            )
        assert runtime.capture() is old
    checkpoint = runtime.checkpoint()
    assert checkpoint.life.travel == old.life.travel
    assert checkpoint.life.rng == old.life.rng
    assert checkpoint.life.identity_row == old.life.identity_row
    runtime.close()
    restored = CanonicalPersistenceRuntime.restore(port(scope), schema_version=11)
    assert store.exact(image_of(restored.capture())) == store.exact(image_of(checkpoint))
    restored.close()


@pytest.mark.parametrize("phase", ["after_write", "before_commit", "after_commit"])
def test_save_failure_quarantines_instance_until_explicit_restore(
    scope: store.OwnedRoot, phase: str
) -> None:
    calls = []

    def fail(at: str) -> None:
        calls.append(at)
        if at == phase:
            raise PersistenceError("uncertain")

    binding = port(scope, inject=fail)
    runtime = CanonicalPersistenceRuntime.create(binding, initial(binding), schema_version=11)
    old = runtime.capture()
    with pytest.raises(PersistenceError, match="uncertain"):
        runtime.checkpoint()
    with pytest.raises(PersistenceError, match="uncertain"):
        runtime.capture()
    with pytest.raises(PersistenceError, match="uncertain"):
        runtime.checkpoint()
    assert calls.count(phase) == 1
    runtime.close()
    reopened = CanonicalPersistenceRuntime.restore(port(scope), schema_version=11)
    assert reopened.capture() == (checkpoint_image(old) if phase == "after_commit" else old)
    reopened.close()


def test_missing_restore_never_calls_create_or_birth(scope: store.OwnedRoot) -> None:
    with pytest.raises(PersistenceError, match="ownership"):
        CanonicalPersistenceRuntime.restore(port(scope), schema_version=11)
    assert not (scope.path / "maple.db").exists()


def test_shutdown_closes_admission_without_an_implicit_save(scope: store.OwnedRoot) -> None:
    binding = port(scope)
    runtime = CanonicalPersistenceRuntime.create(binding, initial(binding), schema_version=11)
    old = runtime.capture()
    runtime.begin_shutdown()
    with pytest.raises(RuntimeClosedError):
        runtime.checkpoint()
    runtime.close()
    assert binding.load(schema_version=11) == old


def test_new_mid_edge_projection_has_fixed_refusal(context: DevelopmentWorld) -> None:
    travel = travel_between(context, "idle.hall_center/idle", "desk.writing/chair")
    cells = travel.route.tiles()
    entered = replace(
        travel, entry=Entry(EdgeStart(cells[1], cells[0], 100000, travel.step_us), cells[0])
    )
    with pytest.raises(CompatibilityRefusal) as error:
        project_eligible(
            context,
            PointRef("desk.writing", "chair"),
            payload(Activity.WRITE, entered.arrives_at),
            entered.departed_at,
            travel=entered,
            origin=PointRef("idle.hall_center", "idle"),
            from_activity=Activity.IDLE,
        )
    assert error.value.args == ("mid_edge",)


def test_collapsed_runtime_proposal_refuses_before_save(scope: store.OwnedRoot) -> None:
    binding = port(scope)
    original = birth_snapshot()
    _, _, document = resources()
    point = next(
        p
        for p in document.catalog.points
        if (p.instance_id, p.template.id) == ("bookshelf.library_1", "front_l")
    )
    seeded = life_changes(
        original,
        revision=2,
        activity="read",
        point_host=point.instance_id,
        point_id=point.template.id,
        tx=point.template.approach.x,
        ty=point.template.approach.y,
    )
    store.create(scope, binding.name, original, binding.catalogs, binding.contexts)
    store.save(
        scope,
        binding.name,
        seeded,
        expected_revision=1,
        catalogs=binding.catalogs,
        contexts=binding.contexts,
    )
    runtime = CanonicalPersistenceRuntime.restore(binding, schema_version=11)
    before = runtime.capture()
    proposed = movement_proposal(
        binding,
        base=seeded,
        target=PointRef("bookshelf.library_1", "front_r"),
        activity=Activity.READ,
    )
    for _ in range(2):
        with pytest.raises(CompatibilityRefusal, match="collapsed_anchor"):
            runtime.preflight_transition(
                proposed,
                facts(proposed),
                datetime.fromisoformat(proposed.life.record.last_updated_at),
                origin=PointRef("bookshelf.library_1", "front_l"),
            )
        assert runtime.capture() is before
        assert store.exact(image_of(binding.load(schema_version=11))) == store.exact(
            image_of(before)
        )
    runtime.close()

    # A pre-existing valid canonical movement is NOT refused by Load, even
    # though this same proposal could not pass prospective Legacy admission.
    store.save(
        scope,
        binding.name,
        image_of(proposed),
        expected_revision=2,
        catalogs=binding.catalogs,
        contexts=binding.contexts,
    )
    restored = CanonicalPersistenceRuntime.restore(port(scope), schema_version=11)
    assert restored.capture() == proposed
    with pytest.raises(CompatibilityRefusal, match="collapsed_anchor"):
        restored.legacy(
            facts(proposed),
            datetime.fromisoformat(proposed.life.record.last_updated_at),
            origin=PointRef("bookshelf.library_1", "front_l"),
        )
    assert restored.capture() == proposed
    assert restored.checkpoint().life.travel == proposed.life.travel
    restored.close()


@pytest.mark.parametrize("corruption", ["future", "foreign", "missing_pointer", "schema"])
def test_runtime_restore_refuses_existing_invalid_store_without_repair(
    scope: store.OwnedRoot, corruption: str
) -> None:
    binding = port(scope)
    runtime = CanonicalPersistenceRuntime.create(binding, initial(binding), schema_version=11)
    runtime.close()
    with store.connect(scope, binding.name) as conn:
        statements = {
            "future": "PRAGMA user_version=12",
            "foreign": "PRAGMA application_id=0",
            "missing_pointer": "DELETE FROM world_state",
            "schema": "DROP INDEX one_active_display_per_item",
        }
        conn.execute(statements[corruption])
    with pytest.raises(PersistenceError) as error:
        CanonicalPersistenceRuntime.restore(port(scope), schema_version=11)
    assert error.value.args == ("version" if corruption in {"future", "foreign"} else "storage",)
    # Refusal must not repair schema, header, pointer, birth or history.
    with store.connect(scope, binding.name, readonly=True) as conn:
        if corruption == "future":
            assert conn.execute("PRAGMA user_version").fetchone() == (12,)
        elif corruption == "foreign":
            assert conn.execute("PRAGMA application_id").fetchone() == (0,)
        elif corruption == "missing_pointer":
            assert conn.execute("SELECT count(*) FROM world_state").fetchone() == (0,)
        else:
            assert conn.execute(
                "SELECT count(*) FROM sqlite_schema WHERE name='one_active_display_per_item'"
            ).fetchone() == (0,)
        assert conn.execute("SELECT count(*) FROM timeline_event WHERE kind='born'").fetchone() == (
            1,
        )


def test_stale_runtime_checkpoint_does_not_retry(scope: store.OwnedRoot) -> None:
    binding = port(scope)
    first = CanonicalPersistenceRuntime.create(binding, initial(binding), schema_version=11)
    stale = CanonicalPersistenceRuntime.restore(port(scope), schema_version=11)
    expected = first.checkpoint()
    with pytest.raises(PersistenceError, match="revision"):
        stale.checkpoint()
    with pytest.raises(PersistenceError, match="uncertain"):
        stale.checkpoint()
    stale.close()
    first.close()
    assert port(scope).load(schema_version=11) == expected


def test_shutdown_drains_permitted_save_before_closing(scope: store.OwnedRoot) -> None:
    from threading import Event, Thread

    entered, release = Event(), Event()
    errors: list[BaseException] = []

    def pause(phase: str) -> None:
        if phase == "before_commit":
            entered.set()
            assert release.wait(timeout=10)

    binding = port(scope, inject=pause)
    runtime = CanonicalPersistenceRuntime.create(binding, initial(binding), schema_version=11)

    def write() -> None:
        try:
            runtime.checkpoint()
        except BaseException as exc:
            errors.append(exc)

    writer = Thread(target=write)
    writer.start()
    try:
        assert entered.wait(timeout=10)
        runtime.begin_shutdown()
        with pytest.raises(RuntimeClosedError):
            runtime.capture()
        release.set()
    finally:
        release.set()
        writer.join(timeout=15)
        assert not writer.is_alive()
        runtime.close()
    assert not errors
    assert port(scope).load(schema_version=11).life.record.revision == 2


@pytest.mark.parametrize("field", ["activity", "started_at", "until", "needs"])
def test_preflight_rejects_presentation_disagreement_before_write(
    scope: store.OwnedRoot, field: str
) -> None:
    from maplegotchi.core.state import Needs

    binding = port(scope)
    runtime = CanonicalPersistenceRuntime.create(binding, initial(binding), schema_version=11)
    before = runtime.capture()
    proposal = movement_proposal(binding)
    presentation = facts(proposal)
    changes: dict[str, Any] = {
        "activity": Activity.READ,
        "started_at": presentation.started_at - timedelta(seconds=1),
        "until": presentation.until + timedelta(seconds=1),
        "needs": Needs(1.0, 2.0, 3.0, 4.0),
    }
    with pytest.raises(CompatibilityRefusal) as error:
        runtime.preflight_transition(
            proposal,
            replace(presentation, **{field: changes[field]}),
            datetime.fromisoformat(proposal.life.record.last_updated_at),
            origin=PointRef("idle.hall_center", "idle"),
        )
    assert error.value.args == ("presentation",)
    assert runtime.capture() is before
    assert binding.load(schema_version=11) == before
    runtime.close()


def test_zero_walk_preflight_is_not_a_state_change(scope: store.OwnedRoot) -> None:
    binding = port(scope)
    runtime = CanonicalPersistenceRuntime.create(binding, initial(binding), schema_version=11)
    before = runtime.capture()
    proposal = checkpoint_image(before)
    result = runtime.preflight_transition(proposal, facts(proposal), before.life.identity.born_at)
    assert result.route is None
    assert runtime.capture() is before
    assert binding.load(schema_version=11) == before
    runtime.close()


# STEP238: actual ordinary-life transitions; no historical database access.
def advance(runtime: CanonicalPersistenceRuntime, now: datetime) -> CanonicalSnapshot:
    from maplegotchi.core.behavior import BehaviorInputs
    from maplegotchi.core.parameters import CoreParameters

    before = runtime.capture()
    return runtime.step(
        now,
        BehaviorInputs(),
        CoreParameters(heartbeat_interval=timedelta(seconds=1)),
        facts(before),
        expected_revision=before.life.record.revision,
    )


def test_actual_life_tick_move_arrive_restart_continue(scope: store.OwnedRoot) -> None:
    binding = port(scope)
    raw = birth_snapshot()
    runtime = CanonicalPersistenceRuntime.create(
        binding, admit(raw, binding.catalogs, binding.contexts), schema_version=11
    )
    born = runtime.capture().life.identity.born_at
    started = advance(runtime, born + timedelta(hours=4))
    assert started.life.rng.tick_counter == started.life.rng.decision_counter == 1
    assert started.life.record.action_counter == 1
    assert started.life.needs.energy < 80
    completed = next(
        row for row in image_of(started).rows("action_event") if row[5] == "activity_completed"
    )
    assert completed[6] == (born + timedelta(minutes=15)).isoformat()
    assert completed[8] == '{"activity":"idle"}'
    decision_columns = image_of(started).table("decision").columns
    decision = dict(zip(decision_columns, image_of(started).rows("decision")[0], strict=True))
    assert type(decision["proposed_duration_minutes"]) is float
    downtime = next(
        row for row in image_of(started).rows("timeline_event") if row[4] == "downtime_gap"
    )
    assert downtime[6] == '{"since":"' + born.isoformat() + '"}'
    travel = started.life.travel
    assert travel is not None and travel.duration_us > 0
    before_bytes = scope.check("maple.db").read_bytes()
    assert advance(runtime, born + timedelta(hours=4)) is started
    assert scope.check("maple.db").read_bytes() == before_bytes
    runtime.close()
    runtime = CanonicalPersistenceRuntime.restore(port(scope), schema_version=11)
    assert runtime.capture() == started
    midway = travel.departed_at + timedelta(seconds=1)
    walking = advance(runtime, midway)
    assert walking.life.travel == travel
    assert walking.life.record.action_counter == 1
    arrived = advance(runtime, travel.arrives_at)
    assert arrived.life.travel is None
    assert (arrived.life.record.tx, arrived.life.record.ty) == (
        travel.route.destination.tx,
        travel.route.destination.ty,
    )
    actions = image_of(arrived).rows("action_event")
    assert sum(row[5] == "arrived" for row in actions) == 1
    assert sum(row[5] == "activity_started" for row in actions) == 1
    again = advance(runtime, travel.arrives_at + timedelta(seconds=1))
    assert image_of(again).rows("action_event") == actions
    continued = advance(runtime, datetime.fromisoformat(again.life.record.activity_until))
    assert continued.life.record.action_counter == 2
    assert continued.life.rng.decision_counter == 2
    assert continued.life.identity_row == started.life.identity_row
    assert len(image_of(continued).rows("decision")) == 2
    assert image_of(continued).rows("world_event") == ()
    runtime.close()
    restored = CanonicalPersistenceRuntime.restore(port(scope), schema_version=11)
    assert restored.capture() == continued
    restored.close()


@pytest.mark.parametrize("phase", ["after_write", "before_commit", "after_commit"])
def test_life_step_atomic_failure_no_retry(scope: store.OwnedRoot, phase: str) -> None:
    def fail(at: str) -> None:
        if at == phase:
            raise PersistenceError("uncertain")

    runtime = CanonicalPersistenceRuntime.create(
        port(scope, inject=fail), initial(port(scope)), schema_version=11
    )
    before = runtime.capture()
    with pytest.raises(PersistenceError):
        advance(runtime, before.life.identity.born_at + timedelta(minutes=15))
    with pytest.raises(PersistenceError, match="uncertain"):
        runtime.capture()
    runtime.close()
    reopened = CanonicalPersistenceRuntime.restore(port(scope), schema_version=11)
    after = reopened.capture()
    assert after.life.record.revision == 1 + int(phase == "after_commit")
    assert len(image_of(after).rows("decision")) == int(phase == "after_commit")
    assert (after == before) == (phase != "after_commit")
    reopened.close()


@pytest.mark.parametrize("critical", [False, True])
def test_priority_blocker_never_commits_a_successful_tick(
    scope: store.OwnedRoot, critical: bool
) -> None:
    from maplegotchi.core.behavior import BehaviorInputs
    from maplegotchi.core.parameters import CoreParameters
    from maplegotchi.core.world.canonical_lifecycle import LifeLoopBlocked

    binding = port(scope)
    runtime = CanonicalPersistenceRuntime.create(binding, initial(binding), schema_version=11)
    if not critical:
        # Explicit synthetic precondition; not claimed as an engine-generated tick.
        runtime.close()
        store.save(
            scope,
            binding.name,
            life_changes(birth_snapshot(), revision=2, energy=5.0),
            expected_revision=1,
            catalogs=binding.catalogs,
            contexts=binding.contexts,
        )
        runtime = CanonicalPersistenceRuntime.restore(binding, schema_version=11)
    before = runtime.capture()
    with pytest.raises(
        LifeLoopBlocked, match="critical_interrupt" if critical else "high_interrupt"
    ):
        runtime.step(
            before.life.identity.born_at + timedelta(minutes=5),
            BehaviorInputs(server_attention=1.0 if critical else 0.0),
            CoreParameters(),
            facts(before),
            expected_revision=before.life.record.revision,
        )
    assert runtime.capture() is before and binding.load(schema_version=11) == before
    runtime.close()


def test_life_step_revision_and_shutdown_guards(scope: store.OwnedRoot) -> None:
    from maplegotchi.core.behavior import BehaviorInputs
    from maplegotchi.core.parameters import CoreParameters

    runtime = CanonicalPersistenceRuntime.create(
        port(scope), initial(port(scope)), schema_version=11
    )
    old = runtime.capture()
    with pytest.raises(PersistenceError, match="revision"):
        runtime.step(
            old.life.identity.born_at + timedelta(minutes=15),
            BehaviorInputs(),
            CoreParameters(),
            facts(old),
            expected_revision=2,
        )
    assert runtime.capture() is old
    runtime.begin_shutdown()
    with pytest.raises(RuntimeClosedError):
        advance(runtime, old.life.identity.born_at + timedelta(minutes=15))
    runtime.close()


def test_stale_actual_life_writer_cannot_overwrite_committed_state(scope: store.OwnedRoot) -> None:
    first = CanonicalPersistenceRuntime.create(port(scope), initial(port(scope)), schema_version=11)
    stale = CanonicalPersistenceRuntime.restore(port(scope), schema_version=11)
    now = first.capture().life.identity.born_at + timedelta(hours=4)
    committed = advance(first, now)
    with pytest.raises(PersistenceError, match="revision"):
        advance(stale, now)
    with pytest.raises(PersistenceError, match="uncertain"):
        stale.capture()
    assert port(scope).load(schema_version=11) == committed
    stale.close()
    first.close()


def test_critical_mid_edge_refuses_before_any_database_write(scope: store.OwnedRoot) -> None:
    from maplegotchi.core.behavior import BehaviorInputs
    from maplegotchi.core.parameters import CoreParameters
    from maplegotchi.core.world.canonical_lifecycle import LifeLoopBlocked

    runtime = CanonicalPersistenceRuntime.create(
        port(scope), initial(port(scope)), schema_version=11
    )
    started = advance(runtime, runtime.capture().life.identity.born_at + timedelta(hours=4))
    travel = started.life.travel
    assert travel is not None
    now = travel.departed_at + timedelta(microseconds=100000)
    assert isinstance(travel.current_at(now), EdgeStart)
    before_bytes = scope.check("maple.db").read_bytes()
    with pytest.raises(LifeLoopBlocked, match="critical_interrupt"):
        runtime.step(
            now,
            BehaviorInputs(server_attention=1),
            CoreParameters(),
            facts(started),
            expected_revision=started.life.record.revision,
        )
    assert runtime.capture() is started
    assert scope.check("maple.db").read_bytes() == before_bytes
    assert port(scope).load(schema_version=11) == started
    runtime.close()
