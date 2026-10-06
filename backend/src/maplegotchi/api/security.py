"""HTTP safety for the app layer (CLAUDE.md §4.4, D13).

- Security headers on every response (pure ASGI, so streaming is unaffected).
- Request bodies are tiny or absent: a declared Content-Length over the limit,
  or a chunked body with no length, is refused before routing.
- Mutating interaction requests must carry an Origin from the explicit
  allowlist. There is no CORS middleware at all: v0.1 is same-origin (FastAPI
  serves the built frontend; in development the Vite proxy is same-origin to
  the browser), so no cross-origin read or write is ever granted.
"""

from __future__ import annotations

import hmac
from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any

from fastapi import HTTPException, Request

Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]

MAX_BODY_BYTES = 1024
# Paths that accept a larger body (a Discord message is up to 2000 characters).
LARGER_BODIES: dict[str, int] = {"/api/conversation/messages": 8192}

SECURITY_HEADERS: tuple[tuple[bytes, bytes], ...] = (
    (
        b"content-security-policy",
        b"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
        b"connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; "
        b"frame-ancestors 'none'",
    ),
    (b"x-content-type-options", b"nosniff"),
    (b"referrer-policy", b"no-referrer"),
    (b"x-frame-options", b"DENY"),
    (b"cross-origin-opener-policy", b"same-origin"),
    (b"cross-origin-resource-policy", b"same-origin"),
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=(), usb=(), payment=()"),
)


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        is_api = str(scope.get("path", "")).startswith("/api")

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = [h for h in message.get("headers", []) if h[0].lower() != b"server"]
                headers.extend(SECURITY_HEADERS)
                has_cache_control = any(h[0].lower() == b"cache-control" for h in headers)
                if is_api and not has_cache_control:
                    headers.append((b"cache-control", b"no-store"))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)


class BodyLimitMiddleware:
    def __init__(self, app: ASGIApp, max_bytes: int = MAX_BODY_BYTES) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            limit = LARGER_BODIES.get(str(scope.get("path", "")), self.max_bytes)
            headers = {k.lower(): v for k, v in scope.get("headers", [])}
            length = headers.get(b"content-length")
            chunked = b"chunked" in headers.get(b"transfer-encoding", b"").lower()
            too_big = False
            if length is not None:
                try:
                    too_big = int(length) > limit
                except ValueError:
                    too_big = True
            if too_big or (chunked and length is None):
                await _plain_error(send, 413, b'{"detail":"request body too large"}')
                return
        await self.app(scope, receive, send)


async def _plain_error(send: Send, status: int, body: bytes) -> None:
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
                *SECURITY_HEADERS,
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


def origin_guard(allowed: tuple[str, ...]) -> Callable[[Request], None]:
    allowed_set = frozenset(allowed)

    def require_trusted_origin(request: Request) -> None:
        origin = request.headers.get("origin")
        if origin is None or origin not in allowed_set:
            raise HTTPException(status_code=403, detail="untrusted origin")

    return require_trusted_origin


def gateway_guard(token: str | None) -> Callable[[Request], None]:
    """Only the local conversation gateway may post messages (ADR-0032).

    Disabled (404) unless a token is configured; requires `Authorization: Bearer`
    with that token (constant-time comparison); refuses browser requests (Origin).
    """
    expected = token.encode() if token else None

    def require_gateway(request: Request) -> None:
        if expected is None:
            raise HTTPException(status_code=404, detail="Not Found")
        if request.headers.get("origin") is not None:
            raise HTTPException(status_code=403, detail="browsers cannot post conversations")
        scheme, _, presented = request.headers.get("authorization", "").partition(" ")
        if scheme.lower() != "bearer" or not hmac.compare_digest(presented.encode(), expected):
            raise HTTPException(status_code=401, detail="gateway token required")

    return require_gateway


async def require_empty_body(request: Request) -> None:
    """Interactions take no parameters: the body must be empty or `{}`."""
    body = await request.body()
    if body.strip() not in (b"", b"{}"):
        raise HTTPException(status_code=400, detail="interactions take no body")
