"""The replaceable Director boundary (ADR-0026 §2), separate from the journal Brain.

A Director receives a `DecisionContext` — frozen, JSON-ready data built by core —
and returns one proposal object (`maple.decision.v1`: goal operation, next
action, duration, one concise reason) or None. It holds no handles and cannot
read files, clocks, storage, or Maple's state; its output is untrusted until
`core.proposal` parses and validates it, and core may refuse it.

Rule direction is not a Director: it is core's own behavior and is always
available as the fallback. The runtime wires a Director only when configured
(`MAPLE_DIRECTOR`), and calls it outside the writer lock.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol

from maplegotchi.core.proposal import DecisionContext


class DirectorKind(StrEnum):
    EXTERNAL = "external"  # e.g. Antigravity through the loopback companion (ADR-0025)


class Director(Protocol):
    @property
    def kind(self) -> DirectorKind: ...

    @property
    def name(self) -> str: ...

    @property
    def version(self) -> str: ...

    def propose_decision(self, context: DecisionContext) -> object | None:
        """One decoded JSON proposal object, or None. Never trusted as-is."""
        ...
