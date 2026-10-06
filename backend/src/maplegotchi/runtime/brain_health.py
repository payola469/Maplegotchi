"""Brain Health (ADR-0034): one bounded companion probe plus the stored audit, read-only.

The probe is a single `GET /health` with a short hard timeout, no redirects and a
size cap, made outside Maple's writer lock on request only (no background polling).
Every failure becomes a reported `reachable=False`; nothing here raises into a route,
touches the life loop, or calls a provider. Only short identifier-like provider and
model strings are passed through; anything else is reported as unknown (None).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx2

from maplegotchi.core.brain_health import (
    CallStats,
    HealthStatus,
    MapleDay,
    StatusReason,
    assess,
)

PROBE_TIMEOUT_SECONDS = 2.0
MAX_HEALTH_BYTES = 4 * 1024
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/+-]{0,63}")


@dataclass(frozen=True, slots=True)
class CompanionHealth:
    reachable: bool
    provider: str | None = None
    model: str | None = None
    error: str | None = None  # timeout | unreachable | http_status | invalid_response


CompanionProbe = Callable[[], CompanionHealth]


def _identifier(value: object) -> str | None:
    return value if isinstance(value, str) and _IDENTIFIER.fullmatch(value) else None


def probe_companion(
    base_url: str,
    *,
    timeout_seconds: float = PROBE_TIMEOUT_SECONDS,
    get: Callable[..., Any] = httpx2.get,
) -> CompanionHealth:
    """Ask the loopback companion's `/health` once. Never raises."""
    try:
        response = get(
            f"{base_url.rstrip('/')}/health", timeout=timeout_seconds, follow_redirects=False
        )
    except httpx2.TimeoutException:
        return CompanionHealth(reachable=False, error="timeout")
    except Exception:  # connection refused, DNS, protocol: all just "not reachable"
        return CompanionHealth(reachable=False, error="unreachable")
    try:
        if response.status_code != 200:
            return CompanionHealth(reachable=False, error="http_status")
        if len(response.content) > MAX_HEALTH_BYTES:
            return CompanionHealth(reachable=False, error="invalid_response")
        payload = response.json()
    except Exception:
        return CompanionHealth(reachable=False, error="invalid_response")
    if not isinstance(payload, dict) or payload.get("status") != "ok":
        return CompanionHealth(reachable=False, error="invalid_response")
    return CompanionHealth(
        reachable=True,
        provider=_identifier(payload.get("provider")),
        model=_identifier(payload.get("model")),
    )


@dataclass(frozen=True, slots=True)
class CallerLabel:
    mode: str  # rule | external
    name: str


@dataclass(frozen=True, slots=True)
class BrainHealthReport:
    as_of: datetime
    status: HealthStatus
    status_reason: StatusReason
    companion: CompanionHealth | None  # None: not probed (no external mode configured)
    journal_brain: CallerLabel
    director: CallerLabel
    replier: CallerLabel
    director_calls: CallStats
    replier_calls: CallStats
    last_success_at: datetime | None
    today: MapleDay


def build_report(
    *,
    as_of: datetime,
    today: MapleDay,
    journal_brain: CallerLabel,
    director: CallerLabel,
    replier: CallerLabel,
    director_calls: CallStats,
    replier_calls: CallStats,
    probe: CompanionProbe | None,
) -> BrainHealthReport:
    """Probe the companion (only if something external is configured) and classify."""
    external = tuple(c.mode == "external" for c in (journal_brain, director, replier))
    configured = any(external) and probe is not None
    companion = probe() if configured and probe is not None else None
    status, reason = assess(
        configured=configured,
        reachable=companion is not None and companion.reachable,
        director=director_calls if external[1] else None,
        replier=replier_calls if external[2] else None,
    )
    successes = [
        t for t in (director_calls.last_success_at, replier_calls.last_success_at) if t is not None
    ]
    return BrainHealthReport(
        as_of=as_of,
        status=status,
        status_reason=reason,
        companion=companion,
        journal_brain=journal_brain,
        director=director,
        replier=replier,
        director_calls=director_calls,
        replier_calls=replier_calls,
        last_success_at=max(successes) if successes else None,
        today=today,
    )
