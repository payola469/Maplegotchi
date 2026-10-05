"""One logical heartbeat of Maple's life, as a pure function.

The caller supplies the time. There is no scheduler, no sleeping, and no Brain
parameter: an ordinary heartbeat cannot invoke an external Brain or Director (D6).

A heartbeat evolves needs, records an arrival, and handles only what may not
wait (ADR-0026): a critical or high-priority interruption, executed by core
rules. Choosing the next goal and action is a separate decision transition;
the heartbeat applies rule direction only when a decision is overdue by
`CoreParameters.decision_grace` (0 by default, so a pure life never stalls).

Need dynamics use only +, -, *, / (no exp/log), which IEEE 754 rounds exactly,
so replays are bit-identical on Windows dev machines and on paolo-core.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta

from maplegotchi.core.activities import Activity
from maplegotchi.core.behavior import BehaviorInputs
from maplegotchi.core.daytime import is_night, local_hour, require_utc
from maplegotchi.core.direction import DecisionTrigger, decide, decision_due, interrupt
from maplegotchi.core.movement import settle_movement
from maplegotchi.core.needs import (
    MOOD_RELAX_PER_HOUR,
    SOCIAL_FLOOR,
    SOCIAL_RELAX_PER_HOUR,
    evolve_needs,
    evolve_through,
    mood_target,
    needs_since,
)
from maplegotchi.core.parameters import CoreParameters
from maplegotchi.core.rng import RngStream
from maplegotchi.core.signals import SignalKind, classify_signals, interrupts
from maplegotchi.core.state import NEED_MAX, MapleState, prune_interactions
from maplegotchi.core.timeline import DowntimeGap, LifeEvent

__all__ = [
    "DOWNTIME_GAP_INTERVALS",
    "MOOD_RELAX_PER_HOUR",
    "SOCIAL_FLOOR",
    "SOCIAL_RELAX_PER_HOUR",
    "TickResult",
    "evolve_needs",
    "evolve_through",
    "heartbeat",
    "mood_target",
    "wakes_rested",
]

# A gap longer than this many heartbeat intervals is recorded as downtime.
DOWNTIME_GAP_INTERVALS = 2


@dataclass(frozen=True, slots=True)
class TickResult:
    state: MapleState
    tick_id: int
    events: tuple[LifeEvent, ...]


def wakes_rested(state: MapleState, now: datetime, params: CoreParameters) -> bool:
    """A meaningful early completion: fully rested in daytime ends sleep."""
    fully_rested = state.needs.energy >= NEED_MAX
    daytime = not is_night(local_hour(now, params.utc_offset))
    return state.activity is Activity.SLEEP and state.route is None and fully_rested and daytime


def heartbeat(
    state: MapleState,
    now: datetime,
    inputs: BehaviorInputs,
    params: CoreParameters,
) -> TickResult:
    """Advance Maple's life to `now`: evolve needs, expire reactions, handle interruptions."""
    require_utc(now, "now")
    if now <= state.last_tick_at:
        raise ValueError("heartbeat time must be after the previous heartbeat")
    if now < state.last_updated_at:
        raise ValueError("heartbeat time must not precede the latest state update")

    tick_id = state.rng.tick_counter + 1
    rng = RngStream(state.rng.seed_hex, "tick", tick_id)
    gap = now - state.last_tick_at
    elapsed = min(now - needs_since(state), params.max_catchup)

    events: list[LifeEvent] = []
    if gap > params.heartbeat_interval * DOWNTIME_GAP_INTERVALS:
        events.append(DowntimeGap(since=state.last_tick_at, until=now))

    reaction = state.reaction
    if reaction is not None and not reaction.is_active(now):
        reaction = None  # housekeeping only; expression already ignores ended reactions

    advanced = replace(
        state,
        needs=evolve_through(state, now, elapsed),
        needs_at=None,  # evolved up to this heartbeat
        reaction=reaction,
        recent_interactions=prune_interactions(state.recent_interactions, now),
        last_tick_at=now,
        last_updated_at=now,
        rng=replace(state.rng, tick_counter=tick_id),
    )

    advanced, arrival = settle_movement(advanced, now)
    events.extend(arrival)

    # Interruptions that cannot wait for the current action (ADR-0026 §7).
    signals = classify_signals(advanced, now, inputs)
    kinds = {s.kind for s in signals}
    if SignalKind.SERVER_PROBLEM not in kinds and advanced.critical_since is not None:
        advanced = replace(advanced, critical_since=None)  # the serious problem has cleared
    for signal in signals:
        if signal.kind is SignalKind.EXHAUSTED and advanced.activity is Activity.SLEEP:
            continue  # already going to bed / asleep
        if signal.kind is SignalKind.SERVER_PROBLEM and advanced.critical_since is not None:
            continue  # this problem is already being (or was) handled
        if interrupts(signal, advanced.action_priority):
            interrupted = interrupt(advanced, now, signal, rng)
            return TickResult(
                state=interrupted.state, tick_id=tick_id, events=(*events, *interrupted.events)
            )

    if wakes_rested(advanced, now, params):
        advanced = replace(advanced, activity_until=now)  # sleep is complete

    trigger = decision_due(advanced, now)
    if trigger is not None and now >= advanced.activity_until + params.decision_grace:
        overdue = params.decision_grace > timedelta(0)  # a Director had its chance
        outcome = decide(
            advanced, now, DecisionTrigger.OVERDUE if overdue else trigger, inputs, params
        )
        advanced = outcome.state
        events.extend(outcome.events)

    return TickResult(state=advanced, tick_id=tick_id, events=tuple(events))
