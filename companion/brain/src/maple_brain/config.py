"""Companion settings from the environment (ADR-0033). No secrets live here."""

from __future__ import annotations

import ipaddress
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum


class BrainConfigError(ValueError):
    pass


class ProviderKind(StrEnum):
    COMMAND = "command"  # run MAPLE_BRAIN_COMMAND (e.g. the Antigravity CLI)
    NONE = "none"  # answer "no proposal": Maple uses its rule fallbacks


# Flags that would let a provider CLI act without asking: never allowed (ADR-0033 §2).
DANGEROUS_FLAGS = (
    "--yolo",
    "--dangerously-skip-permissions",
    "--dangerously-bypass-approvals-and-sandbox",
    "--approval-mode=yolo",
    "--auto-approve",
    "--allow-all-tools",
    "--full-auto",
    "--trust-all-tools",
)


def _command(raw: str) -> tuple[str, ...]:
    try:
        argv = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise BrainConfigError("MAPLE_BRAIN_COMMAND must be a JSON array of strings") from exc
    if not isinstance(argv, list) or not argv or not all(isinstance(a, str) and a for a in argv):
        raise BrainConfigError("MAPLE_BRAIN_COMMAND must be a non-empty JSON array of strings")
    if not argv[0].startswith("/"):
        raise BrainConfigError("MAPLE_BRAIN_COMMAND[0] must be an absolute path")
    lowered = [a.lower() for a in argv]
    for flag in DANGEROUS_FLAGS:
        if any(a == flag or a.startswith(flag + "=") for a in lowered):
            raise BrainConfigError(f"refusing an auto-approve flag in MAPLE_BRAIN_COMMAND: {flag}")
    if any(a in ("-y", "--approval-mode") for a in lowered):
        raise BrainConfigError("refusing an approval-mode switch in MAPLE_BRAIN_COMMAND")
    return tuple(argv)


@dataclass(frozen=True)
class BrainSettings:
    host: str = "127.0.0.1"
    port: int = 8471
    provider: ProviderKind = ProviderKind.NONE
    command: tuple[str, ...] = ()
    model: str = ""
    timeouts: Mapping[str, float] = field(
        default_factory=lambda: {"generate": 25.0, "decide": 12.0, "reply": 12.0}
    )
    max_body_bytes: int = 64 * 1024
    max_output_bytes: int = 32 * 1024

    def __post_init__(self) -> None:
        try:
            loopback = ipaddress.ip_address(self.host).is_loopback
        except ValueError:
            loopback = False
        if not loopback:
            raise BrainConfigError("the companion listens on a loopback address only")
        if not 0 <= self.port <= 65535:  # 0 = an ephemeral port (tests)
            raise BrainConfigError("port must be 0..65535")
        if self.provider is ProviderKind.COMMAND and not self.command:
            raise BrainConfigError("MAPLE_BRAIN_PROVIDER=command needs MAPLE_BRAIN_COMMAND")


def settings_from_env(environ: Mapping[str, str]) -> BrainSettings:
    provider = ProviderKind(environ.get("MAPLE_BRAIN_PROVIDER", ProviderKind.NONE))
    raw_command = environ.get("MAPLE_BRAIN_COMMAND", "")
    timeouts = {
        name: float(environ.get(f"MAPLE_BRAIN_{name.upper()}_TIMEOUT_SECONDS", default))
        for name, default in (("generate", 25.0), ("decide", 12.0), ("reply", 12.0))
    }
    for name, value in timeouts.items():
        if not 1.0 <= value <= 60.0:
            raise BrainConfigError(f"{name} timeout must be within 1-60 seconds")
    return BrainSettings(
        host=environ.get("MAPLE_BRAIN_HOST", "127.0.0.1"),
        port=int(environ.get("MAPLE_BRAIN_PORT", 8471)),
        provider=provider,
        command=_command(raw_command) if raw_command else (),
        model=environ.get("MAPLE_BRAIN_MODEL", ""),
        timeouts=timeouts,
    )
