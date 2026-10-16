"""A created document's read category must remain a canonical TEXT scalar."""

from dataclasses import replace

from maplegotchi.core.tasks import read_task
from maplegotchi.runtime.canonical_persistence import CanonicalPersistenceRuntime
from tests.schema_v11 import owned_store as store
from tests.schema_v11.canonical_binding import image_of
from tests.schema_v11.restart_worker import advanced_snapshot
from tests.schema_v11.test_canonical_boundary import scope as scope
from tests.schema_v11.test_canonical_runtime import initial, port


def test_own_document_catalog_is_readable_by_strict_canonical_record(
    scope: store.OwnedRoot,
) -> None:
    binding = port(scope)
    birth = initial(binding)
    runtime = CanonicalPersistenceRuntime.create(binding, birth, schema_version=11)
    runtime.close()
    store.save(
        scope,
        binding.name,
        advanced_snapshot(image_of(birth)),
        expected_revision=1,
        catalogs=binding.catalogs,
        contexts=binding.contexts,
    )
    runtime = CanonicalPersistenceRuntime.restore(binding, schema_version=11)
    try:
        before = runtime.capture()
        raw = scope.check("maple.db").read_bytes()
        document = next(s for s in binding.task_catalog(before) if s.id.startswith("document:"))
        task = read_task(document)
        # Previously WriteKind (a str subclass) escaped catalog, rejected by v11's
        # exact-type guard after Maple eventually chose to read its own writing.
        assert type(task.category) is str
        encoded = replace(before.life.record, task_category=task.category)
        assert encoded.task_category == document.category
        assert runtime.capture() is before and scope.check("maple.db").read_bytes() == raw
    finally:
        runtime.close()
