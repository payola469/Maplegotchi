"""Unshipped candidate v11 converter; accepts only owned synthetic rehearsal handles."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from importlib.resources import files
from pathlib import Path
from typing import Any

from maplegotchi.core.activities import Activity
from maplegotchi.core.daytime import require_utc
from maplegotchi.core.identity import Identity
from maplegotchi.core.rng import RngState
from maplegotchi.core.room import canonical_point
from maplegotchi.core.state import Needs
from maplegotchi.core.world.catalog import CatalogLayout
from maplegotchi.core.world.coordinates import GRID_HEIGHT, GRID_WIDTH, Tile
from maplegotchi.core.world.layout import WorldLayout
from maplegotchi.core.world.model import RegionKind
from maplegotchi.core.world.movement import MS_PER_STEP, Travel
from maplegotchi.core.world.pathfinding import Route, Waypoint
from maplegotchi.core.world.placement import (
    DisplayItem,
    DisplayPlacement,
    PlacementContext,
    PlacementSnapshot,
    SlotKey,
    derive_storage,
)
from maplegotchi.core.world.resolution import (
    ResolutionSnapshot,
    requirement_for,
    validate_activity_coverage,
)
from maplegotchi.core.world.walkability import validate_safe_layout
from maplegotchi.runtime.world_catalog import parse_catalog
from maplegotchi.runtime.world_layout import parse_layout
from maplegotchi.storage.db import take_pre_migration_snapshot
from maplegotchi.storage.errors import MigrationError, StorageError
from maplegotchi.storage.migrations import _UTC_TS, APPLICATION_ID, schema_version, split_statements
from maplegotchi.storage.repositories import LifeRepository
from tests.rehearsal.fixtures import SyntheticLife, guarded

# Only identity mapping from Final Spec §R; coordinates come from approved catalog data.
POINT_MAP = (
    ("bed.side", "bed.bedroom", "sleep"),
    ("sofa.seat", "sofa.living", "seat"),
    ("bookshelf.front", "bookshelf.library_1", "front_l"),
    ("window.view", "window.living", "view"),
    ("writing_desk.chair", "desk.writing", "chair"),
    ("computer_desk.chair", "desk.computer", "operator"),
    ("open_area.west", "idle.hall_west", "idle"),
    ("open_area.center", "idle.hall_center", "idle"),
    ("open_area.east", "idle.hall_east", "idle"),
)


class Failure(StrEnum):
    SNAPSHOT = "snapshot"
    TABLES = "partial_tables"
    CONVERSION = "conversion"
    FOREIGN_KEYS = "foreign_keys"
    STATE = "state"
    COMMIT = "before_commit"


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def quote(name: str) -> str:
    if not re.fullmatch(r"[a-z_][a-z_0-9]*", name):
        raise ValueError("invalid SQL identifier")
    return '"' + name + '"'


def capture(conn: sqlite3.Connection) -> dict[str, tuple[tuple[Any, ...], ...]]:
    names = [
        r[0]
        for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    ]
    return {
        name: tuple(conn.execute(f"SELECT * FROM {quote(name)} ORDER BY rowid"))  # noqa: S608
        for name in names
    }


def state_row(conn: sqlite3.Connection) -> dict[str, Any]:
    cursor = conn.execute("SELECT * FROM life_state")
    rows = cursor.fetchall()
    if len(rows) != 1:
        raise ValueError("exactly one life state required")
    return dict(zip((c[0] for c in cursor.description), rows[0], strict=True))


def initial_document() -> tuple[str, str, str]:
    root = files("maplegotchi.world_catalog")
    house = json.loads(root.joinpath("initial_house.json").read_text(encoding="utf-8"))
    catalog = json.loads(root.joinpath("initial_catalog.json").read_text(encoding="utf-8"))
    catalog_text = canonical(catalog["types"])
    document = canonical(
        {"house": house, "instances": catalog["instances"], "themes": {}, "lighting_presets": {}}
    )
    return document, catalog_text, digest(catalog_text)


SCHEMA = f"""
CREATE TABLE activity_kind (id TEXT PRIMARY KEY) STRICT;
CREATE TABLE room_kind (id TEXT PRIMARY KEY) STRICT;
CREATE TABLE layout_revision (
 id INTEGER PRIMARY KEY CHECK(id >= 1), created_at TEXT NOT NULL CHECK(created_at {_UTC_TS}),
 author TEXT NOT NULL CHECK(author IN ('paolo','migration')),
 base_revision INTEGER REFERENCES layout_revision(id),
 catalog_version INTEGER NOT NULL CHECK(catalog_version >= 1),
 catalog_hash TEXT NOT NULL CHECK(length(catalog_hash)=64),
 document TEXT NOT NULL CHECK(json_valid(document)),
 validation_digest TEXT NOT NULL CHECK(length(validation_digest)=64)
) STRICT;
CREATE TABLE world_state (
 id INTEGER PRIMARY KEY CHECK(id=1), active_revision INTEGER NOT NULL REFERENCES layout_revision(id)
) STRICT;
CREATE TABLE layout_host (
 revision INTEGER NOT NULL REFERENCES layout_revision(id), id TEXT NOT NULL,
 PRIMARY KEY(revision,id)
) STRICT;
CREATE TABLE layout_room (
 revision INTEGER NOT NULL REFERENCES layout_revision(id), id TEXT NOT NULL,
 kind TEXT NOT NULL REFERENCES room_kind(id), PRIMARY KEY(revision,id)
) STRICT;
CREATE TABLE layout_point (
 revision INTEGER NOT NULL, host_id TEXT NOT NULL, id TEXT NOT NULL,
 PRIMARY KEY(revision,host_id,id), FOREIGN KEY(revision,host_id) REFERENCES layout_host(revision,id)
) STRICT;
CREATE TABLE layout_slot (
 revision INTEGER NOT NULL, host_id TEXT NOT NULL, id TEXT NOT NULL,
 PRIMARY KEY(revision,host_id,id), FOREIGN KEY(revision,host_id) REFERENCES layout_host(revision,id)
) STRICT;
CREATE TABLE world_event (
 id INTEGER PRIMARY KEY AUTOINCREMENT, maple_id INTEGER NOT NULL REFERENCES maple(id),
 type TEXT NOT NULL CHECK(length(type) BETWEEN 1 AND 80),
 at TEXT NOT NULL CHECK(at {_UTC_TS}),
 revision INTEGER NOT NULL CHECK(revision >= 1),
 layout_revision INTEGER REFERENCES layout_revision(id),
 goal_id INTEGER REFERENCES goal(id), action_id INTEGER CHECK(action_id >= 0),
 decision_id INTEGER REFERENCES decision(id),
 priority TEXT CHECK(priority IN ('critical','high','normal','low')),
 payload TEXT NOT NULL CHECK(json_valid(payload))
) STRICT;
CREATE TABLE display_placement (
 id TEXT PRIMARY KEY, item_id TEXT NOT NULL, layout_revision INTEGER NOT NULL,
 host_id TEXT NOT NULL, slot_id TEXT NOT NULL, active INTEGER NOT NULL CHECK(active IN (0,1)),
 link TEXT, origin_event INTEGER REFERENCES world_event(id),
 FOREIGN KEY(layout_revision,host_id,slot_id) REFERENCES layout_slot(revision,host_id,id)
) STRICT;
CREATE UNIQUE INDEX one_active_display_per_item ON display_placement(item_id) WHERE active=1;
"""


def freeze_table(conn: sqlite3.Connection, table: str) -> None:
    for op in ("UPDATE", "DELETE"):
        conn.execute(
            f"CREATE TRIGGER {quote(table + '_' + op.lower() + '_immutable')} "
            f"BEFORE {op} ON {quote(table)} "
            "BEGIN SELECT RAISE(ABORT,'append-only candidate history'); END"
        )


@dataclass(frozen=True, slots=True)
class CandidateLife:
    identity: Identity
    revision: int
    activity: Activity
    needs: Needs
    rng: RngState
    tile: Tile
    host: str
    point: str
    travel: Travel | None
    world: WorldLayout
    catalog: CatalogLayout

    @property
    def region(self) -> str:
        for room in self.world.regions:
            if room.floor.contains(self.tile):
                return room.id
        for door in self.world.doors:
            if door.passage.contains(self.tile):
                return door.south_room
        raise ValueError("position has no region")


def load_candidate(handle: SyntheticLife, items: tuple[DisplayItem, ...] = ()) -> CandidateLife:
    owned = guarded(handle)
    conn = owned.conn
    if schema_version(conn) not in (10, 11):
        raise ValueError("unsupported rehearsal schema")
    revisions = conn.execute(
        "SELECT r.* FROM layout_revision r JOIN world_state w "
        "ON w.active_revision=r.id WHERE w.id=1"
    ).fetchall()
    if len(revisions) != 1:
        raise ValueError("missing active layout")
    revision, created, _author, _base, version, catalog_hash, text, validation = revisions[0]
    require_utc(datetime.fromisoformat(created))
    if canonical(json.loads(text)) != text or digest(text) != validation or version != 1:
        raise ValueError("invalid canonical layout/digest/version")
    document = json.loads(text)
    _, catalog_text, expected_hash = initial_document()
    if catalog_hash != expected_hash:
        raise ValueError("catalog hash mismatch")
    world = parse_layout(canonical(document["house"]))
    catalog = parse_catalog(
        canonical({"types": json.loads(catalog_text), "instances": document["instances"]}), world
    )
    mask = validate_safe_layout(world, catalog)
    validate_activity_coverage(ResolutionSnapshot(world, catalog))
    expected_indexes = {
        "layout_host": tuple(sorted((revision, h.id) for h in catalog.instances)),
        "layout_point": tuple(
            sorted((revision, p.instance_id, p.template.id) for p in catalog.points)
        ),
        "layout_slot": tuple(
            sorted((revision, s.instance_id, s.template.id) for s in catalog.slots)
        ),
        "layout_room": tuple(sorted((revision, r.id, r.kind.value) for r in world.regions)),
    }
    for table, expected in expected_indexes.items():
        actual = tuple(
            sorted(
                conn.execute(
                    f"SELECT * FROM {quote(table)} WHERE revision=?",  # noqa: S608
                    (revision,),
                ).fetchall()
            )
        )
        if actual != expected:
            raise ValueError("layout identity index differs from authoritative document")
    row = state_row(conn)
    if row["layout_revision"] != revision:
        raise ValueError("state and active layout revision differ")
    tile = Tile(row["tx"], row["ty"])
    if tile not in mask.walkable:
        raise ValueError("unsafe candidate position")
    point = next(
        (
            p
            for p in catalog.points
            if (p.instance_id, p.template.id) == (row["point_host"], row["point_id"])
        ),
        None,
    )
    if point is None:
        raise ValueError("unknown active point")
    activity = Activity(row["activity"])
    requirement = requirement_for(activity)
    host = next(h for h in catalog.instances if h.id == point.instance_id)
    room = next(r for r in world.regions if r.id == host.room_id)
    if requirement.room_tier(room.kind) is None or not any(
        all(c in point.template.provides for c in group) for group in requirement.alternatives
    ):
        raise ValueError("candidate point cannot provide active activity")
    destination = Tile(point.template.approach.x, point.template.approach.y)
    travel = None
    if row["route_path"] is not None:
        values = json.loads(row["route_path"])
        route = Route(tuple(Waypoint(*p) for p in values))
        travel = Travel(route, datetime.fromisoformat(row["route_departed_at"]), MS_PER_STEP)
        if (
            travel.arrives_at.isoformat() != row["route_arrives_at"]
            or row["activity_started_at"] != row["route_arrives_at"]
        ):
            raise ValueError("candidate route timing mismatch")
        if (
            route.destination != destination
            or route.origin != tile
            or any(t not in mask.walkable for t in route.tiles())
        ):
            raise ValueError("invalid candidate route/destination")
    elif tile != destination or row["route_arrives_at"] is not None:
        raise ValueError("invalid stationary candidate")
    identity_row = conn.execute("SELECT name,born_at,life_seed FROM maple WHERE id=1").fetchone()
    if identity_row is None:
        raise ValueError("missing candidate identity")
    name, born, seed = identity_row
    identity = Identity(name, datetime.fromisoformat(born))
    times = {
        name: datetime.fromisoformat(row[name])
        for name in ("activity_started_at", "activity_until", "last_tick_at", "last_updated_at")
    }
    for value in times.values():
        require_utc(value)
    if not (
        identity.born_at <= times["activity_started_at"] <= times["activity_until"]
        and identity.born_at <= times["last_tick_at"] <= times["last_updated_at"]
    ):
        raise ValueError("invalid candidate continuity times")
    if travel is None and times["activity_started_at"] > times["last_updated_at"]:
        raise ValueError("stationary activity starts after last update")
    # Authoritative metadata stays outside persistence; never manufacture inventory rows.
    rows = conn.execute(
        "SELECT id,item_id,host_id,slot_id,active,link,layout_revision FROM display_placement "
        "ORDER BY id"
    ).fetchall()
    if any(r[6] != revision and r[4] for r in rows):
        raise ValueError("active display belongs to another layout")
    placements = tuple(
        DisplayPlacement(r[0], r[1], SlotKey(r[2], r[3]), bool(r[4]), r[5]) for r in rows
    )
    derive_storage(
        PlacementContext(
            PlacementSnapshot(world, catalog),
            items,
            placements,
            times["last_updated_at"],
            timedelta(0),
            tile,
        )
    )
    return CandidateLife(
        identity,
        row["revision"],
        Activity(row["activity"]),
        Needs(row["mood"], row["energy"], row["curiosity"], row["social"]),
        RngState(seed, row["tick_counter"], row["interaction_counter"], row["decision_counter"]),
        tile,
        row["point_host"],
        row["point_id"],
        travel,
        world,
        catalog,
    )


def rebuild(conn: sqlite3.Connection, name: str, mapped: dict[str, Any] | None) -> None:
    schema = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()[0]
    objects = conn.execute(
        "SELECT sql FROM sqlite_master WHERE tbl_name=? AND type IN ('index','trigger') "
        "AND sql IS NOT NULL ORDER BY type,name",
        (name,),
    ).fetchall()
    schema = re.sub(
        r"CHECK\s*\(\s*(activity|route_from_activity|suspended_action|proposed_action|executed_action)\s+IN\s+\([^)]*\)\s*\)",
        "REFERENCES activity_kind(id)",
        schema,
    )
    if name == "life_state":
        schema = re.sub(
            r"\s+location\s+TEXT\s+NOT NULL\s+CHECK\s*\(location IN\s*\([^)]*\)\),", "", schema
        )
        schema = re.sub(
            r"point_id\s+TEXT\s+CHECK\s*\(length\(point_id\) BETWEEN 1 AND 40\)",
            "point_id TEXT NOT NULL",
            schema,
        )
        fields = f"""layout_revision INTEGER NOT NULL REFERENCES layout_revision(id),
 point_host TEXT NOT NULL, tx INTEGER NOT NULL CHECK(tx >= 0 AND tx < {GRID_WIDTH}),
 ty INTEGER NOT NULL CHECK(ty >= 0 AND ty < {GRID_HEIGHT}), route_arrives_at TEXT,
 FOREIGN KEY(layout_revision,point_host,point_id) REFERENCES layout_point(revision,host_id,id),
"""
        # Add columns before the first table-level CHECK, not ALTER an existing row.
        schema = schema.replace(
            "    CHECK ((reaction_kind", fields + "    CHECK ((reaction_kind", 1
        )
    temporary = name + "_candidate"
    schema = re.sub(
        r'^CREATE TABLE (?:"' + name + '"|' + name + r")\s*\(",
        "CREATE TABLE " + quote(temporary) + " (",
        schema,
        count=1,
    )
    conn.execute(schema)
    columns = [r[1] for r in conn.execute(f"PRAGMA table_info({quote(temporary)})")]
    if mapped is None:
        conn.execute(f"INSERT INTO {quote(temporary)} SELECT * FROM {quote(name)}")  # noqa: S608
    else:
        conn.execute(
            f"INSERT INTO {quote(temporary)} VALUES ({','.join('?' for _ in columns)})",  # noqa: S608
            tuple(mapped[c] for c in columns),
        )
    conn.execute(f"DROP TABLE {quote(name)}")
    conn.execute(f"ALTER TABLE {quote(temporary)} RENAME TO {quote(name)}")
    for (sql,) in objects:
        conn.execute(sql)


def fsync_directory(path: Path) -> None:
    # Python cannot open directory handles for fsync on Windows; file fsync remains mandatory.
    if sys.platform != "win32":
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def rollback_if_active(conn: sqlite3.Connection) -> None:
    # Inspect live SQLite state after any failed statement, not a cached Python assumption.
    if conn.in_transaction:
        conn.execute("ROLLBACK")


@dataclass(frozen=True, slots=True)
class RehearsalResult:
    backup: str
    validation_digest: str
    position: Tile
    history: tuple[tuple[str, int, int | None], ...]


def rehearse(
    handle: SyntheticLife, at: datetime, failure: Failure | None = None
) -> RehearsalResult:
    owned = guarded(handle)
    require_utc(at)
    conn = owned.conn
    if failure is not None and not isinstance(failure, Failure):
        raise ValueError("unknown failure injection")
    if conn.in_transaction or schema_version(conn) != 10:
        raise MigrationError("requires unconverted schema v10 outside a transaction")
    if conn.execute("PRAGMA application_id").fetchone()[0] != APPLICATION_ID:
        raise MigrationError("incorrect application_id")
    if (
        conn.execute("PRAGMA integrity_check").fetchall() != [("ok",)]
        or conn.execute("PRAGMA foreign_key_check").fetchall()
    ):
        raise MigrationError("source integrity/FK validation failed")
    try:
        source = LifeRepository(conn).load()
        old = state_row(conn)
        if conn.execute("SELECT count(*) FROM maple").fetchone()[0] != 1:
            raise ValueError("exactly one identity required")
        legacy = (
            source.state.point_id
            or canonical_point(source.state.activity, source.state.location).id
        )
        match = next((p for p in POINT_MAP if p[0] == legacy), None)
        if match is None:
            raise ValueError("unknown legacy point")
        if source.state.route is not None and source.state.route.destination.id != legacy:
            raise ValueError("legacy route destination differs from active point")
        if at < source.state.last_updated_at:
            raise ValueError("migration time precedes synthetic state")
    except (ValueError, TypeError, LookupError, StorageError) as exc:
        raise MigrationError("invalid source state/mapping") from exc
    before = capture(conn)
    if failure is Failure.SNAPSHOT:
        raise MigrationError("injected snapshot failure; conversion not started")
    backup = take_pre_migration_snapshot(conn, owned.data_dir, at)
    fsync_directory(owned.data_dir.path("pre-migration"))
    fsync_directory(owned.root)
    document, _, catalog_hash = initial_document()
    parsed = json.loads(document)
    world = parse_layout(canonical(parsed["house"]))
    _, types, _ = initial_document()
    catalog = parse_catalog(
        canonical({"types": json.loads(types), "instances": parsed["instances"]}), world
    )
    point = next(p for p in catalog.points if (p.instance_id, p.template.id) == match[1:])
    tile = Tile(point.template.approach.x, point.template.approach.y)
    original_foreign_keys = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    conn.execute("PRAGMA foreign_keys=OFF")
    try:
        conn.execute("BEGIN IMMEDIATE")
        if capture(conn) != before:
            raise MigrationError("source changed after backup")
        for number, sql in enumerate(split_statements(SCHEMA)):
            conn.execute(sql)
            if failure is Failure.TABLES and number == 1:
                raise MigrationError("injected failure after partial DDL")
        conn.executemany("INSERT INTO activity_kind VALUES (?)", ((a.value,) for a in Activity))
        conn.executemany("INSERT INTO room_kind VALUES (?)", ((k.value,) for k in RegionKind))
        conn.execute(
            "INSERT INTO layout_revision VALUES (1,?,'migration',NULL,1,?,?,?)",
            (at.isoformat(), catalog_hash, document, digest(document)),
        )
        conn.execute("INSERT INTO world_state VALUES (1,1)")
        conn.executemany(
            "INSERT INTO layout_host VALUES (1,?)", ((h.id,) for h in catalog.instances)
        )
        conn.executemany(
            "INSERT INTO layout_room VALUES (1,?,?)", ((r.id, r.kind.value) for r in world.regions)
        )
        conn.executemany(
            "INSERT INTO layout_point VALUES (1,?,?)",
            ((p.instance_id, p.template.id) for p in catalog.points),
        )
        conn.executemany(
            "INSERT INTO layout_slot VALUES (1,?,?)",
            ((s.instance_id, s.template.id) for s in catalog.slots),
        )
        mapped = {
            **old,
            "layout_revision": 1,
            "point_host": match[1],
            "point_id": match[2],
            "tx": tile.tx,
            "ty": tile.ty,
            "route_arrives_at": None,
        }
        if source.state.route is not None:
            mapped.update(
                route_path=canonical([[tile.tx, tile.ty, 0]]),
                route_departed_at=source.state.route.arrives_at.isoformat(),
                route_arrives_at=source.state.route.arrives_at.isoformat(),
            )
        for table in ("life_state", "journal_entry", "decision"):
            rebuild(conn, table, mapped if table == "life_state" else None)
        conn.execute("DELETE FROM sqlite_sequence")
        conn.executemany(
            "INSERT INTO sqlite_sequence(name,seq) VALUES (?,?)", before["sqlite_sequence"]
        )
        for table in (
            "layout_revision",
            "layout_host",
            "layout_point",
            "layout_slot",
            "layout_room",
            "world_event",
        ):
            freeze_table(conn, table)
        if failure is Failure.CONVERSION:
            raise MigrationError("injected data conversion failure")
        if failure is Failure.FOREIGN_KEYS:
            conn.execute("UPDATE world_state SET active_revision=999")
        if conn.execute("PRAGMA foreign_key_check").fetchall():
            raise MigrationError("candidate foreign key validation failed")
        if failure is Failure.STATE:
            conn.execute("UPDATE life_state SET tx=0,ty=0,revision=revision+1")
        candidate = load_candidate(handle)
        after = capture(conn)
        if any(after[table] != rows for table, rows in before.items() if table != "life_state"):
            raise MigrationError("identity/history/sequence preservation failed")
        actual_state = state_row(conn)
        changed = {"location", "point_id", "route_path", "route_departed_at"}
        if any(actual_state[k] != v for k, v in old.items() if k not in changed):
            raise MigrationError("life continuity preservation failed")
        if conn.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise MigrationError("candidate integrity validation failed")
        if failure is Failure.COMMIT:
            raise MigrationError("injected failure before commit")
        conn.execute("PRAGMA user_version=11")
        conn.execute("COMMIT")
    except BaseException as exc:
        rollback_if_active(conn)
        raise MigrationError("candidate conversion refused; transaction rolled back") from exc
    finally:
        conn.execute(f"PRAGMA foreign_keys={int(original_foreign_keys)}")
    history = tuple(
        (name, len(rows), max((int(row[0]) for row in rows), default=None))
        for name, rows in before.items()
        if name in {"timeline_event", "decision", "action_event"}
    )
    return RehearsalResult(backup, digest(document), candidate.tile, history)
