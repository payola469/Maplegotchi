"""Derive the bounded server_attention signal from factual observations.

Observations stay the canonical facts; this is a conservative, deterministic
reduction of them to one number in [0, 1] for the behavior engine. It grants
no capability and never chooses an activity: it only raises the score of
observe_server (CLAUDE.md §3.5, Phase 1 BehaviorInputs).

v0.1 rules (tunable constants, not architecture):
- each available metric crossing a threshold contributes a fixed level;
- a failed service contributes; other service states do not;
- missing data (unavailable/unknown/error) contributes nothing, so gaps
  never manufacture concern;
- the result is the maximum contribution, never a sum.
"""

from __future__ import annotations

from dataclasses import dataclass

from maplegotchi.core.behavior import BehaviorInputs
from maplegotchi.core.observations import Metric, ObservationSnapshot, ServiceState

# (metric, [(threshold, contribution), ...] highest threshold first)
THRESHOLDS: tuple[tuple[Metric, tuple[tuple[float, float], ...]], ...] = (
    (Metric.CPU_USAGE, ((90.0, 0.6), (75.0, 0.3))),
    (Metric.MEMORY_USAGE, ((90.0, 0.6), (80.0, 0.3))),
    (Metric.DISK_USAGE, ((95.0, 0.8), (85.0, 0.4))),
    (Metric.TEMPERATURE, ((85.0, 0.8), (75.0, 0.4))),
)
# 1-minute load divided by CPU count.
LOAD_PER_CPU: tuple[tuple[float, float], ...] = ((2.0, 0.5), (1.0, 0.25))
FAILED_SERVICE = 0.8


@dataclass(frozen=True, slots=True)
class ServerAttention:
    level: float  # 0..1
    reasons: tuple[str, ...]  # factual codes, e.g. "disk_usage:/>=95"


def _first_crossed(value: float, steps: tuple[tuple[float, float], ...]) -> tuple[float, float]:
    for threshold, contribution in steps:
        if value >= threshold:
            return threshold, contribution
    return 0.0, 0.0


def assess_server_attention(snapshot: ObservationSnapshot | None) -> ServerAttention:
    if snapshot is None:
        return ServerAttention(0.0, ())
    contributions: list[tuple[float, str]] = []

    for metric, steps in THRESHOLDS:
        for observation in sorted(snapshot.available(metric), key=lambda o: o.subject):
            if observation.value is None:  # cannot happen for available numeric metrics
                continue
            threshold, level = _first_crossed(observation.value, steps)
            if level:
                contributions.append((level, f"{metric}:{observation.subject}>={threshold:g}"))

    loads = snapshot.available(Metric.LOAD_1M)
    counts = snapshot.available(Metric.CPU_COUNT)
    if loads and counts and loads[0].value is not None and counts[0].value:
        per_cpu = loads[0].value / counts[0].value
        threshold, level = _first_crossed(per_cpu, LOAD_PER_CPU)
        if level:
            contributions.append((level, f"load_per_cpu:1m>={threshold:g}"))

    for service in sorted(snapshot.available(Metric.SERVICE_STATE), key=lambda o: o.subject):
        if service.state is ServiceState.FAILED:
            contributions.append((FAILED_SERVICE, f"service_state:{service.subject}=failed"))

    level = max((c[0] for c in contributions), default=0.0)
    return ServerAttention(level=min(1.0, level), reasons=tuple(c[1] for c in contributions))


def behavior_inputs(snapshot: ObservationSnapshot | None) -> BehaviorInputs:
    return BehaviorInputs(server_attention=assess_server_attention(snapshot).level)
