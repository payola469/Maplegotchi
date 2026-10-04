from pathlib import Path

from maplegotchi.config import BrainMode, SensesKind, Settings
from maplegotchi.core.journal import BrainKind
from maplegotchi.runtime.clock import FakeClock
from maplegotchi.runtime.service import MapleService
from tests.persistence_support import BIRTH


def test_open_defaults_to_rule_brain(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    settings = Settings(
        data_dir=data_dir,
        senses=SensesKind.FAKE,
        brain=BrainMode.RULE,
    )

    service = MapleService.open(settings, clock=FakeClock(BIRTH))

    assert service.runtime.brain.kind is BrainKind.RULE
    assert service.runtime.brain.name == "rule_brain"

    service.runtime.close()


def test_open_uses_external_brain_when_selected(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    settings = Settings(
        data_dir=data_dir,
        senses=SensesKind.FAKE,
        brain=BrainMode.ANTIGRAVITY,
    )

    service = MapleService.open(settings, clock=FakeClock(BIRTH))

    assert service.runtime.brain.kind is BrainKind.EXTERNAL
    assert service.runtime.brain.name == "antigravity"

    service.runtime.close()
