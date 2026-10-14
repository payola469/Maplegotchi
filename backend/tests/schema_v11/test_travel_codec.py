"""Synthetic, supplied-time Travel restart and strict format refusal tests."""

from __future__ import annotations

import builtins
import io
import json
import socket
import sqlite3
import time
from collections.abc import Iterator
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta, timezone
from typing import NoReturn, cast

import pytest

from maplegotchi.core.world import movement
from maplegotchi.core.world.coordinates import Tile, tile_to_feet
from maplegotchi.core.world.movement import EdgeStart, Entry, Travel
from maplegotchi.core.world.pathfinding import Route, Waypoint
from maplegotchi.core.world.walkability import Walkability
from maplegotchi.persistence import travel_codec
from maplegotchi.persistence.travel_codec import (
    V11TravelFormatError,
    decode_travel_path,
    encode_travel_path,
)

AT = datetime(2026, 10, 13, 1, 2, 3, 456789, tzinfo=UTC)
CELLS = tuple(Tile(x, y) for y in range(6) for x in range(6))
MASK = Walkability(CELLS, (), CELLS, (), (), (), (CELLS,), Tile(0, 0))
BASE = Travel(Route((Waypoint(1, 1, 0), Waypoint(3, 1, 2))), AT, 317)
TEXT = '{"entry":null,"format_version":1,"ms_per_step":317,"waypoints":[[1,1,0],[3,1,2]]}'


def canonical(value: object) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    )


def payload() -> dict[str, object]:
    return {
        "entry": None,
        "format_version": 1,
        "ms_per_step": 317,
        "waypoints": [[1, 1, 0], [3, 1, 2]],
    }


def decode(text: str, travel: Travel = BASE, mask: Walkability = MASK) -> Travel:
    return decode_travel_path(
        text,
        departed_at=travel.departed_at,
        route_arrives_at=travel.arrives_at,
        activity_started_at=travel.activity_started_at,
        stored_origin=travel.route.origin,
        walkability=mask,
    )


def with_entry(endpoint: Tile) -> Travel:
    return Travel(
        Route((Waypoint(endpoint.tx, endpoint.ty, 0), Waypoint(endpoint.tx, 4, 3))),
        AT,
        317,
        Entry(EdgeStart(Tile(1, 1), Tile(2, 1), 123457, 317000), endpoint),
    )


def test_exact_canonical_and_stable_roundtrip() -> None:
    assert encode_travel_path(BASE, walkability=MASK) == TEXT
    result = decode(TEXT)
    assert result == BASE and result is not BASE
    assert encode_travel_path(result, walkability=MASK) == TEXT
    with pytest.raises(FrozenInstanceError):
        result.ms_per_step = 1  # type: ignore[misc]  # Verify the core frozen value.


def test_pending_zero_step_exact_format() -> None:
    scheduled = AT + timedelta(days=1, microseconds=1)
    travel = Travel(Route((Waypoint(2, 2, 0),)), scheduled, 317)
    expected = '{"entry":null,"format_version":1,"ms_per_step":317,"waypoints":[[2,2,0]]}'
    assert encode_travel_path(travel, walkability=MASK) == expected
    restored = decode(expected, travel)
    assert restored.departed_at == restored.arrives_at == restored.activity_started_at == scheduled
    assert restored.phase_at(AT) == "pending"
    assert restored.phase_at(scheduled) == "performing"
    assert restored.position_at(AT) == tile_to_feet(Tile(2, 2))


@pytest.mark.parametrize("value", [None, b"{}", 1, True, {}])
def test_nontext_input(value: object) -> None:
    with pytest.raises(V11TravelFormatError, match=r"^json$"):
        decode(cast(str, value))


def test_invalid_supplied_values() -> None:
    with pytest.raises(V11TravelFormatError, match=r"^travel$"):
        encode_travel_path(cast(Travel, None), walkability=MASK)
    with pytest.raises(V11TravelFormatError, match=r"^walkability$"):
        decode(TEXT, mask=cast(Walkability, None))
    with pytest.raises(V11TravelFormatError, match=r"^origin$"):
        decode_travel_path(
            TEXT,
            departed_at=AT,
            route_arrives_at=BASE.arrives_at,
            activity_started_at=BASE.arrives_at,
            stored_origin=cast(Tile, (1, 1)),
            walkability=MASK,
        )


def test_parser_exception_content_is_suppressed() -> None:
    with pytest.raises(V11TravelFormatError, match=r"^json$") as failure:
        decode('{"private-secret": invalid}')
    assert failure.value.args == ("json",)
    assert failure.value.__suppress_context__


@pytest.mark.parametrize("endpoint", [Tile(1, 1), Tile(2, 1)])
def test_entry_exact_canonical(endpoint: Tile) -> None:
    travel = with_entry(endpoint)
    expected = (
        '{"entry":{"a":[1,1],"b":[2,1],"endpoint":['
        + str(endpoint.tx)
        + ',1],"progress_us":123457},"format_version":1,"ms_per_step":317,'
        '"waypoints":[[' + str(endpoint.tx) + ",1,0],[" + str(endpoint.tx) + ",4,3]]}"
    )
    assert encode_travel_path(travel, walkability=MASK) == expected
    assert decode(expected, travel) == travel


@pytest.mark.parametrize(
    "points",
    [
        ((2, 2, 0),),
        ((1, 1, 0), (4, 1, 3)),
        ((4, 1, 0), (1, 1, 3)),
        ((1, 1, 0), (1, 4, 3)),
        ((1, 4, 0), (1, 1, 3)),
        ((1, 1, 0), (4, 1, 3), (4, 4, 6), (2, 4, 8), (2, 2, 10)),
        ((1, 1, 0), (4, 1, 3), (1, 1, 6)),  # Reversal is valid core compression.
    ],
)
def test_route_shapes(points: tuple[tuple[int, int, int], ...]) -> None:
    travel = Travel(Route(tuple(Waypoint(*point) for point in points)), AT, 19)
    text = encode_travel_path(travel, walkability=MASK)
    assert decode(text, travel) == travel


@pytest.mark.parametrize(
    "text",
    [
        "",
        "{",
        "[]",
        "null",
        "true",
        '"private-secret"',
        TEXT + "\n",
        " " + TEXT,
        "\ufeff" + TEXT,
        TEXT.replace(":", ": "),
        '{"waypoints":[[1,1,0],[3,1,2]],"ms_per_step":317,"format_version":1,"entry":null}',
        TEXT.replace('"entry"', '"\\u0065ntry"'),
        TEXT.replace("[1,1,0]", "[1,1,-0]"),
        TEXT.replace("317", "NaN"),
        TEXT.replace("317", "Infinity"),
        TEXT.replace("317", "-Infinity"),
        TEXT.replace("317", "1e999"),
        '{"entry":null,"entry":null,"format_version":1,"ms_per_step":317,"waypoints":[[1,1,0]]}',
        '{"private-secret":1,"private-secret":2}',
        "[" * 2000 + "]" * 2000,
    ],
)
def test_malformed_or_noncanonical(text: str) -> None:
    with pytest.raises(V11TravelFormatError) as failure:
        decode(text)
    assert str(failure.value) in {"json", "canonical", "fields", "integer"}
    assert "private-secret" not in str(failure.value)


@pytest.mark.parametrize("field", ["entry", "format_version", "ms_per_step", "waypoints"])
def test_missing_root_fields(field: str) -> None:
    data = payload()
    del data[field]
    with pytest.raises(V11TravelFormatError, match=r"^fields$"):
        decode(canonical(data))


def test_unknown_root_field_and_unsupported_version() -> None:
    with pytest.raises(V11TravelFormatError, match=r"^fields$"):
        decode(canonical(payload() | {"private-secret": "private-secret"}))
    for version in (0, -1, 2, 999):
        with pytest.raises(V11TravelFormatError, match=r"^version$"):
            decode(canonical(payload() | {"format_version": version}))


@pytest.mark.parametrize("value", [True, False, 1.0, "1", None, [], {}])
@pytest.mark.parametrize(
    "field",
    ["format_version", "ms_per_step", "tx", "ty", "steps", "entry_x", "entry_y", "progress_us"],
)
def test_strict_integer_fields(field: str, value: object) -> None:
    data = payload()
    if field in ("format_version", "ms_per_step"):
        data[field] = value
    elif field in ("tx", "ty", "steps"):
        point: list[object] = [1, 1, 0]
        point[("tx", "ty", "steps").index(field)] = value
        data["waypoints"] = [point, [3, 1, 2]]
    else:
        entry: dict[str, object] = {"a": [1, 1], "b": [2, 1], "endpoint": [1, 1], "progress_us": 1}
        if field == "progress_us":
            entry[field] = value
        else:
            entry["a"] = [value, 1] if field == "entry_x" else [1, value]
        data["entry"] = entry
    with pytest.raises(V11TravelFormatError, match=r"^integer$"):
        decode(canonical(data))


@pytest.mark.parametrize(
    "points",
    [
        [],
        [[1, 1, 1]],
        [[1, 1, -1]],
        [[1, 1, 0], [2, 2, 2]],
        [[1, 1, 0], [1, 1, 0]],
        [[1, 1, 0], [3, 1, 1]],
        [[1, 1, 0], [2, 1, 1], [3, 1, 2]],
        [[-1, 1, 0]],
        [[44, 1, 0]],
        [[1, 26, 0]],
        [[1, -1, 0]],
    ],
)
def test_invalid_route_geometry(points: object) -> None:
    with pytest.raises(V11TravelFormatError, match=r"^route$"):
        decode(canonical(payload() | {"waypoints": points}))


@pytest.mark.parametrize("points", [None, {}, "private-secret", [None], [[1, 1]], [[1, 1, 0, 0]]])
def test_invalid_waypoint_shape(points: object) -> None:
    with pytest.raises(V11TravelFormatError, match=r"^fields$"):
        decode(canonical(payload() | {"waypoints": points}))


@pytest.mark.parametrize("speed", [0, -1])
def test_nonpositive_speed(speed: int) -> None:
    with pytest.raises(V11TravelFormatError, match=r"^integer$"):
        decode(canonical(payload() | {"ms_per_step": speed}))


@pytest.mark.parametrize("speed,category", [(1, "entry"), (318, "timing")])
def test_entry_speed_and_timing_consistency(speed: int, category: str) -> None:
    travel = with_entry(Tile(1, 1))
    text = encode_travel_path(travel, walkability=MASK).replace(
        '"ms_per_step":317', f'"ms_per_step":{speed}'
    )
    with pytest.raises(V11TravelFormatError) as failure:
        decode(text, travel)
    assert failure.value.args == (category,)


@pytest.mark.parametrize(
    "field,value",
    [
        ("a", [0, 0]),
        ("b", [2, 2]),
        ("b", [1, 1]),
        ("endpoint", [3, 1]),
        ("endpoint", [2, 1]),
        ("progress_us", 0),
        ("progress_us", -1),
        ("progress_us", 317000),
        ("progress_us", 317001),
        ("a", [-1, 1]),
    ],
)
def test_invalid_entry(field: str, value: object) -> None:
    entry: dict[str, object] = {"a": [1, 1], "b": [2, 1], "endpoint": [1, 1], "progress_us": 1}
    entry[field] = value
    with pytest.raises(V11TravelFormatError, match=r"^entry$"):
        decode(canonical(payload() | {"entry": entry}))


@pytest.mark.parametrize("field", ["a", "b", "endpoint", "progress_us"])
def test_entry_fields(field: str) -> None:
    entry: dict[str, object] = {"a": [1, 1], "b": [2, 1], "endpoint": [1, 1], "progress_us": 1}
    del entry[field]
    with pytest.raises(V11TravelFormatError, match=r"^fields$"):
        decode(canonical(payload() | {"entry": entry}))


@pytest.mark.parametrize(
    "entry",
    [
        False,
        [],
        "secret",
        {"extra": 1},
        {"a": [1], "b": [2, 1], "endpoint": [1, 1], "progress_us": 1},
        {"a": [1, 1], "b": [2, 1], "endpoint": [1, 1], "progress_us": 1, "step_us": 317000},
    ],
)
def test_entry_shape(entry: object) -> None:
    with pytest.raises(V11TravelFormatError, match=r"^fields$"):
        decode(canonical(payload() | {"entry": entry}))


def test_duplicate_entry_field() -> None:
    text = encode_travel_path(with_entry(Tile(1, 1)), walkability=MASK)
    with pytest.raises(V11TravelFormatError, match=r"^fields$"):
        decode(text.replace('"progress_us":123457', '"progress_us":123457,"progress_us":123457'))


@pytest.mark.parametrize("blocked", [Tile(1, 1), Tile(2, 1), Tile(3, 1)])
def test_every_route_tile_checked_on_encode_and_decode(blocked: Tile) -> None:
    mask = replace(MASK, walkable=tuple(tile for tile in CELLS if tile != blocked))
    for action in (
        lambda: encode_travel_path(BASE, walkability=mask),
        lambda: decode(TEXT, mask=mask),
    ):
        with pytest.raises(V11TravelFormatError, match=r"^walkability$"):
            action()


@pytest.mark.parametrize("endpoint", [Tile(1, 1), Tile(2, 1)])
def test_both_entry_endpoints_must_be_walkable(endpoint: Tile) -> None:
    travel = with_entry(endpoint)
    blocked = Tile(2, 1) if endpoint == Tile(1, 1) else Tile(1, 1)
    mask = replace(MASK, walkable=tuple(tile for tile in CELLS if tile != blocked))
    text = encode_travel_path(travel, walkability=MASK)
    with pytest.raises(V11TravelFormatError, match=r"^walkability$"):
        decode(text, travel, mask)
    with pytest.raises(V11TravelFormatError, match=r"^walkability$"):
        encode_travel_path(travel, walkability=mask)


def test_stored_origin_is_route_origin() -> None:
    with pytest.raises(V11TravelFormatError, match=r"^origin$"):
        decode_travel_path(
            TEXT,
            departed_at=AT,
            route_arrives_at=BASE.arrives_at,
            activity_started_at=BASE.arrives_at,
            stored_origin=Tile(2, 1),
            walkability=MASK,
        )


@pytest.mark.parametrize(
    "travel",
    [
        BASE,
        with_entry(Tile(1, 1)),
        with_entry(Tile(2, 1)),
        Travel(Route((Waypoint(2, 2, 0),)), AT, 317),
    ],
)
def test_supplied_time_restart_boundaries(travel: Travel) -> None:
    restored = decode(encode_travel_path(travel, walkability=MASK), travel)
    entry_us = travel.entry.duration_us if travel.entry else 0
    offsets = {
        -1,
        0,
        1,
        travel.duration_us // 2,
        travel.duration_us - 1,
        travel.duration_us,
        travel.duration_us + 1,
        travel.duration_us + 86400000000,
    }
    if travel.entry:
        offsets.update({entry_us // 2, entry_us - 1, entry_us, entry_us + 1})
    for elapsed in sorted(offsets):
        now = AT + timedelta(microseconds=elapsed)
        assert restored.phase_at(now) == travel.phase_at(now)
        assert restored.current_at(now) == travel.current_at(now)
        assert restored.position_at(now) == travel.position_at(now)
        expected_phase = (
            "pending"
            if elapsed < 0
            else ("walking" if elapsed < travel.duration_us else "performing")
        )
        assert restored.phase_at(now) == expected_phase
    assert restored.position_at(restored.arrives_at) == tile_to_feet(travel.route.destination)


@pytest.mark.parametrize("endpoint,remaining", [(Tile(1, 1), 123457), (Tile(2, 1), 193543)])
def test_exact_entry_microseconds(endpoint: Tile, remaining: int) -> None:
    travel = with_entry(endpoint)
    restored = decode(encode_travel_path(travel, walkability=MASK), travel)
    assert restored.arrives_at == AT + timedelta(microseconds=remaining + 3 * 317000)
    assert restored.current_at(AT + timedelta(microseconds=remaining)) == endpoint
    assert isinstance(restored.current_at(AT + timedelta(microseconds=remaining - 1)), EdgeStart)


def test_stored_speed_independent_of_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(movement, "MS_PER_STEP", 999)
    restored = decode(TEXT)
    assert restored.ms_per_step == 317
    assert restored.arrives_at == AT + timedelta(microseconds=634000)
    assert restored.current_at(AT + timedelta(microseconds=317001)) == EdgeStart(
        Tile(2, 1), Tile(3, 1), 1, 317000
    )


@pytest.mark.parametrize("field", ["departed_at", "route_arrives_at", "activity_started_at"])
@pytest.mark.parametrize("kind", ["early", "late", "naive", "nonutc", "string", "none"])
def test_timing_refusal(field: str, kind: str) -> None:
    times = {
        "departed_at": AT,
        "route_arrives_at": BASE.arrives_at,
        "activity_started_at": BASE.arrives_at,
    }
    original = times[field]
    invalid: object = {
        "early": original - timedelta(microseconds=1),
        "late": original + timedelta(microseconds=1),
        "naive": original.replace(tzinfo=None),
        "nonutc": original.astimezone(timezone(timedelta(hours=7))),
        "string": "private-secret",
        "none": None,
    }[kind]
    times[field] = cast(datetime, invalid)
    with pytest.raises(V11TravelFormatError, match=r"^timing$"):
        decode_travel_path(
            TEXT,
            departed_at=times["departed_at"],
            route_arrives_at=times["route_arrives_at"],
            activity_started_at=times["activity_started_at"],
            stored_origin=BASE.route.origin,
            walkability=MASK,
        )


def test_unrepresentable_arrival_refused() -> None:
    travel = replace(BASE, departed_at=datetime.max.replace(tzinfo=UTC))
    with pytest.raises(V11TravelFormatError, match=r"^timing$"):
        encode_travel_path(travel, walkability=MASK)
    with pytest.raises(V11TravelFormatError, match=r"^timing$"):
        decode_travel_path(
            TEXT,
            departed_at=travel.departed_at,
            route_arrives_at=AT,
            activity_started_at=AT,
            stored_origin=BASE.route.origin,
            walkability=MASK,
        )


def test_no_input_mutation_on_success_or_failure() -> None:
    travel = with_entry(Tile(1, 1))
    before = deepcopy((travel, MASK))
    text = encode_travel_path(travel, walkability=MASK)
    assert decode(text, travel) == travel
    with pytest.raises(V11TravelFormatError):
        decode(text + "\n", travel)
    blocked = replace(MASK, walkable=())
    with pytest.raises(V11TravelFormatError):
        encode_travel_path(travel, walkability=blocked)
    assert (travel, MASK) == before
    assert blocked.walkable == ()


def test_no_io_clock_database_network_or_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: object, **kwargs: object) -> NoReturn:
        pytest.fail("codec attempted a side effect")

    original_import = builtins.__import__

    def guarded_import(
        name: str,
        globals: dict[str, object] | None = None,
        locals: dict[str, object] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> object:
        if name.startswith(("maplegotchi.runtime", "maplegotchi.storage")):
            forbidden()
        return original_import(name, globals, locals, fromlist, level)

    with monkeypatch.context() as guard:
        for module, attribute in (
            (builtins, "open"),
            (io, "open"),
            (sqlite3, "connect"),
            (socket, "socket"),
            (time, "time"),
            (time, "monotonic"),
        ):
            guard.setattr(module, attribute, forbidden)
        guard.setattr(builtins, "__import__", guarded_import)
        assert decode(encode_travel_path(BASE, walkability=MASK)) == BASE
        with pytest.raises(V11TravelFormatError, match=r"^fields$"):
            decode('{"private-secret":"private-secret"}')


@pytest.mark.parametrize(
    "points,coordinates",
    [
        (((2, 2, 0),), ((2, 2),)),
        (((1, 1, 0), (3, 1, 2)), ((1, 1), (2, 1), (3, 1))),
        (((3, 1, 0), (1, 1, 2)), ((3, 1), (2, 1), (1, 1))),
        (((1, 1, 0), (1, 3, 2)), ((1, 1), (1, 2), (1, 3))),
        (((1, 3, 0), (1, 1, 2)), ((1, 3), (1, 2), (1, 1))),
        (
            ((1, 1, 0), (3, 1, 2), (3, 3, 4), (2, 3, 5)),
            ((1, 1), (2, 1), (3, 1), (3, 2), (3, 3), (2, 3)),
        ),
        (
            ((1, 1, 0), (3, 1, 2), (1, 1, 4), (2, 1, 5)),
            ((1, 1), (2, 1), (3, 1), (2, 1), (1, 1), (2, 1)),
        ),
    ],
)
def test_streaming_tile_order_matches_core(
    points: tuple[tuple[int, int, int], ...], coordinates: tuple[tuple[int, int], ...]
) -> None:
    route = Route(tuple(Waypoint(*point) for point in points))
    expected = tuple(Tile(*coordinate) for coordinate in coordinates)
    assert tuple(travel_codec._route_tiles(route)) == expected == route.tiles()


@pytest.mark.parametrize("operation", ["encode", "decode"])
@pytest.mark.parametrize("blocked_index", [None, 0, 1, 2])
def test_streaming_checks_each_tile_and_stops_at_first_blocked(
    monkeypatch: pytest.MonkeyPatch, operation: str, blocked_index: int | None
) -> None:
    expected = (Tile(1, 1), Tile(2, 1), Tile(3, 1))
    # Block the final tile too: an intermediate refusal must stop before reaching it.
    blocked = () if blocked_index is None else expected[blocked_index:]
    mask = replace(MASK, walkable=tuple(tile for tile in CELLS if tile not in blocked))
    before = deepcopy((BASE, mask))
    seen: list[Tile] = []
    original = travel_codec._route_tiles

    def observed(route: Route) -> Iterator[Tile]:
        for tile in original(route):
            seen.append(tile)
            yield tile

    monkeypatch.setattr(travel_codec, "_route_tiles", observed)
    if blocked_index is None:
        if operation == "encode":
            assert encode_travel_path(BASE, walkability=mask) == TEXT
        else:
            assert decode(TEXT, mask=mask) == BASE
        assert tuple(seen) == expected
    else:
        with pytest.raises(V11TravelFormatError) as failure:
            if operation == "encode":
                encode_travel_path(BASE, walkability=mask)
            else:
                decode(TEXT, mask=mask)
        assert failure.value.args == ("walkability",)
        assert tuple(seen) == expected[: blocked_index + 1]
    assert (BASE, mask) == before


@pytest.mark.parametrize("operation", ["encode", "decode"])
def test_streaming_zero_step_checks_origin_once(
    monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    travel = Travel(Route((Waypoint(2, 2, 0),)), AT, 317)
    text = '{"entry":null,"format_version":1,"ms_per_step":317,"waypoints":[[2,2,0]]}'
    seen: list[Tile] = []
    original = travel_codec._route_tiles

    def observed(route: Route) -> Iterator[Tile]:
        for tile in original(route):
            seen.append(tile)
            yield tile

    monkeypatch.setattr(travel_codec, "_route_tiles", observed)
    if operation == "encode":
        assert encode_travel_path(travel, walkability=MASK) == text
    else:
        assert decode(text, travel) == travel
    assert seen == [Tile(2, 2)]


@pytest.mark.parametrize(
    "travel",
    [
        BASE,
        with_entry(Tile(1, 1)),
        with_entry(Tile(2, 1)),
        Travel(Route((Waypoint(2, 2, 0),)), AT, 317),
    ],
)
def test_codec_never_calls_core_tiles(monkeypatch: pytest.MonkeyPatch, travel: Travel) -> None:
    expected = encode_travel_path(travel, walkability=MASK)

    def forbidden(self: Route) -> NoReturn:
        pytest.fail("codec invoked eager Route.tiles()")

    monkeypatch.setattr(Route, "tiles", forbidden)
    before = deepcopy((travel, MASK))
    assert encode_travel_path(travel, walkability=MASK) == expected
    assert decode(expected, travel) == travel
    blocked = replace(MASK, walkable=())
    with pytest.raises(V11TravelFormatError, match=r"^walkability$"):
        encode_travel_path(travel, walkability=blocked)
    with pytest.raises(V11TravelFormatError, match=r"^walkability$"):
        decode(expected, travel, blocked)
    assert (travel, MASK) == before


@pytest.mark.parametrize("count,accepted", [(65536, True), (65537, False)])
def test_step220_exact_utf8_byte_gate_before_parser(
    monkeypatch: pytest.MonkeyPatch, count: int, accepted: bool
) -> None:
    called = False

    def parser(*args: object, **kwargs: object) -> NoReturn:
        nonlocal called
        called = True
        raise ValueError("synthetic invalid JSON")

    monkeypatch.setattr(json, "loads", parser)
    with pytest.raises(V11TravelFormatError, match=r"^json$" if accepted else "^bytes$"):
        decode("x" * count)
    assert called is accepted


def test_step220_multibyte_and_surrogate_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    text = "é" * 32769
    assert len(text) < 65536 and len(text.encode("utf-8")) == 65538

    def forbidden(*args: object, **kwargs: object) -> NoReturn:
        pytest.fail("oversized UTF-8 reached parser")

    monkeypatch.setattr(json, "loads", forbidden)
    with pytest.raises(V11TravelFormatError, match=r"^bytes$"):
        decode(text)
    with pytest.raises(V11TravelFormatError, match=r"^json$"):
        decode("\ud800")


@pytest.mark.parametrize("count,accepted", [(2048, True), (2049, False)])
def test_step220_waypoint_boundary_before_geometry(
    monkeypatch: pytest.MonkeyPatch, count: int, accepted: bool
) -> None:
    points = [[1 + i % 2, 1, i] for i in range(count)]
    raw = payload() | {"waypoints": points}
    text = canonical(raw)
    calls = 0
    original = Waypoint

    def waypoint(*args: int) -> Waypoint:
        nonlocal calls
        calls += 1
        return original(*args)

    monkeypatch.setattr(travel_codec, "Waypoint", waypoint)
    if accepted:
        travel = Travel(Route(tuple(original(*p) for p in points)), AT, 317)
        assert decode(text, travel).route.waypoints == travel.route.waypoints
        assert calls == count
    else:
        with pytest.raises(V11TravelFormatError, match=r"^waypoints$"):
            decode(text)
        assert calls == 0


@pytest.mark.parametrize("count,accepted", [(32768, True), (32769, False)])
def test_step220_work_counter_exact_boundary(count: int, accepted: bool) -> None:
    if accepted:
        travel_codec._work_gate(count)
    else:
        with pytest.raises(V11TravelFormatError, match=r"^work$"):
            travel_codec._work_gate(count)


def test_step220_streaming_work_counts_repeated_visits_and_stops_before_generation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Legal reversals, each 5 steps. Many visits to the same six tiles must count.
    points = tuple(Waypoint(0 if i % 2 == 0 else 5, 0, i * 5) for i in range(2048))
    travel = Travel(Route(points), AT, 1)
    seen = 0
    original = travel_codec._route_tiles

    def observed(route: Route) -> Iterator[Tile]:
        nonlocal seen
        for tile in original(route):
            seen += 1
            yield tile

    monkeypatch.setattr(travel_codec, "_route_tiles", observed)
    monkeypatch.setattr(travel_codec, "MAX_WORK", 100)
    with pytest.raises(V11TravelFormatError, match=r"^work$"):
        travel_codec._walkable(travel, MASK)
    assert seen == 100  # No generated unit above the approved counter.


def test_step220_entry_examinations_count_toward_work(monkeypatch: pytest.MonkeyPatch) -> None:
    travel = with_entry(Tile(1, 1))  # Four route tiles plus two Entry examinations.
    monkeypatch.setattr(travel_codec, "MAX_WORK", 6)
    travel_codec._walkable(travel, MASK)
    monkeypatch.setattr(travel_codec, "MAX_WORK", 5)
    with pytest.raises(V11TravelFormatError, match=r"^work$") as failure:
        travel_codec._walkable(travel, MASK)
    assert failure.value.args == ("work",)


@pytest.mark.parametrize("work,accepted", [(32768, True), (32769, False)])
def test_step220_real_route_work_boundary(
    monkeypatch: pytest.MonkeyPatch, work: int, accepted: bool
) -> None:
    steps = work - 1  # Origin examination is one actual unit of traversal work.
    points = [Waypoint(0, 0, 0)]
    remaining = steps
    while remaining:
        length = min(43, remaining)
        last = points[-1]
        x = last.tx + length if last.tx == 0 else last.tx - length
        points.append(Waypoint(x, 0, last.cumulative_steps + length))
        remaining -= length
    travel = Travel(Route(tuple(points)), AT, 1)
    cells = tuple(Tile(x, 0) for x in range(44))
    mask = replace(MASK, walkable=cells)
    original = travel_codec._route_tiles
    generated = 0

    def observe(route: Route) -> Iterator[Tile]:
        nonlocal generated
        for tile in original(route):
            generated += 1
            yield tile

    monkeypatch.setattr(travel_codec, "_route_tiles", observe)
    if accepted:
        text = encode_travel_path(travel, walkability=mask)
        assert generated == 32768
        generated = 0
        assert decode(text, travel, mask) == travel
        assert generated == 32768
    else:
        with pytest.raises(V11TravelFormatError, match=r"^work$"):
            encode_travel_path(travel, walkability=mask)
        assert generated == 32768
