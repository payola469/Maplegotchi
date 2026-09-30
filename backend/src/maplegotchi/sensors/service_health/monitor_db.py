"""Service health from paolo-core's existing monitoring data (provider #1, D4/D11).

Reads only through the read-only MetricsSource interface (D18); this module
never imports sqlite3. The monitoring schema is not known until the paolo-core
survey, so until an expectation and queries are configured every service reads
as unknown with an honest reason — nothing is guessed.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from maplegotchi.core.observations import ObservationStatus
from maplegotchi.sensors.service_health.interface import ServiceReading, ServiceTarget
from maplegotchi.storage.external.interface import (
    ExternalSourceError,
    MetricsSource,
    SchemaExpectation,
    check_schema,
)


class MonitoringDbServiceHealth:
    source = "monitor_db"

    def __init__(
        self,
        open_source: Callable[[], MetricsSource],
        expectation: SchemaExpectation | None = None,
    ) -> None:
        self._open_source = open_source
        self._expectation = expectation

    def read(self, targets: Sequence[ServiceTarget]) -> Mapping[str, ServiceReading]:
        reason = self._reason()  # one look at the source per pass
        return {
            t.service_id: ServiceReading(ObservationStatus.UNKNOWN, reason=reason) for t in targets
        }

    def _reason(self) -> str:
        if self._expectation is None:
            return "not_surveyed"
        try:
            source = self._open_source()
        except ExternalSourceError as exc:
            return f"source_{exc.code}"
        try:
            if check_schema(source.describe_schema(), self._expectation):
                return "wrong_schema"
        except ExternalSourceError as exc:
            return f"source_{exc.code}"
        finally:
            source.close()
        # Schema fits, but per-service queries are written only after the survey.
        return "query_not_configured"
