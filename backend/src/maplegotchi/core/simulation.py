"""Fake-time simulation of Maple's life, for tests and inspection.

Pure: time advances by arithmetic, never by waiting or reading a clock. The
same initial state, seed, parameters, and inputs always give the same report,
including the same digest.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from maplegotchi.core.activities import Activity
from maplegotchi.core.behavior import BehaviorInputs
from maplegotchi.core.daytime import is_night, local_hour, require_utc
from maplegotchi.core.heartbeat import heartbeat
from maplegotchi.core.interactions import Accepted, apply_interaction
from maplegotchi.core.movement import settle_movement
from maplegotchi.core.parameters import CoreParameters
from maplegotchi.core.state import InteractionKind, MapleState, Needs
from maplegotchi.core.timeline import ActivityChanged

NEED_NAMES = ("mood", "energy", "curiosity", "social")


@dataclass(frozen=True, slots=True)
class ScheduledInteraction:
    at: datetime
    kind: InteractionKind


@dataclass(frozen=True, slots=True)
class NeedRange:
    minimum: float
    maximum: float


@dataclass(frozen=True, slots=True)
class SimulationReport:
    started_at: datetime
    ended_at: datetime
    ticks: int
    final_state: MapleState
    activity_ticks: tuple[tuple[Activity, int], ...]
    activity_changes: int
    night_sleep_ratio: float  # share of night-time ticks spent asleep
    day_sleep_ratio: float  # share of day-time ticks spent asleep
    need_ranges: tuple[tuple[str, NeedRange], ...]
    interactions_accepted: int
    interactions_rejected: int
    digest: str  # sha256 over every step; equal digests mean identical lives


def daily_owner_routine(
    start: datetime, days: int, params: CoreParameters
) -> tuple[ScheduledInteraction, ...]:
    """A plausible owner: greets and pets Maple mornings and evenings.

    Each evening includes a too-early second pet to exercise the cooldown.
    """
    require_utc(start, "start")
    local_midnight = (start + params.utc_offset).replace(hour=0, minute=0, second=0, microsecond=0)
    first_day = local_midnight - params.utc_offset
    plan: list[ScheduledInteraction] = []
    for day in range(days + 1):
        base = first_day + timedelta(days=day)
        for offset, kind in (
            (timedelta(hours=8), InteractionKind.GREET),
            (timedelta(hours=8, seconds=20), InteractionKind.PET),
            (timedelta(hours=20), InteractionKind.PET),
            (timedelta(hours=20, seconds=10), InteractionKind.PET),  # rejected: cooldown
            (timedelta(hours=20, seconds=40), InteractionKind.GREET),
        ):
            at = base + offset
            if start < at <= start + timedelta(days=days):
                plan.append(ScheduledInteraction(at=at, kind=kind))
    return tuple(plan)


def _fingerprint(state: MapleState) -> str:
    n = state.needs
    return "|".join(
        (
            str(state.rng.tick_counter),
            str(state.rng.interaction_counter),
            state.last_updated_at.isoformat(),
            state.activity.value,
            state.location.value,
            state.activity_until.isoformat(),
            state.point.id,
            state.route.arrives_at.isoformat() if state.route else "-",
            str(state.rng.decision_counter),
            f"{state.goal.id}:{state.goal.type.value}" if state.goal else "-",
            str(state.suspended_goal.id) if state.suspended_goal else "-",
            state.action_priority.value,
            repr(n.mood),
            repr(n.energy),
            repr(n.curiosity),
            repr(n.social),
            state.expression_at(state.last_updated_at).value,
            state.reaction.kind.value if state.reaction else "-",
            str(len(state.recent_interactions)),
        )
    )


def simulate(
    initial: MapleState,
    *,
    days: int,
    params: CoreParameters,
    inputs: BehaviorInputs | None = None,
    interactions: Sequence[ScheduledInteraction] = (),
) -> SimulationReport:
    if days <= 0:
        raise ValueError("days must be positive")
    inputs = inputs or BehaviorInputs()
    start = initial.last_tick_at
    end = start + timedelta(days=days)
    pending = sorted(interactions, key=lambda s: s.at)
    if pending and (pending[0].at < initial.last_updated_at or pending[-1].at > end):
        raise ValueError("scheduled interactions must fall within the simulated period")

    digest = hashlib.sha256()
    state = initial
    activity_ticks = dict.fromkeys(Activity, 0)
    night_ticks = night_sleep = day_ticks = day_sleep = 0
    changes = accepted = rejected = 0
    lows = {name: getattr(state.needs, name) for name in NEED_NAMES}
    highs = dict(lows)
    next_pending = 0

    def track(needs: Needs) -> None:
        for name in NEED_NAMES:
            value = getattr(needs, name)
            lows[name] = min(lows[name], value)
            highs[name] = max(highs[name], value)

    now = start
    while now < end:
        tick_start = now
        now = min(now + params.heartbeat_interval, end)

        while next_pending < len(pending) and pending[next_pending].at <= now:
            scheduled = pending[next_pending]
            next_pending += 1
            state, _ = settle_movement(state, scheduled.at)  # the runtime settles arrivals too
            outcome = apply_interaction(state, scheduled.kind, scheduled.at, params)
            if isinstance(outcome, Accepted):
                accepted += 1
                state = outcome.state
                track(state.needs)
                digest.update(f"I:{_fingerprint(state)}\n".encode())
            else:
                rejected += 1
                digest.update(f"R:{outcome.reason.value}:{outcome.retry_after}\n".encode())

        # Attribute the interval that just passed to the activity Maple was doing.
        activity_ticks[state.activity] += 1
        asleep = state.activity is Activity.SLEEP
        if is_night(local_hour(tick_start, params.utc_offset)):
            night_ticks += 1
            night_sleep += asleep
        else:
            day_ticks += 1
            day_sleep += asleep

        result = heartbeat(state, now, inputs, params)
        state = result.state
        changes += sum(isinstance(e, ActivityChanged) for e in result.events)
        track(state.needs)
        digest.update(f"T:{_fingerprint(state)}\n".encode())

    return SimulationReport(
        started_at=start,
        ended_at=end,
        ticks=state.rng.tick_counter - initial.rng.tick_counter,
        final_state=state,
        activity_ticks=tuple(activity_ticks.items()),
        activity_changes=changes,
        night_sleep_ratio=night_sleep / night_ticks if night_ticks else 0.0,
        day_sleep_ratio=day_sleep / day_ticks if day_ticks else 0.0,
        need_ranges=tuple((name, NeedRange(lows[name], highs[name])) for name in NEED_NAMES),
        interactions_accepted=accepted,
        interactions_rejected=rejected,
        digest=digest.hexdigest(),
    )
