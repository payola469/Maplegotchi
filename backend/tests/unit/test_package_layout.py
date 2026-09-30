"""Phase 0 smoke test: the package and every architectural layer import cleanly."""

from __future__ import annotations

import importlib

import pytest

import maplegotchi

LAYERS = [
    "maplegotchi.core",
    "maplegotchi.brain",
    "maplegotchi.sensors",
    "maplegotchi.sensors.service_health",
    "maplegotchi.storage",
    "maplegotchi.runtime",
    "maplegotchi.api",
]


def test_version_is_set() -> None:
    assert maplegotchi.__version__


@pytest.mark.parametrize("module", LAYERS)
def test_layer_imports(module: str) -> None:
    assert importlib.import_module(module).__doc__
