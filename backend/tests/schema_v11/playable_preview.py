"""Explicit localhost-only synthetic playable preview, outside shipped startup.

Run from backend: PYTHONPATH=src python -m tests.schema_v11.playable_preview
Temporary mode owns a fresh execution root. Explicit alpha mode reopens only
its initialized private development session; it never adopts foreign databases.
Runtime processes exit before the next starts. Alpha data survives controller exit.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import signal
import subprocess  # noqa: TID251 -- explicit owned preview children only
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread
from types import FrameType
from typing import Any, cast

from tests.schema_v11 import owned_store as store
from tests.schema_v11.alpha_files import AlphaFiles
from tests.schema_v11.test_restart_process import worker_interpreter


class Preview:
    def __init__(self, alpha: Path | None = None, *, initialize: bool = False) -> None:
        self.scope: store.OwnedRoot | AlphaFiles
        if alpha is None:
            if initialize:
                raise ValueError("initialize requires an explicit alpha root")
            self.scope = store.OwnedRoot.new()
        else:
            self.scope = AlphaFiles.initialize(alpha) if initialize else AlphaFiles(alpha)
            self.scope.lock()
        self.state: dict[str, Any] = {}
        self.paused = True
        self.stopping = False
        self.error: str | None = None
        self.restarts = 0
        self.previous_pid: int | None = None
        try:
            self.command("init" if alpha is None or initialize else "read")
            if initialize and isinstance(self.scope, AlphaFiles):
                self.scope.seal()
        except BaseException:
            if isinstance(self.scope, AlphaFiles):
                self.scope.close()
            else:
                self.scope.cleanup()
            raise

    def command(self, operation: str) -> dict[str, Any]:
        if operation not in {"init", "tick", "next", "read"}:
            raise ValueError("unknown preview operation")
        self.scope._root()
        executable, env = worker_interpreter()
        argv = [
            executable,
            "-B",
            "-m",
            "tests.schema_v11.playable_worker",
            operation,
            str(self.scope.path),
            str(self.scope.identity[0]),
            str(self.scope.identity[1]),
            str(
                self.state.get(
                    "digest",
                    "restore"
                    if isinstance(self.scope, AlphaFiles) and operation == "read"
                    else "new",
                )
            ),
        ]
        if isinstance(self.scope, AlphaFiles):
            if self.scope.fd is None:
                raise ValueError("alpha controller lock required")
            argv.extend([str(os.getpid()), self.scope.token, str(self.scope.fd)])
        process = subprocess.Popen(  # noqa: S603 -- fixed child module + owned capability
            argv,
            cwd=Path(__file__).parents[2],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            pass_fds=(self.scope.fd,)
            if isinstance(self.scope, AlphaFiles) and self.scope.fd is not None
            else (),
        )
        chunks: list[bytes] = []

        def drain() -> None:
            assert process.stdout is not None
            data = process.stdout.read(131073)
            chunks.append(data[:131072])
            if len(data) > 131072:
                process.kill()
            process.stdout.close()

        thread = Thread(target=drain, daemon=True)
        thread.start()
        try:
            code = process.wait(timeout=60)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
            raise ValueError("preview child timed out") from None
        except BaseException:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=10)
            raise
        finally:
            thread.join(timeout=10)
        if code or thread.is_alive():
            raise ValueError("preview worker refused; no automatic retry")
        result = json.loads(b"".join(chunks))
        if not isinstance(result, dict) or result.get("pid") != process.pid:
            raise ValueError("actual worker identity required")
        if operation == "read" and self.state and result.get("digest") != self.state.get("digest"):
            raise ValueError("restart changed canonical state")
        self.previous_pid = self.state.get("pid")
        self.state = result
        return self.view()

    def act(self, operation: str) -> dict[str, Any]:
        if operation == "shutdown":
            if not isinstance(self.scope, AlphaFiles):
                raise ValueError("shutdown is alpha-only")
            self.paused = True
            self.stopping = True
        elif operation == "pause":
            self.paused = True
        elif operation == "play":
            if self.error:
                raise ValueError("preview stopped after failure")
            self.paused = False
        else:
            if self.error:
                raise ValueError("preview stopped after failure; retain owned artifacts")
            if operation == "restart":
                self.paused = True
            if operation == "next" and self.state.get("moving"):
                raise ValueError("finish ordinary movement first")
            try:
                self.command("read" if operation == "restart" else operation)
                if operation == "restart":
                    self.restarts += 1
            except (ValueError, OSError):
                self.paused = True
                self.error = "Runtime stopped; owned state retained. No automatic retry/reset."
                raise
        return self.view()

    def view(self) -> dict[str, Any]:
        return dict(
            self.state,
            paused=self.paused,
            error=self.error,
            restarts=self.restarts,
            previous_pid=self.previous_pid,
            controller_pid=os.getpid(),
            database_identity=list(self.scope.check("maple.db").stat()[i] for i in (2, 1)),
            session=self.scope.metadata["session"] if isinstance(self.scope, AlphaFiles) else None,
        )

    def close(self) -> None:
        if isinstance(self.scope, AlphaFiles):
            self.scope.close()
        elif not self.error:
            self.scope.cleanup()


def handler(preview: Preview, assets: Path, pixi: Path, token: str) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def reply(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; script-src 'self' "
                "'unsafe-eval'; style-src 'self'; connect-src 'self'; "
                "frame-ancestors 'none'; object-src 'none'",
            )
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def admitted(self, *, mutation: bool = False) -> bool:
            host = f"127.0.0.1:{cast(HTTPServer, self.server).server_port}"
            if self.headers.get("Host") != host:
                return False
            if mutation and (
                self.headers.get("Origin") != f"http://{host}"
                or not secrets.compare_digest(self.headers.get("X-Preview-Token", ""), token)
                or self.headers.get("Content-Length", "0") != "0"
                or self.headers.get("Transfer-Encoding") is not None
            ):
                return False
            return True

        def do_GET(self) -> None:
            if not self.admitted():
                self.reply(403, b"Forbidden", "text/plain")
                return
            if self.path == "/state":
                self.reply(200, json.dumps(preview.view()).encode(), "application/json")
            elif self.path == "/":
                body = (assets / "index.html").read_text(encoding="utf-8").replace("TOKEN", token)
                self.reply(200, body.encode(), "text/html; charset=utf-8")
            elif self.path in {"/preview.js", "/preview.css", "/pixi.min.js"}:
                path = pixi if self.path == "/pixi.min.js" else assets / self.path[1:]
                kind = "text/css" if self.path.endswith(".css") else "text/javascript"
                self.reply(200, path.read_bytes(), kind)
            else:
                self.reply(404, b"Not found", "text/plain")

        def do_POST(self) -> None:
            if not self.admitted(mutation=True):
                self.reply(403, b"Forbidden", "text/plain")
                return
            operation = self.path[1:]
            if operation not in {"play", "pause", "tick", "next", "restart", "shutdown"}:
                self.reply(404, b"Not found", "text/plain")
                return
            try:
                state = preview.act(operation)
                self.reply(200, json.dumps(state).encode(), "application/json")
            except (ValueError, OSError):
                self.reply(409, json.dumps(preview.view()).encode(), "application/json")

        def log_message(self, format: str, *args: object) -> None:
            pass

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8473)
    parser.add_argument("--alpha-root", type=Path)
    parser.add_argument("--initialize", action="store_true")
    args = parser.parse_args()

    def stop(_number: int, _frame: FrameType | None) -> None:
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop)
    root = Path(__file__).parents[3]
    assets = root / "frontend/tools/life-preview"
    pixi = root / "frontend/node_modules/pixi.js/dist/pixi.min.js"
    if not pixi.is_file():
        parser.error("Install existing frontend dependencies with pnpm install --frozen-lockfile")
    preview = Preview(args.alpha_root, initialize=args.initialize)
    try:
        server = HTTPServer(
            ("127.0.0.1", args.port), handler(preview, assets, pixi, secrets.token_urlsafe(32))
        )
    except BaseException:
        preview.close()
        raise
    server.timeout = 0.2
    print(f"ISOLATED PREVIEW http://127.0.0.1:{server.server_port} — synthetic only", flush=True)
    print(
        "Each tick saves and exits its worker. "
        + (
            "Ctrl+C stops the controller; alpha state is retained."
            if args.alpha_root
            else "Ctrl+C ends the temporary session."
        ),
        flush=True,
    )
    next_tick = time.monotonic() + 1
    try:
        while not preview.stopping:
            server.handle_request()
            if not preview.paused and time.monotonic() >= next_tick:
                try:
                    preview.act("tick")
                except (ValueError, OSError):
                    pass
                next_tick = time.monotonic() + 1
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        preview.close()


if __name__ == "__main__":
    main()
