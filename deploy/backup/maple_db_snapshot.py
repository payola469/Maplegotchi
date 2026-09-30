#!/usr/bin/python3 -I
"""Stage a consistent copy of Maple's live SQLite database for the nightly backup.

Installed on paolo-core as /usr/local/sbin/maple-db-snapshot (root:root 0755) and
called by /usr/local/sbin/paolo-core-backup, which runs as root. Standard library
only; it never writes to Maple's database and never repairs anything.

    maple-db-snapshot stage --source /data/maple/maple.db --dest "$RUN_DIR/maple.db"
    maple-db-snapshot verify /path/to/restored/maple.db

`stage`:
  live maple.db --(SQLite online backup API, read-only source)--> <dest>.partial
  --> journal_mode=DELETE (self-contained single file, no -wal/-shm needed)
  --> PRAGMA integrity_check must return exactly "ok"
  --> Maplegotchi application_id and a migrated schema must be present
  --> chmod 0600, fsync, atomic rename to <dest>
Never copies the live file byte-wise (it is in WAL mode and changes under us).

Exit codes (the backup script decides what each means for the run):
  0  staged and verified
  3  Maple is not deployed on this host (the source database does not exist):
     nothing staged; the backup script skips Maple on purpose
  1  anything else: the database exists but cannot be opened, copied, or
     verified. Nothing is left at <dest>; the backup job must fail.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import os
import sqlite3
import sys
from collections.abc import Sequence
from pathlib import Path

APPLICATION_ID = 0x4D41504C  # "MAPL", maplegotchi.storage.migrations.APPLICATION_ID
EXIT_OK = 0
EXIT_FAILED = 1
EXIT_NOT_DEPLOYED = 3
BUSY_TIMEOUT_MS = 30_000


class SnapshotError(Exception):
    pass


def _open_read_only(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True, isolation_level=None)
    conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS:d}")
    conn.execute("PRAGMA query_only = ON")
    return conn


def check_database(conn: sqlite3.Connection) -> dict[str, object]:
    """Integrity, identity marker, schema version. Raises SnapshotError on any doubt."""
    rows = conn.execute("PRAGMA integrity_check").fetchall()
    if rows != [("ok",)]:
        raise SnapshotError(f"integrity_check returned {rows[:5]!r}")
    app_id = conn.execute("PRAGMA application_id").fetchone()[0]
    if app_id != APPLICATION_ID:
        raise SnapshotError(f"application_id {app_id:#x} is not a Maplegotchi database")
    version = int(conn.execute("PRAGMA user_version").fetchone()[0])
    if version < 1:
        raise SnapshotError("schema is not migrated (user_version 0)")
    row = conn.execute("SELECT name, born_at, life_seed FROM maple WHERE id = 1").fetchone()
    if row is None:
        raise SnapshotError("no Maple identity row")
    name, born_at, seed = row
    return {
        "integrity": "ok",
        "user_version": version,
        "journal_mode": conn.execute("PRAGMA journal_mode").fetchone()[0],
        "name": name,
        "born_at": born_at,
        # A fingerprint lets the owner compare identities without printing the seed.
        "life_seed_sha256_16": hashlib.sha256(str(seed).encode()).hexdigest()[:16],
    }


def _fsync_path(path: Path, *, directory: bool = False) -> None:
    if directory and os.name != "posix":  # production is Linux; tests also run on Windows
        return
    fd = os.open(path, (os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)) if directory else os.O_RDWR)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def stage(source: Path, dest: Path) -> dict[str, object]:
    if not source.is_absolute() or not dest.is_absolute():
        raise SnapshotError("source and dest must be absolute paths")
    if not dest.parent.is_dir():
        raise SnapshotError(f"destination directory {dest.parent} does not exist")
    if dest.exists() or dest.is_symlink():
        raise SnapshotError(f"{dest} already exists")
    if not source.is_file():
        raise SnapshotError(f"{source} is not a regular file")

    partial = dest.with_name(dest.name + ".partial")
    # Created empty and private first (an empty file is a valid empty database).
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(partial, flags, 0o600)
    os.close(fd)
    try:
        src = _open_read_only(source)
        try:
            dst = sqlite3.connect(partial, isolation_level=None)
            try:
                src.backup(dst)  # one consistent snapshot, even while Maple writes
                mode = dst.execute("PRAGMA journal_mode = DELETE").fetchone()[0]
                if str(mode).lower() != "delete":
                    raise SnapshotError(f"could not switch the copy to DELETE mode ({mode})")
                summary = check_database(dst)
            finally:
                dst.close()
        finally:
            src.close()
        for side in ("-journal", "-wal", "-shm"):
            if partial.with_name(partial.name + side).exists():
                raise SnapshotError(f"the staged copy left a {side} file behind")
        partial.chmod(0o600)
        _fsync_path(partial)
        partial.replace(dest)
        _fsync_path(dest.parent, directory=True)
    except BaseException:
        for leftover in (partial, *(partial.with_name(partial.name + s) for s in ("-journal",))):
            with contextlib.suppress(FileNotFoundError):
                leftover.unlink()
        raise
    summary["bytes"] = dest.stat().st_size
    summary["path"] = str(dest)
    return summary


def verify(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise SnapshotError(f"{path} does not exist")
    conn = _open_read_only(path)
    try:
        return check_database(conn)
    finally:
        conn.close()


def _print(prefix: str, summary: dict[str, object]) -> None:
    fields = " ".join(f"{k}={v}" for k, v in summary.items())
    print(f"maple-db-snapshot: {prefix} {fields}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="maple-db-snapshot")
    sub = parser.add_subparsers(dest="command", required=True)
    st = sub.add_parser("stage", help="stage a verified copy of the live database")
    st.add_argument("--source", type=Path, required=True)
    st.add_argument("--dest", type=Path, required=True)
    vf = sub.add_parser("verify", help="integrity-check a staged or restored copy (read-only)")
    vf.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "stage":
            source: Path = args.source
            if not source.exists() and not source.is_symlink():
                print(f"maple-db-snapshot: {source} absent; Maple is not deployed, skipping")
                return EXIT_NOT_DEPLOYED
            _print("staged", stage(source, args.dest))
        else:
            _print("verified", verify(args.path))
    except (SnapshotError, sqlite3.Error, OSError) as exc:
        print(f"maple-db-snapshot: FAILED: {exc}", file=sys.stderr)
        return EXIT_FAILED
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
