"""Runtime settings, loaded once at startup into a frozen object (CLAUDE.md §4.4).

Environment variables (all optional unless noted):
  MAPLE_DATA_DIR          Maple's writable data directory (required)
  MAPLE_MODE              development (default) | production
  MAPLE_BIND_HOST         loopback address to bind (default 127.0.0.1; D5/D13: never public)
  MAPLE_PORT              default 8470
  MAPLE_ALLOWED_ORIGINS   comma-separated origins allowed to POST Greet/Pet
                          (development default: the local Vite and API origins;
                          production: required, e.g. the tailnet https origin)
  MAPLE_STATIC_DIR        built frontend to serve at / (same origin as /api)
  MAPLE_SENSES            paolo_core (default) | fake
  MAPLE_MONITOR_DB        default /data/monitor/metrics.db (read-only, D11/D18)
  MAPLE_HEARTBEAT_SECONDS default 300 (D6)
"""

from __future__ import annotations

import ipaddress
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

DEFAULT_PORT = 8470
DEV_ORIGINS = (
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://127.0.0.1:8470",
    "http://localhost:8470",
)
_ORIGIN = re.compile(r"https?://[A-Za-z0-9.-]+(?::[0-9]{1,5})?")


class Mode(StrEnum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"


class SensesKind(StrEnum):
    PAOLO_CORE = "paolo_core"
    FAKE = "fake"


class SettingsError(ValueError):
    pass


def _is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    mode: Mode = Mode.DEVELOPMENT
    host: str = "127.0.0.1"
    port: int = DEFAULT_PORT
    allowed_origins: tuple[str, ...] = DEV_ORIGINS
    static_dir: Path | None = None
    senses: SensesKind = SensesKind.PAOLO_CORE
    monitor_db: Path = field(default=Path("/data/monitor/metrics.db"))
    heartbeat_seconds: int = 300
    loop_poll_seconds: float = 5.0

    def __post_init__(self) -> None:
        if not _is_loopback(self.host):
            raise SettingsError(f"bind host {self.host!r} is not loopback (D5: localhost only)")
        if not 1 <= self.port <= 65535:
            raise SettingsError("port must be 1..65535")
        for origin in self.allowed_origins:
            if not _ORIGIN.fullmatch(origin):
                raise SettingsError(
                    f"invalid origin {origin!r} (exact scheme://host[:port], no wildcards)"
                )
        if self.mode is Mode.PRODUCTION and not self.allowed_origins:
            raise SettingsError("production needs MAPLE_ALLOWED_ORIGINS")
        if self.heartbeat_seconds < 1 or self.loop_poll_seconds <= 0:
            raise SettingsError("heartbeat and poll intervals must be positive")

    @property
    def docs_enabled(self) -> bool:
        return self.mode is Mode.DEVELOPMENT


def settings_from_env(environ: Mapping[str, str]) -> Settings:
    try:
        data_dir = environ["MAPLE_DATA_DIR"]
    except KeyError as exc:
        raise SettingsError("MAPLE_DATA_DIR is required") from exc
    mode = Mode(environ.get("MAPLE_MODE", Mode.DEVELOPMENT))
    origins_raw = environ.get("MAPLE_ALLOWED_ORIGINS")
    origins: tuple[str, ...]
    if origins_raw is None:
        origins = DEV_ORIGINS if mode is Mode.DEVELOPMENT else ()
    else:
        origins = tuple(o.strip() for o in origins_raw.split(",") if o.strip())
    static = environ.get("MAPLE_STATIC_DIR")
    return Settings(
        data_dir=Path(data_dir),
        mode=mode,
        host=environ.get("MAPLE_BIND_HOST", "127.0.0.1"),
        port=int(environ.get("MAPLE_PORT", DEFAULT_PORT)),
        allowed_origins=origins,
        static_dir=Path(static) if static else None,
        senses=SensesKind(environ.get("MAPLE_SENSES", SensesKind.PAOLO_CORE)),
        monitor_db=Path(environ.get("MAPLE_MONITOR_DB", "/data/monitor/metrics.db")),
        heartbeat_seconds=int(environ.get("MAPLE_HEARTBEAT_SECONDS", 300)),
    )
