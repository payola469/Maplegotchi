"""Observation model invariants: facts only, explicit status, honest gaps."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import pytest

from maplegotchi.core.observations import (
    METRICS,
    Metric,
    Observation,
    ObservationSnapshot,
    ObservationStatus,
    ServiceState,
    Unit,
    measured,
    not_measured,
)

T = datetime(2026, 1, 1, 5, 0, tzinfo=UTC)
AVAILABLE = ObservationStatus.AVAILABLE


def obs(**overrides: Any) -> Observation:
    fields: dict[str, Any] = {
        "metric": Metric.CPU_USAGE,
        "subject": "cpu",
        "status": AVAILABLE,
        "observed_at": T,
        "source": "fake",
        "value": 18.0,
    }
    fields.update(overrides)
    return Observation(**fields)


def test_every_metric_has_a_unit() -> None:
    assert set(METRICS) == set(Metric)
    assert obs().unit is Unit.PERCENT
    assert obs(metric=Metric.TEMPERATURE, value=54.0).unit is Unit.CELSIUS
    assert obs(metric=Metric.SERVICE_STATE, subject="jellyfin", value=None,
               state=ServiceState.ACTIVE).unit is Unit.STATE  # fmt: skip


@pytest.mark.parametrize(
    ("metric", "value"),
    [
        (Metric.CPU_USAGE, 0.0),
        (Metric.CPU_USAGE, 100.0),
        (Metric.MEMORY_USAGE, 51),
        (Metric.DISK_USAGE, 99.9),
        (Metric.LOAD_1M, 0.0),
        (Metric.LOAD_15M, 250.0),
        (Metric.CPU_COUNT, 1),
        (Metric.TEMPERATURE, -40.0),
        (Metric.TEMPERATURE, 150.0),
    ],
)
def test_measured_accepts_valid_boundaries(metric: Metric, value: float) -> None:
    o = measured(metric, "x", value, observed_at=T, source="fake")
    assert o.status is AVAILABLE and o.value == float(value) and o.reason is None


@pytest.mark.parametrize(
    ("metric", "value"),
    [
        (Metric.CPU_USAGE, -0.01),
        (Metric.CPU_USAGE, 100.01),
        (Metric.MEMORY_USAGE, float("nan")),
        (Metric.DISK_USAGE, float("inf")),
        (Metric.LOAD_1M, -1.0),
        (Metric.LOAD_1M, 1e9),
        (Metric.CPU_COUNT, 0),
        (Metric.TEMPERATURE, -273.0),
        (Metric.TEMPERATURE, 1000.0),
        (Metric.CPU_USAGE, True),
        (Metric.CPU_USAGE, "18"),
        (Metric.CPU_USAGE, None),
        (Metric.CPU_USAGE, [18.0]),
    ],
)
def test_invalid_or_extreme_values_become_errors_not_facts(metric: Metric, value: object) -> None:
    o = measured(metric, "x", value, observed_at=T, source="fake")
    assert o.status is ObservationStatus.ERROR
    assert o.value is None
    assert o.reason == "invalid_value"


def test_available_requires_value_and_no_reason() -> None:
    with pytest.raises(ValueError):
        obs(value=None)
    with pytest.raises(ValueError):
        obs(reason="x")
    with pytest.raises(ValueError):
        obs(value=101.0)
    with pytest.raises(ValueError):
        obs(metric=Metric.SERVICE_STATE, subject="grafana", value=1.0)
    with pytest.raises(ValueError):
        obs(metric=Metric.SERVICE_STATE, subject="grafana", value=None, state="active")


@pytest.mark.parametrize(
    "status", [ObservationStatus.UNAVAILABLE, ObservationStatus.UNKNOWN, ObservationStatus.ERROR]
)
def test_non_available_needs_reason_and_carries_no_value(status: ObservationStatus) -> None:
    o = obs(status=status, value=None, reason="no_temperature_sensors")
    assert o.value is None and o.state is None
    with pytest.raises(ValueError):
        obs(status=status, value=None, reason=None)
    with pytest.raises(ValueError):
        obs(status=status, value=18.0, reason="x")


@pytest.mark.parametrize(
    "reason",
    ["", "Has Spaces", "émoji", "a;;b", "x" * 201, "drop table;", "monitor_db:bad reason"],
)
def test_reason_codes_are_codes_not_prose(reason: str) -> None:
    with pytest.raises(ValueError):
        obs(status=ObservationStatus.UNKNOWN, value=None, reason=reason)


def test_reason_code_grammar_accepts_chained_provider_reasons() -> None:
    o = obs(
        metric=Metric.SERVICE_STATE,
        subject="jellyfin",
        status=ObservationStatus.UNKNOWN,
        value=None,
        reason="monitor_db:not_surveyed;systemd_dbus:unit_not_configured",
    )
    assert o.reason is not None and o.reason.count(";") == 1


@pytest.mark.parametrize("subject", ["", "a b", "x" * 65, "..\\x", "grafana;rm"])
def test_subjects_are_constrained(subject: str) -> None:
    with pytest.raises(ValueError):
        obs(subject=subject)


@pytest.mark.parametrize("source", ["", "Fake", "psutil!", "x" * 33])
def test_sources_are_constrained(source: str) -> None:
    with pytest.raises(ValueError):
        obs(source=source)


def test_timestamps_must_be_utc() -> None:
    with pytest.raises(ValueError):
        obs(observed_at=T.replace(tzinfo=None))
    with pytest.raises(ValueError):
        obs(observed_at=T.astimezone(timezone(timedelta(hours=7))))


def test_not_measured_rejects_available() -> None:
    with pytest.raises(ValueError):
        not_measured(Metric.CPU_USAGE, "cpu", AVAILABLE, "x", observed_at=T, source="fake")


def test_snapshot_rules() -> None:
    a = obs()
    b = obs(metric=Metric.MEMORY_USAGE, subject="memory", value=51.0)
    snap = ObservationSnapshot(observed_at=T, observations=(a, b))
    assert snap.get(Metric.CPU_USAGE, "cpu") == a
    assert snap.get(Metric.CPU_USAGE, "other") is None
    assert snap.available(Metric.MEMORY_USAGE) == (b,)
    with pytest.raises(ValueError):
        ObservationSnapshot(observed_at=T, observations=(a, a))
    with pytest.raises(ValueError):
        ObservationSnapshot(observed_at=T - timedelta(seconds=1), observations=(a,))


def test_observations_hold_no_interpretation_fields() -> None:
    # Facts only (D8): nothing like mood, feeling, or text in the model.
    names = set(Observation.__dataclass_fields__)
    assert names == {
        "metric",
        "subject",
        "status",
        "observed_at",
        "source",
        "value",
        "state",
        "reason",
    }
