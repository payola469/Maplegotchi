"""Behavior engine: activity selection rules."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta

import pytest

from maplegotchi.core.activities import SPECS, Activity, RoomLocation
from maplegotchi.core.behavior import (
    FORCED_SLEEP_ENERGY,
    LOW_ENERGY,
    REPEAT_PENALTY,
    BehaviorInputs,
    candidates,
    choose_next_activity,
    score_activities,
)
from maplegotchi.core.daytime import local_hour
from maplegotchi.core.rng import RngStream
from maplegotchi.core.state import MapleState
from tests.core.support import PARAMS, SEED, at_local, make_state, needs

NOON = at_local(12)
MIDNIGHT = at_local(0)
LATE_EVENING = at_local(23)
EARLY_MORNING = at_local(4)
RUNS = 300


def choices(
    state: MapleState, now: datetime, inputs: BehaviorInputs | None = None, runs: int = RUNS
) -> Counter[Activity]:
    inputs = inputs or BehaviorInputs()
    return Counter(
        choose_next_activity(state, now, inputs, PARAMS, RngStream(SEED, "tick", c)).activity
        for c in range(runs)
    )


@pytest.mark.parametrize("energy", [0.0, 5.0, FORCED_SLEEP_ENERGY])
@pytest.mark.parametrize("now", [NOON, MIDNIGHT])
def test_exhausted_maple_always_sleeps(energy: float, now: datetime) -> None:
    s = make_state(at=now, state_needs=needs(energy=energy, curiosity=100, mood=100))
    assert choices(s, now, BehaviorInputs(server_attention=1.0)) == Counter({Activity.SLEEP: RUNS})


@pytest.mark.parametrize("energy", [FORCED_SLEEP_ENERGY + 0.01, 15.0, LOW_ENERGY - 0.01])
@pytest.mark.parametrize("now", [NOON, MIDNIGHT])
def test_low_energy_only_sleeps_or_rests(energy: float, now: datetime) -> None:
    s = make_state(at=now, state_needs=needs(energy=energy, curiosity=100))
    picked = choices(s, now, BehaviorInputs(server_attention=1.0))
    assert set(picked) <= {Activity.SLEEP, Activity.REST}
    assert picked[Activity.SLEEP] > 0


def test_low_energy_threshold_is_exclusive() -> None:
    s = make_state(at=NOON, state_needs=needs(energy=LOW_ENERGY, curiosity=100))
    assert set(choices(s, NOON)) - {Activity.SLEEP, Activity.REST}


@pytest.mark.parametrize("now", [LATE_EVENING, MIDNIGHT, EARLY_MORNING])
def test_night_and_low_energy_strongly_favours_sleep(now: datetime) -> None:
    s = make_state(at=now, state_needs=needs(energy=40))
    assert choices(s, now)[Activity.SLEEP] / RUNS >= 0.85


@pytest.mark.parametrize("energy", [30.0, 60.0, 89.0])
def test_at_night_sleep_outscores_everything(energy: float) -> None:
    s = make_state(at=MIDNIGHT, state_needs=needs(energy=energy, curiosity=100))
    scores = score_activities(s, 0.0, BehaviorInputs(server_attention=1.0))
    assert scores[Activity.SLEEP] == max(scores.values())


@pytest.mark.parametrize("hour", [6, 9, 12, 15, 18, 21])
def test_rested_maple_never_sleeps_by_day(hour: int) -> None:
    now = at_local(hour)
    s = make_state(at=now, state_needs=needs(energy=90))
    assert choices(s, now)[Activity.SLEEP] == 0


def test_daytime_tired_maple_can_nap() -> None:
    s = make_state(at=NOON, state_needs=needs(energy=26))
    assert score_activities(s, 12.0, BehaviorInputs())[Activity.SLEEP] > 0


def test_high_curiosity_leads_to_reading_or_observing() -> None:
    curious = choices(make_state(at=NOON, state_needs=needs(curiosity=100)), NOON)
    bored = choices(make_state(at=NOON, state_needs=needs(curiosity=0)), NOON)
    curious_share = (curious[Activity.READ] + curious[Activity.OBSERVE_SERVER]) / RUNS
    bored_share = (bored[Activity.READ] + bored[Activity.OBSERVE_SERVER]) / RUNS
    assert curious_share >= 0.4
    assert bored_share <= 0.05


def test_server_attention_draws_maple_to_the_terminal() -> None:
    s = make_state(at=NOON, state_needs=needs(curiosity=30))
    calm = choices(s, NOON, BehaviorInputs(server_attention=0.0))
    alert = choices(s, NOON, BehaviorInputs(server_attention=1.0))
    assert alert[Activity.OBSERVE_SERVER] > calm[Activity.OBSERVE_SERVER] * 2


def test_ordinary_daytime_has_controlled_variation() -> None:
    picked = choices(make_state(at=NOON), NOON)
    assert len(picked) >= 4
    assert picked.most_common(1)[0][1] / RUNS < 0.6


def test_repeat_penalty_applies_to_current_activity_except_sleep() -> None:
    fresh = make_state(at=NOON, activity=Activity.IDLE)
    other = make_state(at=NOON, activity=Activity.REST)
    hour = local_hour(NOON, PARAMS.utc_offset)
    idle_repeat = score_activities(fresh, hour, BehaviorInputs())[Activity.IDLE]
    idle_new = score_activities(other, hour, BehaviorInputs())[Activity.IDLE]
    assert idle_repeat == idle_new * REPEAT_PENALTY

    sleeping = make_state(at=MIDNIGHT, activity=Activity.SLEEP, state_needs=needs(energy=50))
    awake = make_state(at=MIDNIGHT, activity=Activity.IDLE, state_needs=needs(energy=50))
    s1 = score_activities(sleeping, 0.0, BehaviorInputs())[Activity.SLEEP]
    s2 = score_activities(awake, 0.0, BehaviorInputs())[Activity.SLEEP]
    assert s1 == s2


def test_scores_are_non_negative_and_in_activity_order() -> None:
    for energy in (0.0, 10.5, 24.0, 50.0, 100.0):
        for curiosity in (0.0, 100.0):
            s = make_state(state_needs=needs(energy=energy, curiosity=curiosity, mood=0))
            for hour in (0.0, 5.99, 6.0, 12.0, 21.99, 22.0):
                scores = score_activities(s, hour, BehaviorInputs())
                assert list(scores) == list(Activity)
                assert all(v >= 0 for v in scores.values())
                assert max(scores.values()) > 0


def test_candidates_drop_far_weaker_options() -> None:
    pool = candidates({Activity.SLEEP: 100.0, Activity.READ: 24.9, Activity.IDLE: 25.0})
    assert set(pool) == {Activity.SLEEP, Activity.IDLE}
    with pytest.raises(ValueError):
        candidates(dict.fromkeys(Activity, 0.0))


def test_choice_is_deterministic_and_well_formed() -> None:
    s = make_state(at=NOON)
    for c in range(100):
        a = choose_next_activity(s, NOON, BehaviorInputs(), PARAMS, RngStream(SEED, "tick", c))
        b = choose_next_activity(s, NOON, BehaviorInputs(), PARAMS, RngStream(SEED, "tick", c))
        assert a == b
        spec = SPECS[a.activity]
        assert a.location in spec.locations
        minutes = (a.until - NOON) / timedelta(minutes=1)
        assert spec.min_minutes <= minutes <= spec.max_minutes


def test_continuing_activity_keeps_location() -> None:
    s = make_state(
        at=MIDNIGHT, activity=Activity.SLEEP, location=RoomLocation.BED, state_needs=needs(energy=5)
    )
    choice = choose_next_activity(s, MIDNIGHT, BehaviorInputs(), PARAMS, RngStream(SEED, "t", 0))
    assert (choice.activity, choice.location) == (Activity.SLEEP, RoomLocation.BED)


@pytest.mark.parametrize("value", [-0.01, 1.01, float("nan"), float("inf")])
def test_behavior_inputs_validated(value: float) -> None:
    with pytest.raises(ValueError):
        BehaviorInputs(server_attention=value)


def test_choose_requires_utc() -> None:
    with pytest.raises(ValueError):
        choose_next_activity(
            make_state(),
            NOON.replace(tzinfo=None),
            BehaviorInputs(),
            PARAMS,
            RngStream(SEED, "t", 0),
        )


def test_pre_extraction_baseline_vectors_are_bit_identical() -> None:
    """864 frozen vectors from the accepted PR33 tree, including next RNG draw."""
    import hashlib
    import json
    from dataclasses import asdict
    from datetime import timedelta

    from maplegotchi.core.activities import Activity
    from maplegotchi.core.behavior import BehaviorInputs, choose_next_activity, score_activities
    from maplegotchi.core.movement import begin_activity
    from maplegotchi.core.needs import evolve_through
    from maplegotchi.core.rng import RngStream
    from maplegotchi.core.room import points_for
    from maplegotchi.core.signals import classify_signals
    from tests.core.support import PARAMS, SEED, at_local, make_state, needs

    rows = []
    for activity in Activity:
        for energy in (5.0, 20.0, 80.0):
            for hour in (4, 12, 23):
                now = at_local(hour)
                state = make_state(at=now, activity=activity, state_needs=needs(energy=energy))
                inputs = BehaviorInputs()
                for counter in range(4):
                    rng = RngStream(SEED, "decision", counter)
                    choice = choose_next_activity(state, now, inputs, PARAMS, rng)
                    rows.append(
                        [
                            score_activities(state, hour, inputs),
                            choice.activity,
                            choice.location,
                            choice.until.isoformat(),
                            rng.random(),
                        ]
                    )
                for target in (Activity.SLEEP, Activity.REST):
                    point = points_for(target, SPECS[target].locations[0])[0]
                    moved = begin_activity(
                        state, now, target, point, now + timedelta(minutes=30)
                    ).state
                    for secs in (0, 1, 15, 300):
                        t = now + timedelta(seconds=secs)
                        rows.append(
                            [
                                asdict(evolve_through(moved, t, timedelta(seconds=secs))),
                                [s.kind for s in classify_signals(state, t, inputs)],
                            ]
                        )
    assert hashlib.sha256(
        json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest() == ("03cafe0db97f8a745247a8f5c546e92d95c82c13c696b79995042ccb66c9a1c3")
