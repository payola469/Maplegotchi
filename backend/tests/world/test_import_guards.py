"""Negative architecture specimens are parsed strings, never imported or executed."""

from __future__ import annotations

import pytest

from tests.world.import_guards import APPROVED, DIRECT, violations


@pytest.mark.parametrize("caller,target", tuple(DIRECT))
def test_only_exact_approved_named_imports(caller: str, target: str) -> None:
    names = ", ".join(sorted(DIRECT[caller, target]))
    assert not violations({caller: f"from {target} import {names}"})


@pytest.mark.parametrize(
    "caller",
    (
        "maplegotchi/runtime/life.py",
        "maplegotchi/runtime/service.py",
        "maplegotchi/api/app.py",
        "maplegotchi/api/sse.py",
        "maplegotchi/cli.py",
        "maplegotchi/config.py",
        "maplegotchi/persistence/future_codec.py",
        "maplegotchi/runtime/layout_codec.py",
    ),
)
@pytest.mark.parametrize(
    "source",
    (
        "import maplegotchi.core.world.legacy_projection as hidden",
        "from maplegotchi.core.world import layout_validation as hidden",
        "from maplegotchi.core.world.resolution import requirement_for as hidden",
        "from maplegotchi.persistence import life_record as hidden",
        "from maplegotchi.persistence import *",
        "from maplegotchi.runtime import canonical_persistence as hidden",
        "from maplegotchi.storage.canonical_v11 import load as hidden",
    ),
)
def test_unapproved_callers_fail(caller: str, source: str) -> None:
    assert violations({caller: source})


@pytest.mark.parametrize(
    "source",
    (
        "from .canonical_persistence import CanonicalPersistenceRuntime",
        "from ..persistence.life_record import CanonicalLife",
        "from ..core.world import resolution as hidden",
    ),
)
def test_relative_imports_do_not_hide_activation(source: str) -> None:
    assert violations({"maplegotchi/runtime/service.py": source})


@pytest.mark.parametrize(
    "source",
    (
        "import maplegotchi.core.world.resolution as r",
        "from maplegotchi.core.world import resolution as r",
        "from maplegotchi.core.world.resolution import *",
        "from maplegotchi.core.world.resolution import resolve",
        "from ..core.world.resolution import resolve as requirement_for",
    ),
)
def test_approved_requirement_validator_cannot_gain_live_resolution(source: str) -> None:
    assert violations({"maplegotchi/persistence/life_record.py": source})


def test_indirect_default_activation_and_package_reexports_fail() -> None:
    errors = violations(
        {
            "maplegotchi/api/app.py": "from maplegotchi import helper",
            "maplegotchi/helper/__init__.py": "from .bridge import run",
            "maplegotchi/helper/bridge.py": (
                "from maplegotchi.runtime.canonical_persistence import restore"
            ),
            "maplegotchi/runtime/canonical_persistence.py": "",
        }
    )
    assert any("api/app.py: indirect activation" in e for e in errors)
    assert any("helper/__init__.py: indirect activation" in e for e in errors)
    assert any("helper/bridge.py: forbidden activation" in e for e in errors)


def test_new_canonical_target_requires_explicit_approval_even_from_approved_caller() -> None:
    assert violations(
        {
            "maplegotchi/persistence/life_record.py": "from .future_codec import decode",
            "maplegotchi/persistence/future_codec.py": "",
        }
    )


def test_canonical_cycle_fails() -> None:
    errors = violations(
        {
            "maplegotchi/persistence/life_record.py": "from .boundary import capture_life",
            "maplegotchi/persistence/boundary.py": "from .life_record import CanonicalLife",
        }
    )
    assert any("circular canonical dependency" in e for e in errors)


def test_package_initializer_activation_fails() -> None:
    errors = violations(
        {
            "maplegotchi/api/app.py": "import maplegotchi.runtime.lifecycle",
            "maplegotchi/runtime/lifecycle.py": "",
            "maplegotchi/runtime/__init__.py": "from .canonical_persistence import restore",
            "maplegotchi/runtime/canonical_persistence.py": "",
        }
    )
    assert any("api/app.py: indirect activation" in e for e in errors)


def test_module_mentions_are_not_imports() -> None:
    assert not violations(
        {"maplegotchi/api/app.py": '# maplegotchi.core.world.resolution\n"maplegotchi.persistence"'}
    )


def test_allowlist_contains_exact_python_paths_only() -> None:
    assert all(path.startswith("maplegotchi/") and path.endswith(".py") for path in APPROVED)
    assert not any("*" in path for path in APPROVED)


@pytest.mark.parametrize(
    "caller",
    [
        "maplegotchi/runtime/service.py",
        "maplegotchi/runtime/life.py",
        "maplegotchi/api/app.py",
        "maplegotchi/cli.py",
    ],
)
def test_mvp_engine_cannot_activate_default_callers(caller: str) -> None:
    assert violations({caller: "from maplegotchi.core.world.canonical_lifecycle import step"})


@pytest.mark.parametrize(
    "caller",
    [
        "maplegotchi/runtime/service.py",
        "maplegotchi/runtime/life.py",
        "maplegotchi/api/app.py",
        "maplegotchi/api/stream.py",
        "maplegotchi/cli.py",
        "maplegotchi/runtime/future_polling.py",
    ],
)
@pytest.mark.parametrize(
    "source",
    [
        "from maplegotchi.runtime.canonical_polling import snapshot_read",
        "from maplegotchi.runtime import canonical_polling as hidden",
    ],
)
def test_opt_in_read_module_does_not_activate_shipped_or_future_callers(
    caller: str, source: str
) -> None:
    assert violations({caller: source})


def test_polling_permission_does_not_grant_live_resolution_or_projection() -> None:
    for target in ("resolution", "legacy_projection", "layout_validation"):
        assert violations(
            {
                "maplegotchi/runtime/canonical_polling.py": (
                    f"from maplegotchi.core.world import {target}"
                )
            }
        )
