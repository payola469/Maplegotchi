"""Greet and Pet: effects, reactions, cooldowns, and the global rate limit (D14)."""

from __future__ import annotations

from dataclasses import fields, replace
from datetime import datetime, timedelta

import pytest

from maplegotchi.core.activities import Activity
from maplegotchi.core.behavior import BehaviorInputs
from maplegotchi.core.heartbeat import heartbeat
from maplegotchi.core.interactions import (
    EFFECTS,
    Accepted,
    Rejected,
    RejectionReason,
    apply_interaction,
    check_limits,
)
from maplegotchi.core.parameters import (
    GLOBAL_INTERACTION_LIMIT,
    GLOBAL_INTERACTION_WINDOW,
    GREET_COOLDOWN,
    PET_COOLDOWN,
)
from maplegotchi.core.state import (
    Expression,
    InteractionKind,
    InteractionRecord,
    MapleState,
    ReactionKind,
)
from maplegotchi.core.timeline import InteractionAccepted
from tests.core.support import PARAMS, at_local, make_state, needs

GREET = InteractionKind.GREET
PET = InteractionKind.PET
T = at_local(12)


def accept(state: MapleState, kind: InteractionKind, at: datetime) -> MapleState:
    outcome = apply_interaction(state, kind, at, PARAMS)
    assert isinstance(outcome, Accepted), outcome
    return outcome.state


def reject(state: MapleState, kind: InteractionKind, at: datetime) -> Rejected:
    outcome = apply_interaction(state, kind, at, PARAMS)
    assert isinstance(outcome, Rejected), outcome
    return outcome


def secs(n: float) -> timedelta:
    return timedelta(seconds=n)


def test_fixed_limits() -> None:
    assert GREET_COOLDOWN == secs(60)
    assert PET_COOLDOWN == secs(30)
    assert GLOBAL_INTERACTION_LIMIT == 10
    assert GLOBAL_INTERACTION_WINDOW == timedelta(minutes=10)


# ---------------------------------------------------------------- effects and reactions


@pytest.mark.parametrize("kind", [GREET, PET])
def test_accepted_interaction_updates_real_state(kind: InteractionKind) -> None:
    s = make_state(at=T)
    outcome = apply_interaction(s, kind, T, PARAMS)
    assert isinstance(outcome, Accepted)
    after = outcome.state
    effect = EFFECTS[kind]
    assert after.needs.social == s.needs.social + effect.social
    assert after.needs.mood == s.needs.mood + effect.mood
    assert after.needs.energy == s.needs.energy
    assert after.needs.curiosity == s.needs.curiosity
    assert after.recent_interactions == (InteractionRecord(kind, T),)
    assert after.rng.interaction_counter == 1
    assert after.rng.tick_counter == s.rng.tick_counter
    assert after.last_updated_at == T
    assert after.last_tick_at == s.last_tick_at
    assert after.reaction == outcome.reaction
    assert outcome.reaction.started_at == T
    assert outcome.reaction.until == T + PARAMS.reaction_duration
    assert outcome.reaction.kind in (ReactionKind.GREET_HAPPY, ReactionKind.PET_HAPPY)
    assert outcome.event == InteractionAccepted(T, kind, outcome.reaction.kind)
    assert after.expression_at(T) is Expression.HAPPY


@pytest.mark.parametrize(
    ("kind", "expected"), [(GREET, ReactionKind.GREET_SLEEPY), (PET, ReactionKind.PET_SLEEPY)]
)
def test_sleeping_maple_reacts_sleepily_and_takes_in_less(
    kind: InteractionKind, expected: ReactionKind
) -> None:
    awake = make_state(at=at_local(0))
    asleep = make_state(at=at_local(0), activity=Activity.SLEEP)
    outcome = apply_interaction(asleep, kind, at_local(0), PARAMS)
    assert isinstance(outcome, Accepted)
    assert outcome.reaction.kind is expected
    assert outcome.state.activity is Activity.SLEEP  # interactions never wake Maple
    assert outcome.state.expression_at(at_local(0)) is Expression.SLEEPY
    gain_asleep = outcome.state.needs.social - asleep.needs.social
    gain_awake = accept(awake, kind, at_local(0)).needs.social - awake.needs.social
    assert gain_asleep == gain_awake / 2


def test_tired_awake_maple_reacts_sleepily() -> None:
    s = make_state(at=T, state_needs=needs(energy=15))
    outcome = apply_interaction(s, GREET, T, PARAMS)
    assert isinstance(outcome, Accepted)
    assert outcome.reaction.kind is ReactionKind.GREET_SLEEPY


def test_repeated_interactions_have_diminishing_effect() -> None:
    s = make_state(at=T)
    first = accept(s, PET, T)
    second = accept(first, PET, T + PET_COOLDOWN)
    third = accept(second, PET, T + PET_COOLDOWN * 2)
    g1 = first.needs.social - s.needs.social
    g2 = second.needs.social - first.needs.social
    g3 = third.needs.social - second.needs.social
    assert g2 == g1 / 2
    assert g3 == g1 / 4


def test_social_and_mood_clamp_at_maximum() -> None:
    s = make_state(at=T, state_needs=needs(mood=99, social=99))
    after = accept(s, GREET, T)
    assert after.needs.social == 100.0
    assert after.needs.mood == 100.0


def test_reaction_variant_is_deterministic() -> None:
    s = make_state(at=T)
    a = apply_interaction(s, GREET, T, PARAMS)
    b = apply_interaction(s, GREET, T, PARAMS)
    assert a == b


# ---------------------------------------------------------------- cooldowns


@pytest.mark.parametrize(("kind", "cooldown"), [(GREET, GREET_COOLDOWN), (PET, PET_COOLDOWN)])
def test_cooldown_boundaries(kind: InteractionKind, cooldown: timedelta) -> None:
    s = accept(make_state(at=T), kind, T)
    r = reject(s, kind, T)
    assert r == Rejected(RejectionReason.COOLDOWN, cooldown)
    almost = T + cooldown - timedelta(microseconds=1)
    assert reject(s, kind, almost) == Rejected(RejectionReason.COOLDOWN, timedelta(microseconds=1))
    assert reject(s, kind, T + secs(1)).retry_after == cooldown - secs(1)
    accept(s, kind, T + cooldown)


def test_greet_and_pet_cooldowns_are_independent() -> None:
    s = accept(make_state(at=T), GREET, T)
    s = accept(s, PET, T + secs(1))
    assert reject(s, GREET, T + secs(2)).retry_after == secs(58)
    assert reject(s, PET, T + secs(2)).retry_after == secs(29)


def test_rejection_leaves_no_trace() -> None:
    s = accept(make_state(at=T), GREET, T)
    reject(s, GREET, T + secs(5))
    after = accept(s, PET, T + secs(6))
    assert after.rng.interaction_counter == 2
    assert len(after.recent_interactions) == 2


# ---------------------------------------------------------------- global rate limit


def fill_window(start: datetime) -> MapleState:
    """Ten accepted interactions in 4.5 minutes, respecting both cooldowns."""
    s = make_state(at=start)
    for i in range(GLOBAL_INTERACTION_LIMIT):
        kind = GREET if i % 2 == 0 else PET
        s = accept(s, kind, start + secs(30 * i))
    return s


def test_global_limit_blocks_the_eleventh_interaction() -> None:
    s = fill_window(T)
    assert len(s.recent_interactions) == GLOBAL_INTERACTION_LIMIT
    r = reject(s, PET, T + secs(300))
    assert r == Rejected(RejectionReason.RATE_LIMIT, secs(300))  # oldest (T) leaves at T+600
    assert reject(s, GREET, T + secs(599)).reason is RejectionReason.RATE_LIMIT
    after = accept(s, PET, T + secs(600))
    assert len(after.recent_interactions) == GLOBAL_INTERACTION_LIMIT


def test_both_limits_report_the_longer_wait() -> None:
    s = fill_window(T)  # last interaction: PET at T+270
    r = reject(s, PET, T + secs(280))
    assert r == Rejected(RejectionReason.RATE_LIMIT, secs(320))
    only_cooldown = check_limits(s, PET, T + secs(280))
    assert only_cooldown is not None and only_cooldown.retry_after == secs(320)


def test_rate_limit_survives_a_heartbeat() -> None:
    s = fill_window(T)
    s = heartbeat(s, T + secs(300), BehaviorInputs(), PARAMS).state
    assert reject(s, GREET, T + secs(301)).reason is RejectionReason.RATE_LIMIT


def test_limits_survive_a_restart_round_trip() -> None:
    # Everything the limits depend on is in MapleState's fields, so rebuilding the
    # state from its fields (what Phase 2 will do from SQLite) keeps them in force.
    s = fill_window(T)
    rebuilt = MapleState(**{f.name: getattr(s, f.name) for f in fields(MapleState)})
    assert rebuilt == s
    assert reject(rebuilt, PET, T + secs(300)) == reject(s, PET, T + secs(300))
    assert reject(rebuilt, PET, T + secs(271)).reason is RejectionReason.RATE_LIMIT


def test_old_records_do_not_count() -> None:
    s = make_state(at=T)
    old = tuple(
        InteractionRecord(GREET if i % 2 else PET, T - secs(599) + secs(i)) for i in range(10)
    )
    s = replace(s, recent_interactions=old)
    # At T+1 the oldest record is exactly 600 s old and no longer counts.
    accept(s, PET, T + secs(1))


# ---------------------------------------------------------------- input validation


def test_only_known_kinds_accepted() -> None:
    with pytest.raises(TypeError):
        apply_interaction(make_state(at=T), "greet", T, PARAMS)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        apply_interaction(make_state(at=T), "feed", T, PARAMS)  # type: ignore[arg-type]


def test_interaction_time_validation() -> None:
    s = make_state(at=T)
    with pytest.raises(ValueError):
        apply_interaction(s, GREET, T - secs(1), PARAMS)
    with pytest.raises(ValueError):
        apply_interaction(s, GREET, T.replace(tzinfo=None), PARAMS)
    accept(s, GREET, T)  # exactly at the latest update is fine
