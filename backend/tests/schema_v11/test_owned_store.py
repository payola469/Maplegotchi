"""File-backed tests only through the STEP 220 newly owned capability."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from dataclasses import replace
from typing import Any

import pytest

from tests.schema_v11 import owned_store as store
from tests.schema_v11.restart_worker import (
    advanced_snapshot,
    birth_snapshot,
    digest,
    life_changes,
    replace_rows,
    resources,
)


@pytest.fixture
def scope() -> Iterator[store.OwnedRoot]:
    owned = store.OwnedRoot.new()
    try:
        yield owned
    finally:
        try:
            owned.cleanup()
        except (store.StoreError, FileNotFoundError):
            # Preserve uncertain artifacts, never broaden cleanup.
            print("Owned failure artifacts retained:", owned.path)


@pytest.fixture(scope="module")
def inputs() -> tuple[Any, Any, store.Snapshot, store.Snapshot]:
    catalog, context, _ = resources()
    base = birth_snapshot()
    return (catalog,), ((1, context),), base, advanced_snapshot(base)


def prepare(
    scope: store.OwnedRoot, inputs: tuple[Any, Any, store.Snapshot, store.Snapshot]
) -> None:
    catalogs, contexts, base, _ = inputs
    store.create(scope, "maple.db", base, catalogs, contexts)


def test_fresh_factory_complete_save_and_readonly(
    scope: store.OwnedRoot, inputs: tuple[Any, Any, store.Snapshot, store.Snapshot]
) -> None:
    catalogs, contexts, base, target = inputs
    prepare(scope, inputs)
    assert store.load(scope, "maple.db", catalogs, contexts)[0] == base
    store.save(scope, "maple.db", target, expected_revision=1, catalogs=catalogs, contexts=contexts)
    restored, life = store.load(scope, "maple.db", catalogs, contexts)
    assert store.exact(restored) == store.exact(target)
    assert len(base.table("life_state").columns) == 40 and life.record.revision == 2
    assert store.old_history(restored) == store.old_history(target)
    assert restored.sequences == base.sequences
    assert len(restored.rows("timeline_event")) == 1
    with store.connect(scope, "maple.db", readonly=True) as conn:
        assert conn.execute("PRAGMA journal_mode").fetchone() == ("wal",)
        assert conn.execute("PRAGMA synchronous").fetchone() == (2,)
        assert conn.execute("PRAGMA foreign_keys").fetchone() == (1,)
        assert conn.execute("PRAGMA busy_timeout").fetchone() == (5000,)
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("UPDATE life_state SET revision=3")
    assert store.load(scope, "maple.db", catalogs, contexts)[0] == target


def test_existing_missing_and_unowned_paths_refuse(
    scope: store.OwnedRoot, inputs: tuple[Any, Any, store.Snapshot, store.Snapshot]
) -> None:
    catalogs, contexts, base, _ = inputs
    with pytest.raises(store.StoreError, match="ownership"):
        store.load(scope, "missing.db", catalogs, contexts)
    assert not (scope.path / "missing.db").exists()
    prepare(scope, inputs)
    with pytest.raises(store.StoreError, match="ownership"):
        store.create(scope, "maple.db", base, catalogs, contexts)
    for name in ("../escape.db", str(scope.path.parent / "existing.db"), "maple.db/other.db"):
        with pytest.raises(store.StoreError, match="ownership"):
            scope.reserve(name)
    # A file present but never reserved is refused without opening its contents.
    path = scope.path / "foreign.db"
    with path.open("xb") as stream:
        stream.write(b"foreign owned negative specimen")
    try:
        with pytest.raises(store.StoreError, match="ownership"):
            store.load(scope, "foreign.db", catalogs, contexts)
        with pytest.raises(store.StoreError, match="ownership"):
            scope.cleanup()
        assert path.exists()
    finally:
        path.unlink()  # Exactly the support specimen created above.


def test_symlink_and_replaced_root_refuse(scope: store.OwnedRoot) -> None:
    altered = replace(scope, identity=(scope.identity[0], scope.identity[1] + 1))
    with pytest.raises(store.StoreError, match="ownership"):
        altered.reserve("maple.db")
    link = scope.path / "escape.db"
    try:
        link.symlink_to(scope.path.parent)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation unavailable")
    try:
        with pytest.raises(store.StoreError, match="ownership"):
            scope.reserve("escape.db")
    finally:
        link.unlink()  # Remove this known link without following it.


@pytest.mark.parametrize("phase", ["after_write", "before_commit"])
def test_precommit_failure_rolls_back_every_row(
    scope: store.OwnedRoot, inputs: tuple[Any, Any, store.Snapshot, store.Snapshot], phase: str
) -> None:
    catalogs, contexts, base, target = inputs
    prepare(scope, inputs)

    def fail(at: str) -> None:
        if at == phase:
            raise RuntimeError("controlled failure")

    with pytest.raises(RuntimeError, match="controlled failure"):
        store.save(
            scope,
            "maple.db",
            target,
            expected_revision=1,
            catalogs=catalogs,
            contexts=contexts,
            inject=fail,
        )
    assert digest(store.load(scope, "maple.db", catalogs, contexts)[0]) == digest(base)


def test_lost_acknowledgement_keeps_valid_new_state(
    scope: store.OwnedRoot, inputs: tuple[Any, Any, store.Snapshot, store.Snapshot]
) -> None:
    catalogs, contexts, _, target = inputs
    prepare(scope, inputs)

    def fail(phase: str) -> None:
        if phase == "after_commit":
            raise RuntimeError("acknowledgement lost")

    with pytest.raises(RuntimeError):
        store.save(
            scope,
            "maple.db",
            target,
            expected_revision=1,
            catalogs=catalogs,
            contexts=contexts,
            inject=fail,
        )
    assert store.load(scope, "maple.db", catalogs, contexts)[0] == target


def test_consistent_reader_and_stale_writer(
    scope: store.OwnedRoot, inputs: tuple[Any, Any, store.Snapshot, store.Snapshot]
) -> None:
    catalogs, contexts, base, target = inputs
    prepare(scope, inputs)
    with store.connect(scope, "maple.db", readonly=True) as reader:
        reader.execute("BEGIN")
        assert store.load_connection(reader, catalogs, contexts)[0] == base
        store.save(
            scope, "maple.db", target, expected_revision=1, catalogs=catalogs, contexts=contexts
        )
        assert store.load_connection(reader, catalogs, contexts)[0] == base
        reader.execute("ROLLBACK")
        reader.execute("BEGIN")
        assert store.load_connection(reader, catalogs, contexts)[0] == target
        reader.execute("ROLLBACK")
    with pytest.raises(store.StoreError, match="stale"):
        store.save(
            scope, "maple.db", target, expected_revision=1, catalogs=catalogs, contexts=contexts
        )
    assert store.load(scope, "maple.db", catalogs, contexts)[0] == target


@pytest.mark.parametrize("mode", ["stationary", "pending", "walking", "entry_a", "entry_b"])
def test_durable_travel_phases(
    scope: store.OwnedRoot, inputs: tuple[Any, Any, store.Snapshot, store.Snapshot], mode: str
) -> None:
    catalogs, contexts, base, _ = inputs
    target = advanced_snapshot(base, mode)
    prepare(scope, inputs)
    store.save(scope, "maple.db", target, expected_revision=1, catalogs=catalogs, contexts=contexts)
    restored, life = store.load(scope, "maple.db", catalogs, contexts)
    expected = store.validate(target, catalogs, contexts)
    assert digest(restored) == digest(target)
    if life.travel is not None:
        from datetime import timedelta

        for elapsed in (
            -1,
            0,
            1,
            life.travel.duration_us // 2,
            life.travel.duration_us,
            life.travel.duration_us + 1,
        ):
            now = life.travel.departed_at + timedelta(microseconds=elapsed)
            assert expected.travel is not None
            assert life.travel.current_at(now) == expected.travel.current_at(now)
            assert life.travel.phase_at(now) == expected.travel.phase_at(now)


@pytest.mark.parametrize(
    "sql",
    [
        "PRAGMA user_version=12",
        "PRAGMA user_version=0",
        "PRAGMA application_id=0",
        "DROP TABLE display_placement",
        "DROP TRIGGER layout_host_update_immutable",
        "DELETE FROM world_state",
        "UPDATE world_state SET active_revision=999",
        "UPDATE life_state SET revision=revision+1,mood=101",
        "UPDATE life_state SET revision=revision+1,tx=20",
        "UPDATE life_state SET revision=revision+1,route_path='{}'",
        "DELETE FROM sqlite_sequence WHERE name='timeline_event'",
    ],
)
def test_corrupt_owned_snapshot_refuses_without_repair(
    scope: store.OwnedRoot, inputs: tuple[Any, Any, store.Snapshot, store.Snapshot], sql: str
) -> None:
    catalogs, contexts, _, _ = inputs
    prepare(scope, inputs)
    with store.connect(scope, "maple.db") as conn:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("PRAGMA ignore_check_constraints=ON")
        conn.execute(sql)
        version_before = conn.execute("PRAGMA user_version").fetchone()
        rows_before = conn.execute("SELECT * FROM life_state").fetchall()
    with pytest.raises(store.StoreError):
        store.load(scope, "maple.db", catalogs, contexts)
    with store.connect(scope, "maple.db") as conn:
        assert conn.execute("PRAGMA user_version").fetchone() == version_before
        assert conn.execute("SELECT * FROM life_state").fetchall() == rows_before


@pytest.mark.parametrize(
    "kind",
    ["hash", "catalog", "keys", "pointer", "full_field", "birth", "sequence", "unknown_payload"],
)
def test_invalid_candidate_is_never_partially_written(
    scope: store.OwnedRoot, inputs: tuple[Any, Any, store.Snapshot, store.Snapshot], kind: str
) -> None:
    catalogs, contexts, base, target = inputs
    prepare(scope, inputs)
    if kind in {"hash", "catalog"}:
        row = list(target.rows("layout_revision")[0])
        row[7 if kind == "hash" else 5] = "f" * 64
        bad = replace_rows(target, "layout_revision", (tuple(row),))
    elif kind == "keys":
        bad = replace_rows(target, "layout_point", target.rows("layout_point")[1:])
    elif kind == "pointer":
        bad = replace_rows(target, "world_state", ((1, 2),))
    elif kind == "full_field":
        bad = life_changes(target, task_title=None)
    elif kind == "birth":
        bad = replace_rows(target, "timeline_event", ())
    elif kind == "sequence":
        bad = replace(target, sequences=tuple((name, 0) for name, _ in target.sequences))
    else:
        bad = replace_rows(
            target,
            "world_event",
            (
                (
                    1,
                    1,
                    "unknown",
                    "2026-10-14T12:00:00+00:00",
                    1,
                    None,
                    None,
                    None,
                    None,
                    None,
                    "{}",
                ),
            ),
        )
    with pytest.raises(store.StoreError, match="state"):
        store.save(
            scope, "maple.db", bad, expected_revision=1, catalogs=catalogs, contexts=contexts
        )
    assert store.load(scope, "maple.db", catalogs, contexts)[0] == base


def test_sequence_high_water_next_id(
    scope: store.OwnedRoot, inputs: tuple[Any, Any, store.Snapshot, store.Snapshot]
) -> None:
    prepare(scope, inputs)
    with store.connect(scope, "maple.db") as conn:
        before = conn.execute(
            "SELECT seq FROM sqlite_sequence WHERE name='timeline_event'"
        ).fetchone()
        assert before == (1000,)
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "INSERT INTO timeline_event(maple_id,revision,kind,at,payload) "
            "VALUES (1,1,'activity_changed','2026-10-14T12:00:00+00:00','{}')"
        )
        assert conn.execute("SELECT MAX(id) FROM timeline_event").fetchone() == (1001,)
        conn.execute("ROLLBACK")  # Rolled-back storage probe, never a dispatched event.
        assert conn.execute("SELECT COUNT(*) FROM timeline_event").fetchone() == (1,)
        assert (
            conn.execute("SELECT seq FROM sqlite_sequence WHERE name='timeline_event'").fetchone()
            == before
        )


def test_compatibility_checked_before_reserving(
    scope: store.OwnedRoot,
    inputs: tuple[Any, Any, store.Snapshot, store.Snapshot],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sqlite3, "sqlite_version_info", (3, 40, 0))
    catalogs, contexts, base, _ = inputs
    with pytest.raises(store.StoreError, match="compatibility"):
        store.create(scope, "maple.db", base, catalogs, contexts)
    assert not (scope.path / "maple.db").exists()


def test_all_eleven_restored_sequences_allocate_above_high_water(
    scope: store.OwnedRoot, inputs: tuple[Any, Any, store.Snapshot, store.Snapshot]
) -> None:
    catalogs, contexts, _, target = inputs
    prepare(scope, inputs)
    store.save(scope, "maple.db", target, expected_revision=1, catalogs=catalogs, contexts=contexts)
    with store.connect(scope, "maple.db") as conn:
        for name, value in target.sequences:
            table = target.table(name)
            values = dict(zip(table.columns, table.rows[0], strict=True))
            values["id"] = None
            if name == "timeline_event":
                values["kind"] = "activity_changed"
            elif name == "observation":
                values["tick_id"] = 2
            elif name == "daily_reflection":
                values["day"] = "2026-10-15"
            elif name == "memory":
                values["key"] = "another-synthetic-memory"
            elif name == "conversation_message":
                values["external_id"] = "another-synthetic-only"
            conn.execute("BEGIN IMMEDIATE")
            store._insert(conn, table, (tuple(values[column] for column in table.columns),))
            assert conn.execute("SELECT last_insert_rowid()").fetchone() == (value + 1,)
            conn.execute("ROLLBACK")
            assert store.exact(store.capture(conn)) == store.exact(target)


def test_corrupt_file_bytes_refuse_without_rewrite(
    scope: store.OwnedRoot, inputs: tuple[Any, Any, store.Snapshot, store.Snapshot]
) -> None:
    catalogs, contexts, _, _ = inputs
    prepare(scope, inputs)
    # Every connection has closed; overwrite only this registered, newly owned file.
    path = scope.check("maple.db")
    specimen = b"STEP220-owned-corrupt-header" * 64
    path.write_bytes(specimen)
    with pytest.raises(store.StoreError, match="integrity"):
        store.load(scope, "maple.db", catalogs, contexts)
    assert scope.check("maple.db").read_bytes() == specimen


def test_birth_once_and_new_birth_policy(
    scope: store.OwnedRoot, inputs: tuple[Any, Any, store.Snapshot, store.Snapshot]
) -> None:
    catalogs, contexts, _, target = inputs
    with pytest.raises(store.StoreError, match="state"):
        store.create(scope, "advanced.db", target, catalogs, contexts)
    assert not (scope.path / "advanced.db").exists()
    prepare(scope, inputs)
    with store.connect(scope, "maple.db") as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO timeline_event(maple_id,revision,kind,at,payload) "
                "VALUES (1,1,'born',?,?)",
                ("2026-10-14T12:00:00+00:00", '{"name":"Maple"}'),
            )
        assert conn.execute("SELECT COUNT(*) FROM timeline_event WHERE kind='born'").fetchone() == (
            1,
        )


def test_complete_later_save_preserves_all_history_and_cursors(
    scope: store.OwnedRoot, inputs: tuple[Any, Any, store.Snapshot, store.Snapshot]
) -> None:
    catalogs, contexts, _, target = inputs
    prepare(scope, inputs)
    store.save(scope, "maple.db", target, expected_revision=1, catalogs=catalogs, contexts=contexts)
    next_state = life_changes(target, revision=3, mood=62.25)
    store.save(
        scope, "maple.db", next_state, expected_revision=2, catalogs=catalogs, contexts=contexts
    )
    recovered, _ = store.load(scope, "maple.db", catalogs, contexts)
    assert store.old_history(recovered) == store.old_history(target)
    assert len(store.old_history(recovered)) == 16
    assert all(table.rows for table in store.old_history(recovered))
    assert store.exact(recovered) == store.exact(next_state)
