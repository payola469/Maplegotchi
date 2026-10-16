"""Explicit persistent synthetic development ownership, separate from OwnedRoot.

Linux local alpha only. Initialization is exclusive; reopen requires the exact
private root/database identity and a single controller lock. This is not an
admission path for old test roots, user databases, production or shipped startup.
SQL/schema/revision/codec checks stay in the existing writer and loader.
"""

from __future__ import annotations

import json
import os
import secrets
import stat
import sys
from pathlib import Path
from typing import Any

from tests.schema_v11.owned_store import SIDECARS, StoreError


def _private(path: Path, *, directory: bool = False) -> os.stat_result:
    if sys.platform == "linux":
        info = path.lstat()
        kind = stat.S_ISDIR if directory else stat.S_ISREG
        if (
            path.is_symlink()
            or not kind(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != (0o700 if directory else 0o600)
            or (not directory and info.st_nlink != 1)
        ):
            raise StoreError("ownership")
        return info
    else:
        raise StoreError("policy")


def _read(path: Path) -> dict[str, Any]:
    info = _private(path)
    if info.st_size > 8192:
        raise StoreError("ownership")
    value = json.loads(path.read_text(encoding="utf-8"))
    if type(value) is not dict:
        raise StoreError("ownership")
    return value


def _write(path: Path, value: dict[str, Any], *, exclusive: bool = False) -> None:
    if sys.platform == "linux":
        flags = os.O_WRONLY | os.O_NOFOLLOW | (os.O_CREAT | os.O_EXCL if exclusive else os.O_TRUNC)
        fd = os.open(path, flags, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(value, output, sort_keys=True)
            output.flush()
            os.fsync(output.fileno())
    else:
        raise StoreError("policy")


class AlphaFiles:
    path: Path
    identity: tuple[int, int]
    metadata: dict[str, Any]
    fd: int | None
    token: str
    admitted: bool

    def __init__(self, path: Path, *, pending: bool = False) -> None:
        if sys.platform == "linux":
            self.path = path.absolute()
            if self.path != self.path.resolve():
                raise StoreError("ownership")
            info = _private(self.path, directory=True)
            self.identity = (info.st_dev, info.st_ino)
            self.metadata = _read(self.path / "alpha.json")
            if (
                set(self.metadata) != {"format", "session", "root", "path", "uid", "database"}
                or self.metadata["format"] != "maple-synthetic-local-alpha-v1"
                or type(self.metadata["session"]) is not str
                or len(self.metadata["session"]) != 64
                or self.metadata["root"] != list(self.identity)
                or self.metadata["path"] != str(self.path)
                or self.metadata["uid"] != os.getuid()
                or (self.metadata["database"] is None and not pending)
            ):
                raise StoreError("ownership")
            self.fd: int | None = None
            self.token = ""
            self.admitted = False
            self._root()
        else:
            raise StoreError("policy")

    @classmethod
    def initialize(cls, path: Path) -> AlphaFiles:
        if sys.platform == "linux":
            path = path.absolute()
            if path != path.resolve():
                raise StoreError("ownership")
            path.mkdir(mode=0o700)  # Never adopt/overwrite any existing directory.
            info = _private(path, directory=True)
            _write(
                path / "alpha.json",
                dict(
                    format="maple-synthetic-local-alpha-v1",
                    session=secrets.token_hex(32),
                    root=[info.st_dev, info.st_ino],
                    path=str(path),
                    uid=os.getuid(),
                    database=None,
                ),
                exclusive=True,
            )
            _write(path / "ownership.json", {}, exclusive=True)
            _write(path / "controller.lock", {}, exclusive=True)
            return cls(path, pending=True)
        else:
            raise StoreError("policy")

    def _root(self) -> None:
        info = _private(self.path, directory=True)
        if (
            (info.st_dev, info.st_ino) != self.identity
            or self.path != self.path.resolve()
            or _read(self.path / "alpha.json") != self.metadata
        ):
            raise StoreError("ownership")
        allowed = {"alpha.json", "ownership.json", "controller.lock"}
        allowed.update("maple.db" + suffix for suffix in SIDECARS)
        if any(item.name not in allowed for item in self.path.iterdir()):
            raise StoreError("ownership")
        _private(self.path / "controller.lock")
        _read(self.path / "ownership.json")

    def lock(self) -> None:
        if sys.platform == "linux":
            import fcntl

            self._root()
            fd = os.open(self.path / "controller.lock", os.O_RDWR | os.O_NOFOLLOW)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                os.close(fd)
                raise StoreError("ownership") from None
            self.fd = fd
            self.token = secrets.token_hex(32)
            os.ftruncate(fd, 0)
            os.write(fd, json.dumps(dict(pid=os.getpid(), token=self.token)).encode())
            os.fsync(fd)
            self.admitted = True
        else:
            raise StoreError("policy")

    def worker(self, *, parent: int, token: str, inherited_lock: int) -> None:
        if sys.platform == "linux":
            import fcntl

            self._root()
            held = os.fstat(inherited_lock)
            expected_lock = _private(self.path / "controller.lock")
            if (held.st_dev, held.st_ino) != (expected_lock.st_dev, expected_lock.st_ino):
                raise StoreError("ownership")
            if os.getppid() != parent or _read(self.path / "controller.lock") != dict(
                pid=parent, token=token
            ):
                raise StoreError("ownership")
            fd = os.open(self.path / "controller.lock", os.O_RDWR | os.O_NOFOLLOW)
            try:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    self.admitted = True
                    return  # Actual parent still holds the exclusive controller lock.
                raise StoreError("ownership")
            finally:
                os.close(fd)
        else:
            raise StoreError("policy")

    def reserve(self, name: str) -> Path:
        if sys.platform == "linux":
            if not self.admitted:
                raise StoreError("ownership")
            self._root()
            registry = _read(self.path / "ownership.json")
            if name != "maple.db" or self.metadata["database"] is not None or registry:
                raise StoreError("ownership")
            path = self.path / name
            if any((self.path / (name + suffix)).exists() for suffix in SIDECARS):
                raise StoreError("ownership")
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
            info = os.fstat(fd)
            os.close(fd)
            _write(self.path / "ownership.json", {name: [info.st_dev, info.st_ino]})
            return self.check(name)
        else:
            raise StoreError("policy")

    def check(self, name: str) -> Path:
        if not self.admitted:
            raise StoreError("ownership")
        self._root()
        registry = _read(self.path / "ownership.json")
        if name != "maple.db" or set(registry) != {name}:
            raise StoreError("ownership")
        path = self.path / name
        info = _private(path)
        identity = [info.st_dev, info.st_ino]
        if registry[name] != identity or self.metadata["database"] not in (None, identity):
            raise StoreError("ownership")
        for suffix in SIDECARS[1:]:
            item = self.path / (name + suffix)
            if item.exists() or item.is_symlink():
                _private(item)
        return path

    def seal(self) -> None:
        if sys.platform == "linux":
            self.check("maple.db")
            metadata = dict(self.metadata, database=_read(self.path / "ownership.json")["maple.db"])
            temporary = self.path / "alpha.pending"
            _write(temporary, metadata, exclusive=True)
            temporary.replace(self.path / "alpha.json")
            fd = os.open(self.path, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
            self.metadata = metadata
        else:
            raise StoreError("policy")

    def close(self) -> None:
        self.admitted = False
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
