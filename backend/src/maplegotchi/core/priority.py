"""The four priority levels (ADR-0026 §7). Dependency-free so state can use it."""

from __future__ import annotations

from enum import StrEnum


class Priority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


RANK = {Priority.CRITICAL: 3, Priority.HIGH: 2, Priority.NORMAL: 1, Priority.LOW: 0}
