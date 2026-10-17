"""STEP 220 owned synthetic files only; not a shipped repository or migration.

The OwnedRoot capability is a newly created private directory plus an explicit inode
registry. Children receive that capability from their parent, never a free DB
path. No existing database is adopted. Unknown files prevent cleanup. SQLite
WAL/FULL is verified, not a guarantee against arbitrary hardware/filesystems.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import stat
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal, Protocol, cast

from maplegotchi.core.activities import Activity
from maplegotchi.core.timeline import Born
from maplegotchi.core.world.coordinates import Tile
from maplegotchi.core.world.walkability import validate_safe_layout
from tests.schema_v11.declarations import IMMUTABLE, V10_OBJECTS, target_tables
from tests.schema_v11.layout_codec import CatalogSnapshot, LayoutContext
from tests.schema_v11.layout_keys import LayoutKeys, project_layout_keys
from tests.schema_v11.life_record import LIFE_FIELDS, CanonicalLife, reconstruct_life
from tests.schema_v11.revision_snapshot import LifeReference, RevisionRow, validate_layout_snapshot
from tests.schema_v11.row_conservation import HISTORY_SCHEMA, Cell, TableImage
from tests.schema_v11.travel_codec import MAX_BYTES, decode_travel_path

Category = Literal[
    "ownership", "compatibility", "schema", "version", "integrity", "state", "stale", "policy"
]
APPLICATION_ID = 0x4D41504C
SIDECARS = ("", "-wal", "-shm", "-journal")


class StoreError(ValueError):
    """Fixed categories; never disclose state, paths, payloads or seed."""

    def __init__(self, category: Category) -> None:
        super().__init__(category)


class OwnedFiles(Protocol):
    """Explicit file admission capability; SQL never discovers/adopts a path.

    OwnedRoot retains its fresh-execution policy. The opt-in local alpha supplies
    a separately admitted persistent development capability with controller locking.
    """

    def check(self, name: str) -> Path: ...
    def reserve(self, name: str) -> Path: ...


@dataclass(frozen=True)
class OwnedRoot:
    path: Path
    identity: tuple[int, int]

    @classmethod
    def new(cls) -> OwnedRoot:
        path = Path(tempfile.mkdtemp(prefix="maplegotchi-step220-")).resolve()
        info = path.lstat()
        scope = cls(path, (info.st_dev, info.st_ino))
        scope._manifest().write_text("{}", encoding="utf-8")
        return scope

    def _root(self) -> None:
        info = self.path.lstat()
        if (
            self.path.is_symlink()
            or not stat.S_ISDIR(info.st_mode)
            or (info.st_dev, info.st_ino) != self.identity
        ):
            raise StoreError("ownership")
        if self.path.resolve() != self.path:
            raise StoreError("ownership")

    def _manifest(self) -> Path:
        self._root()
        path = self.path / "ownership.json"
        if path.is_symlink():
            raise StoreError("ownership")
        if path.exists() and (not path.is_file() or path.stat().st_nlink != 1):
            raise StoreError("ownership")
        return path

    def _registry(self) -> dict[str, list[int]]:
        value = json.loads(self._manifest().read_text(encoding="utf-8"))
        if not isinstance(value, dict) or any(
            not re.fullmatch(r"[a-z][a-z0-9_]*\.db", name)
            or not isinstance(identity, list)
            or len(identity) != 2
            or any(type(n) is not int for n in identity)
            for name, identity in value.items()
        ):
            raise StoreError("ownership")
        return cast(dict[str, list[int]], value)

    def reserve(self, name: str) -> Path:
        """Exclusive new support file, then registered inode, before SQLite opens."""
        self._root()
        if not re.fullmatch(r"[a-z][a-z0-9_]*\.db", name):
            raise StoreError("ownership")
        registry = self._registry()
        if name in registry:
            raise StoreError("ownership")
        path = self.path / name
        if any(
            (self.path / (name + suffix)).exists() or (self.path / (name + suffix)).is_symlink()
            for suffix in SIDECARS
        ):
            raise StoreError("ownership")
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        info = os.fstat(fd)
        os.close(fd)
        registry[name] = [info.st_dev, info.st_ino]
        self._manifest().write_text(json.dumps(registry, sort_keys=True), encoding="utf-8")
        return self.check(name)

    def check(self, name: str) -> Path:
        registry = self._registry()
        if name not in registry:
            raise StoreError("ownership")
        path = self.path / name
        for suffix in SIDECARS:
            item = self.path / (name + suffix)
            if item.is_symlink():
                raise StoreError("ownership")
            if item.exists():
                info = item.lstat()
                if (
                    not stat.S_ISREG(info.st_mode)
                    or info.st_nlink != 1
                    or item.resolve().parent != self.path
                ):
                    raise StoreError("ownership")
        if not path.exists():
            raise StoreError("ownership")
        info = path.lstat()
        if [info.st_dev, info.st_ino] != registry[name]:
            raise StoreError("ownership")
        return path

    def cleanup(self) -> None:
        """Explicit registry only; unknown/symlink artifacts retain the whole root."""
        registry = self._registry()
        allowed = {"ownership.json"} | {name + suffix for name in registry for suffix in SIDECARS}
        if any(item.name not in allowed for item in self.path.iterdir()):
            raise StoreError("ownership")
        for name in registry:
            self.check(name)
        for name in sorted(allowed - {"ownership.json"}):
            item = self.path / name
            if item.exists():
                item.unlink()
        self._manifest().unlink()
        self.path.rmdir()


def compatibility() -> None:
    # Only a memory probe; no historical migrations or existing DBs.
    if sqlite3.sqlite_version_info < (3, 41, 0):
        raise StoreError("compatibility")
    with sqlite3.connect(":memory:") as conn:
        try:
            if conn.execute("SELECT unhex('4D61706C65')").fetchone() != (b"Maple",):
                raise StoreError("compatibility")
        except sqlite3.Error:
            raise StoreError("compatibility") from None
    conn.close()


def declarations() -> tuple[str, ...]:
    """Reuse frozen declarations verbatim, including every index and trigger."""
    extra = [
        "CREATE UNIQUE INDEX one_active_display_per_item "
        "ON display_placement(item_id) WHERE active=1"
    ]
    for table in IMMUTABLE:
        for op in ("UPDATE", "DELETE"):
            extra.append(
                f"CREATE TRIGGER {table}_{op.lower()}_immutable BEFORE {op} ON {table} "
                "BEGIN SELECT RAISE(ABORT,'immutable structural history'); END"
            )
    return (*target_tables().values(), *V10_OBJECTS, *extra)


def _schema(conn: sqlite3.Connection) -> None:
    expected = {sql.strip().rstrip(";") for sql in declarations()}
    actual = {
        row[0].strip().rstrip(";")
        for row in conn.execute(
            "SELECT sql FROM sqlite_schema WHERE sql IS NOT NULL AND name <> 'sqlite_sequence'"
        )
    }
    if actual != expected:
        raise StoreError("schema")


def _integrity(conn: sqlite3.Connection) -> None:
    if (
        conn.execute("PRAGMA integrity_check").fetchall() != [("ok",)]
        or conn.execute("PRAGMA foreign_key_check").fetchall()
    ):
        raise StoreError("integrity")


@contextmanager
def connect(
    scope: OwnedFiles, name: str, *, readonly: bool = False
) -> Iterator[sqlite3.Connection]:
    path = scope.check(name)
    conn = sqlite3.connect(
        path.as_uri() + ("?mode=ro" if readonly else "?mode=rw"), uri=True, isolation_level=None
    )
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA synchronous=FULL")
        conn.execute("PRAGMA busy_timeout=5000")
        mode = conn.execute(
            "PRAGMA journal_mode" if readonly else "PRAGMA journal_mode=WAL"
        ).fetchone()
        if (
            mode != ("wal",)
            or conn.execute("PRAGMA synchronous").fetchone() != (2,)
            or conn.execute("PRAGMA foreign_keys").fetchone() != (1,)
            or conn.execute("PRAGMA busy_timeout").fetchone() != (5000,)
        ):
            raise StoreError("policy")
        if readonly:
            conn.execute("PRAGMA query_only=ON")
            if conn.execute("PRAGMA query_only").fetchone() != (1,):
                raise StoreError("policy")
        yield conn
    except sqlite3.Error:
        raise StoreError("integrity") from None
    finally:
        conn.close()


@dataclass(frozen=True)
class Snapshot:
    tables: tuple[TableImage, ...]
    sequences: tuple[tuple[str, int], ...]

    def table(self, name: str) -> TableImage:
        found = tuple(table for table in self.tables if table.name == name)
        if len(found) != 1:
            raise StoreError("state")
        return found[0]

    def rows(self, name: str) -> tuple[tuple[Cell, ...], ...]:
        return self.table(name).rows


def capture(conn: sqlite3.Connection) -> Snapshot:
    tables = []
    for name in sorted(target_tables()):
        # Identifiers exclusively from frozen declarations, never caller SQL.
        cursor = conn.execute(
            f'SELECT * FROM "{name}" ORDER BY '  # noqa: S608 -- frozen identifier
            + ",".join(str(n + 1) for n in range(len(_columns(name))))
        )
        tables.append(
            TableImage(name, tuple(col[0] for col in cursor.description), tuple(cursor.fetchall()))
        )
    return Snapshot(
        tuple(tables), tuple(conn.execute("SELECT name,seq FROM sqlite_sequence ORDER BY name"))
    )


def _columns(name: str) -> tuple[str, ...]:
    return tuple(
        re.findall(
            r"(?:^ |, )([a-z_]+) (?:INTEGER|TEXT|REAL)\b", target_tables()[name], re.MULTILINE
        )
    )


def validate(
    snapshot: Snapshot,
    catalogs: tuple[CatalogSnapshot, ...],
    contexts: tuple[tuple[int, LayoutContext], ...],
) -> CanonicalLife:
    """Complete admission; unsupported world hooks explicitly refuse."""
    try:
        if len(snapshot.tables) != len(target_tables()) or {t.name for t in snapshot.tables} != set(
            target_tables()
        ):
            raise StoreError("state")
        for table in snapshot.tables:
            if table.columns != _columns(table.name):
                raise StoreError("state")
        if set(snapshot.rows("activity_kind")) != {(activity.value,) for activity in Activity}:
            raise StoreError("state")
        if snapshot.rows("world_event") or snapshot.rows("display_placement"):
            raise StoreError("state")
        (identity,) = snapshot.rows("maple")
        (raw,) = snapshot.rows("life_state")
        values = dict(zip(LIFE_FIELDS, raw, strict=True))
        reference = LifeReference(
            cast(int, values["maple_id"]),
            cast(int, values["layout_revision"]),
            cast(str, values["point_host"]),
            cast(str, values["point_id"]),
        )
        rows = tuple(RevisionRow(*cast(Any, row)) for row in snapshot.rows("layout_revision"))
        keys = LayoutKeys(
            *(
                cast(Any, snapshot.rows(name))
                for name in ("layout_host", "layout_room", "layout_point", "layout_slot")
            )
        )
        # The pure proof accepts active keys only; separately verify all historic sets.
        active_keys = LayoutKeys(
            *(
                cast(
                    Any,
                    tuple(
                        row for row in snapshot.rows(name) if row[0] == reference.layout_revision
                    ),
                )
                for name in ("layout_host", "layout_room", "layout_point", "layout_slot")
            )
        )
        layout = validate_layout_snapshot(
            rows,
            cast(Any, snapshot.rows("world_state")),
            (reference,),
            active_keys,
            snapshots=catalogs,
            contexts=contexts,
        )
        kinds = {
            (room.kind.value,)
            for revision in layout.revisions
            for room in revision.layout.world.regions
        }
        if set(snapshot.rows("room_kind")) != kinds:
            raise StoreError("state")
        projected = [project_layout_keys(rev.layout, rev.row.id) for rev in layout.revisions]
        for name in ("layout_host", "layout_room", "layout_point", "layout_slot"):
            if tuple(sorted(getattr(keys, name))) != tuple(
                sorted(row for projection in projected for row in getattr(projection, name))
            ):
                raise StoreError("state")
        mask = validate_safe_layout(layout.active.layout.world, layout.active.layout.catalog)
        travel = None
        if values["route_path"] is not None:
            travel = decode_travel_path(
                cast(str, values["route_path"]),
                departed_at=datetime.fromisoformat(cast(str, values["route_departed_at"])),
                route_arrives_at=datetime.fromisoformat(cast(str, values["route_arrives_at"])),
                activity_started_at=datetime.fromisoformat(
                    cast(str, values["activity_started_at"])
                ),
                stored_origin=Tile(cast(int, values["tx"]), cast(int, values["ty"])),
                walkability=mask,
            )
        if any(row[-3:] != (None, None, None) for row in snapshot.rows("decision")):
            raise StoreError("state")
        born_rows = tuple(row for row in snapshot.rows("timeline_event") if row[4] == "born")
        if (
            len(born_rows) != 1
            or born_rows[0][1] != identity[0]
            or born_rows[0][5] != identity[2]
            or json.loads(cast(str, born_rows[0][6]), object_pairs_hook=lambda pairs: pairs)
            != [("name", identity[1])]
        ):
            raise StoreError("state")
        life = reconstruct_life(
            tuple(zip(LIFE_FIELDS, raw, strict=True)),
            identity_row=cast(Any, identity),
            births=(Born(datetime.fromisoformat(cast(str, identity[2])), cast(str, identity[1])),),
            ledger_rows=cast(Any, snapshot.rows("interaction_ledger")),
            goal_rows=cast(Any, snapshot.rows("goal")),
            decisions=cast(Any, tuple(row[:3] for row in snapshot.rows("decision"))),
            layout=layout,
            keys=active_keys,
            travel=travel,
        )
        sequences = dict(snapshot.sequences)
        if len(sequences) != len(snapshot.sequences) or any(
            name not in target_tables()
            or "AUTOINCREMENT" not in target_tables()[name]
            or type(value) is not int
            or value < 0
            for name, value in snapshot.sequences
        ):
            raise StoreError("state")
        for name, sql in target_tables().items():
            if "AUTOINCREMENT" in sql:
                maximum = max((cast(int, row[0]) for row in snapshot.rows(name)), default=0)
                if maximum > sequences.get(name, 0):
                    raise StoreError("state")
        return life
    except (ValueError, TypeError, KeyError, OverflowError, IndexError, RecursionError):
        raise StoreError("state") from None


def load_connection(
    conn: sqlite3.Connection,
    catalogs: tuple[CatalogSnapshot, ...],
    contexts: tuple[tuple[int, LayoutContext], ...],
) -> tuple[Snapshot, CanonicalLife]:
    if conn.execute("PRAGMA application_id").fetchone() != (APPLICATION_ID,) or conn.execute(
        "PRAGMA user_version"
    ).fetchone() != (11,):
        raise StoreError("version")
    _schema(conn)
    _integrity(conn)
    if (
        conn.execute(
            "SELECT 1 FROM layout_revision WHERE length(CAST(document AS BLOB))>262144"
        ).fetchone()
        or conn.execute(
            "SELECT 1 FROM life_state WHERE length(CAST(route_path AS BLOB))>?", (MAX_BYTES,)
        ).fetchone()
    ):
        raise StoreError("state")
    snapshot = capture(conn)
    return snapshot, validate(snapshot, catalogs, contexts)


def load(
    scope: OwnedFiles,
    name: str,
    catalogs: tuple[CatalogSnapshot, ...],
    contexts: tuple[tuple[int, LayoutContext], ...],
) -> tuple[Snapshot, CanonicalLife]:
    with connect(scope, name, readonly=True) as conn:
        conn.execute("BEGIN")
        try:
            return load_connection(conn, catalogs, contexts)
        finally:
            conn.execute("ROLLBACK")


def _insert(
    conn: sqlite3.Connection, table: TableImage, rows: tuple[tuple[Cell, ...], ...] | None = None
) -> None:
    if table.name not in target_tables() or table.columns != _columns(table.name):
        raise StoreError("state")
    conn.executemany(
        f'INSERT INTO "{table.name}" VALUES (' + ",".join("?" for _ in table.columns) + ")",  # noqa: S608 -- allowlisted identifier
        table.rows if rows is None else rows,
    )


def create(
    scope: OwnedFiles,
    name: str,
    snapshot: Snapshot,
    catalogs: tuple[CatalogSnapshot, ...],
    contexts: tuple[tuple[int, LayoutContext], ...],
) -> None:
    compatibility()
    life = validate(snapshot, catalogs, contexts)
    # Explicit fresh birth only; advanced state must follow a distinct save.
    r = life.record
    born = life.identity_row[2]
    if (
        life.layout.revisions[0].row.created_at != born
        or (r.revision, r.activity, r.point_host, r.point_id, r.tx, r.ty)
        != (1, "idle", "idle.hall_center", "idle", 21, 15)
        or (r.mood, r.energy, r.curiosity, r.social) != (60.0, 80.0, 60.0, 50.0)
        or r.activity_started_at != born
        or r.last_tick_at != born
        or r.last_updated_at != born
        or datetime.fromisoformat(r.activity_until) - datetime.fromisoformat(born)
        != timedelta(minutes=15)
        or any(
            (
                r.tick_counter,
                r.interaction_counter,
                r.decision_counter,
                r.action_counter,
                r.goal_counter,
            )
        )
        or life.travel is not None
        or life.ledger_rows
        or life.goal_rows
        or life.reaction
        or life.task
    ):
        raise StoreError("state")
    scope.reserve(name)
    with connect(scope, name) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            for sql in declarations():
                conn.execute(sql)
            conn.execute("PRAGMA defer_foreign_keys=ON")
            if conn.execute("PRAGMA defer_foreign_keys").fetchone() != (1,):
                raise StoreError("policy")
            for table in snapshot.tables:
                _insert(conn, table)
            conn.execute("DELETE FROM sqlite_sequence")
            conn.executemany(
                "INSERT INTO sqlite_sequence(name,seq) VALUES (?,?)", snapshot.sequences
            )
            conn.execute(f"PRAGMA application_id={APPLICATION_ID}")
            conn.execute("PRAGMA user_version=11")
            actual, _ = load_connection(conn, catalogs, contexts)
            if exact(actual) != exact(snapshot):
                raise StoreError("state")
            conn.execute("COMMIT")
        except BaseException:
            conn.set_progress_handler(None, 0)
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise


def save(
    scope: OwnedFiles,
    name: str,
    snapshot: Snapshot,
    *,
    expected_revision: int,
    catalogs: tuple[CatalogSnapshot, ...],
    contexts: tuple[tuple[int, LayoutContext], ...],
    inject: Callable[[str], None] = lambda phase: None,
    commit_progress: Callable[[], int] | None = None,
) -> None:
    """One complete atomic snapshot; append-only facts never rewritten.

    Injection hooks are bounded synthetic test harness hooks. Unknown commit
    acknowledgement is resolved by a later read, never by automatic retry.
    """
    if type(expected_revision) is not int or expected_revision < 1:
        raise StoreError("stale")
    proposed = validate(snapshot, catalogs, contexts)
    with connect(scope, name) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            before, previous = load_connection(conn, catalogs, contexts)
            if (
                previous.record.revision != expected_revision
                or proposed.record.revision != expected_revision + 1
            ):
                raise StoreError("stale")
            if (proposed.layout.revisions, proposed.layout.active_revision) != (
                previous.layout.revisions,
                previous.layout.active_revision,
            ) or proposed.identity_row != previous.identity_row:
                # R4 editing is deferred; pointer and layout remain exact in this lane.
                raise StoreError("state")
            immutable = (
                set(target_tables()) - {schema.name for schema in HISTORY_SCHEMA} - {"life_state"}
            )
            old_seq, new_seq = dict(before.sequences), dict(snapshot.sequences)
            if any(new_seq.get(key, -1) < value for key, value in old_seq.items()):
                raise StoreError("state")
            conn.execute("PRAGMA defer_foreign_keys=ON")
            if conn.execute("PRAGMA defer_foreign_keys").fetchone() != (1,):
                raise StoreError("policy")
            for table in before.tables:
                after = snapshot.table(table.name)
                if table.name == "life_state":
                    continue
                if table.name in immutable or table.name == "maple":
                    if table != after:
                        raise StoreError("state")
                    continue
                if table.name == "interaction_ledger":
                    conn.execute(f'DELETE FROM "{table.name}"')  # noqa: S608 -- frozen identifier
                    _insert(conn, after)
                elif table.name == "journal_state":
                    if not table.rows:
                        _insert(conn, after)
                    elif len(after.rows) == 1 and after.rows[0][0] == table.rows[0][0]:
                        fields = ",".join(f'"{field}"=?' for field in table.columns[1:])
                        conn.execute(
                            f"UPDATE journal_state SET {fields} WHERE maple_id=?",  # noqa: S608 -- frozen columns
                            (*after.rows[0][1:], after.rows[0][0]),
                        )
                    else:
                        raise StoreError("state")
                else:
                    # Histories are append-only; mutable memory updates are deferred
                    # in this bounded synthetic writer, so every old cell survives.
                    if not set(table.rows) <= set(after.rows):
                        raise StoreError("state")
                    _insert(conn, after, tuple(row for row in after.rows if row not in table.rows))
            conn.execute("DELETE FROM sqlite_sequence")
            conn.executemany(
                "INSERT INTO sqlite_sequence(name,seq) VALUES (?,?)", snapshot.sequences
            )
            assignments = ",".join(f'"{field}"=?' for field in LIFE_FIELDS)
            conn.execute(
                f"UPDATE life_state SET {assignments} WHERE maple_id=1 AND revision=?",  # noqa: S608 -- frozen columns
                (*snapshot.rows("life_state")[0], expected_revision),
            )
            inject("after_write")
            actual, _ = load_connection(conn, catalogs, contexts)
            if exact(actual) != exact(snapshot):
                raise StoreError("state")
            inject("before_commit")
            # Progress callback runs inside SQLite's COMMIT VM. Only the owned
            # worker supplies a process-exit hook; normal writes have none.
            conn.set_progress_handler(commit_progress, 1)
            conn.execute("COMMIT")
            conn.set_progress_handler(None, 0)
            inject("after_commit")
        except BaseException:
            conn.set_progress_handler(None, 0)
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise


def exact(snapshot: Snapshot) -> tuple[object, ...]:
    """Typed values, including float hex; row equality cannot hide coercion/-0."""
    return (
        tuple(
            (
                table.name,
                table.columns,
                tuple(
                    tuple(
                        (type(cell).__name__, cell.hex() if type(cell) is float else cell)
                        for cell in row
                    )
                    for row in table.rows
                ),
            )
            for table in snapshot.tables
        ),
        snapshot.sequences,
    )


def old_history(snapshot: Snapshot) -> tuple[TableImage, ...]:
    """Every non-life historical column, retaining the v11 decision triple."""
    return tuple(snapshot.table(schema.name) for schema in HISTORY_SCHEMA)
