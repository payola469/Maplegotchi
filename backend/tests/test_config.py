from pathlib import Path

import pytest

from maplegotchi.config import BrainMode, SettingsError, settings_from_env


def test_brain_defaults_to_rule(tmp_path: Path) -> None:
    data_dir = tmp_path / "maple-test"

    settings = settings_from_env(
        {
            "MAPLE_DATA_DIR": str(data_dir),
        }
    )

    assert settings.data_dir == data_dir
    assert settings.brain is BrainMode.RULE


def test_antigravity_brain_can_be_selected(tmp_path: Path) -> None:
    data_dir = tmp_path / "maple-test"

    settings = settings_from_env(
        {
            "MAPLE_DATA_DIR": str(data_dir),
            "MAPLE_BRAIN": "antigravity",
            "MAPLE_BRAIN_URL": "http://127.0.0.1:8471",
        }
    )

    assert settings.brain is BrainMode.ANTIGRAVITY
    assert settings.brain_url == "http://127.0.0.1:8471"


def test_antigravity_brain_url_must_be_loopback(tmp_path: Path) -> None:
    data_dir = tmp_path / "maple-test"

    settings = settings_from_env(
        {
            "MAPLE_DATA_DIR": str(data_dir),
            "MAPLE_BRAIN": "antigravity",
            "MAPLE_BRAIN_URL": "http://127.0.0.1:8471",
        }
    )

    assert settings.brain_url == "http://127.0.0.1:8471"


def test_antigravity_rejects_external_brain_url(tmp_path: Path) -> None:
    data_dir = tmp_path / "maple-test"

    with pytest.raises(SettingsError, match="loopback host"):
        settings_from_env(
            {
                "MAPLE_DATA_DIR": str(data_dir),
                "MAPLE_BRAIN": "antigravity",
                "MAPLE_BRAIN_URL": "https://example.com",
            }
        )
