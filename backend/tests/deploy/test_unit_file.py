"""Contracts for the deployment files: the systemd sandbox and the production settings."""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

import pytest

from maplegotchi.config import Mode, SensesKind, settings_from_env

REPO = Path(__file__).resolve().parents[3]
DEPLOY = REPO / "deploy"
UNIT = DEPLOY / "systemd" / "maplegotchi.service"
ENV = DEPLOY / "etc" / "maplegotchi" / "maplegotchi.env"


def parse_unit(text: str) -> dict[str, dict[str, list[str]]]:
    sections: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    section = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", ";")):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            continue
        key, sep, value = line.partition("=")
        assert sep, f"not a key=value line: {raw!r}"
        sections[section][key.strip()].append(value.strip())
    return sections


UNIT_SECTIONS = parse_unit(UNIT.read_text(encoding="utf-8"))
SERVICE = UNIT_SECTIONS["Service"]


def one(key: str) -> str:
    values = SERVICE[key]
    assert len(values) == 1, f"{key} set {len(values)} times"
    return values[0]


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("User", "maple-svc"),
        ("Group", "maple-svc"),
        ("SupplementaryGroups", ""),
        ("NoNewPrivileges", "yes"),
        ("CapabilityBoundingSet", ""),
        ("AmbientCapabilities", ""),
        ("ProtectSystem", "strict"),
        ("ProtectHome", "yes"),
        ("PrivateTmp", "yes"),
        ("PrivateDevices", "yes"),
        ("ProtectKernelTunables", "yes"),
        ("ProtectKernelModules", "yes"),
        ("ProtectControlGroups", "yes"),
        ("ProtectProc", "invisible"),
        ("RestrictSUIDSGID", "yes"),
        ("RestrictNamespaces", "yes"),
        ("LockPersonality", "yes"),
        ("MemoryDenyWriteExecute", "yes"),
        ("RestrictAddressFamilies", "AF_UNIX AF_INET"),
        ("IPAddressDeny", "any"),
        ("IPAddressAllow", "localhost"),
        ("UMask", "0027"),
        ("TemporaryFileSystem", "/data:ro"),
        ("BindPaths", "/data/maple"),
        ("BindReadOnlyPaths", "/data/monitor"),
        ("EnvironmentFile", "/etc/maplegotchi/maplegotchi.env"),
        ("ExecStart", "/opt/maplegotchi/current/venv/bin/python -I -m maplegotchi.cli run"),
    ],
)
def test_unit_hardening(key: str, value: str) -> None:
    assert one(key) == value


def test_syscall_filter_allows_services_and_denies_privileged_groups() -> None:
    allow, deny = SERVICE["SystemCallFilter"]
    assert allow == "@system-service"
    assert deny.startswith("~") and {"@privileged", "@resources", "@mount"} <= set(deny[1:].split())


def test_nothing_else_is_writable_or_privileged() -> None:
    forbidden = {"ReadWritePaths", "StateDirectory", "LogsDirectory", "CacheDirectory",
                 "RuntimeDirectory", "DynamicUser", "PermissionsStartOnly", "ExecStartPre",
                 "ExecStartPost", "ExecReload", "ExecStop", "PAMName", "Delegate",
                 "DeviceAllow", "BindPaths+"}  # fmt: skip
    assert not forbidden & set(SERVICE)
    assert SERVICE["BindPaths"] == ["/data/maple"]  # the one writable bind
    exec_line = one("ExecStart")
    assert not exec_line.startswith(("+", "!", "-", "@", ":")), "no privileged exec prefixes"
    assert "sh " not in exec_line and "bash" not in exec_line
    for value in (v for values in SERVICE.values() for v in values):
        assert "docker" not in value.lower() or value.startswith("-/")  # only InaccessiblePaths
    assert "docker.sock" in " ".join(SERVICE["InaccessiblePaths"])


def test_unit_waits_for_data_mounts() -> None:
    assert UNIT_SECTIONS["Unit"]["RequiresMountsFor"] == ["/data/maple /data/monitor"]
    assert UNIT_SECTIONS["Install"]["WantedBy"] == ["multi-user.target"]


def env_file() -> dict[str, str]:
    values = {}
    for line in ENV.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            key, _, value = line.partition("=")
            values[key] = value
    return values


def test_env_template_is_a_valid_production_config_once_the_origin_is_set(tmp_path: Path) -> None:
    env = env_file()
    assert env["MAPLE_ALLOWED_ORIGINS"] == "https://paolo-core.REPLACE-ME.ts.net"
    env["MAPLE_DATA_DIR"] = str(tmp_path)  # stands in for /data/maple on this machine
    settings = settings_from_env(env)
    assert settings.mode is Mode.PRODUCTION
    assert (settings.host, settings.port) == ("127.0.0.1", 8470)
    assert settings.senses is SensesKind.PAOLO_CORE
    assert settings.heartbeat_seconds == 300
    assert str(settings.monitor_db).replace("\\", "/") == "/data/monitor/metrics.db"
    assert env["MAPLE_DATA_DIR"] and env_file()["MAPLE_DATA_DIR"] == "/data/maple"


# The old account name in an owner/user position: User=maple, -o maple, root:maple, ...
OLD_ACCOUNT = re.compile(
    r"(?:\b(?:User|Group)=|\s-[og]\s+|chown\s+(?:-R\s+)?|[\w-]+:)\"?maple\b(?!-)"
)


def test_deploy_files_name_the_canonical_account_only() -> None:
    """The production account is maple-svc (ADR-0020); the old name must not linger."""
    hits = []
    for path in sorted(DEPLOY.rglob("*")):
        if path.suffix in {".sh", ".service", ".rules", ".env", ".md", ".py"}:
            for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if OLD_ACCOUNT.search(line.replace("/data/maple", "/data/X")):
                    hits.append(f"{path.relative_to(DEPLOY)}:{line_no}: {line.strip()}")
    assert hits == []
    rule = (DEPLOY / "polkit" / "50-maplegotchi-deny.rules").read_text(encoding="utf-8")
    assert 'subject.user === "maple-svc"' in rule


def test_old_account_detector_detects() -> None:
    for bad in ("User=maple", "install -o maple x", "chown root:maple f", "maple:maple 0750"):
        assert OLD_ACCOUNT.search(bad), bad
    for good in ("User=maple-svc", "install -o maple-svc x", "root:maple-svc", "/data/X"):
        assert not OLD_ACCOUNT.search(good), good
