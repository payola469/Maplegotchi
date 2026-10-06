"""HTTP-backed replier for conversations (ADR-0032) on the loopback companion boundary.

POSTs the core-built `maple.reply.v1` context to the companion's `/reply` and
returns its reply text, which core validates (and replaces with a rule reply if
anything is wrong). No redirects, size-capped, contract checked.
"""

from __future__ import annotations

from typing import Any

import httpx2

from maplegotchi.core.conversation import REPLY_CONTRACT, ReplyContext

MAX_RESPONSE_BYTES = 16 * 1024


class ReplierResponseError(RuntimeError):
    """The companion answered, but not with a usable maple.reply.v1 response."""


class ExternalHttpReplier:
    kind = "external"
    name = "antigravity"

    def __init__(self, *, base_url: str, timeout_seconds: float = 15.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def reply(self, context: ReplyContext) -> str:
        response = httpx2.post(
            f"{self._base_url}/reply",
            json={"contract": REPLY_CONTRACT, "context": context.as_json()},
            timeout=self._timeout_seconds,
            follow_redirects=False,
        )
        response.raise_for_status()
        if len(response.content) > MAX_RESPONSE_BYTES:
            raise ReplierResponseError("response too large")
        payload: Any = response.json()
        if not isinstance(payload, dict) or payload.get("contract") != REPLY_CONTRACT:
            raise ReplierResponseError("not a maple.reply.v1 response")
        if set(payload) - {"contract", "reply"} or not isinstance(payload.get("reply"), str):
            raise ReplierResponseError("unexpected response shape")
        text: str = payload["reply"]
        return text
