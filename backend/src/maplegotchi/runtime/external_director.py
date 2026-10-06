"""HTTP-backed Director (ADR-0026 §2) on the loopback companion boundary (ADR-0025).

Maplegotchi never runs a provider itself: it POSTs the core-built
`maple.decision.v1` context to the companion's `/decide` endpoint and returns
the decoded proposal object, which core then parses and validates. Redirects
are not followed, responses are size-capped, and the contract name must match.
"""

from __future__ import annotations

from typing import Any

import httpx2

from maplegotchi.brain.director import DirectorKind
from maplegotchi.core.proposal import CONTRACT, DecisionContext

MAX_RESPONSE_BYTES = 16 * 1024


class DirectorResponseError(RuntimeError):
    """The companion answered, but not with a usable maple.decision.v1 response."""


class ExternalHttpDirector:
    kind = DirectorKind.EXTERNAL
    name = "antigravity"
    version = "1"

    def __init__(self, *, base_url: str, timeout_seconds: float = 15.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def propose_decision(self, context: DecisionContext) -> object | None:
        response = httpx2.post(
            f"{self._base_url}/decide",
            json={"contract": CONTRACT, "context": context.as_json()},
            timeout=self._timeout_seconds,
            follow_redirects=False,
        )
        response.raise_for_status()
        if len(response.content) > MAX_RESPONSE_BYTES:
            raise DirectorResponseError("response too large")
        payload: Any = response.json()
        if not isinstance(payload, dict) or payload.get("contract") != CONTRACT:
            raise DirectorResponseError("not a maple.decision.v1 response")
        if set(payload) - {"contract", "proposal"}:
            raise DirectorResponseError("unexpected response fields")
        proposal: object | None = payload.get("proposal")
        return proposal
