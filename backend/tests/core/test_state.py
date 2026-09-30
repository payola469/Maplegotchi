"""State invariants, expression derivation, and identity."""

from __future__ import annotations

from dataclasses import fields, replace
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from maplegotchi.core.activities import SPECS, Activity, RoomLocation
from maplegotchi.core.identity import MAX_NAME_LENGTH, Identity
from maplegotchi.core.rng import RngState
from maplegotchi.core.state import (
    INITIAL_NEEDS,
    REACTION_VARIANTS,
    Expression,
    InteractionKind,
    InteractionRecord,
    MapleState,
    Needs,
    Reaction,
    ReactionKind,
    birth,
)
from tests.core.support import BORN, SEED, at_local, make_state, needs

NEED_FIELDS = ("mood", "energy", "curiosity", "social")


# ---------------------------------------------------------------- birth


def test_birth_state_is_valid_and_calm() -> None:
    maple = birth(name="Maple", born_at=BORN, seed_hex=SEED)
    assert maple.needs == INITIAL_NEEDS
    assert maple.activity is Activity.IDLE
    assert maple.location is RoomLocation.RUG
    assert maple.expression_at(BORN) is Expression.CALM
    assert maple.ticks_lived == 0
    assert maple.rng == RngState(seed_hex=SEED)
    assert maple.recent_interactions == ()
    assert maple.reaction is None
    assert maple.age(BORN) == timedelta(0)


def test_age() -> None:
    maple = make_state()
    assert maple.age(BORN + timedelta(days=3, hours=2)) == timedelta(days=3, hours=2)
    with pytest.raises(ValueError):
        maple.age(BORN - timedelta(seconds=1))


# ---------------------------------------------------------------- needs


@pytest.mark.parametrize("field", NEED_FIELDS)
@pytest.mark.parametrize("value", [0.0, 0, 100.0, 100, 50.5])
def test_needs_accept_boundaries(field: str, value: float) -> None:
    kwargs: dict[str, Any] = {name: 50.0 for name in NEED_FIELDS}
    kwargs[field] = value
    assert getattr(Needs(**kwargs), field) == value


@pytest.mark.parametrize("field", NEED_FIELDS)
@pytest.mark.parametrize(
    "value", [-0.0001, 100.0001, -1e9, 1e9, float("nan"), float("inf"), float("-inf")]
)
def test_needs_reject_out_of_range(field: str, value: float) -> None:
    kwargs: dict[str, Any] = {name: 50.0 for name in NEED_FIELDS}
    kwargs[field] = value
    with pytest.raises(ValueError):
        Needs(**kwargs)


@pytest.mark.parametrize("field", NEED_FIELDS)
@pytest.mark.parametrize("value", [True, "50", None])
def test_needs_reject_non_numbers(field: str, value: object) -> None:
    kwargs: dict[str, Any] = {name: 50.0 for name in NEED_FIELDS}
    kwargs[field] = value
    with pytest.raises(TypeError):
        Needs(**kwargs)


def test_needs_clamped() -> None:
    n = Needs.clamped(mood=-5, energy=150, curiosity=0, social=100)
    assert (n.mood, n.energy, n.curiosity, n.social) == (0.0, 100.0, 0, 100)


def test_replace_revalidates() -> None:
    with pytest.raises(ValueError):
        replace(needs(), energy=101.0)
    with pytest.raises(ValueError):
        replace(make_state(), activity_until=BORN - timedelta(seconds=1))


# ---------------------------------------------------------------- identity and rng state


@pytest.mark.parametrize(
    "name", ["", "   ", " Maple", "Maple ", "a" * (MAX_NAME_LENGTH + 1), "Ma\nple"]
)
def test_identity_rejects_bad_names(name: str) -> None:
    with pytest.raises(ValueError):
        Identity(name=name, born_at=BORN)


def test_identity_accepts_max_length_name() -> None:
    assert Identity(name="a" * MAX_NAME_LENGTH, born_at=BORN).name


@pytest.mark.parametrize(
    "born_at",
    [datetime(2026, 1, 1), datetime(2026, 1, 1, tzinfo=timezone(timedelta(hours=7)))],  # noqa: DTZ001
)
def test_identity_requires_utc(born_at: datetime) -> None:
    with pytest.raises(ValueError):
        Identity(name="Maple", born_at=born_at)


@pytest.mark.parametrize("seed", ["", "ab" * 31, "ab" * 33, "AB" * 32, "zz" * 32])
def test_rng_state_rejects_bad_seed(seed: str) -> None:
    with pytest.raises(ValueError):
        RngState(seed_hex=seed)


@pytest.mark.parametrize(
    ("kwargs", "error"),
    [
        ({"tick_counter": -1}, ValueError),
        ({"interaction_counter": -1}, ValueError),
        ({"tick_counter": True}, TypeError),
        ({"interaction_counter": 1.0}, TypeError),
    ],
)
def test_rng_state_rejects_bad_counters(kwargs: dict[str, Any], error: type[Exception]) -> None:
    with pytest.raises(error):
        RngState(seed_hex=SEED, **kwargs)


# ---------------------------------------------------------------- MapleState invariants


def test_state_time_ordering_invariants() -> None:
    s = make_state()
    before_birth = BORN - timedelta(seconds=1)
    later = s.last_updated_at + timedelta(seconds=1)
    bad_updates: list[dict[str, Any]] = [
        {"activity_started_at": before_birth},
        {"activity_until": s.activity_started_at - timedelta(seconds=1)},
        {"last_tick_at": before_birth},
        {"last_tick_at": later},  # after last_updated_at
        {"last_updated_at": s.last_tick_at - timedelta(seconds=1)},
        {"activity_started_at": later, "activity_until": later},  # starts in the future
    ]
    for update in bad_updates:
        with pytest.raises(ValueError):
            replace(s, **update)


@pytest.mark.parametrize(
    "field", ["activity_started_at", "activity_until", "last_tick_at", "last_updated_at"]
)
def test_state_requires_utc(field: str) -> None:
    s = make_state()
    naive = getattr(s, field).replace(tzinfo=None)
    with pytest.raises(ValueError):
        replace(s, **{field: naive})


@pytest.mark.parametrize(
    ("activity", "location"),
    [(a, loc) for a in Activity for loc in RoomLocation if loc not in SPECS[a].locations],
)
def test_state_rejects_location_not_valid_for_activity(
    activity: Activity, location: RoomLocation
) -> None:
    with pytest.raises(ValueError):
        make_state(activity=activity, location=location)


@pytest.mark.parametrize(
    ("activity", "location"), [(a, loc) for a in Activity for loc in SPECS[a].locations]
)
def test_state_accepts_every_valid_activity_location(
    activity: Activity, location: RoomLocation
) -> None:
    assert make_state(activity=activity, location=location).location is location


def test_state_rejects_raw_strings_for_enums() -> None:
    s = make_state()
    with pytest.raises(TypeError):
        replace(s, activity="sleep")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        replace(s, location="bed")  # type: ignore[arg-type]


def _records(start: datetime, count: int, step: timedelta) -> tuple[InteractionRecord, ...]:
    return tuple(
        InteractionRecord(kind=InteractionKind.GREET, at=start + step * i) for i in range(count)
    )


def test_state_interaction_ledger_invariants() -> None:
    s = make_state()
    now = s.last_updated_at
    ok = _records(now - timedelta(minutes=9), 10, timedelta(seconds=30))
    assert replace(s, recent_interactions=ok).recent_interactions == ok

    too_many = _records(now - timedelta(minutes=9), 11, timedelta(seconds=30))
    outside_window = _records(now - timedelta(minutes=10), 1, timedelta(0))
    in_future = _records(now + timedelta(seconds=1), 1, timedelta(0))
    unsorted = tuple(reversed(ok))
    before_birth = _records(BORN - timedelta(seconds=1), 1, timedelta(0))
    for records in (too_many, outside_window, in_future, unsorted):
        with pytest.raises(ValueError):
            replace(s, recent_interactions=records)
    young = make_state(at=BORN + timedelta(minutes=1))
    with pytest.raises(ValueError):
        replace(young, recent_interactions=before_birth)


def test_interaction_record_rejects_unknown_kind() -> None:
    with pytest.raises(TypeError):
        InteractionRecord(kind="feed", at=BORN)  # type: ignore[arg-type]


def test_reaction_invariants() -> None:
    t = at_local(12)
    with pytest.raises(ValueError):
        Reaction(ReactionKind.GREET_HAPPY, 0, t, t)  # must expire after it starts
    for variant in (-1, REACTION_VARIANTS):
        with pytest.raises(ValueError):
            Reaction(ReactionKind.GREET_HAPPY, variant, t, t + timedelta(seconds=8))
    s = make_state(at=t)
    future = Reaction(ReactionKind.PET_HAPPY, 0, t + timedelta(seconds=1), t + timedelta(seconds=9))
    with pytest.raises(ValueError):
        replace(s, reaction=future)


def test_state_fields_are_all_plain_data() -> None:
    # Phase 2 persists MapleState field by field; there must be no hidden state.
    names = {f.name for f in fields(MapleState)}
    assert names == {
        "identity",
        "needs",
        "activity",
        "location",
        "activity_started_at",
        "activity_until",
        "last_tick_at",
        "last_updated_at",
        "rng",
        "recent_interactions",
        "reaction",
    }


def test_only_greet_and_pet_exist() -> None:
    assert {k.value for k in InteractionKind} == {"greet", "pet"}


def test_activity_and_expression_sets_are_fixed() -> None:
    assert {a.value for a in Activity} == {
        "idle",
        "walk",
        "sleep",
        "read",
        "write",
        "observe_server",
        "rest",
    }
    assert {e.value for e in Expression} == {"calm", "happy", "curious", "sleepy", "focused"}


# ---------------------------------------------------------------- expression


def _reaction(kind: ReactionKind, t: datetime) -> Reaction:
    return Reaction(kind, 0, t, t + timedelta(seconds=8))


@pytest.mark.parametrize(
    ("activity", "state_needs", "reaction", "expected"),
    [
        (Activity.SLEEP, needs(mood=100, energy=100), None, Expression.SLEEPY),
        (Activity.SLEEP, needs(), ReactionKind.PET_HAPPY, Expression.SLEEPY),
        (Activity.IDLE, needs(energy=19.99), None, Expression.SLEEPY),
        (Activity.IDLE, needs(energy=20.0), None, Expression.CALM),
        (Activity.IDLE, needs(), ReactionKind.GREET_HAPPY, Expression.HAPPY),
        (Activity.WRITE, needs(), ReactionKind.PET_HAPPY, Expression.HAPPY),
        (Activity.IDLE, needs(), ReactionKind.GREET_SLEEPY, Expression.CALM),
        (Activity.WRITE, needs(mood=100), None, Expression.FOCUSED),
        (Activity.OBSERVE_SERVER, needs(), None, Expression.FOCUSED),
        (Activity.READ, needs(curiosity=60), None, Expression.CURIOUS),
        (Activity.READ, needs(curiosity=59.99), None, Expression.FOCUSED),
        (Activity.IDLE, needs(mood=70), None, Expression.HAPPY),
        (Activity.WALK, needs(mood=69.99, curiosity=75), None, Expression.CURIOUS),
        (Activity.REST, needs(mood=69.99, curiosity=74.99), None, Expression.CALM),
    ],
)
def test_expression_derives_from_state(
    activity: Activity,
    state_needs: Needs,
    reaction: ReactionKind | None,
    expected: Expression,
) -> None:
    t = at_local(12)
    s = make_state(at=t, activity=activity, state_needs=state_needs)
    if reaction is not None:
        s = replace(s, reaction=_reaction(reaction, t))
    assert s.expression_at(t) is expected


def test_expression_is_not_stored() -> None:
    assert "expression" not in {f.name for f in fields(MapleState)}
