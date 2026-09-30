"""Core parameters: fixed owner decisions as constants, tunables in CoreParameters."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

# Interaction limits — FIXED by owner decision D14 (ADR-0014). Not configurable.
GREET_COOLDOWN = timedelta(seconds=60)
PET_COOLDOWN = timedelta(seconds=30)
GLOBAL_INTERACTION_LIMIT = 10
GLOBAL_INTERACTION_WINDOW = timedelta(minutes=10)

# Production heartbeat interval — D6 (ADR-0006). Configurable via CoreParameters.
DEFAULT_HEARTBEAT_INTERVAL = timedelta(seconds=300)

_MAX_UTC_OFFSET = timedelta(hours=14)


@dataclass(frozen=True, slots=True)
class CoreParameters:
    """Tunable, non-security parameters supplied to core by the caller."""

    heartbeat_interval: timedelta = DEFAULT_HEARTBEAT_INTERVAL
    # Offset of Maple's home from UTC, used for day/night. Production default is
    # paolo-core's Asia/Bangkok (UTC+07:00, no DST) - owner-confirmed (D16).
    # Injectable for tests/simulations; core never reads a timezone database.
    utc_offset: timedelta = timedelta(hours=7)
    # Longest gap a single heartbeat will apply need changes for (bounded catch-up).
    max_catchup: timedelta = timedelta(hours=6)
    # How long a Greet/Pet reaction is shown (D17); it ends by time, not by heartbeat.
    reaction_duration: timedelta = timedelta(seconds=8)

    def __post_init__(self) -> None:
        if self.heartbeat_interval <= timedelta(0):
            raise ValueError("heartbeat_interval must be positive")
        if abs(self.utc_offset) > _MAX_UTC_OFFSET:
            raise ValueError("utc_offset must be within +/-14h")
        if self.max_catchup < self.heartbeat_interval:
            raise ValueError("max_catchup must be >= heartbeat_interval")
        if not timedelta(0) < self.reaction_duration <= timedelta(minutes=1):
            raise ValueError("reaction_duration must be in (0, 60s]")
