"""Storage errors. Every one of these means: stop, do not invent replacement state."""

from __future__ import annotations


class StorageError(Exception):
    """Base class for persistence failures."""


class UnsafePathError(StorageError):
    """A path was rejected by the data-directory guard."""


class NotAMapleDatabaseError(StorageError):
    """The file exists but is not a Maplegotchi database (empty, foreign, or garbage)."""


class CorruptDatabaseError(StorageError):
    """SQLite reports the database file is damaged."""


class SchemaTooNewError(StorageError):
    """The database was written by a newer schema than this code understands."""


class MigrationError(StorageError):
    """A migration failed; the database remains at its previous schema version."""


class CorruptStateError(StorageError):
    """Persisted rows are readable but do not form a valid Maple life."""


class ConcurrentWriteError(StorageError):
    """Another writer changed Maple's state since it was loaded."""
