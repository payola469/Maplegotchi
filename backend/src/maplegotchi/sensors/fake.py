"""Deterministic fake host probe for development and tests.

Each metric returns its configured value, or raises the configured exception
(MetricUnavailable for honest gaps, anything else to simulate a broken source).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from maplegotchi.sensors.interface import MetricUnavailable

Reading = object  # a value, or an Exception instance to raise


def _give(reading: object) -> object:
    if isinstance(reading, BaseException):
        raise reading
    return reading


@dataclass
class FakeHostProbe:
    source: str = "fake"
    cpu: object = 18.0
    memory: object = 51.0
    disks: dict[str, object] = field(default_factory=lambda: {"/": 62.0})
    load: object = (0.42, 0.37, 0.30)
    cpus: object = 4
    temperature: object = 54.0

    def cpu_percent(self) -> float:
        return _give(self.cpu)  # type: ignore[return-value]

    def memory_percent(self) -> float:
        return _give(self.memory)  # type: ignore[return-value]

    def disk_percent(self, mount: str) -> float:
        if mount not in self.disks:
            raise MetricUnavailable("mount_not_found")
        return _give(self.disks[mount])  # type: ignore[return-value]

    def load_average(self) -> tuple[float, float, float]:
        return _give(self.load)  # type: ignore[return-value]

    def cpu_count(self) -> int:
        return _give(self.cpus)  # type: ignore[return-value]

    def temperature_celsius(self) -> float:
        return _give(self.temperature)  # type: ignore[return-value]
