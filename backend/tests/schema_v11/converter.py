"""Unshipped STEP230 forward-only converter, explicit registered fresh handles.

Retained source is never a conversion target. Two independently verified SQLite
backups precede a disposable descendant's one transaction. Public v11 load still
requires11; the internal precommit proof uses capture/validate without relaxing
any version gate. No paths, normal startup, historical migrations or repair.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from maplegotchi.storage.repositories import LifeRepository
from tests.schema_v11 import owned_store as store
from tests.schema_v11.conversion_fixture import ConversionError, Source, admit_v10, guarded, opened
from tests.schema_v11.conversion_mapping import mapped
from tests.schema_v11.declarations import V10_TABLES, target_tables

Inject = Callable[[str], None]


@dataclass(frozen=True)
class Result:
    scope: store.OwnedRoot
    source: store.Snapshot
    target: store.Snapshot
    copies: tuple[str, str] = ("owner.db", "automatic.db")


def copy_verified(
    scope: store.OwnedRoot, source: str, destination: str, expected: store.Snapshot, inject: Inject
) -> None:
    """SQLite online backup, standalone FULL-synchronous copy, independent load."""
    scope.reserve(destination)
    with opened(scope, source) as src, opened(scope, destination, readonly=False) as dst:
        src.backup(dst, pages=128)
        if dst.execute("PRAGMA journal_mode=DELETE").fetchone() != ("delete",):
            raise ConversionError("copy")
    path = scope.check(destination)
    with path.open("rb") as stream:
        os.fsync(stream.fileno())
    inject(f"verify_{destination}")
    with opened(scope, destination) as verified:
        if store.exact(admit_v10(verified)) != store.exact(expected):
            raise ConversionError("copy")


def convert(
    handle: Source,
    at: datetime,
    *,
    inject: Inject = lambda phase: None,
    commit_progress: Callable[[], int] | None = None,
) -> Result:
    owned = guarded(handle)  # Must precede compatibility probe or file opening.
    if owned.attempted:
        raise ConversionError("repeat")
    owned.attempted = True  # Even uncertainty/failed attempts require a fresh fixture.
    commit_started = False
    try:
        store.compatibility()
        scope = owned.scope
        allowed = {
            "ownership.json",
            "source.db",
            "source.db-wal",
            "source.db-shm",
            "source.db-journal",
        }
        if set(scope._registry()) != {"source.db"} or any(
            entry.name not in allowed for entry in scope.path.iterdir()
        ):
            raise ConversionError("ownership")
        with opened(scope, "source.db") as source:
            source.execute("BEGIN")
            try:
                before = admit_v10(source)
                if store.exact(before) != store.exact(owned.baseline):
                    raise ConversionError("source_changed")
                target, catalogs, contexts = mapped(before, LifeRepository(source).load().state, at)
            finally:
                source.execute("ROLLBACK")
        inject("after_preflight")
        for name in ("owner.db", "automatic.db"):
            inject(f"copy_{name}")
            copy_verified(scope, "source.db", name, before, inject)
        copy_verified(scope, "source.db", "target.db", before, inject)
        inject("after_copies")
        # Recheck immutable source after copies and under target writer ownership.
        with opened(scope, "source.db") as src:
            if store.exact(admit_v10(src)) != store.exact(before):
                raise ConversionError("source_changed")
        # Fence the retained source against concurrent writers through target COMMIT.
        # This transaction only holds ownership; it never changes source rows/version.
        with opened(scope, "source.db", readonly=False) as fence:
            fence.execute("BEGIN IMMEDIATE")
            try:
                if store.exact(admit_v10(fence)) != store.exact(before):
                    raise ConversionError("source_changed")
                with opened(scope, "target.db", readonly=False) as conn:
                    if conn.execute("PRAGMA journal_mode=WAL").fetchone() != ("wal",):
                        raise ConversionError("policy")
                    original = conn.execute("PRAGMA foreign_keys").fetchone()[0]
                    conn.execute("PRAGMA foreign_keys=OFF")  # SQLite requires outside BEGIN.
                    if conn.execute("PRAGMA foreign_keys").fetchone() != (0,):
                        raise ConversionError("policy")
                    try:
                        conn.execute("BEGIN IMMEDIATE")
                        if store.exact(admit_v10(conn)) != store.exact(before):
                            raise ConversionError("source_changed")
                        with opened(scope, "source.db") as src:
                            if store.exact(admit_v10(src)) != store.exact(before):
                                raise ConversionError("source_changed")
                        inject("after_begin")
                        for number, (name, sql) in enumerate(target_tables().items()):
                            if name not in V10_TABLES:
                                conn.execute(sql)
                                if number == 0 or name == "activity_kind":
                                    inject("partial_ddl")
                        # Frozen final DDL verbatim; no rename-normalized schema or new format.
                        for name in ("life_state", "journal_entry", "decision"):
                            conn.execute(f'DROP TABLE "{name}"')
                            conn.execute(target_tables()[name])
                        existing = {
                            r[0].strip().rstrip(";")
                            for r in conn.execute(
                                "SELECT sql FROM sqlite_schema WHERE sql IS NOT NULL "
                                "AND name <> 'sqlite_sequence'"
                            )
                        }
                        for sql in store.declarations():
                            if sql.strip().rstrip(";") not in existing:
                                conn.execute(sql)
                        for table in target.tables:
                            if table.name not in V10_TABLES or table.name in {
                                "life_state",
                                "journal_entry",
                                "decision",
                            }:
                                store._insert(conn, table)
                                inject("row_copy")
                        inject("after_rows")
                        conn.execute("DELETE FROM sqlite_sequence")
                        conn.executemany(
                            "INSERT INTO sqlite_sequence(name,seq) VALUES (?,?)", before.sequences
                        )
                        inject("sequence")
                        store._schema(conn)
                        store._integrity(conn)
                        actual = store.capture(conn)
                        store.validate(actual, catalogs, contexts)
                        if store.exact(actual) != store.exact(target):
                            raise ConversionError("conservation")
                        if conn.execute("PRAGMA user_version").fetchone() != (10,):
                            raise ConversionError("version")
                        inject("validated")
                        conn.execute("PRAGMA user_version=11")
                        inject("before_commit")
                        conn.set_progress_handler(commit_progress, 1)
                        commit_started = True
                        conn.execute("COMMIT")
                        conn.set_progress_handler(None, 0)
                        inject("after_commit")
                    except BaseException:
                        conn.set_progress_handler(None, 0)
                        if conn.in_transaction:
                            conn.execute("ROLLBACK")
                        raise
                    finally:
                        conn.execute(f"PRAGMA foreign_keys={int(original)}")
                        if conn.execute("PRAGMA foreign_keys").fetchone() != (original,):
                            raise ConversionError("policy")
            finally:
                fence.execute("ROLLBACK")
        # Final independent readonly reopen through unchanged public admission.
        loaded, _ = store.load(scope, "target.db", catalogs, contexts)
        if store.exact(loaded) != store.exact(target):
            raise ConversionError("conservation")
        with opened(scope, "source.db") as source:
            if store.exact(admit_v10(source)) != store.exact(before):
                raise ConversionError("source_changed")
        return Result(scope, before, loaded)
    except Exception:
        # Never infer rollback after COMMIT began; no retry/restore on either path.
        raise ConversionError("uncertain" if commit_started else "refused") from None
