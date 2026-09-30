"""The production verification script: parsers and verdicts, tested on any OS."""

from __future__ import annotations

import errno
import importlib.util
import os
import sys
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "deploy" / "verify" / "check_boundaries.py"


def load() -> Any:
    spec = importlib.util.spec_from_file_location("check_boundaries", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses resolve annotations through sys.modules
    spec.loader.exec_module(module)
    return module


cb = load()

ACCTS = """root:x:0:0:root:/root:/bin/bash
paolo:x:1000:1000:Paolo:/home/paolo:/bin/bash
maple-svc:x:996:996::/nonexistent:/usr/sbin/nologin
"""
GRPS = """root:x:0:
sudo:x:27:paolo
docker:x:983:paolo
maple-svc:x:996:
"""


def statuses(results: list[Any]) -> dict[str, str]:
    return {r.check: r.status for r in results}


def test_account_checks_pass_for_a_locked_down_system_account() -> None:
    results = cb.evaluate_account(cb.parse_passwd(ACCTS), cb.parse_group(GRPS))
    assert set(statuses(results).values()) == {"PASS"}


@pytest.mark.parametrize(
    ("passwd", "group", "failing"),
    [
        (ACCTS.replace("/usr/sbin/nologin", "/bin/bash"), GRPS, "account has no login shell"),
        (ACCTS.replace("/nonexistent", "/home/maple"), GRPS, "account has no real home"),
        (ACCTS.replace(":996:996:", ":1001:996:"), GRPS, "account is a system account"),
        (ACCTS, GRPS.replace("docker:x:983:paolo", "docker:x:983:paolo,maple-svc"),
         "account is in no privileged group"),
        (ACCTS, GRPS + "video:x:44:maple-svc\n", "account has no supplementary groups"),
    ],
)  # fmt: skip
def test_account_violations_fail(passwd: str, group: str, failing: str) -> None:
    results = cb.evaluate_account(cb.parse_passwd(passwd), cb.parse_group(group))
    assert statuses(results)[failing] == "FAIL"


def test_missing_account_fails() -> None:
    results = cb.evaluate_account(cb.parse_passwd("root:x:0:0::/root:/bin/bash"), {})
    assert [r.status for r in results] == ["FAIL"]


STATUS = """Name:\tpython
Uid:\t996\t996\t996\t996
Gid:\t996\t996\t996\t996
Groups:\t
CapInh:\t0000000000000000
CapPrm:\t0000000000000000
CapEff:\t0000000000000000
CapBnd:\t0000000000000000
CapAmb:\t0000000000000000
NoNewPrivs:\t1
Seccomp:\t2
"""


def test_sandboxed_process_passes() -> None:
    results = cb.evaluate_process(cb.parse_proc_status(STATUS), 996, 996)
    assert set(statuses(results).values()) == {"PASS"}


@pytest.mark.parametrize(
    ("old", "new", "failing"),
    [
        ("Uid:\t996\t996\t996\t996", "Uid:\t0\t0\t0\t0", "process uids are all maple-svc"),
        ("Groups:\t", "Groups:\t983", "process has no supplementary groups"),
        ("CapBnd:\t0000000000000000", "CapBnd:\t000001ffffffffff", "process CapBnd is empty"),
        ("NoNewPrivs:\t1", "NoNewPrivs:\t0", "process has no_new_privs"),
        ("Seccomp:\t2", "Seccomp:\t0", "process runs under a seccomp filter"),
    ],
)
def test_process_violations_fail(old: str, new: str, failing: str) -> None:
    results = cb.evaluate_process(cb.parse_proc_status(STATUS.replace(old, new)), 996, 996)
    assert statuses(results)[failing] == "FAIL"


TCP = """  sl  local_address rem_address st tx_queue rx_queue tr tm->when retrnsmt uid timeout inode
   0: 0100007F:2116 00000000:0000 0A 00000000:00000000 00:00000000 00000000   996        0 1 1
   1: 00000000:0016 00000000:0000 0A 00000000:00000000 00:00000000 00000000     0        0 2 1
   2: 0100007F:2116 0100007F:C350 01 00000000:00000000 00:00000000 00000000   996        0 3 1
"""
TCP6 = """  sl  local_address remote_address st tx_queue rx_queue tr tm->when retrnsmt uid timeout inode
   0: 00000000000000000000000001000000:0CEA 00000000000000000000000000000000:0000 0A 00000000:00000000 00:00000000 00000000  1000        0 4 1
"""  # noqa: E501 - /proc/net/tcp6 lines are long


def test_proc_net_tcp_parsing() -> None:
    v4 = cb.parse_listeners(TCP, ipv6=False)
    assert v4 == [("127.0.0.1", 8470, 996), ("0.0.0.0", 22, 0)]  # noqa: S104
    assert cb.parse_listeners(TCP6, ipv6=True) == [("0:0:0:0:0:0:0:1", 3306, 1000)]


def test_listener_verdicts() -> None:
    good = cb.parse_listeners(TCP, ipv6=False)
    assert set(statuses(cb.evaluate_listeners(good, 996)).values()) == {"PASS"}
    public = [*good, ("0.0.0.0", 8470, 996)]  # noqa: S104
    assert set(statuses(cb.evaluate_listeners(public, 996)).values()) == {"FAIL"}
    extra = [*good, ("127.0.0.1", 9000, 996)]
    assert (
        statuses(cb.evaluate_listeners(extra, 996))["maple-svc listens only on 127.0.0.1:8470"]
        == "FAIL"
    )


def snapshot(**overrides: Any) -> dict[str, Any]:
    services = [
        {"service_id": "maplegotchi", "status": "available", "state": "active",
         "source": "systemd_dbus", "reason": None},
        {"service_id": "metrics_collector", "status": "available", "state": "active",
         "source": "monitor_db", "reason": None},
        {"service_id": "backup", "status": "available", "state": "active",
         "source": "systemd_dbus", "reason": None},
        {"service_id": "grafana", "status": "unknown", "state": None,
         "source": "service_health", "reason": "not_observable:docker_container"},
        {"service_id": "lycan_watch", "status": "unknown", "state": None,
         "source": "service_health", "reason": "not_observable:no_systemd_unit"},
    ]  # fmt: skip
    host = [
        {"metric": m, "subject": s, "status": "available", "value": 12.0, "source": "psutil"}
        for m, s in (
            ("cpu_usage", "cpu"),
            ("memory_usage", "memory"),
            ("disk_usage", "/"),
            ("load_1m", "system"),
            ("temperature", "cpu"),
        )
    ]
    snap: dict[str, Any] = {
        "revision": 12,
        "maple": {
            "identity": {"name": "Maple", "born_at": "2026-10-01T00:00:00Z", "ticks_lived": 9}
        },
        "freshness": {
            "life_loop_running": True, "life_loop_error": None, "heartbeat_status": "fresh",
            "heartbeat_interval_seconds": 300, "sensor_status": "fresh",
        },
        "server": {"observed_at": "2026-10-01T00:05:00Z", "services": services, "host": host},
    }  # fmt: skip
    snap.update(overrides)
    return snap


def test_healthy_snapshot_passes() -> None:
    assert set(statuses(cb.evaluate_snapshot(snapshot())).values()) == {"PASS"}


def test_fabricated_or_stale_service_state_fails() -> None:
    snap = snapshot()
    grafana = snap["server"]["services"][3]
    grafana.update(status="available", state="active", reason=None, source="fake")
    snap["server"]["services"].append({"service_id": "jellyfin", "status": "unknown"})
    snap["freshness"]["heartbeat_status"] = "overdue"
    results = statuses(cb.evaluate_snapshot(snap))
    assert results["service grafana honestly unknown"] == "FAIL"
    assert results["service map is exactly the verified one"] == "FAIL"
    assert results["heartbeat fresh"] == "FAIL"


def test_host_metrics_must_come_from_psutil() -> None:
    snap = snapshot()
    snap["server"]["host"][4].update(status="unavailable", value=None, reason="no_sensors")
    assert statuses(cb.evaluate_snapshot(snap))["host temperature measured by psutil"] == "FAIL"


def test_identity_continuity() -> None:
    before = cb.identity_record(snapshot())
    after = cb.identity_record(snapshot(revision=15))
    assert set(statuses(cb.compare_identity(before, after)).values()) == {"PASS"}
    reborn = dict(after, born_at="2026-10-02T00:00:00Z", revision=1, ticks_lived=0)
    verdict = statuses(cb.compare_identity(before, reborn))
    assert verdict.pop("identity name unchanged") == "PASS"  # same name, new life
    assert set(verdict.values()) == {"FAIL"}


def test_script_refuses_to_run_off_linux(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cb, "IS_LINUX", False)
    assert cb.main([]) == 2


def test_before_the_first_heartbeat_the_checks_are_pending_not_failed() -> None:
    snap = snapshot()
    snap["server"] = {"observed_at": None, "services": [], "host": []}
    snap["freshness"]["sensor_status"] = "none"
    verdict = statuses(cb.evaluate_snapshot(snap))
    assert verdict["no observations yet"] == "WARN"
    assert "FAIL" not in verdict.values()


# ---------------------------------------------------------------- protected metadata


class FakeStat:
    def __init__(self, uid: int, gid: int, mode: int) -> None:
        self.st_uid, self.st_gid, self.st_mode = uid, gid, 0o100000 | mode


def lstat_returning(result: FakeStat | BaseException) -> Any:
    def lstat(path: Path) -> FakeStat:
        if isinstance(result, BaseException):
            raise result
        return result

    return lstat


ENV = cb.Expected(Path("/etc/maplegotchi/maplegotchi.env"), 0, 996, 0o640, "root", "maple-svc")


def test_true_missing_is_a_fail(tmp_path: Path) -> None:
    for absent in (tmp_path / "nope", tmp_path / "no-dir" / "nope"):
        probe = cb.probe_metadata(absent)
        assert isinstance(probe, cb.Missing)
        result = cb.evaluate_metadata(ENV, probe)
        assert (result.status, result.detail) == ("FAIL", "missing (does not exist)")


def test_permission_denied_is_an_owner_check_not_missing() -> None:
    denied = PermissionError(errno.EACCES, "Permission denied")
    probe = cb.probe_metadata(ENV.path, lstat=lstat_returning(denied))
    assert probe == cb.Denied("Permission denied")
    result = cb.evaluate_metadata(ENV, probe)
    assert result.status == "OWNER_CHECK" and "missing" not in result.detail
    assert result.owner_stat == "root:maple-svc 640 /etc/maplegotchi/maplegotchi.env"


@pytest.mark.skipif(
    sys.platform == "win32" or getattr(os, "geteuid", lambda: 0)() == 0,
    reason="needs POSIX permissions and a non-root user",
)
def test_real_eacces_from_an_unsearchable_directory(tmp_path: Path) -> None:
    protected = tmp_path / "protected"
    protected.mkdir()
    (protected / "secret.env").write_text("x", encoding="utf-8")
    protected.chmod(0o000)
    try:
        assert isinstance(cb.probe_metadata(protected / "secret.env"), cb.Denied)
        assert isinstance(cb.probe_metadata(protected / "absent.env"), cb.Denied)  # unknowable
    finally:
        protected.chmod(0o700)


def test_correct_accessible_metadata_passes() -> None:
    probe = cb.probe_metadata(ENV.path, lstat=lstat_returning(FakeStat(0, 996, 0o640)))
    assert probe == cb.Metadata(0, 996, 0o640)
    assert cb.evaluate_metadata(ENV, probe).status == "PASS"


@pytest.mark.parametrize(
    "wrong",
    [
        FakeStat(996, 996, 0o640),
        FakeStat(0, 0, 0o640),
        FakeStat(0, 996, 0o644),
        FakeStat(0, 996, 0o660),
    ],
)
def test_incorrect_accessible_metadata_fails(wrong: FakeStat) -> None:
    result = cb.evaluate_metadata(ENV, cb.probe_metadata(ENV.path, lstat=lstat_returning(wrong)))
    assert result.status == "FAIL"
    assert "want root:maple-svc 640 /etc/maplegotchi/maplegotchi.env" in result.detail


def test_other_os_errors_are_not_mistaken_for_denied(tmp_path: Path) -> None:
    with pytest.raises(OSError):
        cb.probe_metadata(ENV.path, lstat=lstat_returning(OSError(errno.EIO, "I/O error")))


def test_owner_command_matches_the_real_paolo_core_output() -> None:
    """The three Stage C paths, denied to the owner; expected lines = actual sudo stat output."""
    denied = cb.Denied("Permission denied")
    by_path = {e.path.as_posix(): e for e in cb.file_expectations(996, 996)}
    results = [
        cb.evaluate_metadata(by_path[p], denied)
        for p in (
            "/etc/maplegotchi/maplegotchi.env",
            "/etc/polkit-1/rules.d/50-maplegotchi-deny.rules",
            "/data/maple/maple.db",
        )
    ]
    assert {r.status for r in results} == {"OWNER_CHECK"}
    command = cb.owner_stat_command([*results, cb.Result("PASS", "other")])
    assert command is not None
    cmd, lines = command
    assert cmd == (
        "sudo stat -c '%U:%G %a %n' /etc/maplegotchi/maplegotchi.env "
        "/etc/polkit-1/rules.d/50-maplegotchi-deny.rules /data/maple/maple.db"
    )
    assert lines == [  # verbatim from the owner's run on paolo-core
        "root:maple-svc 640 /etc/maplegotchi/maplegotchi.env",
        "root:root 644 /etc/polkit-1/rules.d/50-maplegotchi-deny.rules",
        "maple-svc:maple-svc 640 /data/maple/maple.db",
    ]
    assert cb.owner_stat_command([cb.Result("PASS", "x")]) is None


def test_owner_checks_do_not_fail_the_run_but_missing_does(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    owner = cb.evaluate_metadata(ENV, cb.Denied("Permission denied"))
    monkeypatch.setattr(cb, "IS_LINUX", True)
    monkeypatch.setattr(cb, "run_all", lambda record, compare: [owner, cb.Result("PASS", "x")])
    assert cb.main([]) == 0
    out = capsys.readouterr().out
    assert "1 owner checks" in out
    assert "sudo stat -c '%U:%G %a %n' /etc/maplegotchi/maplegotchi.env" in out
    missing = cb.evaluate_metadata(ENV, cb.Missing())
    monkeypatch.setattr(cb, "run_all", lambda record, compare: [owner, missing])
    assert cb.main([]) == 1
