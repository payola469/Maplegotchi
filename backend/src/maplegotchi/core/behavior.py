"""Behavior engine: choose Maple's next activity from state, time, and inputs.

Deliberately simple utility scoring (CLAUDE.md §2: no over-engineered behavior
tree). Each activity gets a score; hard rules come first; then one activity is
drawn from the reasonable candidates with the tick's seeded RNG, so choices
vary but are reproducible.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta

from maplegotchi.core.activities import SPECS, Activity, RoomLocation
from maplegotchi.core.daytime import DayPhase, day_phase, local_hour, require_utc
from maplegotchi.core.parameters import CoreParameters
from maplegotchi.core.rng import RngStream
from maplegotchi.core.state import MapleState

# At or below this energy Maple must sleep (hard rule).
FORCED_SLEEP_ENERGY = 10.0
# Below this energy only sleep or rest are considered.
LOW_ENERGY = 25.0
# Candidates scoring below this fraction of the best score are dropped.
CANDIDATE_CUTOFF = 0.25
# Doing the same (non-sleep) activity again is less attractive.
REPEAT_PENALTY = 0.5


@dataclass(frozen=True, slots=True)
class BehaviorInputs:
    """Inputs from outside core, already reduced to plain values by the caller.

    server_attention: 0..1, how much the server currently merits a look
    (fed from observations in Phase 3; 0 means nothing notable).
    """

    server_attention: float = 0.0

    def __post_init__(self) -> None:
        if not math.isfinite(self.server_attention) or not 0 <= self.server_attention <= 1:
            raise ValueError("server_attention must be in [0, 1]")


@dataclass(frozen=True, slots=True)
class ActivityChoice:
    activity: Activity
    location: RoomLocation
    until: datetime


def score_activities(
    state: MapleState,
    hour: float,
    inputs: BehaviorInputs,
    bias: Mapping[Activity, float] | None = None,
) -> dict[Activity, float]:
    """Non-negative desirability score per activity, in Activity declaration order."""
    energy = state.needs.energy
    curiosity = state.needs.curiosity
    mood = state.needs.mood
    phase = day_phase(hour)
    scores = dict.fromkeys(Activity, 0.0)

    if energy <= FORCED_SLEEP_ENERGY:
        scores[Activity.SLEEP] = 1.0
        return scores

    if phase is DayPhase.NIGHT:
        scores[Activity.SLEEP] = 40.0 + (100.0 - energy) * 0.8
        scores[Activity.REST] = 10.0
        scores[Activity.READ] = curiosity * 0.2
        scores[Activity.IDLE] = 5.0
        scores[Activity.OBSERVE_SERVER] = inputs.server_attention * 30.0
    else:
        scores[Activity.SLEEP] = max(0.0, 30.0 - energy) * 2.0
        scores[Activity.REST] = max(0.0, 60.0 - energy) * 0.8
        scores[Activity.READ] = curiosity * 0.6
        scores[Activity.OBSERVE_SERVER] = curiosity * 0.35 + inputs.server_attention * 60.0
        scores[Activity.WRITE] = 5.0 + mood * 0.15 + (8.0 if phase is DayPhase.EVENING else 0.0)
        scores[Activity.IDLE] = 20.0
        scores[Activity.WALK] = max(0.0, energy - 40.0) * 0.6
        # Activity set v2 (ADR-0028): a short pause at the window, a little more
        # likely when Maple is in a good mood. [PROPOSED tuning]
        scores[Activity.THINK] = 6.0 + mood * 0.06

    if energy < LOW_ENERGY:
        for activity in Activity:
            if activity not in (Activity.SLEEP, Activity.REST):
                scores[activity] = 0.0
        scores[Activity.SLEEP] = max(scores[Activity.SLEEP], 20.0)
        scores[Activity.REST] = max(scores[Activity.REST], 20.0)

    if state.activity is not Activity.SLEEP:
        scores[state.activity] *= REPEAT_PENALTY

    # A goal's soft preference (ADR-0026 §6): multiplies, so hard rules (zeros) stay.
    if bias:
        for activity, factor in bias.items():
            scores[activity] *= factor

    return scores


def candidates(scores: dict[Activity, float]) -> dict[Activity, float]:
    """Drop activities that score far below the best one."""
    best = max(scores.values())
    if best <= 0:
        raise ValueError("no activity has a positive score")
    floor = best * CANDIDATE_CUTOFF
    return {a: s for a, s in scores.items() if s > 0 and s >= floor}


def choose_next_activity(
    state: MapleState,
    now: datetime,
    inputs: BehaviorInputs,
    params: CoreParameters,
    rng: RngStream,
    bias: Mapping[Activity, float] | None = None,
) -> ActivityChoice:
    require_utc(now, "now")
    hour = local_hour(now, params.utc_offset)
    pool = candidates(score_activities(state, hour, inputs, bias))
    activity = rng.weighted_choice(list(pool), list(pool.values()))
    spec = SPECS[activity]

    if activity is state.activity and state.location in spec.locations:
        location = state.location  # continuing: stay put
    else:
        location = spec.locations[rng.randint(0, len(spec.locations) - 1)]

    minutes = rng.randint(spec.min_minutes, spec.max_minutes)
    return ActivityChoice(activity, location, now + timedelta(minutes=minutes))
