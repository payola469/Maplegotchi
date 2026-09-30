"""Life events produced by core transitions. Storage persists them append-only."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from maplegotchi.core.activities import Activity
from maplegotchi.core.state import InteractionKind, ReactionKind


@dataclass(frozen=True, slots=True)
class Born:
    """Maple's life began. Recorded exactly once per life."""

    at: datetime
    name: str


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


LifeEvent = Born | ActivityChanged | InteractionAccepted | DowntimeGap
