"""Exercise configured import-linter rules and AST rules on planted violations."""

from __future__ import annotations

import ast
import tomllib
from copy import deepcopy
from pathlib import Path

import pytest
from grimp import ImportGraph
from importlinter import configuration
from importlinter.contracts.forbidden import ForbiddenContract

from tests.world.contracts import imports, scan_runtime, violations

CONFIG = Path(__file__).resolve().parents[2] / "pyproject.toml"


def test_runtime_has_no_oracle_or_world_boundary_violations() -> None:
    assert scan_runtime() == []


@pytest.mark.parametrize(
    "source",
    [
        "import random as rng\nrng.random()",
        "from datetime import datetime as dt\ndt.now()",
        "from pathlib import Path\nPath('x').read_text()",
        "from ...runtime import life",
        "from maplegotchi import world_catalog",
        "from maplegotchi.brain import rule_brain",
        "import third_party_geometry",
        "from tests.world.oracle import load_spec",
        "open('approved_tables.json')",
    ],
)
def test_world_rejects_planted_impurity(source: str) -> None:
    assert violations(source, "maplegotchi.core.world.model")


@pytest.mark.parametrize(
    "source",
    [
        "from dataclasses import dataclass\n@dataclass(frozen=True)\nclass Tile:\n    x: int",
        "from ..state import MapleState",
        "from datetime import datetime, timedelta\ndef later(now: datetime) -> datetime:\n"
        "    return now + timedelta(seconds=1)",
    ],
)
def test_world_accepts_pure_code(source: str) -> None:
    assert violations(source, "maplegotchi.core.world.model") == []


@pytest.mark.parametrize(
    "source",
    [
        "import tests.world.oracle",
        "from tests import world",
        "from pathlib import Path\np = Path('docs/architecture/maple-room-final-design-spec.md')",
    ],
)
def test_runtime_cannot_use_test_geometry(source: str) -> None:
    assert violations(source, "maplegotchi.runtime.loader")


def test_relative_test_import_resolution() -> None:
    assert imports(ast.parse("from ...tests import world"), "maplegotchi.core.world.model") == (
        "maplegotchi.tests.world",
    )
    assert imports(ast.parse("from .. import world_catalog"), "maplegotchi.runtime.loader") == (
        "maplegotchi.world_catalog",
    )


@pytest.mark.parametrize("source", ["import json", "DATA = {}", "def load(): pass"])
def test_catalog_cannot_become_python_loader(source: str) -> None:
    assert violations(source, "maplegotchi.world_catalog", package=True)
    assert (
        violations('"""Release data package."""', "maplegotchi.world_catalog", package=True) == []
    )


@pytest.mark.parametrize("contract_index", range(3))
def test_configured_import_contract_accepts_clean_and_rejects_planted_edges(
    contract_index: int,
) -> None:
    config = tomllib.loads(CONFIG.read_text(encoding="utf-8"))["tool"]["importlinter"]
    options = [item for item in config["contracts"] if item["name"].startswith("world:")]
    assert len(options) == 3
    selected = {
        key: str(value).lower() if isinstance(value, bool) else value
        for key, value in options[contract_index].items()
    }
    config["root_packages"] = [config["root_package"]]
    # import-linter configuration API is untyped.
    configuration.configure()  # type: ignore[no-untyped-call]
    contract = ForbiddenContract(selected["name"], config, selected)
    graph = ImportGraph()
    modules = {"maplegotchi", "maplegotchi.core", "maplegotchi.core.world"}
    for option in options:
        modules.update(option["source_modules"])
        modules.update(option["forbidden_modules"])
    for module in sorted(modules):
        graph.add_module(module)
    graph.add_import(importer="maplegotchi.core.world", imported="maplegotchi.core")
    assert contract.check(graph, verbose=False).kept
    for source in selected["source_modules"]:
        for forbidden in selected["forbidden_modules"]:
            planted = deepcopy(graph)
            planted.add_import(importer=source, imported=forbidden)
            assert not contract.check(planted, verbose=False).kept, (source, forbidden)


def test_world_indirect_catalog_dependency_is_rejected() -> None:
    config = tomllib.loads(CONFIG.read_text(encoding="utf-8"))["tool"]["importlinter"]
    selected = next(item for item in config["contracts"] if item["name"].startswith("world: pure"))
    config["root_packages"] = [config["root_package"]]
    # import-linter configuration API is untyped.
    configuration.configure()  # type: ignore[no-untyped-call]
    graph = ImportGraph()
    for module in [
        "maplegotchi",
        "maplegotchi.core",
        "maplegotchi.core.world",
        "maplegotchi.core.bridge",
        *selected["forbidden_modules"],
    ]:
        graph.add_module(module)
    graph.add_import(importer="maplegotchi.core.world", imported="maplegotchi.core.bridge")
    graph.add_import(importer="maplegotchi.core.bridge", imported="maplegotchi.world_catalog")
    assert (
        not ForbiddenContract(selected["name"], config, selected).check(graph, verbose=False).kept
    )
