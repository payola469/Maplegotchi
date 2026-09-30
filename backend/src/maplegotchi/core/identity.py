"""Maple's identity. Identity is data owned by Maple, never by a code module or Brain."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from maplegotchi.core.daytime import require_utc

MAX_NAME_LENGTH = 32


@dataclass(frozen=True, slots=True)
class Identity:
    name: str
    born_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("name must be a non-empty string")
        if self.name != self.name.strip() or len(self.name) > MAX_NAME_LENGTH:
            raise ValueError(f"name must be trimmed and at most {MAX_NAME_LENGTH} characters")
        if not self.name.isprintable():
            raise ValueError("name must be printable")
        require_utc(self.born_at, "born_at")
