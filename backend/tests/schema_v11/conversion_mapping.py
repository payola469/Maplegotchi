"""Contract §§3/5/8/10 mapping, no SQL, birth, runtime or new persisted format."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from maplegotchi.core.daytime import require_utc
from maplegotchi.core.room import canonical_point
from maplegotchi.core.state import MapleState
from maplegotchi.core.world.coordinates import Tile
from maplegotchi.core.world.movement import MS_PER_STEP, Travel
from maplegotchi.core.world.pathfinding import Route, Waypoint
from maplegotchi.core.world.walkability import validate_safe_layout
from maplegotchi.persistence.layout_codec import CatalogSnapshot, LayoutContext
from maplegotchi.persistence.layout_keys import project_layout_keys
from maplegotchi.persistence.travel_codec import encode_travel_path
from tests.schema_v11 import owned_store as store
from tests.schema_v11.conversion_fixture import ConversionError, columns
from tests.schema_v11.declarations import V10_TABLES, target_tables
from tests.schema_v11.restart_worker import resources
from tests.schema_v11.row_conservation import (
    HistoryImage,
    Row,
    TableImage,
    validate_history_conservation,
)

# Fixed Final Spec §R identities, not geometry or normal live projection policy.
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


def mapping_manifest() -> tuple[tuple[str, str, str, str], ...]:
    """Every one of213 source fields has a target rule and exact check obligation."""
    rules = {
        "location": ("derive region from mapped tile; remove competing location", "derived region"),
        "point_id": (
            "nine SpecR identities / canonical fallback for NULL",
            "point_host + point_id",
        ),
        "route_path": (
            "NULL remains NULL; existing route becomes versioned zero-step at destination",
            "route_path",
        ),
        "route_departed_at": (
            "NULL remains NULL; existing route retains original arrival",
            "route_departed_at",
        ),
    }
    result = []
    for name in sorted(V10_TABLES):
        for column in columns(name):
            rule, target = (
                rules.get(column, ("preserve exact SQL type/value/null/text", column))
                if name == "life_state"
                else ("preserve exact SQL type/value/null/text", column)
            )
            result.append(
                (
                    f"{name}.{column}",
                    rule,
                    f"{name}.{target}",
                    "test_all_source_fields_classified_and_conserved",
                )
            )
    return tuple(result)


def history(image: store.Snapshot) -> HistoryImage:
    return HistoryImage(
        tuple(t for t in image.tables if t.name in V10_TABLES and t.name != "life_state"),
        image.sequences,
    )


def mapped(
    source: store.Snapshot, state: MapleState, at: datetime
) -> tuple[store.Snapshot, tuple[CatalogSnapshot, ...], tuple[tuple[int, LayoutContext], ...]]:
    require_utc(at)
    if at < state.last_updated_at:
        raise ConversionError("time")
    legacy = state.point_id or canonical_point(state.activity, state.location).id
    matches = tuple(p for p in POINT_MAP if p[0] == legacy)
    if len(matches) != 1 or (state.route is not None and state.route.destination.id != legacy):
        raise ConversionError("mapping")
    _, host, local = matches[0]
    catalog, context, document = resources()
    point = next(
        p for p in document.catalog.points if (p.instance_id, p.template.id) == (host, local)
    )
    tile = Tile(point.template.approach.x, point.template.approach.y)
    context = replace(context, maple_tile=tile)
    keys = project_layout_keys(document, 1)
    raw = dict(zip(columns("life_state"), source.rows("life_state")[0], strict=True))
    raw.pop("location")
    raw.update(
        layout_revision=1,
        point_host=host,
        point_id=local,
        tx=tile.tx,
        ty=tile.ty,
        route_arrives_at=None,
    )
    if state.route is not None:
        travel = Travel(
            Route((Waypoint(tile.tx, tile.ty, 0),)), state.route.arrives_at, MS_PER_STEP
        )
        raw.update(
            route_path=encode_travel_path(
                travel, walkability=validate_safe_layout(document.world, document.catalog)
            ),
            route_departed_at=raw["activity_started_at"],
            route_arrives_at=raw["activity_started_at"],
        )
    tables = []
    for name in sorted(target_tables()):
        cols = store._columns(name)
        rows: tuple[Row, ...]
        if name == "life_state":
            rows = (tuple(raw[c] for c in cols),)
        elif name in V10_TABLES:
            rows = source.rows(name)
            if name == "decision":
                rows = tuple((*row, None, None, None) for row in rows)
        elif name == "activity_kind":
            from maplegotchi.core.activities import Activity

            rows = tuple((name,) for name in sorted(a.value for a in Activity))
        elif name == "room_kind":
            rows = tuple((kind,) for kind in sorted({r.kind.value for r in document.world.regions}))
        elif name == "layout_revision":
            rows = (
                (
                    1,
                    at.isoformat(),
                    "migration",
                    None,
                    catalog.version,
                    catalog.catalog_hash,
                    document.canonical_bytes.decode(),
                    document.validation_digest,
                ),
            )
        elif name == "world_state":
            rows = ((1, 1),)
        elif name in {"layout_host", "layout_room", "layout_point", "layout_slot"}:
            rows = getattr(keys, name)
        else:
            rows = ()
        tables.append(TableImage(name, cols, rows))
    target = store.Snapshot(tuple(tables), source.sequences)
    validate_history_conservation(history(source), history(target))
    # Every unchanged life cell is exact, including nullable and SQL UTC spelling.
    new = dict(zip(store._columns("life_state"), target.rows("life_state")[0], strict=True))
    old = dict(zip(columns("life_state"), source.rows("life_state")[0], strict=True))
    for field, value in old.items():
        if field not in {"location", "point_id", "route_path", "route_departed_at"} and (
            type(new[field]),
            new[field],
        ) != (type(value), value):
            raise ConversionError("conservation")
    store.validate(target, (catalog,), ((1, context),))
    return target, (catalog,), ((1, context),)
