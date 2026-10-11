"""Synthetic-only v11 rehearsal, preservation, rollback and production isolation gates."""

from __future__ import annotations

import ast
import sqlite3
import sys
from dataclasses import FrozenInstanceError
from datetime import timedelta
from pathlib import Path
from typing import Any, Never, cast

import pytest

from maplegotchi.core.activities import Activity, RoomLocation
from maplegotchi.core.room import POINT_BY_ID
from maplegotchi.core.world.catalog import Category, Owner, Permission
from maplegotchi.core.world.coordinates import Tile
from maplegotchi.core.world.placement import DisplayItem
from maplegotchi.core.world.walkability import validate_safe_layout
from maplegotchi.runtime.clock import FakeClock
from maplegotchi.storage.db import (
    PreMigrationSnapshotError,
    open_life_database,
    take_pre_migration_snapshot,
)
from maplegotchi.storage.errors import MigrationError, SchemaTooNewError
from maplegotchi.storage.migrations import (
    APPLICATION_ID,
    MIGRATIONS,
    latest_version,
    schema_version,
)
from maplegotchi.storage.repositories import LifeRepository
from tests.persistence_support import BIRTH, open_runtime
from tests.rehearsal import v11
from tests.rehearsal.fixtures import Scenario, SyntheticLife, synthetic_life
from tests.rehearsal.v11 import Failure, capture, load_candidate, rehearse, state_row

AT = BIRTH + timedelta(days=90)
EXPECTED = {
    "bed.side": ("bed.bedroom", "sleep", 3, 4),
    "sofa.seat": ("sofa.living", "seat", 12, 6),
    "bookshelf.front": ("bookshelf.library_1", "front_l", 21, 4),
    "window.view": ("window.living", "view", 18, 3),
    "writing_desk.chair": ("desk.writing", "chair", 34, 5),
    "computer_desk.chair": ("desk.computer", "operator", 39, 5),
    "open_area.west": ("idle.hall_west", "idle", 10, 15),
    "open_area.center": ("idle.hall_center", "idle", 21, 15),
    "open_area.east": ("idle.hall_east", "idle", 32, 15),
}
SCENARIOS = tuple(Scenario(kind) for kind in ("fresh", "demo", "aged", "active", "suspended"))
SCENARIOS += tuple(
    Scenario("point", p.id, p.location, p.allowed_actions[0]) for p in POINT_BY_ID.values()
)
NULLS = (
    (RoomLocation.BED, Activity.SLEEP),
    (RoomLocation.SOFA, Activity.REST),
    (RoomLocation.BOOKSHELF, Activity.READ),
    (RoomLocation.WINDOW, Activity.THINK),
    (RoomLocation.DESK, Activity.WRITE),
    (RoomLocation.TERMINAL, Activity.OBSERVE_SERVER),
    (RoomLocation.RUG, Activity.IDLE),
    (RoomLocation.RUG, Activity.WALK),
)
SCENARIOS += tuple(Scenario("null", location=loc, activity=a) for loc, a in NULLS)
SCENARIOS += (Scenario("walking", "bed.side", RoomLocation.BED, Activity.SLEEP),)


def schema(conn: sqlite3.Connection) -> tuple[tuple[Any, ...], ...]:
    return tuple(conn.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY name"))


@pytest.mark.parametrize(
    "scenario", SCENARIOS, ids=lambda s: f"{s.kind}-{s.point or s.location}-{s.activity}"
)
def test_round_trip_preserves_every_row_and_continuity(scenario: Scenario) -> None:
    with synthetic_life(scenario) as life:
        before = capture(life.conn)
        old = state_row(life.conn)
        source = LifeRepository(life.conn).load()
        point = source.state.point.id
        result = rehearse(life, AT)
        candidate = load_candidate(life)
        after = capture(life.conn)
        assert schema_version(life.conn) == 11
        assert life.conn.execute("PRAGMA application_id").fetchone()[0] == APPLICATION_ID
        assert life.conn.execute("PRAGMA foreign_key_check").fetchall() == []
        assert life.conn.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
        for table, rows in before.items():
            if table != "life_state":
                assert after[table] == rows, table
        mapped = state_row(life.conn)
        for key, value in old.items():
            if key not in {"location", "point_id", "route_path", "route_departed_at"}:
                assert mapped[key] == value, key
        host, local, tx, ty = EXPECTED[point]
        assert (candidate.host, candidate.point, candidate.tile) == (host, local, Tile(tx, ty))
        assert candidate.identity == source.state.identity
        assert candidate.needs == source.state.needs
        assert candidate.rng == source.state.rng
        assert len(candidate.world.regions) == 8 and len(candidate.world.doors) == 7
        assert len(validate_safe_layout(candidate.world, candidate.catalog).walkable) == 431
        assert candidate.region
        assert after["world_event"] == () and after["display_placement"] == ()
        assert len(result.validation_digest) == 64
        if source.state.route:
            if scenario.kind == "walking":
                assert source.state.route.departed_at < source.state.last_updated_at
                assert source.state.last_updated_at < source.state.route.arrives_at
            assert candidate.travel is not None
            assert candidate.travel.route.total_steps == 0
            assert (
                candidate.travel.route.origin
                == candidate.travel.route.destination
                == candidate.tile
            )
            assert candidate.travel.arrives_at == source.state.route.arrives_at
            assert candidate.travel.departed_at == source.state.route.arrives_at
        else:
            assert candidate.travel is None
        backup_path = life.data_dir.path(result.backup)
        with sqlite3.connect(backup_path) as backup:
            assert schema_version(backup) == 10
            assert capture(backup) == before
            assert backup.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
            assert backup.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
            assert backup.execute("PRAGMA application_id").fetchone()[0] == APPLICATION_ID
            assert LifeRepository(backup).load() == source
        if sys.platform != "win32":
            assert backup_path.stat().st_mode & 0o777 == 0o600
        with pytest.raises(FrozenInstanceError):
            candidate.tile = Tile(1, 1)  # type: ignore[misc]
        with pytest.raises(MigrationError, match="unconverted"):
            rehearse(life, AT)


@pytest.mark.parametrize("kind", ("fresh", "demo", "aged", "active", "suspended"))
def test_repeated_synthetic_fixture_is_deterministic(kind: str) -> None:
    converted = []
    for _ in range(2):
        with synthetic_life(Scenario(kind)) as life:
            rehearse(life, AT)
            converted.append(capture(life.conn))
    assert converted[0] == converted[1]


@pytest.mark.parametrize("failure", tuple(Failure))
@pytest.mark.parametrize("kind", ("fresh", "aged", "suspended", "walking"))
def test_atomic_rollback_and_usable_v10(failure: Failure, kind: str) -> None:
    scenario = Scenario(kind, "bed.side", RoomLocation.BED, Activity.SLEEP)
    with synthetic_life(scenario) as life:
        before, ddl = capture(life.conn), schema(life.conn)
        source = LifeRepository(life.conn).load()
        with pytest.raises(MigrationError):
            rehearse(life, AT, failure)
        assert capture(life.conn) == before
        assert schema(life.conn) == ddl
        assert schema_version(life.conn) == 10
        assert not life.conn.in_transaction
        assert life.conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert LifeRepository(life.conn).load() == source
        backups = list(life.data_dir.root.glob("pre-migration/*.db"))
        if failure is Failure.SNAPSHOT:
            assert not backups
        else:
            assert len(backups) == 1
            with sqlite3.connect(backups[0]) as backup:
                assert capture(backup) == before
        runtime = open_runtime(life.data_dir, FakeClock(source.state.last_updated_at))
        runtime.close()
        assert schema_version(life.conn) == 10


@pytest.mark.parametrize(
    "mutation",
    (
        "PRAGMA user_version=9",
        "PRAGMA user_version=12",
        "PRAGMA application_id=1",
        "DELETE FROM life_state",
        "UPDATE life_state SET point_id='unknown'",
        "UPDATE life_state SET point_id='bed.side'",
        "UPDATE life_state SET route_path='[]'",
        "UPDATE life_state SET activity='unknown'",
        "UPDATE life_state SET mood=999",
        "UPDATE life_state SET last_updated_at='not-a-time'",
    ),
)
def test_invalid_source_refused_without_ddl_or_snapshot(mutation: str) -> None:
    with synthetic_life() as life:
        life.conn.execute("PRAGMA ignore_check_constraints=ON")
        if "life_state" in mutation:
            triggers = life.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='life_state'"
            ).fetchall()
            for (name,) in triggers:
                life.conn.execute(f"DROP TRIGGER {v11.quote(name)}")
        life.conn.execute(mutation)
        life.conn.execute("PRAGMA ignore_check_constraints=OFF")
        before, ddl = capture(life.conn), schema(life.conn)
        with pytest.raises(MigrationError):
            rehearse(life, AT)
        assert capture(life.conn) == before and schema(life.conn) == ddl
        assert not list(life.data_dir.root.glob("pre-migration/*"))


def test_mismatched_route_destination_refused() -> None:
    with synthetic_life(Scenario("walking", "bed.side", RoomLocation.BED, Activity.SLEEP)) as life:
        life.conn.execute("UPDATE life_state SET point_id='sofa.seat',revision=revision+1")
        before = capture(life.conn)
        with pytest.raises(MigrationError):
            rehearse(life, AT)
        assert capture(life.conn) == before


def test_real_snapshot_error_stops_before_conversion(monkeypatch: pytest.MonkeyPatch) -> None:
    with synthetic_life() as life:
        before, ddl = capture(life.conn), schema(life.conn)

        def fail(*args: object, **kwargs: object) -> str:
            raise PreMigrationSnapshotError("synthetic disk failure")

        monkeypatch.setattr(v11, "take_pre_migration_snapshot", fail)
        with pytest.raises(PreMigrationSnapshotError):
            rehearse(life, AT)
        assert capture(life.conn) == before and schema(life.conn) == ddl


@pytest.mark.parametrize(
    "table",
    ("layout_revision", "layout_host", "layout_point", "layout_slot", "layout_room", "world_event"),
)
@pytest.mark.parametrize("operation", ("UPDATE", "DELETE"))
def test_append_only_history(table: str, operation: str) -> None:
    with synthetic_life() as life:
        rehearse(life, AT)
        if table == "world_event":
            life.conn.execute(
                "INSERT INTO world_event(maple_id,type,at,revision,layout_revision,payload) "
                "VALUES (1,'synthetic_check',?,1,1,'{}')",
                (AT.isoformat(),),
            )
        sql = (
            f"DELETE FROM {v11.quote(table)}"  # noqa: S608
            if operation == "DELETE"
            else f"UPDATE {v11.quote(table)} SET "  # noqa: S608
            + ("id=id" if table in {"world_event", "layout_revision"} else "revision=revision")
        )
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            life.conn.execute(sql)


@pytest.mark.parametrize(
    "statement",
    (
        "UPDATE life_state SET activity='bad'",
        "UPDATE life_state SET suspended_action='bad'",
        "UPDATE life_state SET route_from_activity='bad'",
        "UPDATE world_state SET active_revision=99",
        "UPDATE life_state SET point_id='bad'",
        "UPDATE life_state SET point_host='bad'",
        "INSERT INTO layout_room VALUES(1,'bad','bad')",
        "INSERT INTO display_placement VALUES('x','i',1,'bad','bad',1,NULL,NULL)",
    ),
)
def test_candidate_foreign_keys_reject_unknown_values(statement: str) -> None:
    with synthetic_life() as life:
        rehearse(life, AT)
        with pytest.raises(sqlite3.IntegrityError):
            life.conn.execute(
                statement + ",revision=revision+1"
                if statement.startswith("UPDATE life_state")
                else statement
            )


@pytest.mark.parametrize(
    "statement",
    (
        "UPDATE life_state SET activity='sleep'",
        "UPDATE life_state SET tx=0,ty=0",
        "UPDATE life_state SET tx=3,ty=4",
        "UPDATE life_state SET route_path='[[21,15,0],[22,15,99]]'",
        "UPDATE life_state SET route_arrives_at='bad'",
        "UPDATE life_state SET layout_revision=99",
    ),
)
def test_candidate_loader_rejects_invalid_state(statement: str) -> None:
    with synthetic_life() as life:
        rehearse(life, AT)
        life.conn.execute("PRAGMA foreign_keys=OFF")
        life.conn.execute("PRAGMA ignore_check_constraints=ON")
        life.conn.execute(
            statement + ",revision=revision+1"
            if statement.startswith("UPDATE life_state")
            else statement
        )
        with pytest.raises((ValueError, TypeError)):
            load_candidate(life)


def test_display_relationship_uses_existing_contracts() -> None:
    item = DisplayItem(
        "creation.one",
        "creation.small",
        Category.CREATION_DISPLAY,
        Owner.MAPLE,
        (Permission.MAPLE,),
        True,
        True,
        link="artifact:one",
    )
    with synthetic_life() as life:
        rehearse(life, AT)
        life.conn.execute(
            "INSERT INTO display_placement VALUES "
            "('placement.one','creation.one',1,'side_table.library','top',1,?,NULL)",
            (item.link,),
        )
        with pytest.raises(ValueError, match="invalid active"):
            load_candidate(life)
        load_candidate(life, (item,))
        with pytest.raises(sqlite3.IntegrityError):
            life.conn.execute(
                "INSERT INTO display_placement VALUES "
                "('placement.two','creation.one',1,'side_table.library','top',1,NULL,NULL)"
            )
        life.conn.execute("UPDATE display_placement SET active=0")
        load_candidate(life)


@pytest.mark.parametrize(
    "value",
    (
        "/data/maple.db",
        "/opt/maplegotchi/maple.db",
        Path("maple.db"),
        SyntheticLife(object()),
        None,
    ),
)
def test_external_inputs_cannot_enter_rehearsal(value: object) -> None:
    with pytest.raises(ValueError, match="handle"):
        rehearse(cast(SyntheticLife, value), AT)


def test_expired_handle_and_connections_rejected() -> None:
    with synthetic_life() as life:
        with pytest.raises(ValueError):
            rehearse(cast(SyntheticLife, life.conn), AT)
    with pytest.raises(ValueError, match="expired"):
        rehearse(life, AT)


def test_path_replacement_rejected() -> None:
    with synthetic_life() as life:
        path = life.data_dir.root / "maple.db"
        path.rename(path.with_suffix(".original"))
        path.write_bytes(b"not a database")
        with pytest.raises(ValueError, match="changed"):
            rehearse(life, AT)


def no_birth() -> Never:
    raise AssertionError("existing database must never birth replacement state")


def test_shipped_registry_startup_and_too_new_guard() -> None:
    assert latest_version() == MIGRATIONS[-1].version == 10
    with synthetic_life() as life:
        assert schema_version(life.conn) == 10
        connection = open_life_database(life.data_dir, no_birth)
        connection.close()
        assert schema_version(life.conn) == 10
        rehearse(life, AT)
        before = capture(life.conn)
        with pytest.raises(SchemaTooNewError):
            open_life_database(life.data_dir, no_birth)
        with pytest.raises(SchemaTooNewError):
            open_runtime(life.data_dir, FakeClock(AT))
        assert capture(life.conn) == before and schema_version(life.conn) == 11


def test_no_shipped_import_or_deployment_entrypoint() -> None:
    root = Path(__file__).resolve().parents[3]
    for path in (root / "backend/src").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith(("tests", "rehearsal")), path
            elif isinstance(node, ast.Import):
                assert all(not n.name.startswith(("tests", "rehearsal")) for n in node.names), path
        assert "rehearsal" not in path.read_text(encoding="utf-8"), path
    for path in (root / "deploy").rglob("*"):
        if path.is_file() and path.suffix in {".py", ".sh", ".service"}:
            assert "rehearsal" not in path.read_text(encoding="utf-8"), path
    pyproject = (root / "backend/pyproject.toml").read_text(encoding="utf-8")
    assert 'packages = ["src/maplegotchi"]' in pyproject


@pytest.mark.parametrize(
    "column,value",
    (
        ("validation_digest", "0" * 64),
        ("catalog_hash", "0" * 64),
        ("catalog_version", 2),
        ("document", "{}"),
    ),
)
def test_invalid_revision_refused(column: str, value: object) -> None:
    with synthetic_life() as life:
        rehearse(life, AT)
        life.conn.execute("DROP TRIGGER layout_revision_update_immutable")
        life.conn.execute(
            f"UPDATE layout_revision SET {v11.quote(column)}=?",  # noqa: S608
            (value,),
        )
        with pytest.raises(ValueError):
            load_candidate(life)


def test_revision_revert_is_new_record_and_indices_are_authoritative() -> None:
    with synthetic_life() as life:
        rehearse(life, AT)
        original = life.conn.execute("SELECT * FROM layout_revision").fetchone()
        life.conn.execute(
            "INSERT INTO layout_revision SELECT 2,created_at,'paolo',1,catalog_version,"
            "catalog_hash,document,validation_digest FROM layout_revision WHERE id=1"
        )
        assert life.conn.execute("SELECT * FROM layout_revision WHERE id=1").fetchone() == original
        assert life.conn.execute(
            "SELECT base_revision FROM layout_revision WHERE id=2"
        ).fetchone() == (1,)
        life.conn.execute("INSERT INTO layout_host VALUES(1,'unexpected.host')")
        with pytest.raises(ValueError, match="identity index"):
            load_candidate(life)


@pytest.mark.parametrize("table", ("life_state", "journal_entry", "decision"))
def test_activity_lists_replaced_by_lookup_foreign_keys(table: str) -> None:
    with synthetic_life() as life:
        rehearse(life, AT)
        sql = life.conn.execute("SELECT sql FROM sqlite_master WHERE name=?", (table,)).fetchone()[
            0
        ]
        assert "location IN" not in sql
        for name in (
            "activity",
            "route_from_activity",
            "suspended_action",
            "proposed_action",
            "executed_action",
        ):
            assert f"{name} IN" not in sql
        assert any(
            r[2] == "activity_kind"
            for r in life.conn.execute(f"PRAGMA foreign_key_list({v11.quote(table)})")
        )
        assert {r[0] for r in life.conn.execute("SELECT id FROM activity_kind")} == set(Activity)


def test_source_change_after_backup_refuses_conversion(monkeypatch: pytest.MonkeyPatch) -> None:
    original = take_pre_migration_snapshot
    with synthetic_life() as life:

        def changed(*args: Any, **kwargs: Any) -> str:
            result = original(*args, **kwargs)
            life.conn.execute("UPDATE life_state SET revision=revision+1")
            return result

        monkeypatch.setattr(v11, "take_pre_migration_snapshot", changed)
        before_schema = schema(life.conn)
        with pytest.raises(MigrationError):
            rehearse(life, AT)
        assert schema(life.conn) == before_schema
        assert schema_version(life.conn) == 10
        assert state_row(life.conn)["revision"] == 2


@pytest.mark.parametrize("failure", (None, Failure.CONVERSION))
def test_foreign_key_mode_restored(failure: Failure | None) -> None:
    with synthetic_life() as life:
        life.conn.execute("PRAGMA foreign_keys=OFF")
        if failure:
            with pytest.raises(MigrationError):
                rehearse(life, AT, failure)
        else:
            rehearse(life, AT)
        assert life.conn.execute("PRAGMA foreign_keys").fetchone() == (0,)


def test_one_immediate_transaction_and_version_bump_last() -> None:
    with synthetic_life() as life:
        trace: list[str] = []
        life.conn.set_trace_callback(trace.append)
        rehearse(life, AT)
        begins = [i for i, sql in enumerate(trace) if sql.upper().startswith("BEGIN")]
        commits = [i for i, sql in enumerate(trace) if sql.upper() == "COMMIT"]
        assert len(begins) == len(commits) == 1
        assert trace[begins[0]] == "BEGIN IMMEDIATE"
        bump = trace.index("PRAGMA user_version=11")
        assert begins[0] < bump < commits[0]
        assert trace[bump + 1] == "COMMIT"
        assert any(sql.startswith("PRAGMA foreign_key_check") for sql in trace[begins[0] : bump])


@pytest.mark.parametrize("value", ("/data/maple.db", "/opt/maplegotchi", Path("external.db")))
def test_fixture_factory_rejects_external_path(value: object) -> None:
    with pytest.raises(ValueError, match="no paths"):
        with synthetic_life(cast(Scenario, value)):
            pytest.fail("external path was accepted")
