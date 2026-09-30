"""The fixed v0.1 activity set and Maple's logical room locations.

Activities are domain concepts only: duration range, where in the room they
happen, and how they change Maple's needs per hour. Rendering is the UI's job.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType


class Activity(StrEnum):
    IDLE = "idle"
    WALK = "walk"
    SLEEP = "sleep"
    READ = "read"
    WRITE = "write"
    OBSERVE_SERVER = "observe_server"
    REST = "rest"


class RoomLocation(StrEnum):
    BED = "bed"
    DESK = "desk"
    BOOKSHELF = "bookshelf"
    WINDOW = "window"
    TERMINAL = "terminal"
    RUG = "rug"


@dataclass(frozen=True, slots=True)
class ActivitySpec:
    min_minutes: int
    max_minutes: int
    # Ordered tuple (not a set) so RNG-driven choices are reproducible across processes.
    locations: tuple[RoomLocation, ...]
    energy_per_hour: float
    curiosity_per_hour: float
    mood_per_hour: float

    def __post_init__(self) -> None:
        if not 0 < self.min_minutes <= self.max_minutes:
            raise ValueError("durations must satisfy 0 < min <= max")
        if not self.locations or len(set(self.locations)) != len(self.locations):
            raise ValueError("locations must be non-empty and unique")


SPECS: Mapping[Activity, ActivitySpec] = MappingProxyType(
    {
        Activity.IDLE: ActivitySpec(
            10, 30, (RoomLocation.RUG, RoomLocation.WINDOW), -2.0, 5.0, 0.0
        ),
        Activity.WALK: ActivitySpec(
            5,
            15,
            (RoomLocation.RUG, RoomLocation.WINDOW, RoomLocation.DESK, RoomLocation.BOOKSHELF),
            -6.0,
            4.0,
            1.0,
        ),
        Activity.SLEEP: ActivitySpec(90, 240, (RoomLocation.BED,), 12.0, 2.0, 0.0),
        Activity.READ: ActivitySpec(20, 60, (RoomLocation.BOOKSHELF,), -3.0, -8.0, 1.0),
        Activity.WRITE: ActivitySpec(20, 50, (RoomLocation.DESK,), -4.0, 1.0, 1.0),
        Activity.OBSERVE_SERVER: ActivitySpec(10, 30, (RoomLocation.TERMINAL,), -3.0, -10.0, 0.5),
        Activity.REST: ActivitySpec(15, 45, (RoomLocation.BED, RoomLocation.RUG), 5.0, 3.0, 0.5),
    }
)

if set(SPECS) != set(Activity):
    raise RuntimeError("every Activity needs an ActivitySpec")
