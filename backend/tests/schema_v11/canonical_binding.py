"""Synthetic-owned binding of the production-safe port; never runtime startup."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from maplegotchi.core.tasks import SourceRef, ToolRecord
from maplegotchi.persistence.boundary import capture_life
from maplegotchi.persistence.layout_codec import CatalogSnapshot, LayoutContext
from maplegotchi.persistence.life_record import CanonicalLife
from maplegotchi.runtime.tasks import TaskFacts, TaskWorker
from maplegotchi.storage.canonical_v11 import CanonicalSnapshot, PersistenceError
from maplegotchi.storage.repositories import LifeRepository
from tests.schema_v11 import owned_store as store
from tests.schema_v11.row_conservation import TableImage


def admit(
    image: store.Snapshot,
    catalogs: tuple[CatalogSnapshot, ...],
    contexts: tuple[tuple[int, LayoutContext], ...],
) -> CanonicalSnapshot:
    life = capture_life(store.validate(image, catalogs, contexts))
    return CanonicalSnapshot(
        life,
        tuple((table.name, table.columns, table.rows) for table in image.tables),
        image.sequences,
    )


def image_of(snapshot: CanonicalSnapshot) -> store.Snapshot:
    return store.Snapshot(
        tuple(TableImage(name, columns, rows) for name, columns, rows in snapshot.tables),
        snapshot.sequences,
    )


@dataclass(frozen=True)
class OwnedBinding:
    scope: store.OwnedFiles
    name: str
    catalogs: tuple[CatalogSnapshot, ...]
    contexts: tuple[tuple[int, LayoutContext], ...]
    inject: Callable[[str], None] = lambda phase: None
    commit_progress: Callable[[], int] | None = None

    def create(self, snapshot: CanonicalSnapshot, *, schema_version: int) -> None:
        if type(schema_version) is not int or schema_version != 11:
            raise PersistenceError("version")
        image = image_of(snapshot)
        try:
            if admit(image, self.catalogs, self.contexts) != snapshot:
                raise PersistenceError("invalid")
            store.create(self.scope, self.name, image, self.catalogs, self.contexts)
        except store.StoreError as exc:
            if str(exc) == "ownership":
                raise PersistenceError("ownership") from None
            raise PersistenceError("storage") from None

    def close(self) -> None:
        """Every store operation closes its owned connection before returning.

        This binding retains only a capability, no open SQLite handle. Runtime
        shutdown still calls this explicitly; it never performs a final write.
        """

    def load(self, *, schema_version: int) -> CanonicalSnapshot:
        if type(schema_version) is not int or schema_version != 11:
            raise PersistenceError("version")
        try:
            image, _ = store.load(self.scope, self.name, self.catalogs, self.contexts)
            return admit(image, self.catalogs, self.contexts)
        except store.StoreError as exc:
            category = str(exc)
            if category == "ownership":
                raise PersistenceError("ownership") from None
            if category == "version":
                raise PersistenceError("version") from None
            raise PersistenceError("storage") from None

    def save(
        self, snapshot: CanonicalSnapshot, *, schema_version: int, expected_revision: int
    ) -> None:
        if type(schema_version) is not int or schema_version != 11:
            raise PersistenceError("version")
        image = image_of(snapshot)
        try:
            if admit(image, self.catalogs, self.contexts) != snapshot:
                raise PersistenceError("invalid")
            store.save(
                self.scope,
                self.name,
                image,
                expected_revision=expected_revision,
                catalogs=self.catalogs,
                contexts=self.contexts,
                inject=self.inject,
                commit_progress=self.commit_progress,
            )
        except store.StoreError as exc:
            if str(exc) == "stale":
                raise PersistenceError("revision") from None
            if str(exc) == "ownership":
                raise PersistenceError("ownership") from None
            if str(exc) == "state":
                raise PersistenceError("invalid") from None
            # Storage failures may occur around COMMIT; no retry or rollback claim.
            raise PersistenceError("uncertain") from None

    def task_catalog(self, before: CanonicalSnapshot) -> tuple[SourceRef, ...]:
        """Read only the exact owned revision; never use a v10 state reader/writer."""
        with store.connect(self.scope, self.name, readonly=True) as conn:
            conn.execute("BEGIN")
            actual, _ = store.load_connection(conn, self.catalogs, self.contexts)
            if store.exact(actual) != store.exact(image_of(before)):
                raise PersistenceError("revision")
            return TaskWorker().catalog(LifeRepository(conn))

    def task_effects(
        self,
        before: CanonicalSnapshot,
        after: CanonicalLife,
        now: datetime,
    ) -> tuple[ToolRecord, ...]:
        """Task work on a consistent read-only, synthetic-owned view.

        LifeRepository is used ONLY for inherited table reads. load/create/commit
        are never invoked; the connection itself is read-only. Draft/provenance
        commit through the unchanged canonical writer, not this connection.
        """

        def facts(life: CanonicalLife) -> TaskFacts:
            return TaskFacts(
                life.record.action_counter,
                datetime.fromisoformat(life.record.activity_until),
                life.activity,
                life.active_goal,
                life.task,
                life.identity,
            )

        with store.connect(self.scope, self.name, readonly=True) as conn:
            conn.execute("BEGIN")
            actual, _ = store.load_connection(conn, self.catalogs, self.contexts)
            if store.exact(actual) != store.exact(image_of(before)):
                raise PersistenceError("revision")
            return TaskWorker().effects(LifeRepository(conn), facts(before.life), facts(after), now)
