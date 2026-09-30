"""Deterministic fake service-health provider for development and tests."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime

from maplegotchi.core.observations import ObservationStatus
from maplegotchi.sensors.service_health.interface import ServiceReading, ServiceTarget


class FakeServiceHealth:
    def __init__(
        self,
        readings: Mapping[str, ServiceReading],
        *,
        source: str = "fake",
        failure: Exception | None = None,
    ) -> None:
        self.source = source
        self._readings = dict(readings)
        self._failure = failure

    def read(
        self, targets: Sequence[ServiceTarget], *, now: datetime
    ) -> Mapping[str, ServiceReading]:
        if self._failure is not None:
            raise self._failure
        missing = ServiceReading(ObservationStatus.UNKNOWN, reason="not_in_fake")
        return {t.service_id: self._readings.get(t.service_id, missing) for t in targets}
