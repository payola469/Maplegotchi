"""Heartbeat transition and need evolution."""

from __future__ import annotations

import inspect
from dataclasses import replace
from datetime import timedelta

import pytest

from maplegotchi.core.activities import SPECS, Activity
from maplegotchi.core.behavior import FORCED_SLEEP_ENERGY, BehaviorInputs
from maplegotchi.core.heartbeat import (
    SOCIAL_FLOOR,
    evolve_needs,
    heartbeat,
    mood_target,
)
from maplegotchi.core.state import (
    InteractionKind,
    InteractionRecord,
    Needs,
    Reaction,
    ReactionKind,
)
from maplegotchi.core.timeline import ActivityChanged, DowntimeGap
from tests.core.support import OTHER_SEED, PARAMS, at_local, make_state, needs

TICK = PARAMS.heartbeat_interval
NO_INPUTS = BehaviorInputs()
NOON = at_local(12)
MIDNIGHT = at_local(0)


# ---------------------------------------------------------------- guards


def test_heartbeat_takes_no_brain() -> None:
    # D6: an ordinary heartbeat cannot invoke an external Brain — it is never given one.
    assert list(inspect.signature(heartbeat).parameters) == ["state", "now", "inputs", "params"]


def test_heartbeat_time_must_advance() -> None:
    s = make_state(at=NOON)
    with pytest.raises(ValueError):
        heartbeat(s, NOON, NO_INPUTS, PARAMS)
    with pytest.raises(ValueError):
        heartbeat(s, NOON - timedelta(seconds=1), NO_INPUTS, PARAMS)
    after_interaction = replace(s, last_updated_at=NOON + timedelta(minutes=2))
    with pytest.raises(ValueError):
        heartbeat(after_interaction, NOON + timedelta(minutes=1), NO_INPUTS, PARAMS)


def test_heartbeat_requires_utc() -> None:
    with pytest.raises(ValueError):
        heartbeat(make_state(at=NOON), (NOON + TICK).replace(tzinfo=None), NO_INPUTS, PARAMS)


# ---------------------------------------------------------------- bookkeeping


def test_heartbeat_advances_counters_and_times() -> None:
    s = make_state(at=NOON)
    r = heartbeat(s, NOON + TICK, NO_INPUTS, PARAMS)
    assert r.tick_id == 1
    assert r.state.ticks_lived == 1
    assert r.state.last_tick_at == r.state.last_updated_at == NOON + TICK
    assert r.state.rng.interaction_counter == s.rng.interaction_counter
    assert r.state.rng.seed_hex == s.rng.seed_hex
    assert r.state.identity == s.identity


def test_heartbeat_is_deterministic() -> None:
    s = make_state(at=NOON, until=timedelta(0))
    now = NOON + TICK
    assert heartbeat(s, now, NO_INPUTS, PARAMS) == heartbeat(s, now, NO_INPUTS, PARAMS)


def test_seed_changes_choices() -> None:
    a = make_state(at=NOON, until=timedelta(0))
    b = make_state(at=NOON, until=timedelta(0), seed=OTHER_SEED)
    outcomes_a, outcomes_b = [], []
    for i in range(1, 30):
        now = NOON + TICK * i
        ra = heartbeat(replace(a, rng=replace(a.rng, tick_counter=i)), now, NO_INPUTS, PARAMS)
        rb = heartbeat(replace(b, rng=replace(b.rng, tick_counter=i)), now, NO_INPUTS, PARAMS)
        outcomes_a.append((ra.state.activity, ra.state.activity_until))
        outcomes_b.append((rb.state.activity, rb.state.activity_until))
    assert outcomes_a != outcomes_b


# ---------------------------------------------------------------- need evolution


def test_awake_maple_gets_tired_and_sleeping_maple_recovers() -> None:
    awake = heartbeat(make_state(at=NOON), NOON + TICK, NO_INPUTS, PARAMS).state
    assert awake.needs.energy < 80.0
    asleep = heartbeat(
        make_state(at=MIDNIGHT, activity=Activity.SLEEP), MIDNIGHT + TICK, NO_INPUTS, PARAMS
    ).state
    assert asleep.needs.energy > 80.0


@pytest.mark.parametrize("activity", list(Activity))
def test_energy_and_curiosity_follow_activity_rates(activity: Activity) -> None:
    start = needs(energy=50, curiosity=50)
    after = evolve_needs(start, activity, timedelta(hours=1))
    spec = SPECS[activity]
    assert after.energy == pytest.approx(50 + spec.energy_per_hour)
    assert after.curiosity == pytest.approx(50 + spec.curiosity_per_hour)


def test_reading_satisfies_curiosity_and_idling_builds_it() -> None:
    start = needs(curiosity=50)
    assert evolve_needs(start, Activity.READ, timedelta(hours=1)).curiosity < 50
    assert evolve_needs(start, Activity.OBSERVE_SERVER, timedelta(hours=1)).curiosity < 50
    assert evolve_needs(start, Activity.IDLE, timedelta(hours=1)).curiosity > 50


@pytest.mark.parametrize("start", [0.0, 10.0, 19.9, 20.0, 50.0, 100.0])
def test_social_relaxes_toward_floor_without_crossing(start: float) -> None:
    previous = start
    for hours in (1, 5, 24, 240, 10_000):
        value = evolve_needs(needs(social=start), Activity.IDLE, timedelta(hours=hours)).social
        if start >= SOCIAL_FLOOR:
            assert SOCIAL_FLOOR <= value <= previous
        else:
            assert previous <= value <= SOCIAL_FLOOR
        previous = value


def test_mood_relaxes_toward_target() -> None:
    low = evolve_needs(needs(mood=0, energy=100, social=100), Activity.REST, timedelta(hours=2))
    assert low.mood > 0
    high = evolve_needs(needs(mood=100, energy=0, social=0), Activity.SLEEP, timedelta(hours=2))
    assert high.mood < 100
    assert mood_target(0, 0) == 20.0
    assert mood_target(100, 100) == 100.0


def test_zero_elapsed_changes_nothing() -> None:
    n = needs(mood=33.3, energy=44.4, curiosity=55.5, social=66.6)
    after = evolve_needs(n, Activity.WALK, timedelta(0))
    assert (after.energy, after.curiosity, after.social) == (44.4, 55.5, 66.6)


def test_negative_elapsed_rejected() -> None:
    with pytest.raises(ValueError):
        evolve_needs(needs(), Activity.IDLE, timedelta(seconds=-1))


EXTREMES = [0.0, 100.0]


@pytest.mark.parametrize("activity", list(Activity))
@pytest.mark.parametrize("hours", [0.001, 1, 24, 10_000])
def test_needs_stay_in_range_from_extremes(activity: Activity, hours: float) -> None:
    for mood in EXTREMES:
        for energy in EXTREMES:
            for curiosity in EXTREMES:
                for social in EXTREMES:
                    start = Needs(mood=mood, energy=energy, curiosity=curiosity, social=social)
                    after = evolve_needs(start, activity, timedelta(hours=hours))
                    for value in (after.mood, after.energy, after.curiosity, after.social):
                        assert 0.0 <= value <= 100.0


def test_sleep_clamps_energy_at_full() -> None:
    s = make_state(at=MIDNIGHT, activity=Activity.SLEEP, state_needs=needs(energy=99.9))
    assert heartbeat(s, MIDNIGHT + timedelta(hours=1), NO_INPUTS, PARAMS).state.needs.energy == 100


# ---------------------------------------------------------------- activity transitions


def test_activity_continues_until_its_planned_end() -> None:
    s = make_state(at=NOON, activity=Activity.READ, until=timedelta(minutes=30))
    r = heartbeat(s, NOON + TICK, NO_INPUTS, PARAMS)
    assert r.state.activity is Activity.READ
    assert r.state.activity_started_at == NOON
    assert r.events == ()


def test_activity_is_rechosen_at_planned_end() -> None:
    s = make_state(at=NOON, activity=Activity.READ, until=TICK)
    r = heartbeat(s, NOON + TICK, NO_INPUTS, PARAMS)
    assert r.state.activity_until > NOON + TICK
    changed = [e for e in r.events if isinstance(e, ActivityChanged)]
    if r.state.activity is Activity.READ:
        assert changed == []
        assert r.state.activity_started_at == NOON
    else:
        assert changed == [ActivityChanged(NOON + TICK, Activity.READ, r.state.activity)]
        assert r.state.activity_started_at == NOON + TICK


def test_exhaustion_interrupts_activity_with_sleep() -> None:
    s = make_state(
        at=NOON,
        activity=Activity.WALK,
        state_needs=needs(energy=FORCED_SLEEP_ENERGY + 0.2),
        until=timedelta(minutes=15),
    )
    r = heartbeat(s, NOON + TICK, NO_INPUTS, PARAMS)  # walking drains 0.5 energy per tick
    assert r.state.activity is Activity.SLEEP
    assert ActivityChanged(NOON + TICK, Activity.WALK, Activity.SLEEP) in r.events


def test_fully_rested_maple_wakes_early_in_the_day_but_not_at_night() -> None:
    day = make_state(
        at=at_local(9),
        activity=Activity.SLEEP,
        state_needs=needs(energy=100),
        until=timedelta(hours=3),
    )
    assert (
        heartbeat(day, at_local(9) + TICK, NO_INPUTS, PARAMS).state.activity is not Activity.SLEEP
    )

    night = make_state(
        at=MIDNIGHT,
        activity=Activity.SLEEP,
        state_needs=needs(energy=100),
        until=timedelta(hours=3),
    )
    assert heartbeat(night, MIDNIGHT + TICK, NO_INPUTS, PARAMS).state.activity is Activity.SLEEP


# ---------------------------------------------------------------- reactions, ledger, catch-up


def test_expired_reaction_is_cleared_and_live_one_kept() -> None:
    s = make_state(at=NOON)
    expired = Reaction(ReactionKind.PET_HAPPY, 0, NOON, NOON + timedelta(seconds=8))
    assert (
        heartbeat(replace(s, reaction=expired), NOON + TICK, NO_INPUTS, PARAMS).state.reaction
        is None
    )
    live = Reaction(ReactionKind.PET_HAPPY, 1, NOON, NOON + timedelta(minutes=6))
    kept = heartbeat(replace(s, reaction=live), NOON + TICK, NO_INPUTS, PARAMS).state.reaction
    assert kept == live


def test_heartbeat_prunes_interactions_outside_window() -> None:
    s = make_state(at=NOON)
    old = InteractionRecord(InteractionKind.GREET, NOON - timedelta(minutes=8))
    recent = InteractionRecord(InteractionKind.PET, NOON - timedelta(minutes=1))
    s = replace(s, recent_interactions=(old, recent))
    after = heartbeat(s, NOON + TICK, NO_INPUTS, PARAMS).state  # old is now 13 min ago
    assert after.recent_interactions == (recent,)


def test_catch_up_is_bounded_and_gap_recorded() -> None:
    s = make_state(at=NOON, activity=Activity.WALK, until=timedelta(days=10))
    later = NOON + timedelta(days=3)
    r = heartbeat(s, later, NO_INPUTS, PARAMS)
    assert DowntimeGap(since=NOON, until=later) in r.events
    capped = evolve_needs(s.needs, Activity.WALK, PARAMS.max_catchup)
    # Needs reflect at most max_catchup of change, not three days of it.
    assert r.state.needs.curiosity == capped.curiosity
    assert r.state.needs.social == capped.social


def test_no_gap_event_for_normal_or_borderline_intervals() -> None:
    s = make_state(at=NOON, until=timedelta(hours=1))
    for gap in (TICK, TICK * 2):
        assert not any(
            isinstance(e, DowntimeGap) for e in heartbeat(s, NOON + gap, NO_INPUTS, PARAMS).events
        )
    events = heartbeat(s, NOON + TICK * 2 + timedelta(seconds=1), NO_INPUTS, PARAMS).events
    assert any(isinstance(e, DowntimeGap) for e in events)
