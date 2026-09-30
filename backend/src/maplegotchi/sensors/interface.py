"""Host sensor contract. Probes only read; they never write, execute, or connect."""

from __future__ import annotations

from typing import Protocol


class MetricUnavailable(Exception):
    """The metric does not exist here, or has no value yet. `reason` is a reason code."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class HostProbe(Protocol):
    """Raw host readings. Raise MetricUnavailable for honest gaps; never invent values."""

    source: str

    def cpu_percent(self) -> float: ...

    def memory_percent(self) -> float: ...

    def disk_percent(self, mount: str) -> float: ...

    def load_average(self) -> tuple[float, float, float]: ...

    def cpu_count(self) -> int: ...

    def temperature_celsius(self) -> float: ...
