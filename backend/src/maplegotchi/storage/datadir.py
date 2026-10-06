"""The writable-data boundary: every Maple-owned write resolves inside MAPLE_DATA_DIR.

This is the in-process layer of CLAUDE.md §4.4. It complements, and does not
replace, the systemd sandbox (ReadWritePaths=/data/maple) added in Phase 7.

Names are relative paths chosen by code, so the accepted syntax is deliberately
narrow: components of [A-Za-z0-9._-], no dot components, no Windows device
names, no separators other than "/". After syntax checks the path is resolved
(following symlinks and junctions) and must still lie strictly inside the root.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from maplegotchi.storage.errors import UnsafePathError

_COMPONENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
_MAX_NAME_LENGTH = 200
_WINDOWS_DEVICE_NAMES = frozenset(
    {"con", "prn", "aux", "nul"} | {f"com{i}" for i in range(10)} | {f"lpt{i}" for i in range(10)}
)


def _check_syntax(name: str) -> tuple[str, ...]:
    if not isinstance(name, str):
        raise UnsafePathError("path must be a string")
    if not name or len(name) > _MAX_NAME_LENGTH:
        raise UnsafePathError("path must be 1-200 characters")
    parts = tuple(name.split("/"))
    for part in parts:
        if part in ("", ".", ".."):
            raise UnsafePathError(f"empty or dot path component in {name!r}")
        if not _COMPONENT.fullmatch(part):
            raise UnsafePathError(f"disallowed characters in path component {part!r}")
        if part.endswith("."):
            raise UnsafePathError(f"path component may not end with '.': {part!r}")
        if part.split(".", 1)[0].lower() in _WINDOWS_DEVICE_NAMES:
            raise UnsafePathError(f"reserved device name: {part!r}")
    return parts


class DataDir:
    """A resolved, existing directory that Maple may write inside."""

    __slots__ = ("_root",)

    def __init__(self, root: Path) -> None:
        if not root.is_absolute():
            raise UnsafePathError("data directory must be an absolute path")
        try:
            resolved = root.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise UnsafePathError(f"data directory is not usable: {exc}") from exc
        if not resolved.is_dir():
            raise UnsafePathError("data directory must be an existing directory")
        self._root = resolved

    @property
    def root(self) -> Path:
        return self._root

    def path(self, name: str) -> Path:
        """Validated absolute path for `name` inside the data directory."""
        parts = _check_syntax(name)
        candidate = self._root.joinpath(*parts)
        try:
            resolved = candidate.resolve(strict=False)  # follows existing symlinks/junctions
        except (OSError, RuntimeError) as exc:  # e.g. symlink loops
            raise UnsafePathError(f"cannot resolve {name!r}: {exc}") from exc
        if resolved == self._root or not resolved.is_relative_to(self._root):
            raise UnsafePathError(f"{name!r} resolves outside the data directory")
        return resolved

    def exists(self, name: str) -> bool:
        return self.path(name).exists()

    def remove(self, name: str) -> None:
        """Remove a file inside the data directory if present."""
        target = self.path(name)
        if target.is_dir():
            raise UnsafePathError(f"refusing to remove directory {name!r}")
        target.unlink(missing_ok=True)

    def publish(self, source: str, destination: str) -> None:
        """Make `source` visible as `destination` without ever replacing an existing file.

        Uses a hard link, which fails if `destination` exists, then removes the
        source name. Raises FileExistsError if `destination` already exists.
        """
        src = self.path(source)
        dst = self.path(destination)
        os.link(src, dst)
        src.unlink()

    def make_dir(self, name: str) -> Path:
        """Create (if needed) a directory inside the data directory; returns its path."""
        target = self.path(name)
        target.mkdir(mode=0o700, exist_ok=True)
        resolved = target.resolve(strict=True)
        if not resolved.is_dir() or not resolved.is_relative_to(self._root):
            raise UnsafePathError(f"{name!r} is not a directory inside the data directory")
        return resolved

    def names_with_prefix(self, prefix: str) -> list[str]:
        """Top-level file names in the data directory starting with `prefix`."""
        _check_syntax(prefix)
        return sorted(p.name for p in self._root.iterdir() if p.name.startswith(prefix))
