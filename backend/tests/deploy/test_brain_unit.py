"""The maple-brain unit keeps the provider away from Maple's data (ADR-0033)."""

from __future__ import annotations

from pathlib import Path

from tests.deploy.test_discord_unit import directives

REPO = Path(__file__).resolve().parents[3]
UNIT = REPO / "deploy" / "brain" / "maple-brain.service"
ENV = REPO / "deploy" / "brain" / "maple-brain.env"


def test_brain_runs_as_its_own_unprivileged_account() -> None:
    d = directives(UNIT)
    assert d["User"] == ["maple-brain-svc"] and d["Group"] == ["maple-brain-svc"]
    assert d["SupplementaryGroups"] == [""]
    for key, value in {
        "NoNewPrivileges": "yes",
        "ProtectSystem": "strict",
        "ProtectHome": "yes",
        "PrivateTmp": "yes",
        "CapabilityBoundingSet": "",
        "StateDirectory": "maple-brain",
        "StateDirectoryMode": "0700",
    }.items():
        assert d[key] == [value], key


def test_brain_cannot_see_maples_data_or_any_config() -> None:
    hidden = " ".join(directives(UNIT)["InaccessiblePaths"]).split()
    assert {"-/data", "-/etc/maplegotchi", "-/etc/maple-discord"} <= set(hidden)


def test_brain_env_is_loopback_and_safe_by_default() -> None:
    env = directives(ENV)
    assert env["MAPLE_BRAIN_HOST"] == ["127.0.0.1"]
    assert env["MAPLE_BRAIN_PROVIDER"] == ["none"]
    text = ENV.read_text(encoding="utf-8").lower()
    for flag in ("--yolo", "--dangerously-skip-permissions"):
        assert f'"{flag}"' not in text  # never suggested as an argument


def test_memory_deny_write_execute_exception_is_brain_only() -> None:
    # Owner-approved exception (ADR-0033 review): JIT provider CLIs, this unit only.
    assert "MemoryDenyWriteExecute" not in directives(UNIT)
    for other in ("systemd/maplegotchi.service", "discord/maple-discord.service"):
        assert directives(REPO / "deploy" / other)["MemoryDenyWriteExecute"] == ["yes"], other


def test_no_provider_or_model_is_hard_coded() -> None:
    sources = [*(REPO / "companion" / "brain" / "src").rglob("*.py"), ENV]
    for path in sources:
        text = path.read_text(encoding="utf-8").lower()
        assert "gemini" not in text and "flash" not in text, path


def test_release_bundle_ships_both_companions() -> None:
    script = (REPO / "scripts" / "build_release.sh").read_text(encoding="utf-8")
    assert "companion/brain companion/discord" in script
