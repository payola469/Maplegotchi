"""Bounded synthetic full-life records, trusted Travel values and pure contexts."""

from __future__ import annotations

import ast
import builtins
import json
import re
import socket
import sqlite3
from copy import deepcopy
from dataclasses import FrozenInstanceError, dataclass, fields, replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, NoReturn, cast, get_args, get_type_hints

import pytest

from maplegotchi.core.rng import RngStream
from maplegotchi.core.timeline import Born
from maplegotchi.core.world.coordinates import Tile
from maplegotchi.core.world.movement import EdgeStart, Entry, Travel
from maplegotchi.core.world.pathfinding import Route, Waypoint
from maplegotchi.core.world.walkability import validate_safe_layout
from tests.schema_v11 import life_record, travel_codec
from tests.schema_v11.declarations import target_tables
from tests.schema_v11.layout_codec import CatalogSnapshot, LayoutContext, encode_layout_document
from tests.schema_v11.layout_keys import project_layout_keys
from tests.schema_v11.life_record import (
    LIFE_FIELDS,
    CanonicalLife,
    CanonicalLifeRecord,
    V11LifeError,
    life_fields,
    reconstruct_life,
    validate_restart_equivalence,
)
from tests.schema_v11.revision_snapshot import LifeReference, RevisionRow, validate_layout_snapshot
from tests.schema_v11.row_conservation import (
    DECISION_REFS,
    HISTORY_SCHEMA,
    HistoryImage,
    TableImage,
)
from tests.world.validation_corpus import canonical_candidate

EXPECTED_FIELDS = tuple(
    """maple_id revision mood energy curiosity social activity
activity_started_at activity_until last_tick_at last_updated_at tick_counter
interaction_counter reaction_kind reaction_variant reaction_started_at reaction_until
point_id route_departed_at route_from_activity route_path needs_at decision_counter
action_counter goal_counter action_priority active_goal_id suspended_goal_id
suspended_action decision_due_since critical_since task_tool task_target task_title
task_category layout_revision point_host tx ty route_arrives_at""".split()
)
BORN = "2026-10-14T12:00:00+00:00"
UPDATED = "2026-10-14T12:10:00+00:00"
SEED = "5e" * 32


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


@dataclass(frozen=True)
class Fixture:
    values: tuple[tuple[str, object], ...]
    context: dict[str, Any]
    row: RevisionRow
    snapshot: CatalogSnapshot
    validation_context: LayoutContext
    wire: dict[str, Any]


@pytest.fixture(scope="module")
def fixture() -> Fixture:
    root = Path(__file__).parents[2] / "src/maplegotchi/world_catalog"
    resource = json.loads((root / "initial_catalog.json").read_text(encoding="utf-8"))
    wire = dict(
        format_version=1,
        house=json.loads((root / "initial_house.json").read_text(encoding="utf-8")),
        instances=resource["instances"],
        themes={},
        lighting_presets={},
    )
    candidate = canonical_candidate()
    validation_context = LayoutContext(candidate.art, candidate.legacy_targets, Tile(34, 5))
    snapshot = CatalogSnapshot(1, canonical(resource["types"]))
    document = encode_layout_document(
        wire,
        catalog_version=1,
        catalog_hash=snapshot.catalog_hash,
        snapshots=(snapshot,),
        context=validation_context,
    )
    keys = project_layout_keys(document, 1)
    row = RevisionRow(
        1,
        BORN,
        "migration",
        None,
        1,
        snapshot.catalog_hash,
        document.canonical_bytes.decode(),
        document.validation_digest,
    )
    layout = validate_layout_snapshot(
        (row,),
        ((1, 1),),
        (LifeReference(1, 1, "desk.writing", "chair"),),
        keys,
        snapshots=(snapshot,),
        contexts=((1, validation_context),),
    )
    # Independently specified complete row, exercising every nullable bundle
    # except Travel (tested separately with exact canonical envelope literals).
    raw: tuple[object, ...] = (
        1,
        12,
        61.25,
        72.5,
        43.75,
        54.0,
        "write",
        "2026-10-14T12:05:00+00:00",
        "2026-10-14T12:35:00+00:00",
        "2026-10-14T12:05:00+00:00",
        UPDATED,
        5,
        3,
        "pet_happy",
        2,
        "2026-10-14T12:09:58+00:00",
        "2026-10-14T12:10:06+00:00",
        "chair",
        None,
        None,
        None,
        "2026-10-14T12:08:00+00:00",
        7,
        9,
        4,
        "high",
        3,
        2,
        "read",
        "2026-10-14T12:09:00+00:00",
        "2026-10-14T12:09:30+00:00",
        "writer",
        "note:restart_proof",
        "Restart proof",
        "self",
        1,
        "desk.writing",
        34,
        5,
        None,
    )
    context: dict[str, Any] = dict(
        identity_row=(1, "Maple", BORN, SEED),
        births=(Born(datetime.fromisoformat(BORN), "Maple"),),
        ledger_rows=(
            (1, 0, "greet", "2026-10-14T12:08:00+00:00"),
            (1, 1, "pet", "2026-10-14T12:09:00+00:00"),
        ),
        goal_rows=(
            (
                2,
                1,
                4,
                "learn",
                "Read carefully",
                "rule",
                8,
                "2026-10-14T12:01:00+00:00",
                "2026-10-14T12:31:00+00:00",
            ),
            (
                3,
                1,
                4,
                "create",
                "Write a useful note",
                "rule",
                8,
                "2026-10-14T12:02:00+00:00",
                "2026-10-14T12:45:00+00:00",
            ),
        ),
        decisions=((8, 1, 4),),
        layout=layout,
        keys=keys,
        travel=None,
    )
    assert len(raw) == 40
    return Fixture(
        tuple(zip(EXPECTED_FIELDS, raw, strict=True)),
        context,
        row,
        snapshot,
        validation_context,
        wire,
    )


def restored(
    fixture: Fixture, changes: dict[str, object] | None = None, **context: Any
) -> CanonicalLife:
    values = tuple((name, (changes or {}).get(name, value)) for name, value in fixture.values)
    arguments = fixture.context | context
    return reconstruct_life(values, **arguments)


def test_frozen_schema_exact_40_field_coverage() -> None:
    declaration = target_tables()["life_state"]  # Trusted SQL text only, never executed.
    columns = tuple(re.findall(r"^ ([a-z_]+) (?:INTEGER|REAL|TEXT)\b", declaration, re.MULTILINE))
    assert columns == EXPECTED_FIELDS == LIFE_FIELDS
    assert tuple(field.name for field in fields(CanonicalLifeRecord)) == EXPECTED_FIELDS
    assert len(columns) == 40 and "location" not in columns
    hints = get_type_hints(CanonicalLifeRecord)
    for name, sql_type, constraints in re.findall(
        r"^ ([a-z_]+) (INTEGER|REAL|TEXT)([^\n]*)", declaration, re.MULTILINE
    ):
        expected = {{"INTEGER": int, "REAL": float, "TEXT": str}[sql_type]}
        if "NOT NULL" not in constraints and name != "maple_id":
            expected.add(type(None))
        assert set(get_args(hints[name]) or (hints[name],)) == expected, name


def test_complete_independent_expected_record(fixture: Fixture) -> None:
    life = restored(fixture)
    assert life_fields(life.record) == fixture.values
    assert life.record.revision == 12 and life.layout.active_revision == 1
    assert life.identity.name == "Maple" and life.identity.born_at == datetime.fromisoformat(BORN)
    assert life.rng.seed_hex == SEED
    assert (life.rng.tick_counter, life.rng.interaction_counter, life.rng.decision_counter) == (
        5,
        3,
        7,
    )
    assert life.active_goal is not None and life.active_goal.id == 3
    assert life.suspended_goal is not None and life.suspended_goal.id == 2
    assert life.suspended_action == "read" and life.priority == "high"
    assert life.reaction is not None and life.reaction.variant == 2
    assert life.task is not None and life.task.target == "note:restart_proof"
    assert len(life.recent_interactions) == 2


def test_lossless_reconstruction_and_no_draws_or_mutation(fixture: Fixture) -> None:
    before = deepcopy(fixture)
    first = restored(fixture)
    second = reconstruct_life(life_fields(first.record), **fixture.context)
    assert first == second and fixture == before
    assert life_fields(second.record) == fixture.values
    assert (
        RngStream(first.rng.seed_hex, "decision", first.rng.decision_counter).random()
        == RngStream(second.rng.seed_hex, "decision", second.rng.decision_counter).random()
    )
    with pytest.raises(FrozenInstanceError):
        first.record.tx = 3  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        first.needs.mood = 0.0  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        first.identity.name = "Other"  # type: ignore[misc]
    with pytest.raises(TypeError):
        cast(Any, first.ledger_rows)[0][2] = "pet"


def test_complete_initial_record_with_all_optional_bundles_absent(fixture: Fixture) -> None:
    changes: dict[str, object] = dict(
        revision=1,
        mood=60.0,
        energy=80.0,
        curiosity=60.0,
        social=50.0,
        activity="idle",
        activity_started_at=BORN,
        activity_until="2026-10-14T12:15:00+00:00",
        last_tick_at=BORN,
        last_updated_at=BORN,
        tick_counter=0,
        interaction_counter=0,
        decision_counter=0,
        action_counter=0,
        goal_counter=0,
        action_priority="normal",
        point_host="idle.hall_center",
        point_id="idle",
        tx=21,
        ty=15,
    )
    for name in (
        "reaction_kind",
        "reaction_variant",
        "reaction_started_at",
        "reaction_until",
        "needs_at",
        "active_goal_id",
        "suspended_goal_id",
        "suspended_action",
        "decision_due_since",
        "critical_since",
        "task_tool",
        "task_target",
        "task_title",
        "task_category",
    ):
        changes[name] = None
    layout = validate_layout_snapshot(
        (fixture.row,),
        ((1, 1),),
        (LifeReference(1, 1, "idle.hall_center", "idle"),),
        fixture.context["keys"],
        snapshots=(fixture.snapshot,),
        contexts=((1, fixture.validation_context),),
    )
    life = restored(fixture, changes, layout=layout, ledger_rows=(), goal_rows=(), decisions=())
    assert len(life_fields(life.record)) == 40
    assert life.reaction is None and life.task is None and life.active_goal is None
    assert life.suspended_goal is None and life.recent_interactions == ()


def test_expired_state_is_preserved_without_ticks_or_cleanup(fixture: Fixture) -> None:
    life = restored(fixture, {"last_updated_at": "2026-10-14T13:00:00+00:00"}, ledger_rows=())
    assert life.active_goal is not None and life.active_goal.horizon_until < datetime.fromisoformat(
        life.record.last_updated_at
    )
    assert life.reaction is not None and life.reaction.until < datetime.fromisoformat(
        life.record.last_updated_at
    )
    assert life.record.tick_counter == 5 and life.record.revision == 12


@pytest.mark.parametrize("name", EXPECTED_FIELDS)
def test_each_missing_field_refused(fixture: Fixture, name: str) -> None:
    with pytest.raises(V11LifeError, match=r"^fields$"):
        reconstruct_life(
            tuple(pair for pair in fixture.values if pair[0] != name), **fixture.context
        )


@pytest.mark.parametrize("name", EXPECTED_FIELDS)
def test_each_duplicate_field_refused(fixture: Fixture, name: str) -> None:
    with pytest.raises(V11LifeError, match=r"^fields$"):
        reconstruct_life((*fixture.values, (name, dict(fixture.values)[name])), **fixture.context)


@pytest.mark.parametrize(
    "value", [None, [], {}, (("extra", 1),), (("maple_id",),), ((1, "value"),)]
)
def test_unknown_and_malformed_fields(fixture: Fixture, value: Any) -> None:
    with pytest.raises(V11LifeError, match=r"^fields$"):
        reconstruct_life(value, **fixture.context)
    with pytest.raises(V11LifeError, match=r"^fields$"):
        reconstruct_life((*fixture.values, ("extra", "private")), **fixture.context)


@pytest.mark.parametrize("name", EXPECTED_FIELDS)
@pytest.mark.parametrize("value", [True, [], {}])
def test_wrong_primitive_for_every_column(fixture: Fixture, name: str, value: object) -> None:
    with pytest.raises(V11LifeError, match=r"^type$"):
        restored(fixture, {name: value})


NONNULL = tuple(
    """maple_id revision mood energy curiosity social activity activity_started_at
activity_until last_tick_at last_updated_at tick_counter interaction_counter point_id
decision_counter
action_counter goal_counter action_priority layout_revision point_host tx ty""".split()
)


@pytest.mark.parametrize("name", NONNULL)
def test_all_nonnullable_fields_refused(fixture: Fixture, name: str) -> None:
    with pytest.raises(V11LifeError, match=r"^null$"):
        restored(fixture, {name: None})


@pytest.mark.parametrize(
    "name",
    ["tick_counter", "interaction_counter", "decision_counter", "action_counter", "goal_counter"],
)
@pytest.mark.parametrize("value", [-1, 1.0, "1"])
def test_invalid_counters(fixture: Fixture, name: str, value: object) -> None:
    with pytest.raises(V11LifeError):
        restored(fixture, {name: value})


@pytest.mark.parametrize("name", ["mood", "energy", "curiosity", "social"])
@pytest.mark.parametrize("value", [-0.1, 100.1, float("nan"), float("inf"), "50"])
def test_needs_without_clamping(fixture: Fixture, name: str, value: object) -> None:
    with pytest.raises(V11LifeError):
        restored(fixture, {name: value})


@pytest.mark.parametrize(
    "identity",
    [
        (2, "Maple", BORN, SEED),
        (True, "Maple", BORN, SEED),
        (1, " Maple", BORN, SEED),
        (1, "Maple", BORN, "AA" * 32),
        (1, "Maple", BORN, " " * 64),
        (1, "Maple", BORN, "g" * 64),
        (1, "Maple", BORN, "ab" * 31),
        None,
        [],
    ],
)
def test_identity_and_rng_seed_refusal(fixture: Fixture, identity: Any) -> None:
    with pytest.raises(V11LifeError):
        restored(fixture, identity_row=identity)


@pytest.mark.parametrize(
    "births",
    [
        (),
        [],
        (None,),
        (Born(datetime.fromisoformat(BORN), "Other"),),
        (Born(datetime.fromisoformat(UPDATED), "Maple"),),
        (Born(datetime(2026, 10, 14, 12), "Maple"),),  # noqa: DTZ001 -- naive refusal specimen
    ],
)
def test_one_true_matching_birth(fixture: Fixture, births: Any) -> None:
    with pytest.raises(V11LifeError, match=r"^identity$"):
        restored(fixture, births=births)
    with pytest.raises(V11LifeError, match=r"^identity$"):
        restored(fixture, births=fixture.context["births"] * 2)


@pytest.mark.parametrize(
    "name",
    [
        "activity_started_at",
        "activity_until",
        "last_tick_at",
        "last_updated_at",
        "needs_at",
        "reaction_started_at",
        "reaction_until",
        "decision_due_since",
        "critical_since",
    ],
)
@pytest.mark.parametrize(
    "value",
    [
        "2026-02-30T12:00:00+00:00",
        "2026-10-14T12:00:00Z",
        "2026-10-14 12:00:00+00:00",
        "2026-10-14T12:00:00+07:00",
    ],
)
def test_exact_sql_utc_semantic_refusal(fixture: Fixture, name: str, value: str) -> None:
    with pytest.raises(V11LifeError, match=r"^time$"):
        restored(fixture, {name: value})


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("activity_started_at", "2026-10-14T11:59:00+00:00"),
        ("activity_until", BORN),
        ("last_tick_at", "2026-10-14T12:11:00+00:00"),
        ("last_updated_at", BORN),
        ("needs_at", BORN),
        ("needs_at", "2026-10-14T12:11:00+00:00"),
        ("decision_due_since", "2026-10-14T11:59:00+00:00"),
        ("critical_since", "2026-10-14T12:11:00+00:00"),
    ],
)
def test_temporal_order(fixture: Fixture, name: str, value: str) -> None:
    with pytest.raises(V11LifeError):
        restored(fixture, {name: value})


def test_utc_text_and_nullable_needs_preserved_without_normalization(fixture: Fixture) -> None:
    text = "2026-10-14T12:08:00.000000+00:00"
    life = restored(fixture, {"needs_at": text})
    assert life.record.needs_at == text
    assert restored(fixture, {"needs_at": None}).record.needs_at is None


@pytest.mark.parametrize(
    "name", ["reaction_kind", "reaction_variant", "reaction_started_at", "reaction_until"]
)
def test_reaction_bundle(fixture: Fixture, name: str) -> None:
    with pytest.raises(V11LifeError, match=r"^reaction$"):
        restored(fixture, {name: None})


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("reaction_kind", "unknown"),
        ("reaction_variant", -1),
        ("reaction_variant", 3),
        ("reaction_started_at", "2026-10-14T11:59:00+00:00"),
        ("reaction_started_at", "2026-10-14T12:10:01+00:00"),
        ("reaction_until", BORN),
    ],
)
def test_reaction_domain_rules(fixture: Fixture, name: str, value: object) -> None:
    with pytest.raises(V11LifeError, match=r"^reaction$"):
        restored(fixture, {name: value})


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("active_goal_id", 99),
        ("goal_counter", 2),
        ("suspended_goal_id", 3),
        ("suspended_action", None),
        ("suspended_goal_id", None),
        ("suspended_action", "unknown"),
    ],
)
def test_goals_and_suspension(fixture: Fixture, name: str, value: object) -> None:
    with pytest.raises(V11LifeError):
        restored(fixture, {name: value})


@pytest.mark.parametrize(
    ("index", "value"),
    [
        (0, True),
        (1, 2),
        (2, 13),
        (3, "unknown"),
        (4, ""),
        (5, "unknown"),
        (6, 999),
        (7, "2026-10-14T11:59:00+00:00"),
        (8, "2026-10-14T12:02:00+00:00"),
    ],
)
def test_goal_fact_fields(fixture: Fixture, index: int, value: object) -> None:
    goals = list(fixture.context["goal_rows"])
    row = list(goals[0])
    row[index] = value
    goals[0] = tuple(row)
    with pytest.raises(V11LifeError):
        restored(fixture, goal_rows=tuple(goals))


def test_goal_duplicates_missing_and_decision_references(fixture: Fixture) -> None:
    rows = fixture.context["goal_rows"]
    for goals in [(), (*rows, rows[0]), [*rows], (None,)]:
        with pytest.raises(V11LifeError):
            restored(fixture, goal_rows=goals)
    for decisions in [(), ((8, 2, 4),), ((8, 1, 13),), ((8, 1, 4), (8, 1, 4)), ((True, 1, 4),)]:
        with pytest.raises(V11LifeError):
            restored(fixture, decisions=decisions)
    assert restored(fixture, goal_rows=tuple(reversed(rows))) == restored(fixture)


@pytest.mark.parametrize("name", ["task_tool", "task_target", "task_title", "task_category"])
def test_task_bundle(fixture: Fixture, name: str) -> None:
    with pytest.raises(V11LifeError, match=r"^task$"):
        restored(fixture, {name: None})


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("task_tool", "unknown"),
        ("task_tool", "reader"),
        ("task_target", "path/to/file"),
        ("task_target", "a" * 60 + ":x"),
        ("task_title", "x" * 81),
        ("task_title", "line\n"),
        ("task_category", ""),
        ("task_category", "x" * 41),
    ],
)
def test_task_rules_and_sql_bounds(fixture: Fixture, name: str, value: object) -> None:
    with pytest.raises(V11LifeError, match=r"^task$"):
        restored(fixture, {name: value})


@pytest.mark.parametrize(
    "rows",
    [
        None,
        [],
        ((2, 0, "pet", UPDATED),),
        ((1, True, "pet", UPDATED),),
        ((1, 1, "pet", UPDATED),),
        ((1, 0, "unknown", UPDATED),),
        ((1, 0, "pet", BORN),),
        ((1, 0, "pet", "2026-10-14T12:11:00+00:00"),),
    ],
)
def test_ledger_identity_position_window_and_kind(fixture: Fixture, rows: Any) -> None:
    with pytest.raises(V11LifeError):
        restored(fixture, ledger_rows=rows)


def test_ledger_order_count_and_duplicates(fixture: Fixture) -> None:
    rows = fixture.context["ledger_rows"]
    for ledger in [
        rows * 2,
        ((1, 0, "pet", UPDATED), (1, 1, "greet", "2026-10-14T12:09:00+00:00")),
        tuple((1, i, "pet", UPDATED) for i in range(11)),
    ]:
        with pytest.raises(V11LifeError, match=r"^ledger$"):
            restored(fixture, ledger_rows=ledger)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("maple_id", 2),
        ("revision", 0),
        ("layout_revision", 2),
        ("point_host", "desk.computer"),
        ("point_id", "desktop"),
        ("point_id", ""),
        ("point_host", "x" * 129),
        ("tx", -1),
        ("tx", 44),
        ("ty", 26),
        ("tx", 0),
        ("tx", 35),
    ],
)
def test_identity_revision_grid_and_reference_mismatches(
    fixture: Fixture, name: str, value: object
) -> None:
    with pytest.raises(V11LifeError):
        restored(fixture, {name: value})


def test_capability_is_not_merely_a_valid_point(fixture: Fixture) -> None:
    with pytest.raises(V11LifeError, match=r"^layout$"):
        restored(fixture, {"activity": "sleep"})
    bad = replace(fixture.context["keys"], layout_point=fixture.context["keys"].layout_point[1:])
    with pytest.raises(V11LifeError, match=r"^layout$"):
        restored(fixture, keys=bad)


@pytest.mark.parametrize(
    ("activity", "host", "point", "tx", "ty"),
    [
        ("idle", "idle.hall_center", "idle", 21, 15),
        ("walk", "idle.hall_center", "idle", 21, 15),
        ("sleep", "bed.bedroom", "sleep", 3, 4),
        ("read", "bookshelf.library_1", "front_l", 21, 4),
        ("write", "desk.writing", "chair", 34, 5),
        ("observe_server", "desk.computer", "operator", 39, 5),
        ("rest", "sofa.living", "seat", 12, 6),
        ("think", "window.living", "view", 18, 3),
    ],
)
def test_all_existing_activity_capability_and_room_contracts(
    fixture: Fixture, activity: str, host: str, point: str, tx: int, ty: int
) -> None:
    context = fixture.context
    layout = validate_layout_snapshot(
        (fixture.row,),
        ((1, 1),),
        (LifeReference(1, 1, host, point),),
        context["keys"],
        snapshots=(fixture.snapshot,),
        contexts=((1, fixture.validation_context),),
    )
    life = restored(
        fixture,
        dict(
            activity=activity,
            point_host=host,
            point_id=point,
            tx=tx,
            ty=ty,
            task_tool=None,
            task_target=None,
            task_title=None,
            task_category=None,
        ),
        layout=layout,
    )
    assert life.activity.value == activity and (life.record.tx, life.record.ty) == (tx, ty)


def traveling(fixture: Fixture, travel: Travel, **changes: object) -> CanonicalLife:
    # Expected canonical route text is independently specified for the simple
    # one-step fixture; Entry/zero-step use the approved existing encoder.
    text = travel_codec.encode_travel_path(
        travel,
        walkability=validate_safe_layout(
            fixture.context["layout"].active.layout.world,
            fixture.context["layout"].active.layout.catalog,
        ),
    )
    values: dict[str, object] = dict(
        route_path=text,
        route_departed_at=travel.departed_at.isoformat(),
        route_from_activity="read",
        route_arrives_at=travel.arrives_at.isoformat(),
        activity_started_at=travel.arrives_at.isoformat(),
        tx=travel.route.origin.tx,
        ty=travel.route.origin.ty,
    )
    values.update(changes)
    return restored(fixture, values, travel=travel)


def one_step(departure: str = UPDATED) -> Travel:
    return Travel(
        Route((Waypoint(34, 6, 0), Waypoint(34, 5, 1))), datetime.fromisoformat(departure), 317
    )


def test_exact_travel_envelope_and_restart_time_derivation(fixture: Fixture) -> None:
    travel = one_step()
    life = traveling(fixture, travel)
    assert (
        life.record.route_path
        == '{"entry":null,"format_version":1,"ms_per_step":317,"waypoints":[[34,6,0],[34,5,1]]}'
    )
    assert life.record.route_arrives_at == "2026-10-14T12:10:00.317000+00:00"
    assert life_fields(life.record) == life_fields(
        reconstruct_life(life_fields(life.record), **(fixture.context | {"travel": travel})).record
    )
    for delta, expected in [
        (timedelta(microseconds=-1), "pending"),
        (timedelta(0), "walking"),
        (timedelta(microseconds=317000), "performing"),
        (timedelta(seconds=1), "performing"),
    ]:
        assert (
            life.travel is not None and life.travel.phase_at(travel.departed_at + delta) == expected
        )
    assert traveling(fixture, travel, last_updated_at="2026-10-14T12:10:01+00:00").travel == travel


def test_pending_zero_step_preserves_original_future_arrival(fixture: Fixture) -> None:
    travel = Travel(
        Route((Waypoint(34, 5, 0),)), datetime.fromisoformat("2026-10-14T12:15:00+00:00"), 317
    )
    life = traveling(fixture, travel)
    assert life.record.last_updated_at == UPDATED
    assert (
        life.record.route_departed_at
        == life.record.route_arrives_at
        == life.record.activity_started_at
        == "2026-10-14T12:15:00+00:00"
    )
    assert (
        life.travel == travel and life.travel.phase_at(datetime.fromisoformat(UPDATED)) == "pending"
    )


@pytest.mark.parametrize("endpoint", ["a", "b"])
def test_temporal_entry_exact_microseconds(fixture: Fixture, endpoint: str) -> None:
    selected = Tile(34, 6) if endpoint == "a" else Tile(34, 5)
    travel = Travel(
        Route((Waypoint(34, 6, 0), Waypoint(34, 5, 1)))
        if endpoint == "a"
        else Route((Waypoint(34, 5, 0),)),
        datetime.fromisoformat(UPDATED),
        317,
        Entry(EdgeStart(Tile(34, 6), Tile(34, 5), 123457, 317000), selected),
    )
    life = traveling(fixture, travel)
    assert life.record.tx == selected.tx and life.record.ty == selected.ty
    expected = (
        "2026-10-14T12:10:00.440457+00:00"
        if endpoint == "a"
        else "2026-10-14T12:10:00.193543+00:00"
    )
    assert life.record.route_arrives_at == expected
    assert life.travel == travel


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("route_path", "private-untrusted-text"),
        ("route_path", None),
        ("route_departed_at", None),
        ("route_from_activity", None),
        ("route_arrives_at", None),
        ("route_from_activity", "unknown"),
        ("route_arrives_at", "2026-10-14T12:10:01+00:00"),
        ("activity_started_at", UPDATED),
        ("tx", 33),
    ],
)
def test_travel_bundle_timing_origin_and_payload_refusal(
    fixture: Fixture, name: str, value: object
) -> None:
    with pytest.raises(V11LifeError):
        traveling(fixture, one_step(), **{name: value})


def test_future_nonzero_departure_and_wrong_destination_refused(fixture: Fixture) -> None:
    with pytest.raises(V11LifeError, match=r"^time$"):
        traveling(fixture, one_step("2026-10-14T12:11:00+00:00"))
    wrong = Travel(
        Route((Waypoint(34, 5, 0), Waypoint(34, 6, 1))), datetime.fromisoformat(UPDATED), 317
    )
    with pytest.raises(V11LifeError, match=r"^travel$"):
        traveling(fixture, wrong)
    with pytest.raises(V11LifeError, match=r"^travel$"):
        restored(fixture, travel=one_step())


def test_supplied_travel_required_even_with_four_present_columns(fixture: Fixture) -> None:
    life = traveling(fixture, one_step())
    with pytest.raises(V11LifeError, match=r"^travel$"):
        reconstruct_life(life_fields(life.record), **fixture.context)


def test_historical_catalog_and_layout_revision_remain_explicit(fixture: Fixture) -> None:
    types = json.loads(fixture.snapshot.canonical_types)
    types[0]["states"].append("historical_test_variant")
    newer = CatalogSnapshot(2, canonical(types))
    document = encode_layout_document(
        fixture.wire,
        catalog_version=2,
        catalog_hash=newer.catalog_hash,
        snapshots=(newer,),
        context=fixture.validation_context,
    )
    second = RevisionRow(
        2,
        UPDATED,
        "paolo",
        1,
        2,
        newer.catalog_hash,
        document.canonical_bytes.decode(),
        document.validation_digest,
    )
    keys = project_layout_keys(document, 2)
    snapshot = validate_layout_snapshot(
        (second, fixture.row),
        ((1, 2),),
        (LifeReference(1, 2, "desk.writing", "chair"),),
        keys,
        snapshots=(newer, fixture.snapshot),
        contexts=((1, fixture.validation_context), (2, fixture.validation_context)),
    )
    life = restored(fixture, {"layout_revision": 2}, layout=snapshot, keys=keys)
    assert life.layout.active.layout.catalog_hash == newer.catalog_hash
    assert life.record.layout_revision == 2 and life.record.revision == 12
    assert restored(fixture).layout.active.layout.catalog_hash == fixture.snapshot.catalog_hash
    with pytest.raises(V11LifeError, match=r"^layout$"):
        restored(fixture, layout=snapshot, keys=keys)


def histories(life: CanonicalLife) -> tuple[HistoryImage, HistoryImage]:
    source = []
    target = []
    for schema in HISTORY_SCHEMA:
        rows: tuple[tuple[Any, ...], ...] = ()
        if schema.name == "maple":
            rows = (life.identity_row,)
        elif schema.name == "interaction_ledger":
            rows = life.ledger_rows
        elif schema.name == "goal":
            rows = life.goal_rows
        elif schema.name == "decision":
            rows = tuple(
                tuple(
                    id
                    if col == "id"
                    else maple
                    if col == "maple_id"
                    else revision
                    if col == "revision"
                    else None
                    for col in schema.columns
                )
                for id, maple, revision in life.decisions
            )
        elif schema.name == "timeline_event":
            rows = ((1, 1, 1, None, "born", BORN, '{"name":"Maple"}'),)
        source.append(TableImage(schema.name, schema.columns, rows))
        target.append(
            TableImage(
                schema.name,
                schema.columns + (DECISION_REFS if schema.name == "decision" else ()),
                tuple((*row, None, None, None) for row in rows)
                if schema.name == "decision"
                else rows,
            )
        )
    sequences = (("decision", 100), ("timeline_event", 99))
    return HistoryImage(tuple(source), sequences), HistoryImage(tuple(target), sequences)


def test_full_record_and_existing_history_conservation(fixture: Fixture) -> None:
    first, second = restored(fixture), restored(fixture)
    source, target = histories(first)
    validate_restart_equivalence(first, second, source_history=source, target_history=target)
    changed = restored(fixture, {"tick_counter": 6})
    with pytest.raises(V11LifeError, match=r"^conservation$"):
        validate_restart_equivalence(first, changed, source_history=source, target_history=target)
    with pytest.raises(V11LifeError, match=r"^conservation$"):
        validate_restart_equivalence(
            first,
            second,
            source_history=source,
            target_history=replace(target, sequences=(("decision", 99), ("timeline_event", 99))),
        )


def test_conserved_fact_row_order_does_not_change_equivalence(fixture: Fixture) -> None:
    life = restored(fixture)
    source, target = histories(life)
    target = replace(
        target,
        tables=tuple(
            replace(item, rows=tuple(reversed(item.rows))) for item in reversed(target.tables)
        ),
        sequences=tuple(reversed(target.sequences)),
    )
    validate_restart_equivalence(life, life, source_history=source, target_history=target)


@pytest.mark.parametrize(
    "payload",
    [
        '{"name":"Other"}',
        '{"name":"Maple","name":"Maple"}',
        '{"name":"Maple","extra":1}',
        "private-malformed",
    ],
)
def test_conserved_birth_payload_must_match_identity(fixture: Fixture, payload: str) -> None:
    life = restored(fixture)
    source, target = histories(life)

    def altered(image: HistoryImage) -> HistoryImage:
        return replace(
            image,
            tables=tuple(
                replace(item, rows=((1, 1, 1, None, "born", BORN, payload),))
                if item.name == "timeline_event"
                else item
                for item in image.tables
            ),
        )

    with pytest.raises(V11LifeError, match=r"^conservation$"):
        validate_restart_equivalence(
            life, life, source_history=altered(source), target_history=altered(target)
        )


@pytest.mark.parametrize(
    "table", ["maple", "interaction_ledger", "goal", "decision", "timeline_event"]
)
def test_conserved_history_must_match_life_not_just_itself(fixture: Fixture, table: str) -> None:
    life = restored(fixture)
    source, target = histories(life)

    def remove(image: HistoryImage) -> HistoryImage:
        return replace(
            image,
            tables=tuple(
                replace(item, rows=()) if item.name == table else item for item in image.tables
            ),
        )

    with pytest.raises(V11LifeError, match=r"^conservation$"):
        validate_restart_equivalence(
            life, life, source_history=remove(source), target_history=remove(target)
        )


def test_untrusted_travel_decoder_and_io_never_used(
    fixture: Fixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    travel = one_step()
    life = traveling(fixture, travel)
    arguments = fixture.context | {"travel": travel}

    def forbidden(*args: object, **kwargs: object) -> NoReturn:
        raise AssertionError("unexpected side effect or untrusted Travel decoding")

    monkeypatch.setattr(travel_codec, "decode_travel_path", forbidden)
    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(sqlite3, "connect", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    assert reconstruct_life(life_fields(life.record), **arguments) == life


def test_dependency_isolation_and_safe_errors(fixture: Fixture) -> None:
    source = Path(life_record.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith(
                ("maplegotchi.runtime", "maplegotchi.storage", "maplegotchi.api")
            )
        if isinstance(node, ast.Import):
            assert all(alias.name in {"json", "math", "re"} for alias in node.names)
    with pytest.raises(V11LifeError) as error:
        restored(fixture, {"activity": "private-secret-marker"})
    assert error.value.args == ("type",) and error.value.__suppress_context__


def test_memory_error_not_suppressed(fixture: Fixture, monkeypatch: pytest.MonkeyPatch) -> None:
    def exhausted(*args: object, **kwargs: object) -> NoReturn:
        raise MemoryError

    monkeypatch.setattr(life_record, "RngState", exhausted)
    with pytest.raises(MemoryError):
        restored(fixture)
