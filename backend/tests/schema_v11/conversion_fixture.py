"""Fresh registered v10 specimens only; no historical migration/setup execution.

The public factory creates its own OwnedRoot. A separately tracked worker may
receive an empty parent-created root through its private stdin handoff. Handles
are identity-registered in this process; paths, forged/expired handles refuse.
"""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import cast

from maplegotchi.core.activities import Activity
from maplegotchi.core.room import POINT_BY_ID, plan_route, whereabouts
from maplegotchi.storage.repositories import LifeRepository, encode_route_path
from tests.schema_v11 import owned_store as store
from tests.schema_v11.declarations import V10_OBJECTS, V10_TABLES
from tests.schema_v11.restart_worker import (
    BORN,
    UPDATED,
    advanced_snapshot,
    birth_snapshot,
    canonical,
)
from tests.schema_v11.row_conservation import TableImage


class ConversionError(ValueError):
    """Fixed category, never source paths, seeds, payloads or SQLite diagnostics."""

    def __init__(self, category: str) -> None:
        super().__init__(category)


@dataclass(frozen=True, slots=True)
class Source:
    token: object


@dataclass
class OwnedSource:
    handle: Source
    scope: store.OwnedRoot
    baseline: store.Snapshot
    attempted: bool = False


_LIVE: dict[int, OwnedSource] = {}


def columns(name: str) -> tuple[str, ...]:
    return tuple(re.findall(r"^ ([a-z_]+) (?:INTEGER|TEXT|REAL)\b", V10_TABLES[name], re.MULTILINE))


def guarded(handle: Source) -> OwnedSource:
    if type(handle) is not Source:
        raise ConversionError("ownership")
    owned = _LIVE.get(id(handle))
    if owned is None or owned.handle is not handle:
        raise ConversionError("ownership")
    try:
        owned.scope.check("source.db")
    except (store.StoreError, OSError):
        raise ConversionError("ownership") from None
    return owned


@contextmanager
def opened(
    scope: store.OwnedRoot, name: str, *, readonly: bool = True
) -> Iterator[sqlite3.Connection]:
    """No create flag; an inode-registered file must already exist."""
    path = scope.check(name)
    conn = sqlite3.connect(
        path.as_uri() + ("?mode=ro" if readonly else "?mode=rw"), uri=True, isolation_level=None
    )
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=2000")
        conn.execute("PRAGMA synchronous=FULL")
        if readonly:
            conn.execute("PRAGMA query_only=ON")
        yield conn
    finally:
        conn.close()


def capture_v10(conn: sqlite3.Connection) -> store.Snapshot:
    tables = []
    for name in sorted(V10_TABLES):
        # Closed authoritative names; never caller-controlled SQL identifiers.
        cursor = conn.execute(
            f'SELECT * FROM "{name}" ORDER BY '  # noqa: S608
            + ",".join(str(i + 1) for i in range(len(columns(name))))
        )
        tables.append(
            TableImage(name, tuple(c[0] for c in cursor.description), tuple(cursor.fetchall()))
        )
    return store.Snapshot(
        tuple(tables), tuple(conn.execute("SELECT name,seq FROM sqlite_sequence ORDER BY name"))
    )


def admit_v10(conn: sqlite3.Connection) -> store.Snapshot:
    if conn.execute("PRAGMA application_id").fetchone() != (store.APPLICATION_ID,) or conn.execute(
        "PRAGMA user_version"
    ).fetchone() != (10,):
        raise ConversionError("version")
    expected = {s.strip().rstrip(";") for s in (*V10_TABLES.values(), *V10_OBJECTS)}
    actual = {
        r[0].strip().rstrip(";")
        for r in conn.execute(
            "SELECT sql FROM sqlite_schema WHERE sql IS NOT NULL AND name <> 'sqlite_sequence'"
        )
    }
    if actual != expected:
        raise ConversionError("schema")
    store._integrity(conn)
    image = capture_v10(conn)
    LifeRepository(conn).load()  # Pure v10 reconstruction; never normal open/birth/migrate.
    (identity,) = image.rows("maple")
    births = tuple(row for row in image.rows("timeline_event") if row[4] == "born")
    if (
        len(births) != 1
        or births[0][5] != identity[2]
        or births[0][6] != canonical({"name": identity[1]})
    ):
        raise ConversionError("identity")
    sequence = dict(image.sequences)
    allowed = {n for n, sql in V10_TABLES.items() if "AUTOINCREMENT" in sql}
    if len(sequence) != len(image.sequences) or not set(sequence) <= allowed:
        raise ConversionError("sequence")
    for name in allowed:
        if max((cast(int, row[0]) for row in image.rows(name)), default=0) > sequence.get(name, 0):
            raise ConversionError("sequence")
    return image


def _fresh(
    scope: store.OwnedRoot,
    point: str,
    travel: bool,
    variant: int,
    null_point: bool,
    zero_step: bool = False,
    completed: bool = False,
) -> Source:
    """Internal worker factory: root must still be empty except ownership.json."""
    scope._root()
    if scope._registry() or {p.name for p in scope.path.iterdir()} != {"ownership.json"}:
        raise ConversionError("ownership")
    if (
        point not in POINT_BY_ID
        or type(travel) is not bool
        or type(variant) is not int
        or not 0 <= variant <= 2
    ):
        raise ConversionError("fixture")
    if zero_step:
        raise ConversionError("fixture")  # Existing v10 Route requires positive duration.
    specimen = advanced_snapshot(birth_snapshot())
    values = dict(
        zip(specimen.table("life_state").columns, specimen.rows("life_state")[0], strict=True)
    )
    dest = POINT_BY_ID[point]
    activity = dest.allowed_actions[0]
    values.update(
        location=dest.location.value,
        activity=activity.value,
        point_id=None if null_point else point,
        mood=61.25 + variant,
    )
    if activity is not Activity.WRITE:
        values.update(task_tool=None, task_target=None, task_title=None, task_category=None)
    if travel or zero_step:
        departure = datetime.fromisoformat("2026-10-14T12:04:00+00:00" if completed else UPDATED)
        start = POINT_BY_ID["open_area.west" if point != "open_area.west" else "open_area.east"]
        route = plan_route(
            whereabouts(None, start, departure),
            dest,
            departure,
            from_activity=Activity.IDLE,
        )
        assert route is not None
        values.update(
            route_departed_at=departure.isoformat(),
            route_from_activity="idle",
            route_path=encode_route_path(route),
            activity_started_at=route.arrives_at.isoformat(),
        )
    else:
        values.update(route_departed_at=None, route_from_activity=None, route_path=None)
    identity = (
        1,
        ("Maple", "เมเปิล", "Maple-variant")[variant],
        BORN,
        ("5e", "a7", "01")[variant] * 32,
    )
    tables = []
    for name in sorted(V10_TABLES):
        cols = columns(name)
        rows = specimen.rows(name)
        if name == "life_state":
            rows = (tuple(values[c] for c in cols),)
        elif name == "maple":
            rows = (identity,)
        elif name == "decision":
            rows = tuple(row[:-3] for row in rows)
        elif name == "timeline_event":
            rows = ((1, 1, 1, None, "born", BORN, canonical({"name": identity[1]})),)
        tables.append(TableImage(name, cols, rows))
    image = store.Snapshot(
        tuple(tables), tuple((name, seq + variant * 17) for name, seq in specimen.sequences)
    )
    scope.reserve("source.db")
    with opened(scope, "source.db", readonly=False) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("BEGIN IMMEDIATE")
        try:
            for sql in (*V10_TABLES.values(), *V10_OBJECTS):
                conn.execute(sql)
            conn.execute("PRAGMA defer_foreign_keys=ON")
            for table in image.tables:
                markers = ",".join("?" for _ in table.columns)
                conn.executemany(
                    f'INSERT INTO "{table.name}" VALUES ({markers})',  # noqa: S608 -- frozen names
                    table.rows,
                )
            conn.execute("DELETE FROM sqlite_sequence")
            conn.executemany("INSERT INTO sqlite_sequence(name,seq) VALUES (?,?)", image.sequences)
            conn.execute(f"PRAGMA application_id={store.APPLICATION_ID}")
            conn.execute("PRAGMA user_version=10")
            if store.exact(admit_v10(conn)) != store.exact(image):
                raise ConversionError("fixture")
            conn.execute("COMMIT")
        except BaseException:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
    handle = Source(object())
    _LIVE[id(handle)] = OwnedSource(handle, scope, image)
    return handle


def new_source(
    point: str = "writing_desk.chair",
    *,
    travel: bool = False,
    variant: int = 0,
    null_point: bool = False,
    zero_step: bool = False,
    completed: bool = False,
) -> Source:
    scope = store.OwnedRoot.new()
    try:
        return _fresh(scope, point, travel, variant, null_point, zero_step, completed)
    except BaseException:
        scope.cleanup()
        raise


def release(handle: Source) -> None:
    owned = guarded(handle)
    owned.scope.cleanup()
    del _LIVE[id(handle)]
