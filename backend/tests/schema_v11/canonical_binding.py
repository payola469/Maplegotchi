"""Synthetic-owned binding of the production-safe port; never runtime startup."""

from collections.abc import Callable
from dataclasses import dataclass

from maplegotchi.persistence.boundary import capture_life
from maplegotchi.persistence.layout_codec import CatalogSnapshot, LayoutContext
from maplegotchi.storage.canonical_v11 import CanonicalSnapshot, PersistenceError
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
    scope: store.OwnedRoot
    name: str
    catalogs: tuple[CatalogSnapshot, ...]
    contexts: tuple[tuple[int, LayoutContext], ...]
    inject: Callable[[str], None] = lambda phase: None

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
