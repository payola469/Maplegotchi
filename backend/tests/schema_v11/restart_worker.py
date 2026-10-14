"""Bounded STEP 220 child executable and deterministic synthetic specimen.

No module-level I/O. Only main() opens an explicitly parent-owned capability.
The digest is harness evidence, not an invented persisted document format.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, NoReturn

from maplegotchi.core.world.coordinates import Tile
from maplegotchi.core.world.movement import EdgeStart, Entry, Travel
from maplegotchi.core.world.pathfinding import Route, Waypoint
from maplegotchi.core.world.walkability import validate_safe_layout
from tests.schema_v11.declarations import target_tables
from tests.schema_v11.layout_codec import CatalogSnapshot, LayoutContext, encode_layout_document
from tests.schema_v11.layout_keys import project_layout_keys
from tests.schema_v11.life_record import LIFE_FIELDS, NULLABLE_FIELDS
from tests.schema_v11.owned_store import (
    OwnedRoot,
    Snapshot,
    StoreError,
    _columns,
    create,
    exact,
    load,
    save,
    validate,
)
from tests.schema_v11.row_conservation import TableImage
from tests.schema_v11.travel_codec import encode_travel_path
from tests.world.validation_corpus import canonical_candidate

BORN = "2026-10-14T12:00:00+00:00"
UPDATED = "2026-10-14T12:10:00+00:00"


def canonical(value: object) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    )


def resources() -> tuple[CatalogSnapshot, LayoutContext, Any]:
    root = Path(__file__).parents[2] / "src/maplegotchi/world_catalog"
    catalog = json.loads((root / "initial_catalog.json").read_text(encoding="utf-8"))
    wire = dict(
        format_version=1,
        house=json.loads((root / "initial_house.json").read_text(encoding="utf-8")),
        instances=catalog["instances"],
        themes={},
        lighting_presets={},
    )
    candidate = canonical_candidate()
    context = LayoutContext(candidate.art, candidate.legacy_targets, Tile(21, 15))
    snapshot = CatalogSnapshot(1, canonical(catalog["types"]).encode())
    document = encode_layout_document(
        wire,
        catalog_version=1,
        catalog_hash=snapshot.catalog_hash,
        snapshots=(snapshot,),
        context=context,
    )
    return snapshot, context, document


def replace_rows(snapshot: Snapshot, name: str, rows: tuple[tuple[Any, ...], ...]) -> Snapshot:
    return replace(
        snapshot,
        tables=tuple(
            replace(table, rows=rows) if table.name == name else table for table in snapshot.tables
        ),
    )


def life_changes(snapshot: Snapshot, **changes: Any) -> Snapshot:
    raw = dict(zip(LIFE_FIELDS, snapshot.rows("life_state")[0], strict=True)) | changes
    return replace_rows(snapshot, "life_state", (tuple(raw[name] for name in LIFE_FIELDS),))


def birth_snapshot() -> Snapshot:
    catalog, _, document = resources()
    keys = project_layout_keys(document, 1)
    tables = {name: TableImage(name, _columns(name), ()) for name in sorted(target_tables())}

    def put(name: str, *rows: tuple[Any, ...]) -> None:
        tables[name] = replace(tables[name], rows=rows)

    put("maple", (1, "Maple", BORN, "5e" * 32))
    put(
        "activity_kind",
        *(
            (s,)
            for s in sorted(
                ("idle", "walk", "sleep", "read", "write", "observe_server", "rest", "think")
            )
        ),
    )
    put("room_kind", *((s,) for s in sorted({room.kind.value for room in document.world.regions})))
    put(
        "layout_revision",
        (
            1,
            BORN,
            "migration",
            None,
            1,
            catalog.catalog_hash,
            document.canonical_bytes.decode(),
            document.validation_digest,
        ),
    )
    put("world_state", (1, 1))
    for name in ("layout_host", "layout_room", "layout_point", "layout_slot"):
        put(name, *getattr(keys, name))
    values: dict[str, Any] = {name: None for name in NULLABLE_FIELDS}
    values.update(
        maple_id=1,
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
        point_id="idle",
        layout_revision=1,
        point_host="idle.hall_center",
        tx=21,
        ty=15,
    )
    put("life_state", tuple(values[name] for name in LIFE_FIELDS))
    put("timeline_event", (1, 1, 1, None, "born", BORN, canonical({"name": "Maple"})))
    sequences = tuple(
        (name, 1000)
        for name, sql in sorted(target_tables().items())
        if "AUTOINCREMENT" in sql and name != "world_event"
    )
    return Snapshot(tuple(tables.values()), sequences)


def advanced_snapshot(base: Snapshot, mode: str = "stationary") -> Snapshot:
    """Exercise every nullable state bundle with actual synthetic referenced facts."""
    result = life_changes(
        base,
        revision=2,
        mood=61.25,
        energy=72.5,
        curiosity=43.75,
        social=54.0,
        activity="write",
        activity_started_at="2026-10-14T12:05:00+00:00",
        activity_until="2026-10-14T12:35:00+00:00",
        last_tick_at="2026-10-14T12:05:00+00:00",
        last_updated_at=UPDATED,
        tick_counter=5,
        interaction_counter=3,
        reaction_kind="pet_happy",
        reaction_variant=2,
        reaction_started_at="2026-10-14T12:09:58+00:00",
        reaction_until="2026-10-14T12:10:06+00:00",
        point_id="chair",
        point_host="desk.writing",
        tx=34,
        ty=5,
        needs_at="2026-10-14T12:08:00+00:00",
        decision_counter=7,
        action_counter=9,
        goal_counter=4,
        action_priority="high",
        active_goal_id=3,
        suspended_goal_id=2,
        suspended_action="read",
        decision_due_since="2026-10-14T12:09:00+00:00",
        critical_since="2026-10-14T12:09:30+00:00",
        task_tool="writer",
        task_target="note:restart_proof",
        task_title="Restart proof",
        task_category="self",
    )
    result = replace_rows(
        result,
        "interaction_ledger",
        ((1, 0, "greet", "2026-10-14T12:08:00+00:00"), (1, 1, "pet", "2026-10-14T12:09:00+00:00")),
    )
    decision: dict[str, Any] = {name: None for name in _columns("decision")}
    decision.update(
        id=8,
        maple_id=1,
        revision=1,
        at=BORN,
        trigger="no_plan",
        director_kind="rule",
        director_name="synthetic",
        director_version="1",
        context_summary="Synthetic restart specimen",
        verdict="accepted",
        clamped="[]",
    )
    result = replace_rows(
        result, "decision", (tuple(decision[name] for name in _columns("decision")),)
    )
    result = replace_rows(
        result,
        "goal",
        (
            (
                2,
                1,
                1,
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
                1,
                "create",
                "Write a useful note",
                "rule",
                8,
                "2026-10-14T12:02:00+00:00",
                "2026-10-14T12:45:00+00:00",
            ),
        ),
    )
    # Nonempty specimens in all 16 non-life tables, including mutable cursors
    # and exact raw JSON/Unicode. These are synthetic historical SQL facts;
    # no event dispatcher, world payload or converter is enabled.
    historical: dict[str, dict[str, Any]] = {
        "observation": dict(
            id=1,
            maple_id=1,
            revision=1,
            tick_id=1,
            observed_at=BORN,
            metric="cpu_usage",
            subject="synthetic",
            status="available",
            value=12.5,
            unit="percent",
            source="synthetic",
        ),
        "journal_entry": dict(
            id=1,
            maple_id=1,
            revision=1,
            tick_id=1,
            created_at=BORN,
            category="daily_life",
            trigger_kind="activity",
            topic="synthetic",
            text="A synthetic note — เมเปิล",
            importance="normal",
            brain_kind="rule",
            brain_name="synthetic",
            brain_version="1",
            template_id="synthetic",
            activity="idle",
            expression="calm",
        ),
        "journal_entry_observation": dict(entry_id=1, observation_id=1, position=0),
        "journal_state": dict(
            maple_id=1,
            journal_day="2026-10-14",
            daily_seen='["synthetic"]',
            interactions_today=1,
            notices_today=2,
            last_interaction_entry_at=BORN,
            active_alerts="{}",
            last_reflection_day="2026-10-13",
            milestones="[]",
        ),
        "action_event": dict(
            id=1,
            maple_id=1,
            revision=1,
            action_id=1,
            goal_id=2,
            kind="activity_started",
            at=BORN,
            priority="normal",
            payload="{}",
        ),
        "document": dict(
            id=1,
            maple_id=1,
            revision=1,
            kind="note",
            title="Synthetic note",
            body="A complete preserved body.\nSecond line.",
            created_at=BORN,
            action_id=1,
            goal_id=2,
            sources="[]",
        ),
        "tool_use": dict(
            id=1,
            maple_id=1,
            revision=1,
            at=BORN,
            action_id=1,
            goal_id=2,
            tool="writer",
            operation="write_completed",
            target="note:synthetic",
            title="Synthetic note",
            category="self",
            status="success",
            chars=39,
            document_id=1,
        ),
        "memory": dict(
            id=1,
            maple_id=1,
            revision=1,
            kind="writing",
            tier="long_term",
            status="active",
            key="synthetic:memory",
            text="A preserved synthetic memory",
            source="synthetic",
            importance=0.75,
            evidence_days='["2026-10-14"]',
            created_at=BORN,
            last_seen_at=UPDATED,
        ),
        "memory_event": dict(
            id=1,
            maple_id=1,
            revision=1,
            memory_id=1,
            kind="created",
            at=BORN,
            detail="Synthetic proof",
        ),
        "daily_reflection": dict(
            id=1,
            maple_id=1,
            revision=1,
            day="2026-10-14",
            created_at=BORN,
            recovered=0,
            summary="Synthetic reflection",
            learned="[]",
            moments="[]",
            memory_candidates="[]",
            promoted="[]",
            preference_candidates="[]",
            intent_type="create",
            intent_summary="Keep the note",
            needs='{"mood":60.0,"energy":80.0,"curiosity":60.0,"social":50.0}',
        ),
        "conversation_message": dict(
            id=1,
            maple_id=1,
            revision=1,
            at=BORN,
            channel="discord",
            direction="in",
            speaker="paolo",
            external_id="synthetic-only",
            text="A synthetic message",
        ),
    }
    for name, fields in historical.items():
        result = replace_rows(
            result, name, (tuple(fields.get(column) for column in _columns(name)),)
        )
    if mode != "stationary":
        _, _, document = resources()
        departed = datetime.fromisoformat(UPDATED)
        entry = None
        if mode == "pending":
            departed += timedelta(minutes=5)
            route = Route((Waypoint(34, 5, 0),))
        elif mode in {"entry_a", "entry_b"}:
            endpoint = Tile(34, 6) if mode == "entry_a" else Tile(34, 5)
            entry = Entry(EdgeStart(Tile(34, 6), Tile(34, 5), 123457, 317000), endpoint)
            route = (
                Route((Waypoint(34, 6, 0), Waypoint(34, 5, 1)))
                if mode == "entry_a"
                else Route((Waypoint(34, 5, 0),))
            )
        else:
            route = Route((Waypoint(34, 6, 0), Waypoint(34, 5, 1)))
        travel = Travel(route, departed, 317, entry)
        result = life_changes(
            result,
            route_path=encode_travel_path(
                travel, walkability=validate_safe_layout(document.world, document.catalog)
            ),
            route_departed_at=departed.isoformat(),
            route_from_activity="read",
            route_arrives_at=travel.arrives_at.isoformat(),
            activity_started_at=travel.arrives_at.isoformat(),
            tx=route.origin.tx,
            ty=route.origin.ty,
        )
    return result


def digest(snapshot: Snapshot) -> str:
    return hashlib.sha256(canonical(exact(snapshot)).encode()).hexdigest()


def main() -> int:
    # Parent supplies the capability identity, never inferred from an arbitrary
    # existing root. Argument count and operation are closed.
    if len(sys.argv) != 7:
        return 2
    operation, root, device, inode, name, mode = sys.argv[1:]
    scope = OwnedRoot(Path(root), (int(device), int(inode)))
    catalog, context, _ = resources()
    catalogs, contexts = (catalog,), ((1, context),)
    base = birth_snapshot()
    target = advanced_snapshot(base, mode)
    try:
        if operation == "writer":
            create(scope, name, base, catalogs, contexts)
            save(scope, name, target, expected_revision=1, catalogs=catalogs, contexts=contexts)
        elif operation in {"after_write", "before_commit", "during_commit", "after_commit"}:
            # Exit only this harness-created process at an explicit checkpoint.
            def interrupt(phase: str) -> None:
                if phase == operation:
                    os._exit(73)

            def commit_loss() -> NoReturn:
                os._exit(73)

            save(
                scope,
                name,
                target,
                expected_revision=1,
                catalogs=catalogs,
                contexts=contexts,
                inject=interrupt,
                commit_progress=commit_loss if operation == "during_commit" else None,
            )
        elif operation != "reader":
            return 2
        snapshot, life = load(scope, name, catalogs, contexts)
        expected = target if snapshot.rows("life_state")[0][1] == 2 else base
        if digest(snapshot) != digest(expected):
            raise StoreError("state")
        validate(snapshot, catalogs, contexts)
        print(
            canonical(
                dict(
                    pid=os.getpid(),
                    digest=digest(snapshot),
                    revision=life.record.revision,
                    fields=40,
                )
            )
        )
        return 0
    except StoreError as exc:
        print(canonical(dict(error=str(exc))))
        return 3


if __name__ == "__main__":
    sys.exit(main())
