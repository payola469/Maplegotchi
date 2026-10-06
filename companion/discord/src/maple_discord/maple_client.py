"""Talking to Maple's local API: one authenticated write, the rest read-only GETs."""

from __future__ import annotations

from typing import Any

import httpx


class MapleUnavailable(RuntimeError):
    """Maple's API could not be reached or did not answer usefully."""


class MapleClient:
    def __init__(
        self,
        base_url: str,
        gateway_token: str,
        *,
        timeout_seconds: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout_seconds,
            follow_redirects=False,
            transport=transport,
        )
        self._auth = {"Authorization": f"Bearer {gateway_token}"}

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _get(self, path: str) -> Any:
        try:
            response = await self._client.get(path, headers={"accept": "application/json"})
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise MapleUnavailable(str(exc)) from exc

    async def converse(self, message_id: str, text: str) -> dict[str, Any]:
        """Relay one of Paolo's messages; returns Maple's ConversationOut."""
        body = {"message_id": message_id, "channel": "discord", "speaker": "paolo", "text": text}
        try:
            response = await self._client.post(
                "/api/conversation/messages", json=body, headers=self._auth
            )
            response.raise_for_status()
            data: Any = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise MapleUnavailable(str(exc)) from exc
        if not isinstance(data, dict) or not isinstance(data.get("reply"), str):
            raise MapleUnavailable("unexpected reply shape")
        return data

    async def snapshot(self) -> dict[str, Any]:
        data: dict[str, Any] = await self._get("/api/snapshot")
        return data

    async def journal(self, limit: int = 5) -> list[dict[str, Any]]:
        data: list[dict[str, Any]] = await self._get(f"/api/journal?limit={limit}")
        return data

    async def memory(self, limit: int = 8) -> list[dict[str, Any]]:
        data: list[dict[str, Any]] = await self._get(f"/api/memory?tier=long_term&limit={limit}")
        return data
