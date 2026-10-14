"""Actual canonical port integration using only fresh owned synthetic databases."""

import ast
from collections.abc import Iterator
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

from maplegotchi.core.rng import RngStream
from maplegotchi.persistence.boundary import capture_life
from maplegotchi.persistence.life_record import V11LifeError, life_fields
from maplegotchi.storage.canonical_v11 import (
    TABLE_NAMES,
    CanonicalSnapshot,
    PersistenceError,
    load,
    save,
)
from tests.schema_v11 import owned_store as store
from tests.schema_v11.canonical_binding import OwnedBinding, admit, image_of
from tests.schema_v11.declarations import target_tables
from tests.schema_v11.restart_worker import (
    advanced_snapshot,
    birth_snapshot,
    life_changes,
    resources,
)
from tests.security.forbidden_apis import scan_source


def test_serialization_package_remains_pure_and_dormant() -> None:
    root = Path(__file__).parents[2] / "src/maplegotchi/persistence"
    allowed = {
        "__future__",
        "collections",
        "dataclasses",
        "datetime",
        "hashlib",
        "itertools",
        "json",
        "math",
        "re",
        "typing",
    }
    for path in root.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert scan_source(source, core=True) == []
        for node in ast.walk(ast.parse(source)):
            names = []
            if isinstance(node, ast.ImportFrom):
                assert node.level == 0
                names = [node.module or ""]
            elif isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            for name in names:
                assert name.split(".")[0] in allowed or name.startswith(
                    ("maplegotchi.core.", "maplegotchi.persistence.")
                )


@pytest.fixture
def scope() -> Iterator[store.OwnedRoot]:
    root = store.OwnedRoot.new()
    try:
        yield root
    finally:
        root.cleanup()


def binding(scope: store.OwnedRoot, *, create: bool = True) -> OwnedBinding:
    catalog, context, _ = resources()
    result = OwnedBinding(scope, "maple.db", (catalog,), ((1, context),))
    if create:
        store.create(scope, result.name, birth_snapshot(), result.catalogs, result.contexts)
    return result


@pytest.mark.parametrize("mode", ["stationary", "walking", "pending", "entry_a", "entry_b"])
def test_save_load_complete_boundary(scope: store.OwnedRoot, mode: str) -> None:
    port = binding(scope)
    old = load(port, schema_version=11)
    proposal = admit(advanced_snapshot(image_of(old), mode), port.catalogs, port.contexts)
    captured = capture_life(proposal.life)
    assert len(life_fields(captured.record)) == 40
    assert TABLE_NAMES == set(target_tables())
    save(port, proposal, schema_version=11, expected_revision=1)
    # A new binding, no cached state; consistent read and full validation again.
    restored = load(replace(port), schema_version=11)
    assert store.exact(image_of(restored)) == store.exact(image_of(proposal))
    assert restored.life == captured
    assert restored.sequences == proposal.sequences
    assert len(image_of(restored).rows("timeline_event")) == 1
    assert store.old_history(image_of(restored)) == store.old_history(image_of(proposal))
    for stream, counter in (
        ("tick", captured.rng.tick_counter),
        ("interaction", captured.rng.interaction_counter),
        ("decision", captured.rng.decision_counter),
    ):
        before = RngStream(captured.rng.seed_hex, stream, counter)
        after = RngStream(restored.life.rng.seed_hex, stream, counter)
        assert [before.random() for _ in range(5)] == [after.random() for _ in range(5)]
    if captured.travel is not None:
        assert restored.life.travel == captured.travel
    assert load(port, schema_version=11) == restored
    with pytest.raises(FrozenInstanceError):
        restored.life.record.tx = 0  # type: ignore[misc]


def test_capture_rejects_forged_derived_state(scope: store.OwnedRoot) -> None:
    port = binding(scope)
    life = load(port, schema_version=11).life
    with pytest.raises(V11LifeError, match="fields"):
        capture_life(replace(life, rng=replace(life.rng, tick_counter=12)))
    with pytest.raises(V11LifeError, match="type"):
        capture_life(object())  # type: ignore[arg-type]
    with pytest.raises(V11LifeError, match="layout"):
        capture_life(replace(life, layout=replace(life.layout, revisions=())))
    with pytest.raises(V11LifeError, match="fields"):
        capture_life(replace(life, record=None))  # type: ignore[arg-type]


@pytest.mark.parametrize("version", [0, 10, 12, True])
def test_version_refuses_before_binding(scope: store.OwnedRoot, version: int) -> None:
    port = binding(scope, create=False)
    with pytest.raises(PersistenceError, match="version"):
        load(port, schema_version=version)
    assert not (scope.path / "maple.db").exists()


def test_missing_load_does_not_create(scope: store.OwnedRoot) -> None:
    port = binding(scope, create=False)
    with pytest.raises(PersistenceError, match="ownership"):
        load(port, schema_version=11)
    assert not (scope.path / "maple.db").exists()


@pytest.mark.parametrize("version", [10, 12])
def test_database_version_refused_without_repair(scope: store.OwnedRoot, version: int) -> None:
    port = binding(scope)
    with store.connect(scope, port.name) as conn:
        conn.execute(f"PRAGMA user_version={version}")
    with pytest.raises(PersistenceError, match="version"):
        load(port, schema_version=11)
    with store.connect(scope, port.name, readonly=True) as conn:
        assert conn.execute("PRAGMA user_version").fetchone() == (version,)


def test_inconsistent_referenced_fact_rejected_before_write(scope: store.OwnedRoot) -> None:
    port = binding(scope)
    before = load(port, schema_version=11)
    proposal = admit(advanced_snapshot(image_of(before)), port.catalogs, port.contexts)
    broken = tuple(
        (name, columns, ((1, 99),) if name == "world_state" else rows)
        for name, columns, rows in proposal.tables
    )
    with pytest.raises(PersistenceError, match="invalid"):
        save(port, replace(proposal, tables=broken), schema_version=11, expected_revision=1)
    assert load(port, schema_version=11) == before


@pytest.mark.parametrize("phase", ["after_write", "before_commit", "after_commit"])
def test_failure_has_no_hybrid_or_automatic_retry(scope: store.OwnedRoot, phase: str) -> None:
    port = binding(scope)
    before = load(port, schema_version=11)
    proposed = admit(advanced_snapshot(image_of(before)), port.catalogs, port.contexts)
    calls = []

    def fail(at: str) -> None:
        calls.append(at)
        if at == phase:
            raise PersistenceError("uncertain")

    with pytest.raises(PersistenceError, match="uncertain"):
        save(replace(port, inject=fail), proposed, schema_version=11, expected_revision=1)
    restored = load(port, schema_version=11)
    expected = proposed if phase == "after_commit" else before
    assert store.exact(image_of(restored)) == store.exact(image_of(expected))
    assert calls.count(phase) == 1


def test_stale_save_and_invalid_image_refuse(scope: store.OwnedRoot) -> None:
    port = binding(scope)
    old = load(port, schema_version=11)
    proposal = admit(advanced_snapshot(image_of(old)), port.catalogs, port.contexts)
    save(port, proposal, schema_version=11, expected_revision=1)
    with pytest.raises(PersistenceError, match="revision"):
        save(port, proposal, schema_version=11, expected_revision=1)
    with pytest.raises(PersistenceError, match="invalid"):
        replace(proposal, tables=proposal.tables[:-1])
    changed = life_changes(image_of(proposal), revision=3)
    tables = tuple((t.name, t.columns, t.rows) for t in changed.tables)
    with pytest.raises(PersistenceError, match="invalid"):
        CanonicalSnapshot(proposal.life, tables, proposal.sequences)
    assert load(port, schema_version=11) == proposal
