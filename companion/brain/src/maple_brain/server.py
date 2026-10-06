"""The loopback HTTP service (ADR-0033): /generate, /decide, /reply, /health.

Standard library only. JSON in, JSON out, bodies capped, one provider call at a time
per endpoint, and every failure is an explicit "no answer" that Maple falls back from.
"""

from __future__ import annotations

import json
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from maple_brain.config import BrainSettings
from maple_brain.prompts import decide_prompt, first_json_object, reply_prompt
from maple_brain.provider import Provider, ProviderError

DECISION_CONTRACT = "maple.decision.v1"
REPLY_CONTRACT = "maple.reply.v1"
MAX_REPLY = 1500


class BrainService:
    """Request handling, independent of the HTTP plumbing (tested directly)."""

    def __init__(self, settings: BrainSettings, provider: Provider) -> None:
        self.settings = settings
        self.provider = provider
        self._locks = {name: threading.Lock() for name in ("generate", "decide", "reply")}

    def _ask(self, endpoint: str, prompt: str) -> str | None:
        lock = self._locks[endpoint]
        if not lock.acquire(timeout=self.settings.timeouts[endpoint]):
            raise ProviderError("busy")
        try:
            return self.provider(prompt, self.settings.timeouts[endpoint])
        finally:
            lock.release()

    def generate(self, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        prompt = body.get("prompt")
        if set(body) != {"prompt"} or not isinstance(prompt, str) or not prompt.strip():
            return HTTPStatus.BAD_REQUEST, {"error": "expected {prompt}"}
        try:
            answer = self._ask("generate", prompt)
        except ProviderError as exc:
            return HTTPStatus.SERVICE_UNAVAILABLE, {"error": str(exc)}
        return HTTPStatus.OK, {"response": answer or ""}

    def decide(self, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        context = body.get("context")
        if body.get("contract") != DECISION_CONTRACT or not isinstance(context, dict):
            return HTTPStatus.BAD_REQUEST, {"error": f"expected a {DECISION_CONTRACT} request"}
        try:
            answer = self._ask("decide", decide_prompt(context))
        except ProviderError as exc:
            return HTTPStatus.SERVICE_UNAVAILABLE, {"error": str(exc)}
        proposal = first_json_object(answer) if answer else None
        return HTTPStatus.OK, {"contract": DECISION_CONTRACT, "proposal": proposal}

    def reply(self, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        context = body.get("context")
        if body.get("contract") != REPLY_CONTRACT or not isinstance(context, dict):
            return HTTPStatus.BAD_REQUEST, {"error": f"expected a {REPLY_CONTRACT} request"}
        try:
            answer = self._ask("reply", reply_prompt(context))
        except ProviderError as exc:
            return HTTPStatus.SERVICE_UNAVAILABLE, {"error": str(exc)}
        if not answer:
            return HTTPStatus.SERVICE_UNAVAILABLE, {"error": "no reply"}
        return HTTPStatus.OK, {"contract": REPLY_CONTRACT, "reply": answer.strip()[:MAX_REPLY]}

    def health(self) -> dict[str, Any]:
        """Liveness plus the configured provider kind and model (ADR-0034 §1).

        Never the command argv, credentials, prompts, or answers.
        """
        return {
            "status": "ok",
            "provider": self.settings.provider.value,
            "model": self.settings.model or None,
        }


def make_handler(service: BrainService) -> type[BaseHTTPRequestHandler]:
    routes = {"/generate": service.generate, "/decide": service.decide, "/reply": service.reply}

    class Handler(BaseHTTPRequestHandler):
        server_version = "maple-brain"
        sys_version = ""

        def _send(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("content-type", "application/json; charset=utf-8")
            self.send_header("content-length", str(len(body)))
            self.send_header("cache-control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            if self.path == "/health":
                self._send(HTTPStatus.OK, service.health())
            else:
                self._send(HTTPStatus.NOT_FOUND, {"error": "not found"})

        def do_POST(self) -> None:
            route = routes.get(self.path)
            if route is None:
                self._send(HTTPStatus.NOT_FOUND, {"error": "not found"})
                return
            length = self.headers.get("content-length", "")
            if not length.isdigit() or int(length) > service.settings.max_body_bytes:
                self._send(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "body too large"})
                return
            try:
                body = json.loads(self.rfile.read(int(length)) or b"{}")
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._send(HTTPStatus.BAD_REQUEST, {"error": "invalid JSON"})
                return
            if not isinstance(body, dict):
                self._send(HTTPStatus.BAD_REQUEST, {"error": "expected a JSON object"})
                return
            status, payload = route(body)
            self._send(status, payload)

        def log_message(self, format: str, *args: Any) -> None:
            # Request lines only: never bodies, prompts, or answers.
            super().log_message(format, *args)

    return Handler


def serve(settings: BrainSettings, provider: Provider) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(
        (settings.host, settings.port), make_handler(BrainService(settings, provider))
    )
    server.daemon_threads = True
    return server
