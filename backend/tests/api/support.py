"""Helpers for API tests: a real service on a temp data dir, driven by a fake clock."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from maplegotchi.api.app import create_app
from maplegotchi.config import Mode, Settings
from maplegotchi.runtime.clock import FakeClock
from maplegotchi.runtime.life import LifeRuntime
from maplegotchi.runtime.senses import Senses
from maplegotchi.runtime.service import MapleService, fake_senses
from maplegotchi.storage.datadir import DataDir
from tests.persistence_support import BIRTH, PARAMS, SEED

ORIGIN = "http://127.0.0.1:5173"
TRUSTED = {"Origin": ORIGIN}


def make_service(
    data_root: Path, clock: FakeClock | None = None, senses: Senses | None = None
) -> MapleService:
    data_root.mkdir(exist_ok=True)
    clock = clock or FakeClock(BIRTH)
    runtime = LifeRuntime.open(DataDir(data_root), clock, PARAMS, new_seed=lambda: SEED)
    return MapleService(runtime, senses or fake_senses(), clock, PARAMS)


def make_settings(tmp_path: Path, **overrides: object) -> Settings:
    fields: dict[str, object] = {"data_dir": tmp_path / "data"}
    fields.update(overrides)
    return Settings(**fields)  # type: ignore[arg-type]


def make_client(
    service: MapleService,
    tmp_path: Path,
    *,
    sse_max_events: int | None = None,
    **settings: Any,
) -> TestClient:
    app = create_app(
        service,
        make_settings(tmp_path, **settings),
        run_life_loop=False,
        sse_max_events=sse_max_events,
    )
    return TestClient(app)


def production(tmp_path: Path) -> dict[str, Any]:
    return {"mode": Mode.PRODUCTION, "allowed_origins": ("https://maple.tailnet.example",)}
