"""Fresh owned v10 conversion, independent field/mapping checks and fault matrix."""

from __future__ import annotations

import ast
import errno
import hashlib
import json
import os
import sqlite3
import sys
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest

from maplegotchi.storage.repositories import LifeRepository
from tests.schema_v11 import owned_store as store
from tests.schema_v11.conversion_fixture import (
    ConversionError,
    Source,
    admit_v10,
    columns,
    guarded,
    new_source,
    opened,
    release,
)
from tests.schema_v11.conversion_mapping import mapping_manifest
from tests.schema_v11.converter import Result, convert
from tests.schema_v11.declarations import SOURCE_SHA256, V10_TABLES

AT = datetime(2026, 10, 15, tzinfo=UTC)
# Independent FinalSpec §R expectations; converter's map is deliberately not imported.
SPEC = (
    ("bed.side", "bed.bedroom", "sleep", 3, 4),
    ("sofa.seat", "sofa.living", "seat", 12, 6),
    ("bookshelf.front", "bookshelf.library_1", "front_l", 21, 4),
    ("window.view", "window.living", "view", 18, 3),
    ("writing_desk.chair", "desk.writing", "chair", 34, 5),
    ("computer_desk.chair", "desk.computer", "operator", 39, 5),
    ("open_area.west", "idle.hall_west", "idle", 10, 15),
    ("open_area.center", "idle.hall_center", "idle", 21, 15),
    ("open_area.east", "idle.hall_east", "idle", 32, 15),
)


@pytest.fixture
def source() -> Iterator[Source]:
    handle = new_source()
    try:
        yield handle
    finally:
        release(handle)


@pytest.fixture(scope="module")
def converted() -> Iterator[Result]:
    handle = new_source(variant=1, travel=True)
    try:
        yield convert(handle, AT)
    finally:
        release(handle)


def exact_cell(value: Any) -> tuple[type[Any], Any]:
    return type(value), value.hex() if type(value) is float else value


@pytest.mark.parametrize("table,column", [(n, c) for n in sorted(V10_TABLES) for c in columns(n)])
def test_all_source_fields_classified_and_conserved(
    converted: Result, table: str, column: str
) -> None:
    manifest = mapping_manifest()
    assert len(manifest) == len({entry[0] for entry in manifest}) == 213
    assert f"{table}.{column}" in {entry[0] for entry in manifest}
    before, after = converted.source.table(table), converted.target.table(table)
    if table == "life_state" and column in {
        "location",
        "point_id",
        "route_path",
        "route_departed_at",
    }:
        raw = dict(zip(after.columns, after.rows[0], strict=True))
        assert raw["point_host"] == "desk.writing" and raw["point_id"] == "chair"
        assert (raw["tx"], raw["ty"]) == (34, 5) and "location" not in after.columns
        assert raw["route_departed_at"] == raw["route_arrives_at"] == raw["activity_started_at"]
        return
    i, j = before.columns.index(column), after.columns.index(column)
    assert tuple(exact_cell(row[i]) for row in before.rows) == tuple(
        exact_cell(row[j]) for row in after.rows
    )


@pytest.mark.parametrize("point,host,local,tx,ty", SPEC)
@pytest.mark.parametrize("travel", [False, True])
def test_nine_specr_mappings(
    point: str, host: str, local: str, tx: int, ty: int, travel: bool
) -> None:
    handle = new_source(point, travel=travel)
    try:
        result = convert(handle, AT)
        raw = dict(
            zip(
                result.target.table("life_state").columns,
                result.target.rows("life_state")[0],
                strict=True,
            )
        )
        assert (raw["point_host"], raw["point_id"], raw["tx"], raw["ty"]) == (host, local, tx, ty)
        if travel:
            payload = json.loads(str(raw["route_path"]))
            assert payload["waypoints"] == [[tx, ty, 0]] and payload["entry"] is None
            assert raw["route_departed_at"] == raw["activity_started_at"] == raw["route_arrives_at"]
        else:
            assert all(
                raw[k] is None
                for k in (
                    "route_path",
                    "route_departed_at",
                    "route_from_activity",
                    "route_arrives_at",
                )
            )
        assert result.target.rows("world_state") == ((1, 1),)
        assert result.target.rows("layout_revision")[0][1:4] == (AT.isoformat(), "migration", None)
        assert not result.target.rows("world_event") and not result.target.rows("display_placement")
    finally:
        release(handle)


@pytest.mark.parametrize("point", [row[0] for row in SPEC])
def test_null_legacy_point_uses_existing_core_canonical_point(point: str) -> None:
    handle = new_source(point, null_point=True)
    try:
        result = convert(handle, AT)
        row = result.target.rows("life_state")[0]
        raw = dict(zip(result.target.table("life_state").columns, row, strict=True))
        expected = (
            "idle.hall_center"
            if point.startswith("open_area.")
            else next(s[1] for s in SPEC if s[0] == point)
        )
        assert raw["point_host"] == expected
    finally:
        release(handle)


@pytest.mark.parametrize("variant", [0, 1, 2])
def test_independent_source_variants_and_retained_copies(variant: int) -> None:
    h = new_source(variant=variant)
    try:
        result = convert(h, AT)
        assert result.target.rows("maple") == result.source.rows("maple")
        assert result.target.rows("maple")[0][1] == ("Maple", "เมเปิล", "Maple-variant")[variant]
        assert result.target.sequences == result.source.sequences
        assert all(
            value > max(cast(int, r[0]) for r in result.target.rows(name))
            for name, value in result.target.sequences
        )
        for name in ("source.db", *result.copies):
            with opened(result.scope, name) as conn:
                assert store.exact(admit_v10(conn)) == store.exact(result.source)
                assert (
                    LifeRepository(conn).load().state.identity.name
                    == result.source.rows("maple")[0][1]
                )
        with opened(result.scope, "target.db") as conn:
            with pytest.raises(ConversionError, match="version"):
                admit_v10(conn)
    finally:
        release(h)


PHASES = (
    "copy_owner.db",
    "copy_automatic.db",
    "verify_owner.db",
    "verify_automatic.db",
    "verify_target.db",
    "after_copies",
    "after_begin",
    "partial_ddl",
    "row_copy",
    "after_rows",
    "sequence",
    "validated",
    "before_commit",
)


@pytest.mark.parametrize("phase", PHASES)
def test_controlled_failure_refuses_without_hybrid_and_retains_copies(
    source: Source, phase: str
) -> None:
    owned = guarded(source)
    reached: list[str] = []

    def fail(current: str) -> None:
        if current == phase:
            reached.append(current)
            raise sqlite3.OperationalError("bounded synthetic fault")

    with pytest.raises(ConversionError, match=r"^refused$"):
        convert(source, AT, inject=fail)
    assert reached == [phase]
    with opened(owned.scope, "source.db") as conn:
        assert store.exact(admit_v10(conn)) == store.exact(owned.baseline)
    for name in ("owner.db", "automatic.db", "target.db"):
        if name in owned.scope._registry():
            with opened(owned.scope, name) as conn:
                # A copy callback may fail before verification but backup itself completed.
                assert store.exact(admit_v10(conn)) == store.exact(owned.baseline)
    with pytest.raises(ConversionError, match="repeat"):
        convert(source, AT)


@pytest.mark.parametrize("fault", ["permission", "disk_full"])
def test_bounded_storage_failure(source: Source, fault: str) -> None:
    reached: list[str] = []

    def fail(phase: str) -> None:
        if phase == "after_rows":
            reached.append(phase)
            if fault == "permission":
                raise PermissionError("synthetic read-only filesystem")
            raise sqlite3.OperationalError("database or disk is full")

    with pytest.raises(ConversionError, match="refused"):
        convert(source, AT, inject=fail)
    assert reached == ["after_rows"]
    with opened(guarded(source).scope, "target.db") as conn:
        assert admit_v10(conn) == guarded(source).baseline


@pytest.mark.parametrize("phase", ["after_preflight", "after_copies", "after_rows"])
def test_source_modification_detected_or_fenced(source: Source, phase: str) -> None:
    owned = guarded(source)
    reached: list[str] = []

    def alter(current: str) -> None:
        if current == phase:
            reached.append(current)
            with opened(owned.scope, "source.db", readonly=False) as conn:
                conn.execute("UPDATE journal_state SET notices_today=notices_today+1")

    with pytest.raises(ConversionError, match="refused"):
        convert(source, AT, inject=alter)
    assert reached == [phase]
    if phase == "after_rows":
        with opened(owned.scope, "source.db") as conn:
            assert admit_v10(conn) == owned.baseline
    if "target.db" in owned.scope._registry():
        with opened(owned.scope, "target.db") as conn:
            assert admit_v10(conn) == owned.baseline


@pytest.mark.parametrize(
    "sql",
    [
        "PRAGMA user_version=0",
        "PRAGMA user_version=11",
        "PRAGMA user_version=12",
        "PRAGMA application_id=123",
        "DROP TABLE conversation_message",
        "ALTER TABLE maple ADD COLUMN unexpected TEXT",
        "DROP INDEX timeline_event_one_birth",
        "UPDATE life_state SET point_id='unknown'",
        "UPDATE life_state SET route_path='[]'",
        "UPDATE life_state SET route_departed_at=activity_started_at, route_from_activity='idle', "
        "route_path='[[640,470,0,\"writing_desk.chair\"]]'",
        "UPDATE life_state SET mood=101",
        "UPDATE goal SET decision_id=9999",
        "UPDATE sqlite_sequence SET seq=0",
        "UPDATE timeline_event SET payload='{}'",
    ],
)
def test_invalid_v10_source_refuses_before_target(source: Source, sql: str) -> None:
    owned = guarded(source)
    # Disposable corrupt specimens only; never relax constraints in the actual converter.
    with opened(owned.scope, "source.db", readonly=False) as conn:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("PRAGMA ignore_check_constraints=ON")
        if sql.startswith("UPDATE timeline_event"):
            conn.execute("DROP TRIGGER timeline_event_append_only_update")
        if sql.startswith("UPDATE goal"):
            conn.execute("DROP TRIGGER goal_append_only_update")
        if sql.startswith("UPDATE life_state"):
            sql += ", revision=revision+1"
        conn.execute(sql)
    with pytest.raises(ConversionError, match="refused"):
        convert(source, AT)
    assert set(owned.scope._registry()) == {"source.db"}


def test_sqlite_preflight_before_copy(source: Source, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sqlite3, "sqlite_version_info", (3, 40, 1))
    with pytest.raises(ConversionError, match="refused"):
        convert(source, AT)
    assert set(guarded(source).scope._registry()) == {"source.db"}


@pytest.mark.parametrize(
    "value",
    ["/data/maple/maple.db", "../old.db", "/tmp/historical.db", None, Source(object())],  # noqa: S108 -- refusal specimen
)
def test_unregistered_handles_and_paths_never_open(
    value: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> None:
        pytest.fail("ownership must precede all SQLite calls")

    monkeypatch.setattr(sqlite3, "connect", forbidden)
    with pytest.raises(ConversionError, match="ownership"):
        convert(value, AT)


def test_duplicate_conversion_and_no_secret_diagnostics(source: Source) -> None:
    result = convert(source, AT)
    with pytest.raises(ConversionError, match="repeat") as error:
        convert(source, AT)
    assert str(error.value) == "repeat"
    assert result.target.rows("maple")[0] == result.source.rows("maple")[0]


def test_ack_loss_is_uncertain_not_rollback(source: Source) -> None:
    owned = guarded(source)

    def fail(phase: str) -> None:
        if phase == "after_commit":
            raise OSError("ack lost")

    with pytest.raises(ConversionError, match="uncertain"):
        convert(source, AT, inject=fail)
    with opened(owned.scope, "target.db") as conn:
        assert conn.execute("PRAGMA user_version").fetchone() == (11,)
    with pytest.raises(ConversionError, match="repeat"):
        convert(source, AT)


def test_frozen_registry_default_and_source_boundaries() -> None:
    root = Path(__file__).parents[2]
    assert (
        hashlib.sha256((root / "src/maplegotchi/storage/migrations.py").read_bytes()).hexdigest()
        == SOURCE_SHA256
    )
    tree = ast.parse((root / "src/maplegotchi/storage/migrations.py").read_text(encoding="utf-8"))
    registry = next(
        n.value
        for n in tree.body
        if isinstance(n, ast.AnnAssign)
        and isinstance(n.target, ast.Name)
        and n.target.id == "MIGRATIONS"
    )
    assert isinstance(registry, ast.Tuple)
    assert [
        n.args[0].value
        for n in registry.elts
        if isinstance(n, ast.Call) and isinstance(n.args[0], ast.Constant)
    ] == list(range(1, 11))
    for path in (root / "src").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith("tests.")
            if isinstance(node, ast.Import):
                assert not any(a.name.startswith("tests.") for a in node.names)


def test_independent_copy_verification_detects_changed_valid_v10(source: Source) -> None:
    owned = guarded(source)

    def corrupt(phase: str) -> None:
        if phase == "verify_automatic.db":
            with opened(owned.scope, "automatic.db", readonly=False) as conn:
                conn.execute("UPDATE journal_state SET notices_today=notices_today+1")

    with pytest.raises(ConversionError, match="refused"):
        convert(source, AT, inject=corrupt)
    assert "target.db" not in owned.scope._registry()
    with opened(owned.scope, "owner.db") as conn:
        assert admit_v10(conn) == owned.baseline
    with opened(owned.scope, "automatic.db") as conn:
        assert admit_v10(conn) != owned.baseline


@pytest.mark.parametrize("name", [n for n, s in V10_TABLES.items() if "AUTOINCREMENT" in s])
def test_converted_sequence_next_id_above_high_water(converted: Result, name: str) -> None:
    table = converted.target.table(name)
    row = dict(zip(table.columns, table.rows[0], strict=True))
    row["id"] = None
    overrides: dict[str, dict[str, Any]] = {
        "timeline_event": {"kind": "activity_changed"},
        "observation": {"tick_id": 2},
        "daily_reflection": {"day": "2026-10-15"},
        "memory": {"key": "another-synthetic-memory"},
        "conversation_message": {"external_id": "another-synthetic-message"},
    }
    row.update(overrides.get(name, {}))
    with opened(converted.scope, "target.db", readonly=False) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            store._insert(conn, table, (tuple(row[c] for c in table.columns),))
            assert conn.execute("SELECT last_insert_rowid()").fetchone() == (
                dict(converted.target.sequences)[name] + 1,
            )
        finally:
            conn.execute("ROLLBACK")


@pytest.mark.parametrize("kind", ["readonly", "disk_full"])
def test_actual_sqlite_failure_on_bounded_disposable_target(
    source: Source, kind: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from contextlib import contextmanager

    from tests.schema_v11 import converter

    original = opened
    sqlite_codes: list[int] = []

    @contextmanager
    def limited(
        scope: store.OwnedRoot, name: str, *, readonly: bool = True
    ) -> Iterator[sqlite3.Connection]:
        if name == "target.db" and not readonly:
            with original(scope, name, readonly=False) as conn:
                if kind == "readonly" and conn.execute("PRAGMA user_version").fetchone() == (10,):
                    conn.execute("PRAGMA query_only=ON")
                if kind == "disk_full":
                    count = conn.execute("PRAGMA page_count").fetchone()[0]
                    conn.execute(f"PRAGMA max_page_count={int(count)}")
                try:
                    yield conn
                except sqlite3.Error as error:
                    sqlite_codes.append(error.sqlite_errorcode & 255)
                    raise
        else:
            with original(scope, name, readonly=readonly) as conn:
                yield conn

    monkeypatch.setattr(converter, "opened", limited)
    with pytest.raises(ConversionError, match="refused"):
        convert(source, AT)
    assert sqlite_codes == [sqlite3.SQLITE_READONLY if kind == "readonly" else sqlite3.SQLITE_FULL]
    with opened(guarded(source).scope, "target.db") as conn:
        assert admit_v10(conn) == guarded(source).baseline


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE world_state SET active_revision=999",
        "UPDATE life_state SET tx=0,ty=0,revision=revision+1",
        "INSERT INTO world_event(maple_id,type,at,revision,payload) "
        "VALUES(1,'unapproved','2026-10-15T00:00:00+00:00',2,'{}')",
    ],
)
def test_in_transaction_fk_canonical_and_payload_refusal(
    source: Source, sql: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = store._insert
    target_connections = []

    def tracked(conn: sqlite3.Connection, table: Any, rows: Any = None) -> None:
        target_connections.append(conn)
        original(conn, table, rows)

    monkeypatch.setattr(store, "_insert", tracked)

    def corrupt(phase: str) -> None:
        if phase == "after_rows":
            target_connections[-1].execute(sql)

    with pytest.raises(ConversionError, match="refused"):
        convert(source, AT, inject=corrupt)
    with opened(guarded(source).scope, "target.db") as conn:
        assert admit_v10(conn) == guarded(source).baseline


def test_target_transaction_and_version_order(
    source: Source, monkeypatch: pytest.MonkeyPatch
) -> None:
    from contextlib import contextmanager

    from tests.schema_v11 import converter

    traces: list[str] = []
    connections: list[sqlite3.Connection] = []

    @contextmanager
    def traced(
        scope: store.OwnedRoot, name: str, *, readonly: bool = True
    ) -> Iterator[sqlite3.Connection]:
        with opened(scope, name, readonly=readonly) as conn:
            if name == "target.db" and not readonly:
                conn.set_trace_callback(traces.append)
                connections.append(conn)
            yield conn

    monkeypatch.setattr(converter, "opened", traced)

    def observe(phase: str) -> None:
        if phase == "validated":
            assert connections[-1].execute("PRAGMA user_version").fetchone() == (10,)

    convert(source, AT, inject=observe)
    assert traces.count("BEGIN IMMEDIATE") == traces.count("COMMIT") == 1
    version = traces.index("PRAGMA user_version=11")
    assert traces[version + 1] == "COMMIT"
    assert traces.index("PRAGMA foreign_keys=OFF") < traces.index("BEGIN IMMEDIATE")
    assert traces.index("PRAGMA foreign_keys=1") > traces.index("COMMIT")


@pytest.mark.parametrize("zero,completed", [(True, False), (True, True), (False, True)])
def test_source_zero_step_and_completed_route_original_times(zero: bool, completed: bool) -> None:
    if zero:
        with pytest.raises(ConversionError, match="fixture"):
            new_source(travel=True, zero_step=True, completed=completed)
        return
    handle = new_source(travel=True, completed=completed)
    try:
        result = convert(handle, AT)
        old = dict(
            zip(
                result.source.table("life_state").columns,
                result.source.rows("life_state")[0],
                strict=True,
            )
        )
        new = dict(
            zip(
                result.target.table("life_state").columns,
                result.target.rows("life_state")[0],
                strict=True,
            )
        )
        assert new["route_departed_at"] == new["route_arrives_at"] == old["activity_started_at"]
        assert (
            new["activity_until"] == old["activity_until"]
            and new["last_updated_at"] == old["last_updated_at"]
        )
    finally:
        release(handle)


def test_forged_root_symlink_replaced_inode_and_expired_handle(source: Source) -> None:
    owned = guarded(source)
    path = owned.scope.check("source.db")
    saved = path.with_suffix(".saved")
    path.rename(saved)
    try:
        path.symlink_to(saved)
        with pytest.raises(ConversionError, match="ownership"):
            convert(source, AT)
        path.unlink()
        path.write_bytes(b"owned replacement")
        with pytest.raises(ConversionError, match="ownership"):
            convert(source, AT)
        path.unlink()
    finally:
        if path.is_symlink():
            path.unlink()
        saved.rename(path)
    fake = Source(object())
    with pytest.raises(ConversionError, match="ownership"):
        convert(fake, AT)


def test_expired_handle_refused_before_sqlite(monkeypatch: pytest.MonkeyPatch) -> None:
    handle = new_source()
    release(handle)

    def forbidden(*args: Any, **kwargs: Any) -> None:
        pytest.fail("expired handle opened SQLite")

    monkeypatch.setattr(sqlite3, "connect", forbidden)
    with pytest.raises(ConversionError, match="ownership"):
        convert(handle, AT)


@pytest.mark.parametrize("at", [datetime(2026, 10, 13, tzinfo=UTC), datetime(2026, 10, 15)])  # noqa: DTZ001 -- refusal specimen
def test_invalid_migration_time_before_copies(source: Source, at: datetime) -> None:
    with pytest.raises(ConversionError, match="refused"):
        convert(source, at)
    assert set(guarded(source).scope._registry()) == {"source.db"}


def test_unexpected_registered_file_refused_before_copy(source: Source) -> None:
    owned = guarded(source)
    owned.scope.reserve("extra.db")
    with pytest.raises(ConversionError, match="refused"):
        convert(source, AT)
    assert set(owned.scope._registry()) == {"source.db", "extra.db"}


def test_missing_source_refuses_without_create(source: Source) -> None:
    owned = guarded(source)
    path = owned.scope.check("source.db")
    saved = path.with_suffix(".saved")
    path.rename(saved)
    try:
        with pytest.raises(ConversionError, match="ownership"):
            convert(source, AT)
        assert not path.exists()
    finally:
        saved.rename(path)


@pytest.mark.parametrize("fault", ["catalog", "document", "keys"])
def test_corrupt_target_admission_rolls_back_without_version_bump(
    source: Source, fault: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = store._insert
    mutated: list[str] = []

    def corrupt(conn: sqlite3.Connection, table: Any, rows: Any = None) -> None:
        if table.name == "layout_revision" and fault in {"catalog", "document"}:
            row = list(table.rows[0])
            row[5 if fault == "catalog" else 7] = "f" * 64
            table = replace(table, rows=(tuple(row),))
        if table.name == "layout_point" and fault == "keys":
            table = replace(table, rows=table.rows[1:])
        if table.name == ("layout_point" if fault == "keys" else "layout_revision"):
            mutated.append(fault)
        original(conn, table, rows)

    monkeypatch.setattr(store, "_insert", corrupt)
    with pytest.raises(ConversionError, match="refused"):
        convert(source, AT)
    assert mutated == [fault]
    with opened(guarded(source).scope, "target.db") as conn:
        assert admit_v10(conn) == guarded(source).baseline


@pytest.mark.parametrize("fault", ["name", "seed", "birth"])
def test_invalid_source_identity_or_birth_with_frozen_schema(source: Source, fault: str) -> None:
    from tests.schema_v11.declarations import V10_OBJECTS

    owned = guarded(source)
    trigger = "timeline_event_append_only_update" if fault == "birth" else "maple_immutable_update"
    with opened(owned.scope, "source.db", readonly=False) as conn:
        conn.execute(f"DROP TRIGGER {trigger}")
        if fault == "name":
            conn.execute("UPDATE maple SET name='Changed'")
        elif fault == "seed":
            conn.execute("UPDATE maple SET life_seed=?", ("ff" * 32,))
        else:
            conn.execute("UPDATE timeline_event SET payload='{}'")
        conn.execute(
            next(sql for sql in V10_OBJECTS if sql.startswith("CREATE TRIGGER " + trigger + " "))
        )
    with pytest.raises(ConversionError, match="refused"):
        convert(source, AT)
    assert set(owned.scope._registry()) == {"source.db"}


def test_retained_copy_sync_requires_writable_owned_handle(
    source: Source, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exercise Windows FlushFileBuffers access rights on every platform.

    Native Windows additionally proves the original readonly-handle failure.
    Real fsync still executes for all three owned copies; none is bypassed.
    """
    owned = guarded(source)
    original_open = Path.open
    original_sync = os.fsync
    streams: dict[int, Any] = {}
    synced: list[str] = []
    allowed = {owned.scope.path / n for n in ("owner.db", "automatic.db", "target.db")}

    def tracked(path: Path, *args: Any, **kwargs: Any) -> Any:
        stream = original_open(path, *args, **kwargs)
        if path in allowed:
            assert owned.scope.check(path.name) == path
            info = os.fstat(stream.fileno())
            assert [info.st_dev, info.st_ino] == owned.scope._registry()[path.name]
            streams[stream.fileno()] = stream
        return stream

    def windows_sync(fd: int) -> None:
        stream = streams[fd]
        assert not stream.closed
        if not stream.writable():
            raise OSError(errno.EBADF, "synthetic Windows writable-handle requirement")
        original_sync(fd)
        synced.append(Path(stream.name).name)

    monkeypatch.setattr(Path, "open", tracked)
    monkeypatch.setattr(os, "fsync", windows_sync)
    try:
        result = convert(source, AT)
    except ConversionError as refusal:
        cause = refusal.__context__
        print(
            json.dumps(
                dict(
                    stage="retained_copy_sync",
                    error=type(cause).__name__,
                    errno=getattr(cause, "errno", None),
                )
            )
        )
        raise
    assert synced == ["owner.db", "automatic.db", "target.db"]
    assert all(stream.closed for stream in streams.values())
    for name in result.copies:
        with opened(owned.scope, name) as conn:
            assert admit_v10(conn) == owned.baseline
    if sys.platform == "win32":
        # Bounded native evidence: errno only, never path or SQLite payload.
        with original_open(owned.scope.check("owner.db"), "rb") as readonly:
            with pytest.raises(OSError) as error:
                original_sync(readonly.fileno())
        assert error.value.errno
        print(
            json.dumps(dict(stage="readonly_copy_sync", error="OSError", errno=error.value.errno))
        )


@pytest.mark.parametrize("destination", ["owner.db", "automatic.db", "target.db"])
def test_retained_copy_sync_failure_refuses_before_conversion(
    source: Source, destination: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    owned = guarded(source)
    original_sync = os.fsync
    calls: list[str] = []
    phases: list[str] = []

    def fail_sync(fd: int) -> None:
        name = ("owner.db", "automatic.db", "target.db")[len(calls)]
        calls.append(name)
        if name == destination:
            raise OSError(errno.EACCES, "synthetic retained-copy sync refusal")
        original_sync(fd)

    monkeypatch.setattr(os, "fsync", fail_sync)
    with pytest.raises(ConversionError, match=r"^refused$") as error:
        convert(source, AT, inject=phases.append)
    # The public category stays fixed; bounded test-only evidence names the cause.
    cause = error.value.__context__
    assert isinstance(cause, OSError) and cause.errno == errno.EACCES
    assert str(error.value) == "refused" and "after_copies" not in phases
    assert calls[-1] == destination
    for name in owned.scope._registry():
        with opened(owned.scope, name) as conn:
            assert admit_v10(conn) == owned.baseline
    with pytest.raises(ConversionError, match="repeat"):
        convert(source, AT)


def test_source_boundary_scan_ignores_windows_default_encoding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Run the full source scanner under the failed CI's cp1252 default."""
    original_read = Path.read_text

    def windows_default(path: Path, encoding: str | None = None, errors: str | None = None) -> str:
        return original_read(path, encoding=encoding or "cp1252", errors=errors)

    monkeypatch.setattr(Path, "read_text", windows_default)
    test_frozen_registry_default_and_source_boundaries()
