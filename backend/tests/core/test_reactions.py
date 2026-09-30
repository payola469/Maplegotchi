"""Transient Greet/Pet reactions end at `until`, derived from supplied time (D17).

No heartbeat, scheduler, or timer is involved: the same state presents a
reaction before `until` and normal expression from `until` onward.
"""

from __future__ import annotations

from dataclasses import fields
from datetime import datetime, timedelta

import pytest

from maplegotchi.core.activities import Activity
from maplegotchi.core.behavior import BehaviorInputs
from maplegotchi.core.heartbeat import heartbeat
from maplegotchi.core.interactions import Accepted, apply_interaction
from maplegotchi.core.state import Expression, InteractionKind, MapleState, Reaction, ReactionKind
from tests.core.support import PARAMS, at_local, make_state, needs

T = at_local(12)  # "Pet at 12:00:00"
DURATION = PARAMS.reaction_duration
UNTIL = T + DURATION  # 12:00:08
TINY = timedelta(microseconds=1)


def petted(state: MapleState | None = None, at: datetime = T) -> MapleState:
    # Idle, mood 50: the normal expression is calm, so any "happy" comes from the reaction.
    state = state or make_state(at=at, state_needs=needs(mood=50))
    outcome = apply_interaction(state, InteractionKind.PET, at, PARAMS)
    assert isinstance(outcome, Accepted)
    return outcome.state


def rebuild(state: MapleState) -> MapleState:
    """Reconstruct from plain fields, as Phase 2 will after a restart."""
    return MapleState(**{f.name: getattr(state, f.name) for f in fields(MapleState)})


def test_reaction_duration_is_eight_seconds() -> None:
    assert DURATION == timedelta(seconds=8)
    reaction = petted().reaction
    assert reaction is not None and reaction.until == UNTIL


def test_reaction_active_at_start() -> None:
    s = petted()
    assert s.active_reaction(T) == s.reaction
    assert s.expression_at(T) is Expression.HAPPY


def test_reaction_active_immediately_before_expiry() -> None:
    s = petted()
    assert s.active_reaction(UNTIL - TINY) is not None
    assert s.expression_at(UNTIL - TINY) is Expression.HAPPY


def test_reaction_over_exactly_at_expiry() -> None:
    s = petted()
    assert s.active_reaction(UNTIL) is None
    assert s.expression_at(UNTIL) is Expression.CALM


def test_reaction_over_immediately_after_expiry() -> None:
    s = petted()
    assert s.active_reaction(UNTIL + TINY) is None
    assert s.expression_at(UNTIL + TINY) is Expression.CALM


def test_expiry_needs_no_heartbeat() -> None:
    s = petted()
    # Same state object, well before the next 5-minute heartbeat.
    assert s.last_tick_at == T
    assert s.expression_at(T + timedelta(seconds=4)) is Expression.HAPPY
    assert s.expression_at(T + timedelta(seconds=9)) is Expression.CALM
    assert s.expression_at(T + timedelta(minutes=4, seconds=59)) is Expression.CALM


def test_after_expiry_expression_follows_normal_state() -> None:
    # Same pet while writing: happy during the reaction, focused after it.
    s = petted(make_state(at=T, activity=Activity.WRITE))
    assert s.expression_at(T) is Expression.HAPPY
    assert s.expression_at(UNTIL) is Expression.FOCUSED


def test_reconstruction_while_reaction_active() -> None:
    s = rebuild(petted())
    assert s == petted()
    mid = T + timedelta(seconds=4)
    assert s.active_reaction(mid) is not None
    assert s.expression_at(mid) is Expression.HAPPY
    assert s.expression_at(UNTIL) is Expression.CALM


def test_reconstruction_after_reaction_expired() -> None:
    s = rebuild(petted())
    later = UNTIL + timedelta(seconds=30)
    assert s.active_reaction(later) is None
    assert s.expression_at(later) is Expression.CALM
    # The stored record is still there until housekeeping; presentation ignores it.
    assert s.reaction is not None


def test_heartbeat_drops_ended_reaction_as_housekeeping() -> None:
    s = petted()
    after = heartbeat(s, T + PARAMS.heartbeat_interval, BehaviorInputs(), PARAMS).state
    assert after.reaction is None


def test_sleepy_reaction_never_shows_happy() -> None:
    s = make_state(at=at_local(0), activity=Activity.SLEEP)
    outcome = apply_interaction(s, InteractionKind.PET, at_local(0), PARAMS)
    assert isinstance(outcome, Accepted)
    assert outcome.reaction.kind is ReactionKind.PET_SLEEPY
    assert outcome.state.expression_at(at_local(0)) is Expression.SLEEPY


def test_cannot_present_state_before_its_latest_update() -> None:
    s = petted()
    with pytest.raises(ValueError):
        s.expression_at(T - TINY)
    with pytest.raises(ValueError):
        s.active_reaction(T - TINY)
    with pytest.raises(ValueError):
        s.expression_at(T.replace(tzinfo=None))


def test_reaction_until_is_exclusive() -> None:
    r = Reaction(ReactionKind.GREET_HAPPY, 0, T, UNTIL)
    assert r.is_active(T)
    assert r.is_active(UNTIL - TINY)
    assert not r.is_active(UNTIL)
    assert not r.is_active(T - TINY)
