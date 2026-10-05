"""The maple-discord unit and config keep the bot token and Maple's data apart (ADR-0032)."""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
UNIT = REPO / "deploy" / "discord" / "maple-discord.service"
GATEWAY_ENV = REPO / "deploy" / "discord" / "maple-discord.env"
MAPLE_ENV = REPO / "deploy" / "etc" / "maplegotchi" / "maplegotchi.env"
MAPLE_UNIT = REPO / "deploy" / "systemd" / "maplegotchi.service"


def directives(path: Path) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "[")) or "=" not in line:
            continue
        key, value = line.split("=", 1)
        found.setdefault(key, []).append(value)
    return found


def test_gateway_runs_as_its_own_unprivileged_account() -> None:
    d = directives(UNIT)
    assert d["User"] == ["maple-discord-svc"] and d["Group"] == ["maple-discord-svc"]
    assert d["SupplementaryGroups"] == [""]
    for key, value in {
        "NoNewPrivileges": "yes",
        "ProtectSystem": "strict",
        "ProtectHome": "yes",
        "PrivateTmp": "yes",
        "PrivateDevices": "yes",
        "RestrictSUIDSGID": "yes",
        "MemoryDenyWriteExecute": "yes",
        "CapabilityBoundingSet": "",
    }.items():
        assert d[key] == [value], key


def test_gateway_cannot_see_maples_data_or_config() -> None:
    hidden = " ".join(directives(UNIT)["InaccessiblePaths"])
    assert "-/data" in hidden.split() and "-/etc/maplegotchi" in hidden.split()


def test_secrets_are_credentials_not_environment() -> None:
    d = directives(UNIT)
    assert sorted(d["LoadCredential"]) == [
        "discord-bot-token:/etc/maple-discord/discord-bot-token",
        "maple-gateway-token:/etc/maple-discord/maple-gateway-token",
    ]
    env = directives(GATEWAY_ENV)
    assert env["DISCORD_BOT_TOKEN_FILE"] == ["discord-bot-token"]
    assert "DISCORD_BOT_TOKEN" not in env and "MAPLE_GATEWAY_TOKEN" not in env
    assert env["MAPLE_API_URL"] == ["http://127.0.0.1:8470"]


def test_maplegotchi_never_carries_the_bot_token() -> None:
    for path in (MAPLE_ENV, MAPLE_UNIT):
        text = path.read_text(encoding="utf-8").upper()
        assert "BOT_TOKEN" not in text and "DISCORD-BOT-TOKEN" not in text, path.name
        assert "/ETC/MAPLE-DISCORD" not in directives(path).get("EnvironmentFile", [""])[0].upper()
