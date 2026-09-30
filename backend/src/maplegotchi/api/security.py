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

from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any

from fastapi import HTTPException, Request

Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]

MAX_BODY_BYTES = 1024

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
            headers = {k.lower(): v for k, v in scope.get("headers", [])}
            length = headers.get(b"content-length")
            chunked = b"chunked" in headers.get(b"transfer-encoding", b"").lower()
            too_big = False
            if length is not None:
                try:
                    too_big = int(length) > self.max_bytes
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


async def require_empty_body(request: Request) -> None:
    """Interactions take no parameters: the body must be empty or `{}`."""
    body = await request.body()
    if body.strip() not in (b"", b"{}"):
        raise HTTPException(status_code=400, detail="interactions take no body")
