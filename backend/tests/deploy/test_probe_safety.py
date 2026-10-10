"""Isolated safety tests: no production host, service or HTTP access."""

from __future__ import annotations

import errno
import importlib.util
import os
import signal
import stat
import sys
import urllib.error
from email.message import Message
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from tests.deploy.test_check_boundaries import STATUS, cb

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location(
    "sandbox_probe", ROOT / "deploy/verify/sandbox_probe.py"
)
assert spec and spec.loader
probe = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = probe
spec.loader.exec_module(probe)


@pytest.fixture
def linux_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exercise mocked Linux security operations on any test host."""
    monkeypatch.setattr(probe, "sys", SimpleNamespace(platform="linux"))


@pytest.mark.parametrize("platform", ["win32", "darwin"])
@pytest.mark.parametrize("helper", ["host", "inside"])
def test_direct_helpers_reject_unsupported_platform_before_unix_access(
    monkeypatch: pytest.MonkeyPatch, platform: str, helper: str
) -> None:
    monkeypatch.setattr(probe, "sys", SimpleNamespace(platform=platform))
    # Importing pwd or reaching the first identity check must fail this test.
    monkeypatch.setitem(sys.modules, "pwd", None)

    def unexpected_access(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("unsupported platform reached Unix operations")

    monkeypatch.setattr(probe.os, "geteuid", unexpected_access, raising=False)
    monkeypatch.setattr(Path, "readlink", unexpected_access)
    monkeypatch.setattr(probe.subprocess, "run", unexpected_access)
    with pytest.raises(RuntimeError, match=r"^Linux only$"):
        if helper == "host":
            probe.host("a" * 40)
        else:
            probe.inside("mnt:[42]", 995, 979)


def test_exclusive_creation_preserves_existing_file(tmp_path: Path) -> None:
    existing = tmp_path / "sentinel"
    existing.write_bytes(b"real data")
    owned = probe.ProbeFiles()
    with pytest.raises(FileExistsError):
        owned.create(existing)
    owned.cleanup()
    assert existing.read_bytes() == b"real data"
    assert not owned.files and not owned.fds


def test_round_trip_random_exclusive_modes_and_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mkdir = Path.mkdir
    open_file = os.open
    paths: list[Path] = []
    modes: list[int] = []

    def make(path: Path, mode: int = 0o777, **kwargs: Any) -> None:
        paths.append(path)
        assert mode == 0o700 and not kwargs.get("exist_ok", False)
        mkdir(path, mode=mode, **kwargs)

    def create(path: Path, flags: int, mode: int) -> int:
        assert flags & os.O_EXCL and flags & os.O_CREAT and not flags & os.O_TRUNC
        modes.append(mode)
        return open_file(path, flags, mode)

    monkeypatch.setattr(Path, "mkdir", make)
    monkeypatch.setattr(probe.os, "open", create)
    if os.name == "nt":  # Windows lacks Unix modes; verify supplied modes above.
        monkeypatch.setattr(
            probe.stat, "S_IMODE", lambda mode: 0o700 if stat.S_ISDIR(mode) else 0o600
        )
    for _ in range(2):
        owned = probe.ProbeFiles()
        owned.round_trip(tmp_path)
        assert not owned.files and not owned.directories and not owned.fds
    assert paths[0] != paths[1]
    assert all(len(p.name.removeprefix(".od01-probe-")) == 32 for p in paths)
    assert modes == [0o600, 0o600]
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("error", [errno.EROFS, errno.EACCES, errno.EPERM])
def test_only_explicit_denials_pass(error: int, monkeypatch: pytest.MonkeyPatch) -> None:
    def denied(*args: Any) -> int:
        raise OSError(error, "denied")

    monkeypatch.setattr(probe.os, "open", denied)
    owned = probe.ProbeFiles()
    owned.denied(Path("unused"))
    assert not owned.files


@pytest.mark.parametrize("error", [errno.ENOENT, errno.EEXIST, errno.EIO, errno.ENOSPC])
def test_other_errors_fail(error: int, monkeypatch: pytest.MonkeyPatch) -> None:
    def failed(*args: Any) -> int:
        raise OSError(error, "failed")

    monkeypatch.setattr(probe.os, "open", failed)
    with pytest.raises(RuntimeError, match="unexpected create errno"):
        probe.ProbeFiles().denied(Path("unused"))


def test_forbidden_success_fails_and_removes_only_own_path(tmp_path: Path) -> None:
    keep = tmp_path / ".od01-deny-existing"
    keep.write_bytes(b"keep")
    owned = probe.ProbeFiles()
    with pytest.raises(RuntimeError, match="forbidden creation succeeded"):
        owned.denied(tmp_path)
    assert list(tmp_path.iterdir()) == [keep]
    assert keep.read_bytes() == b"keep"
    assert not owned.files and not owned.fds


def test_cleanup_failure_is_not_pass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    owned = probe.ProbeFiles()
    owned.close(owned.create(tmp_path / "owned"))

    def failed(*args: Any, **kwargs: Any) -> None:
        raise PermissionError("cleanup blocked")

    monkeypatch.setattr(Path, "unlink", failed)
    with pytest.raises(PermissionError):
        owned.cleanup()
    assert owned.files == [tmp_path / "owned"]


def test_cleanup_never_recursively_removes_untracked_children(tmp_path: Path) -> None:
    owned = probe.ProbeFiles()
    directory = tmp_path / "owned"
    directory.mkdir()
    owned.directories.append(directory)
    metadata = directory.stat()
    owned.identities[directory] = metadata.st_dev, metadata.st_ino
    (directory / "untracked").write_bytes(b"keep")
    with pytest.raises(OSError):
        owned.cleanup()
    assert (directory / "untracked").read_bytes() == b"keep"


def test_cleanup_refuses_replaced_probe_file(tmp_path: Path) -> None:
    owned = probe.ProbeFiles()
    path = tmp_path / "probe"
    owned.close(owned.create(path))
    replacement = tmp_path / "replacement"
    replacement.write_bytes(b"not probe data")
    replacement.replace(path)
    with pytest.raises(RuntimeError, match="refusing cleanup"):
        owned.cleanup()
    assert path.read_bytes() == b"not probe data"


def test_normal_checker_does_not_print_snapshot_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Path, "read_text", lambda *a, **kw: "")
    monkeypatch.setattr(
        cb, "parse_passwd", lambda _: {cb.ACCOUNT: SimpleNamespace(uid=996, gid=996)}
    )
    monkeypatch.setattr(cb, "parse_group", lambda _: {})
    for name in (
        "evaluate_account",
        "check_files",
        "check_release",
        "check_process",
        "check_sockets",
        "evaluate_snapshot",
    ):
        monkeypatch.setattr(cb, name, lambda *a: [])
    monkeypatch.setattr(cb, "check_http", lambda: ([], {"private": "snapshot"}))

    def forbidden(*args: Any) -> Any:
        pytest.fail("ordinary probe must not extract private identity")

    monkeypatch.setattr(cb, "identity_record", forbidden)
    assert cb.run_all(None, None) == []


def test_http_is_get_only_and_does_not_disclose_bodies(monkeypatch: pytest.MonkeyPatch) -> None:
    requests: list[tuple[str, Any]] = []

    def get(path: str, headers: Any = None) -> tuple[int, dict[str, str], bytes]:
        requests.append((path, headers))
        if path == "/api/snapshot":
            return 200, {}, b"{}"
        return (
            404 if path == "/api/docs" else 200,
            {**cb.REQUIRED_HEADERS, "content-security-policy": "default-src 'self'"},
            b"<SECRET RESPONSE>",
        )

    monkeypatch.setattr(cb, "_get", get)
    results, _ = cb.check_http()
    assert all(r.status == "PASS" for r in results)
    assert "SECRET" not in str(results)
    assert {p for p, _ in requests} == {"/api/health", "/", "/api/docs", "/api/snapshot"}
    assert ("/", {"Origin": "https://evil.example"}) in requests


def test_http_cors_permission_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cb, "_get", lambda *args: (200, {"access-control-allow-origin": "*"}, b"{}")
    )
    results, _ = cb.check_http()
    assert any(r.status == "FAIL" and "CORS" in r.check for r in results)


def test_transport_has_no_redirect_proxy_or_mutation(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[Any] = []

    class Opener:
        def open(self, request: Any, timeout: int) -> Any:
            assert request.get_method() == "GET" and request.data is None
            assert request.full_url == "http://127.0.0.1:8470/api/health"
            raise urllib.error.HTTPError(request.full_url, 302, "redirect", Message(), None)

    def build(*handlers: Any) -> Opener:
        seen.extend(handlers)
        return Opener()

    monkeypatch.setattr(cb.urllib.request, "build_opener", build)
    assert cb._get("/api/health")[0] == 302
    assert seen[0].proxies == {}
    assert seen[1].redirect_request(None, None, 302, "", {}, "https://elsewhere") is None
    with pytest.raises(ValueError):
        cb._get("/api/interactions/greet")


def test_runbook_and_scripts_agree() -> None:
    docs = (ROOT / "deploy/install.md").read_text(encoding="utf-8")
    section = docs.split("## 6.", 1)[1].split("## 8.", 1)[0]
    assert "sudo sh deploy/verify/sandbox_probe.sh 160ed4f" in section
    assert "systemctl stop" not in section and "systemctl restart" not in section
    for term in (
        "EROFS",
        "EACCES",
        "EPERM",
        "0700",
        "0600",
        "SIGKILL",
        "does NOT prove POST Origin rejection",
        "polkit denial",
        "cgroup network",
    ):
        assert term in section
    wrapper = (ROOT / "deploy/verify/sandbox_probe.sh").read_text(encoding="utf-8")
    assert "sandbox_probe.py" in wrapper and "exec /usr/bin/python3 -B" in wrapper
    assert "rm " not in wrapper and "sudo " not in "\n".join(
        line for line in wrapper.splitlines() if not line.startswith("#")
    )


def test_parent_interruption_waits_for_child_cleanup(monkeypatch: pytest.MonkeyPatch) -> None:
    completed = []
    previous = signal.getsignal(signal.SIGINT)

    def run(*args: Any, **kwargs: Any) -> Any:
        handler = signal.getsignal(signal.SIGINT)
        assert callable(handler)
        handler(signal.SIGINT, None)
        completed.append("child finished cleanup")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(probe.subprocess, "run", run)
    with pytest.raises(RuntimeError, match="parent interrupted"):
        probe.run_child(["never executed"], "source")
    assert completed == ["child finished cleanup"]
    assert signal.getsignal(signal.SIGINT) == previous


@pytest.mark.parametrize("change_at", [1, 2, 3])
def test_host_stops_on_service_identity_change(
    monkeypatch: pytest.MonkeyPatch, change_at: int, linux_probe: None
) -> None:
    monkeypatch.setitem(
        sys.modules,
        "pwd",
        SimpleNamespace(getpwnam=lambda _: SimpleNamespace(pw_uid=996, pw_gid=996)),
    )
    monkeypatch.setattr(probe.os, "geteuid", lambda: 0, raising=False)
    monkeypatch.setattr(probe.socket, "gethostname", lambda: "paolo-core")
    before = (123, "100", "/release", "mnt:[42]")
    snapshots = iter([before] * change_at + [(124, "101", "/release", "mnt:[43]")])
    monkeypatch.setattr(probe, "snapshot", lambda _: next(snapshots))
    read = Path.read_text
    monkeypatch.setattr(
        Path,
        "read_text",
        lambda p, **kw: STATUS if str(p).replace("\\", "/").startswith("/proc/") else read(p, **kw),
    )
    monkeypatch.setattr(
        cb,
        "parse_listeners",
        lambda text, ipv6: [] if ipv6 else [("127.0.0.1", 8470, 996), ("127.0.0.1", 8471, 997)],
    )
    launched = []
    monkeypatch.setattr(probe, "run_child", lambda args, source: launched.append(args))
    with pytest.raises(RuntimeError, match="service changed"):
        probe.host("a" * 40)
    assert len(launched) == (0 if change_at == 1 else 1)
    if launched:
        assert "--clear-groups" in launched[0]
        assert "--bounding-set=-all" in launched[0]
        assert "-B" in launched[0] and "--inside" in launched[0]


@pytest.mark.parametrize(
    ("groups", "valid"), [("979", True), ("", True), ("979 27", False), ("0", False)]
)
def test_service_group_validation(
    monkeypatch: pytest.MonkeyPatch, groups: str, valid: bool, linux_probe: None
) -> None:
    monkeypatch.setitem(
        sys.modules,
        "pwd",
        SimpleNamespace(getpwnam=lambda _: SimpleNamespace(pw_uid=995, pw_gid=979)),
    )
    monkeypatch.setattr(probe.os, "geteuid", lambda: 0, raising=False)
    monkeypatch.setattr(probe.socket, "gethostname", lambda: "paolo-core")
    monkeypatch.setattr(probe, "snapshot", lambda _: (1395361, "100", "/release", "mnt:[42]"))
    status = STATUS.replace("Uid:\t996\t996\t996\t996", "Uid:\t995\t995\t995\t995")
    status = status.replace("Gid:\t996\t996\t996\t996", "Gid:\t979\t979\t979\t979")
    status = status.replace("Groups:\t", f"Groups:\t{groups}")
    monkeypatch.setattr(Path, "read_text", lambda *args, **kwargs: status)
    monkeypatch.setattr(
        cb,
        "parse_listeners",
        lambda text, ipv6: [] if ipv6 else [("127.0.0.1", 8470, 995), ("127.0.0.1", 8471, 997)],
    )
    launched: list[bool] = []
    monkeypatch.setattr(probe, "run_child", lambda *args: launched.append(True))
    if valid:
        probe.host("a" * 40)
        assert launched == [True]
    else:
        with pytest.raises(RuntimeError, match="process has no supplementary groups"):
            probe.host("a" * 40)
        assert not launched


@pytest.mark.parametrize("groups", [[], [979], [979, 27], [0]])
def test_helper_still_requires_empty_groups(
    monkeypatch: pytest.MonkeyPatch, groups: list[int], linux_probe: None
) -> None:
    monkeypatch.setattr(probe.os, "geteuid", lambda: 995, raising=False)
    monkeypatch.setattr(probe.os, "getegid", lambda: 979, raising=False)
    monkeypatch.setattr(probe.os, "getgroups", lambda: groups, raising=False)

    def stop_after_group_check(*args: Any) -> Any:
        raise RuntimeError("passed group gate; stop before any namespace or file access")

    monkeypatch.setattr(Path, "readlink", stop_after_group_check)
    expected = "helper supplementary groups are not empty" if groups else "passed group gate"
    with pytest.raises(RuntimeError, match=expected):
        probe.inside("mnt:[42]", 995, 979)
