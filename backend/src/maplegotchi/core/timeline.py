"""Life events produced by core transitions. Persisting them is Phase 2+."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from maplegotchi.core.activities import Activity
from maplegotchi.core.state import InteractionKind, ReactionKind


@dataclass(frozen=True, slots=True)
class ActivityChanged:
    at: datetime
    previous: Activity
    current: Activity


@dataclass(frozen=True, slots=True)
class InteractionAccepted:
    at: datetime
    kind: InteractionKind
    reaction: ReactionKind


@dataclass(frozen=True, slots=True)
class DowntimeGap:
    """No heartbeat ran between `since` and `until` (e.g. the service was down)."""

    since: datetime
    until: datetime


LifeEvent = ActivityChanged | InteractionAccepted | DowntimeGap
