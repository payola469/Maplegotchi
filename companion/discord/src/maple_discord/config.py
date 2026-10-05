"""Gateway settings from the environment (ADR-0032).

Secrets are read from files (systemd `LoadCredential=` puts them in
`$CREDENTIALS_DIRECTORY`), never from the repository: the Discord bot token and
the shared gateway token for Maple's local API. Maple's API must be loopback HTTP.
"""

from __future__ import annotations

import ipaddress
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit


class GatewayConfigError(ValueError):
    pass


def _secret(environ: Mapping[str, str], name: str) -> str:
    """A secret from `<NAME>_FILE` (a path, or a credential name), else `<NAME>`."""
    path = environ.get(f"{name}_FILE")
    if path:
        file = Path(path)
        if not file.is_absolute():
            credentials = environ.get("CREDENTIALS_DIRECTORY")
            if not credentials:
                raise GatewayConfigError(f"{name}_FILE is relative but no CREDENTIALS_DIRECTORY")
            file = Path(credentials) / path
        try:
            value = file.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise GatewayConfigError(f"cannot read {name}_FILE: {exc}") from exc
    else:
        value = environ.get(name, "").strip()
    if not value:
        raise GatewayConfigError(f"{name} (or {name}_FILE) is required")
    return value


def _int(environ: Mapping[str, str], name: str) -> int:
    raw = environ.get(name, "")
    if not raw.isdigit():
        raise GatewayConfigError(f"{name} must be a Discord id (digits)")
    return int(raw)


def _loopback_http(url: str) -> str:
    parts = urlsplit(url)
    host = parts.hostname or ""
    try:
        loopback = host == "localhost" or ipaddress.ip_address(host).is_loopback
    except ValueError:
        loopback = False
    if parts.scheme != "http" or not loopback:
        raise GatewayConfigError("MAPLE_API_URL must be http on a loopback address")
    return url.rstrip("/")


@dataclass(frozen=True)
class GatewaySettings:
    bot_token: str = field(repr=False)
    gateway_token: str = field(repr=False)
    guild_id: int
    channel_id: int  # the #maple-chat channel
    owner_id: int  # Paolo's Discord user id: only his messages are conversations
    maple_api_url: str = "http://127.0.0.1:8470"
    timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        if len(self.gateway_token) < 32:
            raise GatewayConfigError("the gateway token must be at least 32 characters")


def settings_from_env(environ: Mapping[str, str]) -> GatewaySettings:
    return GatewaySettings(
        bot_token=_secret(environ, "DISCORD_BOT_TOKEN"),
        gateway_token=_secret(environ, "MAPLE_GATEWAY_TOKEN"),
        guild_id=_int(environ, "MAPLE_DISCORD_GUILD_ID"),
        channel_id=_int(environ, "MAPLE_DISCORD_CHANNEL_ID"),
        owner_id=_int(environ, "MAPLE_DISCORD_OWNER_ID"),
        maple_api_url=_loopback_http(environ.get("MAPLE_API_URL", "http://127.0.0.1:8470")),
    )
