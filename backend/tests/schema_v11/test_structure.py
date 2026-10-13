"""Structural specimens confer no semantic validity or event/payload approval."""

import hashlib
import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from maplegotchi.storage.migrations import MIGRATIONS, latest_version
from tests.schema_v11.declarations import (
    IMMUTABLE,
    NEW_TABLES,
    SOURCE_SHA256,
    V10_OBJECTS,
    V10_TABLES,
    fresh_database,
    target_tables,
)

AT = "2026-10-13T00:00:00+00:00"
HASH = "a" * 64
REVISION: dict[str, object] = dict(
    id=1,
    created_at=AT,
    author="migration",
    base_revision=None,
    catalog_version=1,
    catalog_hash=HASH,
    document="{}",
    validation_digest=HASH,
)
LIFE: dict[str, object] = dict(
    maple_id=1,
    revision=1,
    mood=50,
    energy=50,
    curiosity=50,
    social=50,
    activity="idle",
    activity_started_at=AT,
    activity_until=AT,
    last_tick_at=AT,
    last_updated_at=AT,
    tick_counter=0,
    interaction_counter=0,
    point_id="point",
    layout_revision=1,
    point_host="host",
    tx=0,
    ty=0,
)
DECISION: dict[str, object] = dict(
    id=1,
    maple_id=1,
    revision=1,
    at=AT,
    trigger="no_plan",
    director_kind="rule",
    director_name="synthetic",
    director_version="1",
    context_summary="specimen",
    verdict="accepted",
)
JOURNAL: dict[str, object] = dict(
    id=1,
    maple_id=1,
    revision=1,
    created_at=AT,
    category="daily_life",
    trigger_kind="activity",
    topic="synthetic",
    text="storage specimen",
    importance="normal",
    brain_kind="rule",
    brain_name="synthetic",
    brain_version="1",
    template_id="synthetic",
    activity="idle",
    expression="calm",
)
# Negative storage/mutation probe only. Never enabled, dispatched or domain-serialized.
NEGATIVE_EVENT: dict[str, object] = dict(
    id=1, maple_id=1, type="negative-storage-probe", at=AT, revision=1, payload="{}"
)
ROWS: dict[str, dict[str, object]] = {
    "activity_kind": dict(id="probe"),
    "room_kind": dict(id="probe"),
    "layout_revision": REVISION | dict(id=2, base_revision=1),
    "world_state": dict(id=1, active_revision=1),
    "layout_host": dict(revision=1, id="other"),
    "layout_room": dict(revision=1, id="other", kind="hall"),
    "layout_point": dict(revision=1, host_id="host", id="other"),
    "layout_slot": dict(revision=1, host_id="host", id="other"),
    "display_placement": dict(
        id="placement", item_id="item", layout_revision=1, host_id="host", slot_id="slot", active=1
    ),
    "world_event": NEGATIVE_EVENT,
    "life_state": LIFE,
    "decision": DECISION,
    "journal_entry": JOURNAL,
}
EXPECTED_COLUMNS = {
    "activity_kind": "id",
    "room_kind": "id",
    "layout_revision": (
        "id created_at author base_revision catalog_version catalog_hash document validation_digest"
    ),
    "world_state": "id active_revision",
    "layout_host": "revision id",
    "layout_room": "revision id kind",
    "layout_point": "revision host_id id",
    "layout_slot": "revision host_id id",
    "world_event": (
        "id maple_id type at revision layout_revision goal_id action_id "
        "decision_id priority payload"
    ),
    "display_placement": "id item_id layout_revision host_id slot_id active link origin_event",
    "life_state": (
        "maple_id revision mood energy curiosity social activity activity_started_at "
        "activity_until last_tick_at last_updated_at tick_counter interaction_counter "
        "reaction_kind reaction_variant reaction_started_at reaction_until point_id "
        "route_departed_at route_from_activity route_path needs_at decision_counter "
        "action_counter goal_counter action_priority active_goal_id suspended_goal_id "
        "suspended_action decision_due_since critical_since task_tool task_target "
        "task_title task_category layout_revision point_host tx ty route_arrives_at"
    ),
    "journal_entry": (
        "id maple_id revision tick_id created_at category trigger_kind topic text "
        "importance brain_kind brain_name brain_version template_id activity expression"
    ),
    "decision": (
        "id maple_id revision at trigger priority director_kind director_name "
        "director_version context_summary proposed_goal_op proposed_goal_type "
        "proposed_goal_summary proposed_horizon_minutes proposed_abandon_reason "
        "proposed_action proposed_duration_minutes proposed_reason verdict reason_code "
        "clamped executed_by executed_reason goal_id action_id executed_action "
        "executed_point executed_duration_minutes latency_ms executed_layout_revision "
        "executed_point_host executed_point_id"
    ),
}


def insert(db: sqlite3.Connection, table: str, row: dict[str, object]) -> None:
    assert table in ROWS or table == "maple"
    columns = ",".join(row)
    markers = ",".join("?" for _ in row)
    db.execute(f"INSERT INTO {table} ({columns}) VALUES ({markers})", tuple(row.values()))  # noqa: S608


@contextmanager
def seeded_database() -> Iterator[sqlite3.Connection]:
    conn = fresh_database()
    try:
        insert(conn, "maple", dict(id=1, name="Synthetic", born_at=AT, life_seed=HASH))
        conn.executemany(
            "INSERT INTO activity_kind VALUES (?)",
            [
                (s,)
                for s in (
                    "idle",
                    "walk",
                    "sleep",
                    "read",
                    "write",
                    "observe_server",
                    "rest",
                    "think",
                )
            ],
        )
        conn.executemany(
            "INSERT INTO room_kind VALUES (?)",
            [
                (s,)
                for s in (
                    "bedroom",
                    "living",
                    "library",
                    "studio",
                    "hall",
                    "future",
                    "creation",
                    "system",
                )
            ],
        )
        insert(conn, "layout_revision", REVISION)
        conn.execute("INSERT INTO layout_host VALUES (1,'host')")
        conn.execute("INSERT INTO layout_point VALUES (1,'host','point')")
        conn.execute("INSERT INTO layout_slot VALUES (1,'host','slot')")
        conn.commit()
        assert conn.execute("SELECT count(*) FROM world_event").fetchone() == (0,)
        yield conn
    finally:
        conn.close()


@pytest.fixture
def db() -> Iterator[sqlite3.Connection]:
    with seeded_database() as conn:
        yield conn


def fingerprint(db: sqlite3.Connection) -> str:
    objects = db.execute(
        "SELECT type,name,tbl_name,sql FROM sqlite_schema "
        "WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name"
    ).fetchall()
    return hashlib.sha256(json.dumps(objects, separators=(",", ":")).encode()).hexdigest()


def test_shape_and_fingerprint(db: sqlite3.Connection) -> None:
    assert len(NEW_TABLES) == 10
    names = {
        r[1]
        for r in db.execute("PRAGMA table_list")
        if r[1] not in ("sqlite_schema", "sqlite_temp_schema", "sqlite_sequence")
    }
    # Stage A persistence contract §3 inventory + §5 ten new tables.
    assert names == set(
        """
        maple life_state interaction_ledger timeline_event observation journal_entry
        journal_entry_observation journal_state goal decision action_event document tool_use
        memory memory_event daily_reflection conversation_message activity_kind room_kind
        layout_revision world_state layout_host layout_room layout_point layout_slot
        world_event display_placement
    """.split()
    )
    assert sum(len(db.execute(f"PRAGMA table_info({t})").fetchall()) for t in names) == 262
    assert all(r[5] == 1 for r in db.execute("PRAGMA table_list") if r[1] in names)
    for table, columns in EXPECTED_COLUMNS.items():
        info = db.execute(f"PRAGMA table_info({table})").fetchall()
        assert [r[1] for r in info] == columns.split()
        defaults = {r[1]: r[4] for r in info if r[4] is not None}
        assert defaults == (
            dict(
                decision_counter="0",
                action_counter="0",
                goal_counter="0",
                action_priority="'normal'",
            )
            if table == "life_state"
            else {}
        )
    assert fingerprint(db) == EXPECTED_FINGERPRINT
    assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    assert db.execute("PRAGMA integrity_check").fetchone() == ("ok",)


def test_v10_preserved_and_not_activated(db: sqlite3.Connection) -> None:
    source = Path(__file__).parents[2] / "src/maplegotchi/storage/migrations.py"
    assert hashlib.sha256(source.read_bytes()).hexdigest() == SOURCE_SHA256
    assert [m.version for m in MIGRATIONS] == list(range(1, 11))
    assert latest_version() == 10
    assert db.execute("PRAGMA user_version").fetchone() == (0,)
    assert db.execute("PRAGMA application_id").fetchone() == (0,)
    assert db.execute("PRAGMA database_list").fetchall() == [(0, "main", "")]
    targets = target_tables()
    rebuilt = {"life_state", "journal_entry", "decision"}
    assert {t for t in V10_TABLES if targets[t] != V10_TABLES[t]} == rebuilt
    for table in set(V10_TABLES) - rebuilt:
        assert db.execute("SELECT sql FROM sqlite_schema WHERE name=?", (table,)).fetchone()[
            0
        ] == V10_TABLES[table].rstrip(";")
    for sql in V10_OBJECTS:
        assert sql.rstrip(";") in {r[0] for r in db.execute("SELECT sql FROM sqlite_schema")}
    assert db.execute("SELECT count(*) FROM sqlite_schema WHERE type='trigger'").fetchone() == (44,)
    assert db.execute(
        "SELECT count(*) FROM sqlite_schema WHERE type='index' AND sql IS NOT NULL"
    ).fetchone() == (10,)
    for path in source.parents[1].rglob("*.py"):
        assert "tests.schema_v11" not in path.read_text(encoding="utf8")


@pytest.mark.parametrize("table", ROWS)
def test_strict_types_and_nullability(db: sqlite3.Connection, table: str) -> None:
    row = ROWS[table]
    for _, name, kind, required, _, pk in db.execute(f"PRAGMA table_info({table})"):
        with pytest.raises(sqlite3.IntegrityError):
            insert(db, table, row | {name: b"invalid blob"})
        if kind == "INTEGER":
            with pytest.raises(sqlite3.IntegrityError):
                insert(db, table, row | {name: 1.5})
        if required and not (pk and kind == "INTEGER"):
            with pytest.raises(sqlite3.IntegrityError):
                insert(db, table, row | {name: None})
        db.rollback()


@pytest.mark.parametrize(
    ("table", "field", "value"),
    [
        ("layout_revision", "id", 0),
        ("layout_revision", "base_revision", 2),
        ("layout_revision", "base_revision", 0),
        ("layout_revision", "base_revision", 99),
        ("layout_revision", "author", "other"),
        ("layout_revision", "catalog_version", 0),
        ("layout_revision", "catalog_hash", "A" * 64),
        ("layout_revision", "catalog_hash", "g" * 64),
        ("layout_revision", "catalog_hash", "a" * 63),
        ("layout_revision", "validation_digest", "f" * 65),
        ("layout_revision", "created_at", "not-UTC"),
        ("layout_revision", "document", "{"),
        ("layout_revision", "document", '"' + "é" * 131072 + '"'),
        ("world_state", "id", 2),
        ("world_state", "active_revision", 99),
        ("layout_host", "revision", 99),
        ("layout_room", "kind", "unknown"),
        ("layout_point", "host_id", "unknown"),
        ("layout_slot", "revision", 2),
        ("display_placement", "active", 2),
        ("display_placement", "origin_event", 99),
        ("display_placement", "slot_id", "missing"),
        ("display_placement", "layout_revision", 2),
        ("life_state", "tx", 44),
        ("life_state", "tx", -1),
        ("life_state", "ty", 26),
        ("life_state", "activity", "unknown"),
        ("life_state", "point_id", "unknown"),
        ("life_state", "reaction_kind", "pet_happy"),
        ("life_state", "suspended_action", "idle"),
        ("life_state", "route_arrives_at", AT),
        ("life_state", "route_path", "{}"),
        ("life_state", "mood", 101),
        ("life_state", "tick_counter", -1),
        ("life_state", "task_tool", "shell"),
        ("life_state", "task_title", "x" * 81),
        ("journal_entry", "activity", "unknown"),
        ("journal_entry", "text", "two\nlines"),
        ("decision", "proposed_action", "unknown"),
        ("decision", "executed_action", "unknown"),
        ("decision", "executed_layout_revision", 1),
        ("decision", "latency_ms", -1),
        ("decision", "executed_point", "x" * 41),
        # Negative storage tests, not accepted event contracts.
        ("world_event", "id", 0),
        ("world_event", "maple_id", 99),
        ("world_event", "type", ""),
        ("world_event", "payload", "{"),
        ("world_event", "at", "bad"),
        ("world_event", "revision", 0),
        ("world_event", "layout_revision", 99),
        ("world_event", "goal_id", 99),
        ("world_event", "decision_id", 99),
        ("world_event", "action_id", -1),
        ("world_event", "priority", "bad"),
    ],
    ids=lambda value: str(value)[:60],
)
def test_invalid_storage_rows(
    db: sqlite3.Connection, table: str, field: str, value: object
) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        insert(db, table, ROWS[table] | {field: value})
    assert db.execute("SELECT count(*) FROM world_event").fetchone() == (0,)


# Stage A §5 K fields. Integer-only IDs are deliberately absent: their six
# former (empty/129-character) cases did not exercise a text identifier.
IDENTIFIER_FIELDS = {
    "activity_kind": ("id",),
    "room_kind": ("id",),
    "layout_host": ("id",),
    "layout_room": ("id", "kind"),
    "layout_point": ("host_id", "id"),
    "layout_slot": ("host_id", "id"),
    "display_placement": ("id", "item_id", "host_id", "slot_id"),
}


@pytest.mark.parametrize("table", IDENTIFIER_FIELDS)
@pytest.mark.parametrize("value", ["", "x" * 129])
def test_world_identifier_bounds(db: sqlite3.Connection, table: str, value: str) -> None:
    fields = {r[1] for r in db.execute(f"PRAGMA table_info({table})")}
    assert IDENTIFIER_FIELDS[table]
    assert set(IDENTIFIER_FIELDS[table]) <= fields
    for field in IDENTIFIER_FIELDS[table]:
        with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
            insert(db, table, ROWS[table] | {field: value})


@pytest.mark.parametrize("table", (*IMMUTABLE, "journal_entry", "decision"))
@pytest.mark.parametrize("operation", ["UPDATE", "DELETE"])
def test_immutable_mutation_refusal(db: sqlite3.Connection, table: str, operation: str) -> None:
    # Event mutation probe exists only in this rolled-back negative storage transaction.
    if table not in ("layout_revision", "layout_host", "layout_point", "layout_slot"):
        insert(db, table, ROWS[table])
    before = db.execute(f"SELECT * FROM {table}").fetchall()  # noqa: S608
    field = db.execute(f"PRAGMA table_info({table})").fetchone()[1]
    sql = f"UPDATE {table} SET {field}={field}" if operation == "UPDATE" else f"DELETE FROM {table}"  # noqa: S608 -- fixed internal identifiers
    with pytest.raises(sqlite3.IntegrityError, match=r"append.only|immutable"):
        db.execute(sql)
    assert db.execute(f"SELECT * FROM {table}").fetchall() == before  # noqa: S608
    db.rollback()
    assert db.execute("SELECT count(*) FROM world_event").fetchone() == (0,)


def test_references_uniqueness_and_history(db: sqlite3.Connection) -> None:
    insert(db, "life_state", LIFE)
    insert(db, "decision", DECISION | dict(executed_point="unchanged.legacy", goal_id=999))
    assert db.execute(
        "SELECT executed_point,executed_layout_revision,executed_point_host,"
        "executed_point_id FROM decision"
    ).fetchone() == ("unchanged.legacy", None, None, None)
    with pytest.raises(sqlite3.IntegrityError):
        insert(
            db,
            "decision",
            DECISION
            | dict(
                id=2,
                executed_layout_revision=1,
                executed_point_host="wrong",
                executed_point_id="point",
            ),
        )
    insert(
        db,
        "decision",
        DECISION
        | dict(
            id=2, executed_layout_revision=1, executed_point_host="host", executed_point_id="point"
        ),
    )
    insert(db, "world_state", ROWS["world_state"])
    with pytest.raises(sqlite3.IntegrityError):
        insert(db, "world_state", ROWS["world_state"])
    insert(db, "display_placement", ROWS["display_placement"])
    with pytest.raises(sqlite3.IntegrityError):
        insert(db, "display_placement", ROWS["display_placement"] | dict(id="second"))
    insert(db, "display_placement", ROWS["display_placement"] | dict(id="inactive", active=0))
    insert(db, "display_placement", ROWS["display_placement"] | dict(id="other", item_id="other"))
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("UPDATE display_placement SET active=1 WHERE id='inactive'")
    db.execute("UPDATE display_placement SET active=0 WHERE id='placement'")
    db.execute("UPDATE display_placement SET active=1 WHERE id='inactive'")
    insert(db, "layout_room", ROWS["layout_room"])
    for table, token in (("activity_kind", "idle"), ("room_kind", "hall")):
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(f"DELETE FROM {table} WHERE id=?", (token,))  # noqa: S608
    insert(db, "layout_host", dict(revision=1, id="é" * 128))
    insert(db, "layout_host", dict(revision=1, id="HOST"))


def test_document_exact_byte_cap(db: sqlite3.Connection) -> None:
    text = '"' + "é" * 131071 + '"'
    assert len(text.encode()) == 262144
    insert(db, "layout_revision", REVISION | dict(id=2, base_revision=1, document=text))
    assert db.execute(
        "SELECT length(CAST(document AS BLOB)) FROM layout_revision WHERE id=2"
    ).fetchone() == (262144,)


@pytest.mark.parametrize("fail", [False, True])
def test_atomic_revision_transaction(db: sqlite3.Connection, fail: bool) -> None:
    insert(db, "life_state", LIFE)
    insert(db, "world_state", ROWS["world_state"])
    db.commit()
    try:
        with db:
            insert(db, "layout_revision", ROWS["layout_revision"])
            insert(db, "layout_host", dict(revision=2, id="host"))
            insert(db, "layout_point", dict(revision=2, host_id="host", id="point"))
            db.execute("UPDATE world_state SET active_revision=2")
            db.execute("UPDATE life_state SET layout_revision=2,revision=2")
            if fail:
                insert(db, "display_placement", ROWS["display_placement"] | dict(layout_revision=2))
    except sqlite3.IntegrityError:
        assert fail
    expected = 1 if fail else 2
    assert db.execute("SELECT active_revision FROM world_state").fetchone() == (expected,)
    assert db.execute("SELECT layout_revision,revision FROM life_state").fetchone() == (
        expected,
        expected,
    )
    assert db.execute("SELECT count(*) FROM layout_revision").fetchone() == (expected,)
    assert db.execute("SELECT count(*) FROM layout_host WHERE revision=2").fetchone() == (
        0 if fail else 1,
    )
    assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    assert db.execute("SELECT count(*) FROM world_event").fetchone() == (0,)


def test_life_revision_and_counters(db: sqlite3.Connection) -> None:
    insert(db, "life_state", LIFE)
    for sql in (
        "DELETE FROM life_state",
        "UPDATE life_state SET revision=3",
        "UPDATE life_state SET tick_counter=1",
    ):
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(sql)
    db.execute("UPDATE life_state SET revision=2,tick_counter=1,decision_counter=1")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("UPDATE life_state SET revision=3,tick_counter=0")


EXPECTED_FINGERPRINT = "1f3e90186092c906432037daa9356f5759f2bf156f5fee10ff27f7d3260942e5"


@pytest.mark.parametrize("table", NEW_TABLES)
def test_exact_new_table_metadata(db: sqlite3.Connection, table: str) -> None:
    integers = {
        "layout_revision": {"id", "base_revision", "catalog_version"},
        "world_state": {"id", "active_revision"},
        "layout_host": {"revision"},
        "layout_room": {"revision"},
        "layout_point": {"revision"},
        "layout_slot": {"revision"},
        "world_event": {
            "id",
            "maple_id",
            "revision",
            "layout_revision",
            "goal_id",
            "action_id",
            "decision_id",
        },
        "display_placement": {"layout_revision", "active", "origin_event"},
    }
    nullable = {
        "layout_revision": {"base_revision"},
        "world_event": {"layout_revision", "goal_id", "action_id", "decision_id", "priority"},
        "display_placement": {"link", "origin_event"},
    }
    keys = {
        "layout_host": ["revision", "id"],
        "layout_room": ["revision", "id"],
        "layout_point": ["revision", "host_id", "id"],
        "layout_slot": ["revision", "host_id", "id"],
    }
    pk = keys.get(table, ["id"])
    for _, name, kind, required, default, ordinal in db.execute(f"PRAGMA table_info({table})"):
        assert kind == ("INTEGER" if name in integers.get(table, set()) else "TEXT")
        assert ordinal == (pk.index(name) + 1 if name in pk else 0)
        # SQLite INTEGER PRIMARY KEY is non-null by rowid semantics, pragma says 0.
        expected_required = name not in nullable.get(table, set()) and not (
            name == "id" and kind == "INTEGER"
        )
        assert bool(required) == expected_required
        assert default is None
    assert all(
        r[5:7] == ("NO ACTION", "NO ACTION")
        for r in db.execute(f"PRAGMA foreign_key_list({table})")
    )


def test_rebuild_metadata_and_fk_inventory(db: sqlite3.Connection) -> None:
    original = sqlite3.connect(":memory:")
    try:
        for sql in V10_TABLES.values():
            original.execute(sql)
        for table in ("life_state", "decision", "journal_entry"):
            old = {r[1]: r for r in original.execute(f"PRAGMA table_info({table})")}
            new = {r[1]: r for r in db.execute(f"PRAGMA table_info({table})")}
            for name, row in old.items():
                if table == "life_state" and name == "location":
                    assert name not in new
                elif table == "life_state" and name == "point_id":
                    assert new[name][2:] == ("TEXT", 1, None, 0)
                else:
                    assert new[name][2:] == row[2:]
    finally:
        original.close()
    expected = {
        "activity_kind": set(),
        "room_kind": set(),
        "layout_revision": {("base_revision", "layout_revision", "id")},
        "world_state": {("active_revision", "layout_revision", "id")},
        "layout_host": {("revision", "layout_revision", "id")},
        "layout_room": {("revision", "layout_revision", "id"), ("kind", "room_kind", "id")},
        "layout_point": {("revision", "layout_host", "revision"), ("host_id", "layout_host", "id")},
        "layout_slot": {("revision", "layout_host", "revision"), ("host_id", "layout_host", "id")},
        "world_event": {
            ("maple_id", "maple", "id"),
            ("layout_revision", "layout_revision", "id"),
            ("goal_id", "goal", "id"),
            ("decision_id", "decision", "id"),
        },
        "display_placement": {
            ("layout_revision", "layout_slot", "revision"),
            ("host_id", "layout_slot", "host_id"),
            ("slot_id", "layout_slot", "id"),
            ("origin_event", "world_event", "id"),
        },
    }
    for table, refs in expected.items():
        rows = db.execute(f"PRAGMA foreign_key_list({table})").fetchall()
        assert {(r[3], r[2], r[4]) for r in rows} == refs
    for table, fields in {
        "life_state": {"activity", "route_from_activity", "suspended_action"},
        "journal_entry": {"activity"},
        "decision": {"proposed_action", "executed_action"},
    }.items():
        rows = db.execute(f"PRAGMA foreign_key_list({table})").fetchall()
        assert {r[3] for r in rows if r[2] == "activity_kind"} == fields
        if table != "journal_entry":
            prefix = "" if table == "life_state" else "executed_"
            local = "point_host" if table == "life_state" else "executed_point_host"
            expected_group = [
                (prefix + "layout_revision", "revision"),
                (local, "host_id"),
                (prefix + "point_id", "id"),
            ]
            group = sorted((r[1], r[3], r[4]) for r in rows if r[2] == "layout_point")
            assert [(a, b) for _, a, b in group] == expected_group
            assert len({r[0] for r in rows if r[2] == "layout_point"}) == 1


@pytest.mark.parametrize("table", ROWS)
def test_primary_key_refusal(db: sqlite3.Connection, table: str) -> None:
    # Includes a rolled-back negative event storage probe, never an enabled event.
    insert(db, table, ROWS[table])
    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
        insert(db, table, ROWS[table])
    db.rollback()
    assert db.execute("SELECT count(*) FROM world_event").fetchone() == (0,)


def test_import_does_not_open_database(monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib

    from tests.schema_v11 import declarations

    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("test declaration import opened a database")

    monkeypatch.setattr(sqlite3, "connect", forbidden)
    importlib.reload(declarations)


@pytest.mark.parametrize("failed_table", ["maple", "layout_revision"])
def test_seeding_failure_closes_connection(
    monkeypatch: pytest.MonkeyPatch, failed_table: str
) -> None:
    conn = fresh_database()
    original_insert = insert

    def injected_insert(db: sqlite3.Connection, table: str, row: dict[str, object]) -> None:
        if table == failed_table:
            raise sqlite3.IntegrityError("synthetic seeding failure")
        original_insert(db, table, row)

    # Temporary test patches are restored by pytest; no shared connection survives.
    monkeypatch.setattr(__name__ + ".fresh_database", lambda: conn)
    monkeypatch.setattr(__name__ + ".insert", injected_insert)
    with pytest.raises(sqlite3.IntegrityError, match="synthetic seeding failure"):
        with seeded_database():
            pytest.fail("failed seeding must never yield a database")
    with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
        conn.execute("SELECT 1")


@pytest.mark.parametrize("field", ["catalog_hash", "validation_digest"])
@pytest.mark.parametrize(
    "value", ["\0" + "a" * 63, "a" * 32 + "\0" + "a" * 31], ids=["leading-nul", "middle-nul"]
)
def test_nul_hash_sql_refusal(db: sqlite3.Connection, field: str, value: str) -> None:
    # §5 H requires exactly 64 lowercase hex characters; these fail SQL length.
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        insert(db, "layout_revision", ROWS["layout_revision"] | {field: value})


def test_nul_identifier_is_not_a_blanket_sql_ban(db: sqlite3.Connection) -> None:
    # §5 does not expressly ban NUL in a K identifier. This specimen has three
    # Unicode code points; do not invent a semantic rejection rule here.
    value = "a\0b"
    insert(db, "activity_kind", dict(id=value))
    actual, sql_length = db.execute(
        "SELECT id,length(id) FROM activity_kind WHERE id=?", (value,)
    ).fetchone()
    assert actual == value and len(actual) == 3 and sql_length == 1
    db.rollback()


@pytest.mark.parametrize("table", ["life_state", "journal_entry", "decision"])
def test_rebuild_metadata_against_stage_a_contract(db: sqlite3.Connection, table: str) -> None:
    # Independent expectations: Stage A contract §3 per-column inventory and
    # §5 exhaustive deltas. No expected metadata is obtained from declarations.
    integers = {
        "life_state": set(
            (
                "maple_id revision tick_counter interaction_counter decision_counter "
                "action_counter goal_counter reaction_variant active_goal_id "
                "suspended_goal_id layout_revision tx ty"
            ).split()
        ),
        "journal_entry": {"id", "maple_id", "revision", "tick_id"},
        "decision": set(
            (
                "id maple_id revision goal_id action_id executed_duration_minutes "
                "latency_ms executed_layout_revision"
            ).split()
        ),
    }
    reals = {
        "life_state": {"mood", "energy", "curiosity", "social"},
        "journal_entry": set(),
        "decision": {"proposed_horizon_minutes", "proposed_duration_minutes"},
    }
    required = {
        "life_state": set(
            (
                "revision mood energy curiosity social activity activity_started_at "
                "activity_until last_tick_at last_updated_at tick_counter "
                "interaction_counter point_id decision_counter action_counter goal_counter "
                "action_priority layout_revision point_host tx ty"
            ).split()
        ),
        "journal_entry": set(
            (
                "maple_id revision created_at category trigger_kind topic text importance "
                "brain_kind brain_name brain_version template_id activity expression"
            ).split()
        ),
        "decision": set(
            (
                "maple_id revision at trigger director_kind director_name director_version "
                "context_summary verdict"
            ).split()
        ),
    }
    defaults = (
        {
            "decision_counter": "0",
            "action_counter": "0",
            "goal_counter": "0",
            "action_priority": "'normal'",
        }
        if table == "life_state"
        else {}
    )
    key = "maple_id" if table == "life_state" else "id"
    for _, name, kind, nonnull, default, pk in db.execute(f"PRAGMA table_info({table})"):
        assert kind == (
            "INTEGER" if name in integers[table] else "REAL" if name in reals[table] else "TEXT"
        )
        assert bool(nonnull) == (name in required[table])
        assert pk == int(name == key)
        assert default == defaults.get(name)


def test_indexes_against_stage_a_contract(db: sqlite3.Connection) -> None:
    # §3 explicit index inventory + §5 approved partial uniqueness.
    expected = {
        "decision_by_time": ("decision", False, ("at",), None),
        "action_event_by_action": ("action_event", False, ("action_id",), None),
        "timeline_event_by_time": ("timeline_event", False, ("at",), None),
        "timeline_event_one_birth": ("timeline_event", True, ("maple_id",), "kind = 'born'"),
        "journal_entry_by_time": ("journal_entry", False, ("created_at",), None),
        "tool_use_by_action": ("tool_use", False, ("action_id",), None),
        "memory_by_key": ("memory", True, ("key",), "key IS NOT NULL"),
        "memory_by_tier": ("memory", False, ("tier", "last_seen_at"), None),
        "conversation_message_external": (
            "conversation_message",
            True,
            ("channel", "external_id"),
            "external_id IS NOT NULL",
        ),
        "one_active_display_per_item": ("display_placement", True, ("item_id",), "active=1"),
    }
    actual = {
        name: (table, sql)
        for name, table, sql in db.execute(
            "SELECT name,tbl_name,sql FROM sqlite_schema WHERE type='index' AND sql IS NOT NULL"
        )
    }
    assert set(actual) == set(expected)
    for name, (table, unique, columns, predicate) in expected.items():
        assert actual[name][0] == table
        info = next(r for r in db.execute(f"PRAGMA index_list({table})") if r[1] == name)
        assert bool(info[2]) == unique and bool(info[4]) == (predicate is not None)
        assert tuple(r[2] for r in db.execute(f"PRAGMA index_info({name})")) == columns
        actual_predicate = actual[name][1].partition(" WHERE ")[2]
        assert actual_predicate == (predicate or "")


def test_trigger_inventory_against_stage_a_contract(db: sqlite3.Connection) -> None:
    # §3 inherits 32 trigger names; §5 freezes six new histories in both directions.
    expected: dict[str, str] = {}
    for table, stem in {
        "maple": "maple_immutable",
        "observation": "observation_append_only",
        "journal_entry_observation": "journal_entry_observation_append_only",
        "timeline_event": "timeline_event_append_only",
        "journal_entry": "journal_entry_append_only",
        "goal": "goal_append_only",
        "decision": "decision_append_only",
        "action_event": "action_event_append_only",
        "document": "document_append_only",
        "tool_use": "tool_use_append_only",
        "memory_event": "memory_event_append_only",
        "daily_reflection": "daily_reflection_append_only",
        "conversation_message": "conversation_message_append_only",
    }.items():
        for op in ("update", "delete"):
            expected[stem + "_" + op] = table
    expected |= {
        "journal_state_no_delete": "journal_state",
        "life_state_no_delete": "life_state",
        "life_state_revision_advances": "life_state",
        "life_state_counters_never_decrease": "life_state",
        "memory_no_delete": "memory",
        "memory_identity_is_fixed": "memory",
    }
    for table in (
        "layout_revision",
        "layout_host",
        "layout_room",
        "layout_point",
        "layout_slot",
        "world_event",
    ):
        for op in ("update", "delete"):
            expected[table + "_" + op + "_immutable"] = table
    actual = dict(db.execute("SELECT name,tbl_name FROM sqlite_schema WHERE type='trigger'"))
    assert actual == expected


def test_composite_fk_groups_against_stage_a_contract(db: sqlite3.Connection) -> None:
    # §5 ordered composite keys, without deriving expectations from CREATE SQL.
    expected = {
        "layout_point": ("layout_host", ("revision", "host_id"), ("revision", "id")),
        "layout_slot": ("layout_host", ("revision", "host_id"), ("revision", "id")),
        "display_placement": (
            "layout_slot",
            ("layout_revision", "host_id", "slot_id"),
            ("revision", "host_id", "id"),
        ),
        "life_state": (
            "layout_point",
            ("layout_revision", "point_host", "point_id"),
            ("revision", "host_id", "id"),
        ),
        "decision": (
            "layout_point",
            ("executed_layout_revision", "executed_point_host", "executed_point_id"),
            ("revision", "host_id", "id"),
        ),
    }
    for table, (target, columns, target_columns) in expected.items():
        rows = sorted(
            (r for r in db.execute(f"PRAGMA foreign_key_list({table})") if r[2] == target),
            key=lambda r: r[1],
        )
        assert len(rows) == len(columns)
        assert len({r[0] for r in rows}) == 1
        assert tuple(r[3] for r in rows) == columns
        assert tuple(r[4] for r in rows) == target_columns
        assert all(r[5:7] == ("NO ACTION", "NO ACTION") for r in rows)


# Independent STEP185 field allowlist; includes changed life and nullable decision refs.
BOUNDED_FIELDS = [
    ("activity_kind", "id", 128),
    ("room_kind", "id", 128),
    ("layout_host", "id", 128),
    ("layout_room", "id", 128),
    ("layout_room", "kind", 128),
    ("layout_point", "host_id", 128),
    ("layout_point", "id", 128),
    ("layout_slot", "host_id", 128),
    ("layout_slot", "id", 128),
    ("display_placement", "id", 128),
    ("display_placement", "item_id", 128),
    ("display_placement", "host_id", 128),
    ("display_placement", "slot_id", 128),
    ("life_state", "point_id", 128),
    ("life_state", "point_host", 128),
    ("decision", "executed_point_host", 128),
    ("decision", "executed_point_id", 128),
    ("world_event", "type", 80),
]


def bounded_row(
    db: sqlite3.Connection, table: str, field: str, value: str, *, seed_refs: bool
) -> dict[str, object]:
    """Supply matching synthetic FKs for valid probes; never disable enforcement."""
    row = ROWS[table] | {field: value}
    if table == "decision":
        row = row | dict(
            executed_layout_revision=1, executed_point_host="host", executed_point_id="point"
        )
        row[field] = value
    if not seed_refs:
        return row
    if table == "layout_room" and field == "kind":
        insert(db, "room_kind", dict(id=value))
    if (
        (table in ("layout_point", "layout_slot", "display_placement") and field == "host_id")
        or (table == "life_state" and field == "point_host")
        or (table == "decision" and field == "executed_point_host")
    ):
        insert(db, "layout_host", dict(revision=1, id=value))
    if table == "display_placement" and field in ("host_id", "slot_id"):
        insert(db, "layout_slot", dict(revision=1, host_id=row["host_id"], id=row["slot_id"]))
    if table in ("life_state", "decision"):
        host = row["point_host" if table == "life_state" else "executed_point_host"]
        point = row["point_id" if table == "life_state" else "executed_point_id"]
        insert(db, "layout_point", dict(revision=1, host_id=host, id=point))
    return row


@pytest.mark.parametrize(("table", "field", "limit"), BOUNDED_FIELDS)
@pytest.mark.parametrize(
    "unit",
    ["x", "ก", "界", "😀", "e\u0301"],
    ids=["ascii", "thai", "japanese", "supplementary", "combining"],
)
@pytest.mark.parametrize("boundary", [1, 0, -1], ids=["minimum", "maximum", "overlong"])
def test_complete_unicode_bounds(
    db: sqlite3.Connection, table: str, field: str, limit: int, unit: str, boundary: int
) -> None:
    count = 1 if boundary == 1 else limit - boundary
    value = (unit * count)[:count]
    assert len(value) == count
    if unit != "x" and count == limit:
        assert len(value.encode("utf8")) > limit
    valid = count <= limit
    row = bounded_row(db, table, field, value, seed_refs=valid)
    if valid:
        insert(db, table, row)
        query = f"SELECT {field} FROM {table} WHERE {field}=?"  # noqa: S608
        assert db.execute(query, (value,)).fetchone() == (value,)
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    else:
        with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
            insert(db, table, row)
    # world_event rows are rolled-back structural probes, never enabled payloads.
    db.rollback()
    assert db.execute("SELECT count(*) FROM world_event").fetchone() == (0,)


@pytest.mark.parametrize(("table", "field", "limit"), BOUNDED_FIELDS)
@pytest.mark.parametrize(
    "case",
    [
        "empty",
        "leading",
        "middle",
        "trailing",
        "repeated",
        "nul-only",
        "max-nuls",
        "hidden-overlong",
        "nul-overlong",
    ],
)
def test_complete_nul_bounds(
    db: sqlite3.Connection, table: str, field: str, limit: int, case: str
) -> None:
    value = {
        "empty": "",
        "leading": "\0" + "界" * (limit - 1),
        "middle": "ก" * (limit // 2) + "\0" + "😀" * (limit - limit // 2 - 1),
        "trailing": "x" * (limit - 1) + "\0",
        "repeated": "\0a\0b\0",
        "nul-only": "\0",
        "max-nuls": "\0" * limit,
        "hidden-overlong": "x" * limit + "\0suffix",
        "nul-overlong": "\0" * (limit + 1),
    }[case]
    valid = 1 <= len(value) <= limit
    row = bounded_row(db, table, field, value, seed_refs=valid)
    if valid:
        insert(db, table, row)
        query = f"SELECT {field} FROM {table} WHERE {field}=?"  # noqa: S608
        assert db.execute(query, (value,)).fetchone() == (value,)
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    else:
        with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
            insert(db, table, row)
    db.rollback()
    assert db.execute("SELECT count(*) FROM world_event").fetchone() == (0,)


@pytest.mark.parametrize("field", ["catalog_hash", "validation_digest"])
@pytest.mark.parametrize(
    "value",
    [
        "0123456789abcdef" * 4,
        "a" * 63,
        "a" * 65,
        "A" * 64,
        "g" * 64,
        "\0" + "a" * 63,
        "a" * 32 + "\0" + "a" * 31,
        "a" * 63 + "\0",
        "\0" * 64,
        HASH + "\0suffix",
        "界" * 64,
        "😀" * 64,
    ],
)
def test_complete_hash_bounds(db: sqlite3.Connection, field: str, value: str) -> None:
    row = ROWS["layout_revision"] | {field: value}
    if len(value) == 64 and all(c in "0123456789abcdef" for c in value):
        insert(db, "layout_revision", row)
        assert db.execute(f"SELECT {field} FROM layout_revision WHERE id=2").fetchone() == (value,)  # noqa: S608
    else:
        with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
            insert(db, "layout_revision", row)


def test_nullable_decision_reference_preserved(db: sqlite3.Connection) -> None:
    insert(db, "decision", DECISION)
    assert db.execute(
        "SELECT executed_layout_revision,executed_point_host,executed_point_id FROM decision"
    ).fetchone() == (None, None, None)
    db.rollback()
    for field, value in (
        ("executed_layout_revision", 1),
        ("executed_point_host", "host"),
        ("executed_point_id", "point"),
    ):
        with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
            insert(db, "decision", DECISION | {field: value})


@pytest.mark.parametrize(
    ("version", "permitted"),
    [
        ((3, 38, 0), False),
        ((3, 40, 0), False),
        ((3, 40, 1), False),
        ((3, 41, 0), True),
        ((3, 53, 1), True),
    ],
)
def test_simulated_sqlite_preflight(
    monkeypatch: pytest.MonkeyPatch, version: tuple[int, int, int], permitted: bool
) -> None:
    from tests.schema_v11 import declarations

    calls: list[str] = []

    def intercepted_connect(path: str) -> sqlite3.Connection:
        calls.append(path)
        raise RuntimeError("preflight permitted connection")

    monkeypatch.setattr(sqlite3, "sqlite_version_info", version)
    monkeypatch.setattr(sqlite3, "connect", intercepted_connect)
    message = (
        "preflight permitted connection" if permitted else "Schema v11 requires SQLite >=3.41.0"
    )
    with pytest.raises(RuntimeError, match=message) as exc:
        declarations.fresh_database()
    assert calls == ([":memory:"] if permitted else [])
    if not permitted:
        assert ".".join(map(str, version)) in str(exc.value)


def test_inherited_17_bounded_fields_unchanged() -> None:
    inherited = {
        "life_state": ("task_target", "task_title", "task_category"),
        "decision": (
            "director_name",
            "director_version",
            "context_summary",
            "proposed_goal_summary",
            "proposed_abandon_reason",
            "proposed_reason",
            "reason_code",
            "executed_reason",
            "executed_point",
        ),
        "journal_entry": ("topic", "text", "brain_name", "brain_version", "template_id"),
    }
    assert sum(map(len, inherited.values())) == 17
    targets = target_tables()
    for table, fields in inherited.items():
        for field in fields:
            original = next(
                line
                for line in V10_TABLES[table].splitlines()
                if line.strip().startswith(field + " TEXT")
            )
            assert "length(" in original
            assert original in targets[table].splitlines()
