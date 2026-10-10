#!/usr/bin/env python3
"""Read-only production checks for Maplegotchi on paolo-core (Phase 7, CLAUDE.md §4.6).

Run as your ordinary user (no sudo). Standard library only; it runs no commands,
changes nothing on the host, and only talks HTTP to 127.0.0.1:8470. The one file
it may write is the optional `--record` file you name (for the restart check).

    python3 check_boundaries.py                         # everything below
    python3 check_boundaries.py --record /tmp/maple-before.json
    # Restart continuity is separate, owner-authorized work; never part of OD-01.
    python3 check_boundaries.py --compare /tmp/maple-before.json

Protected paths (the env file under /etc/maplegotchi 0750, Maple's database
under /data/maple 0750, polkit's rules.d) cannot be stat()ed by an unprivileged
user. Permission denied is NOT reported as "missing": such a path becomes an
OWNER_CHECK with the exact `sudo stat -c '%U:%G %a %n' ...` command and the
expected output lines, printed at the end. Only a path that provably does not
exist (ENOENT from a readable parent) is a FAIL.

Checks: account and groups, file ownership/modes (code, config, data), release
integrity, the running process (uid, groups, capabilities, no_new_privs,
seccomp), listening sockets (loopback only), HTTP (health, frontend, headers,
absence of CORS permissions), the live snapshot (heartbeat, host metrics, service map), and
identity continuity across a restart. The mount-namespace view (what Maple can
and cannot see) is checked by sandbox_probe.sh, which needs nsenter (root).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
import urllib.error
import urllib.request
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ACCOUNT = "maple-svc"
PORT = 8470
BASE = f"http://127.0.0.1:{PORT}"
OPT = Path("/opt/maplegotchi")
ETC = Path("/etc/maplegotchi")
ENV_FILE = ETC / "maplegotchi.env"
DATA = Path("/data/maple")
MONITOR = Path("/data/monitor")
UNIT_FILE = Path("/etc/systemd/system/maplegotchi.service")
POLKIT_RULE = Path("/etc/polkit-1/rules.d/50-maplegotchi-deny.rules")
NOLOGIN_SHELLS = frozenset({"/usr/sbin/nologin", "/sbin/nologin", "/bin/false", "/usr/bin/false"})
PRIVILEGED_GROUPS = frozenset(
    {"root", "sudo", "adm", "docker", "lxd", "systemd-journal", "wheel", "disk", "shadow"}
)
EXPECTED_SERVICES: Mapping[str, str | None] = {
    # service_id -> required "unknown" reason, or None when it must be available
    "maplegotchi": None,
    "metrics_collector": None,
    "backup": None,
    "grafana": "not_observable:docker_container",
    "lycan_watch": "not_observable:no_systemd_unit",
}
REQUIRED_HEADERS: Mapping[str, str] = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "no-referrer",
}
_SHA = re.compile(r"[0-9a-f]{40}")
_SUM_LINE = re.compile(r"([0-9a-f]{64}) [ *](.+)")  # sha256sum text or binary form
# A plain flag (not an inline sys.platform check) so mypy analyses both branches.
IS_LINUX: bool = sys.platform.startswith("linux")


@dataclass(frozen=True)
class Result:
    status: str  # PASS | FAIL | WARN | INFO | OWNER_CHECK
    check: str
    detail: str = ""
    owner_stat: str | None = None  # expected `stat -c '%U:%G %a %n'` line, if OWNER_CHECK

    def __str__(self) -> str:
        return f"[{self.status}] {self.check}" + (f": {self.detail}" if self.detail else "")


def ok(check: str, cond: bool, detail: str = "", *, warn: bool = False) -> Result:
    return Result("PASS" if cond else ("WARN" if warn else "FAIL"), check, detail)


# ---------------------------------------------------------------- parsers (unit-tested)


@dataclass(frozen=True)
class Account:
    name: str
    uid: int
    gid: int
    home: str
    shell: str


def parse_passwd(text: str) -> dict[str, Account]:
    accounts: dict[str, Account] = {}
    for line in text.splitlines():
        parts = line.split(":")
        if len(parts) == 7 and not line.startswith("#"):
            accounts[parts[0]] = Account(parts[0], int(parts[2]), int(parts[3]), parts[5], parts[6])
    return accounts


def parse_group(text: str) -> dict[str, tuple[int, frozenset[str]]]:
    groups: dict[str, tuple[int, frozenset[str]]] = {}
    for line in text.splitlines():
        parts = line.split(":")
        if len(parts) == 4 and not line.startswith("#"):
            members = frozenset(m for m in parts[3].split(",") if m)
            groups[parts[0]] = (int(parts[2]), members)
    return groups


def parse_proc_status(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in text.splitlines():
        key, sep, value = line.partition(":")
        if sep:
            fields[key.strip()] = value.strip()
    return fields


def _ipv4(hex_addr: str) -> str:
    raw = bytes.fromhex(hex_addr)[::-1]
    return ".".join(str(b) for b in raw)


def _ipv6(hex_addr: str) -> str:
    raw = b"".join(bytes.fromhex(hex_addr[i : i + 8])[::-1] for i in range(0, 32, 8))
    if raw[:12] == b"\x00" * 10 + b"\xff\xff":
        return "::ffff:" + ".".join(str(b) for b in raw[12:])
    groups = [raw[i : i + 2].hex() for i in range(0, 16, 2)]
    return ":".join(g.lstrip("0") or "0" for g in groups)


def parse_listeners(text: str, *, ipv6: bool) -> list[tuple[str, int, int]]:
    """(address, port, uid) of every LISTEN socket in /proc/net/tcp or tcp6."""
    listeners = []
    for line in text.splitlines()[1:]:
        fields = line.split()
        if len(fields) < 8 or fields[3] != "0A":  # 0A = TCP_LISTEN
            continue
        addr_hex, port_hex = fields[1].split(":")
        address = _ipv6(addr_hex) if ipv6 else _ipv4(addr_hex)
        listeners.append((address, int(port_hex, 16), int(fields[7])))
    return listeners


def is_loopback(address: str) -> bool:
    return address.startswith("127.") or address in {"0:0:0:0:0:0:0:1", "::ffff:127.0.0.1"}


# ---------------------------------------------------------------- evaluations (unit-tested)


def evaluate_account(
    passwd: Mapping[str, Account], groups: Mapping[str, tuple[int, frozenset[str]]]
) -> list[Result]:
    account = passwd.get(ACCOUNT)
    if account is None:
        return [Result("FAIL", "account", f"{ACCOUNT} does not exist")]
    own = groups.get(ACCOUNT)
    supplementary = sorted(name for name, (_, members) in groups.items() if ACCOUNT in members)
    return [
        ok("account is a system account", account.uid < 1000, f"uid={account.uid}"),
        ok("account has no login shell", account.shell in NOLOGIN_SHELLS, account.shell),
        ok("account has no real home", account.home == "/nonexistent", account.home),
        ok(
            "account primary group is its own",
            own is not None and own[0] == account.gid,
            f"gid={account.gid}",
        ),
        ok("account has no supplementary groups", not supplementary, ",".join(supplementary)),
        ok(
            "account is in no privileged group",
            not (set(supplementary) & PRIVILEGED_GROUPS),
            ",".join(sorted(set(supplementary) & PRIVILEGED_GROUPS)),
        ),
    ]


def evaluate_process(status: Mapping[str, str], uid: int, gid: int) -> list[Result]:
    def ids(key: str) -> set[int]:
        return {int(x) for x in status.get(key, "").split()}

    groups = ids("Groups")
    return [
        ok("process uids are all maple-svc", ids("Uid") == {uid}, status.get("Uid", "")),
        ok("process gids are all maple-svc", ids("Gid") == {gid}, status.get("Gid", "")),
        ok("process has no supplementary groups", groups <= {gid}, status.get("Groups", "")),
        *(
            ok(f"process {cap} is empty", int(status.get(cap, "1"), 16) == 0, status.get(cap, ""))
            for cap in ("CapInh", "CapPrm", "CapEff", "CapBnd", "CapAmb")
        ),
        ok("process has no_new_privs", status.get("NoNewPrivs") == "1"),
        ok("process runs under a seccomp filter", status.get("Seccomp") == "2"),
    ]


def evaluate_listeners(listeners: Iterable[tuple[str, int, int]], uid: int) -> list[Result]:
    listeners = list(listeners)
    maple = sorted({(a, p) for a, p, u in listeners if u == uid})
    on_port = sorted({a for a, p, _ in listeners if p == PORT})
    return [
        ok(
            "maple-svc listens only on 127.0.0.1:8470",
            maple == [("127.0.0.1", PORT)],
            str(maple),
        ),
        ok(
            "nothing listens on 8470 beyond loopback",
            bool(on_port) and all(is_loopback(a) for a in on_port),
            str(on_port),
        ),
    ]


def evaluate_snapshot(snapshot: Mapping[str, Any]) -> list[Result]:
    results = []
    fresh = snapshot.get("freshness", {})
    results.append(ok("life loop running", fresh.get("life_loop_running") is True))
    results.append(ok("life loop error-free", fresh.get("life_loop_error") is None))
    results.append(ok("heartbeat fresh", fresh.get("heartbeat_status") == "fresh"))
    results.append(
        ok("heartbeat interval is 300 s", fresh.get("heartbeat_interval_seconds") == 300)
    )
    results.append(
        ok("observations fresh", fresh.get("sensor_status") == "fresh", warn=True)
    )  # "none" right after the very first start
    server = snapshot.get("server", {})
    if server.get("observed_at") is None:
        # Birth happens at start; the first observed heartbeat comes one interval later.
        results.append(Result("WARN", "no observations yet", "re-run after the first heartbeat"))
        return results
    host = {(o.get("metric"), o.get("subject")): o for o in server.get("host", [])}
    for metric, subject in (
        ("cpu_usage", "cpu"),
        ("memory_usage", "memory"),
        ("disk_usage", "/"),
        ("load_1m", "system"),
        ("temperature", "cpu"),
    ):
        o = host.get((metric, subject), {})
        warm = metric == "cpu_usage" and o.get("reason") == "warming_up"
        results.append(
            ok(
                f"host {metric} measured by psutil",
                o.get("status") == "available" and o.get("source") == "psutil",
                f"{o.get('status')} {o.get('value')} {o.get('reason') or ''}".strip(),
                warn=warm,
            )
        )
    services = {s.get("service_id"): s for s in server.get("services", [])}
    results.append(
        ok(
            "service map is exactly the verified one",
            set(services) == set(EXPECTED_SERVICES),
            ",".join(sorted(services)),
        )
    )
    for service_id, reason in EXPECTED_SERVICES.items():
        s = services.get(service_id, {})
        if reason is None:
            results.append(
                ok(
                    f"service {service_id} observed",
                    s.get("status") == "available",
                    f"{s.get('state')} via {s.get('source')} {s.get('reason') or ''}".strip(),
                )
            )
        else:
            results.append(
                ok(
                    f"service {service_id} honestly unknown",
                    s.get("status") == "unknown" and s.get("reason") == reason,
                    str(s.get("reason")),
                )
            )
    maple = services.get("maplegotchi", {})
    results.append(ok("Maple sees itself active", maple.get("state") == "active"))
    return results


def identity_record(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    maple = snapshot["maple"]
    return {
        "name": maple["identity"]["name"],
        "born_at": maple["identity"]["born_at"],
        "ticks_lived": maple["identity"]["ticks_lived"],
        "revision": snapshot["revision"],
    }


def compare_identity(before: Mapping[str, Any], after: Mapping[str, Any]) -> list[Result]:
    return [
        ok("identity name unchanged", before["name"] == after["name"]),
        ok("identity born_at unchanged", before["born_at"] == after["born_at"]),
        ok(
            "revision continued (not reset)",
            after["revision"] >= before["revision"],
            f"{before['revision']} -> {after['revision']}",
        ),
        ok(
            "ticks continued (not reset)",
            after["ticks_lived"] >= before["ticks_lived"],
            f"{before['ticks_lived']} -> {after['ticks_lived']}",
        ),
    ]


# ---------------------------------------------------------------- host probes (Linux only)


@dataclass(frozen=True)
class Metadata:
    uid: int
    gid: int
    mode: int


class Missing:
    """lstat() said ENOENT: the path does not exist."""


@dataclass(frozen=True)
class Denied:
    """lstat() was refused (EACCES/EPERM): unverifiable without privilege."""

    error: str


Probe = Metadata | Missing | Denied


def probe_metadata(path: Path, lstat: Any = os.lstat) -> Probe:
    """Owner/group/mode of `path`, telling "does not exist" apart from "not allowed to look"."""
    try:
        st = lstat(path)
    except FileNotFoundError:
        return Missing()
    except PermissionError as exc:
        return Denied(exc.strerror or type(exc).__name__)
    return Metadata(st.st_uid, st.st_gid, stat.S_IMODE(st.st_mode))


@dataclass(frozen=True)
class Expected:
    path: Path
    uid: int
    gid: int
    mode: int
    owner: str  # names, for the owner-run `stat -c '%U:%G %a %n'` comparison
    group: str

    def stat_line(self) -> str:
        return f"{self.owner}:{self.group} {self.mode:o} {self.path.as_posix()}"


def evaluate_metadata(expected: Expected, probe: Probe) -> Result:
    check = f"{expected.path.as_posix()} owner/mode"
    if isinstance(probe, Missing):
        return Result("FAIL", check, "missing (does not exist)")
    if isinstance(probe, Denied):
        return Result(
            "OWNER_CHECK",
            check,
            f"not readable without privilege ({probe.error}); expect '{expected.stat_line()}'",
            owner_stat=expected.stat_line(),
        )
    got = (probe.uid, probe.gid, probe.mode)
    want = (expected.uid, expected.gid, expected.mode)
    return ok(
        check, got == want, f"{probe.uid}:{probe.gid} {probe.mode:o} (want {expected.stat_line()})"
    )


def owner_stat_command(results: Sequence[Result]) -> tuple[str, list[str]] | None:
    """The one sudo command the owner runs for every OWNER_CHECK, and its expected lines."""
    lines = [r.owner_stat for r in results if r.status == "OWNER_CHECK" and r.owner_stat]
    if not lines:
        return None
    paths = " ".join(line.split(" ", 2)[2] for line in lines)
    return f"sudo stat -c '%U:%G %a %n' {paths}", lines


def _mode(path: Path) -> tuple[int, int, int] | None:
    try:
        st = path.lstat()
    except OSError:
        return None
    return st.st_uid, st.st_gid, stat.S_IMODE(st.st_mode)


def file_expectations(uid: int, gid: int) -> list[Expected]:
    svc = ACCOUNT
    return [
        Expected(ETC, 0, gid, 0o750, "root", svc),
        Expected(ENV_FILE, 0, gid, 0o640, "root", svc),  # under 0750: owner-check for paolo
        Expected(DATA, uid, gid, 0o750, svc, svc),
        Expected(DATA / "maple.db", uid, gid, 0o640, svc, svc),  # under 0750: owner-check
        Expected(UNIT_FILE, 0, 0, 0o644, "root", "root"),
        Expected(POLKIT_RULE, 0, 0, 0o644, "root", "root"),  # rules.d is 0700 root
    ]


def check_files(uid: int, gid: int) -> list[Result]:
    results = [evaluate_metadata(e, probe_metadata(e.path)) for e in file_expectations(uid, gid)]

    writable_by_others: list[str] = []
    owned_by_maple: list[str] = []
    for root, dirs, files in os.walk(OPT):
        for name in (*dirs, *files):
            p = Path(root) / name
            got = _mode(p)
            if got is None or stat.S_ISLNK(p.lstat().st_mode):
                continue
            if got[0] != 0 or got[2] & 0o022:
                writable_by_others.append(str(p))
            if got[0] == uid or got[1] == gid:
                owned_by_maple.append(str(p))
    opt = _mode(OPT)
    results.append(ok("/opt/maplegotchi is root-owned, 0755", opt == (0, 0, 0o755), str(opt)))
    results.append(
        ok(
            "nothing under /opt/maplegotchi is writable by non-root",
            not writable_by_others,
            ", ".join(writable_by_others[:5]),
        )
    )
    results.append(
        ok(
            "nothing under /opt/maplegotchi belongs to maple-svc",
            not owned_by_maple,
            ", ".join(owned_by_maple[:5]),
        )
    )
    strays = [str(p) for p in MONITOR.iterdir() if (m := _mode(p)) and m[0] == uid]
    results.append(ok("Maple created nothing in /data/monitor", not strays, ", ".join(strays)))
    return results


def check_release() -> list[Result]:
    current = OPT / "current"
    try:
        target = current.readlink().as_posix()
    except OSError as exc:
        return [Result("FAIL", "current release symlink", str(exc))]
    sha = Path(target).name
    release = OPT / "releases" / sha
    results = [
        ok(
            "current -> releases/<commit-sha>",
            target == f"releases/{sha}" and bool(_SHA.fullmatch(sha)),
            target,
        ),
        ok("release marked complete", (release / ".complete").is_file()),
    ]
    sums = release / "SHA256SUMS"
    bad: list[str] = []
    count = 0
    try:
        for line in sums.read_text(encoding="utf-8").splitlines():
            match = _SUM_LINE.fullmatch(line)
            if match is None:
                bad.append(f"unparsable: {line[:40]}")
                continue
            digest, rel = match.groups()
            count += 1
            actual = hashlib.sha256((release / rel).read_bytes()).hexdigest()
            if actual != digest:
                bad.append(rel)
    except OSError as exc:
        bad.append(f"{sums}: {exc}")
    results.append(
        ok(
            "release files match SHA256SUMS",
            count > 0 and not bad,
            f"{count} files; bad: {bad[:5]}",
        )
    )
    unit_copy = release / "deploy" / "systemd" / "maplegotchi.service"
    try:
        same = UNIT_FILE.read_bytes() == unit_copy.read_bytes()
    except OSError:
        same = False
    results.append(ok("installed unit matches the release's unit", same))
    return results


def find_maple_pids() -> list[int]:
    pids = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            argv = (entry / "cmdline").read_bytes().split(b"\0")
        except OSError:
            continue
        if b"maplegotchi.cli" in argv and b"run" in argv:
            pids.append(int(entry.name))
    return pids


def check_process(uid: int, gid: int) -> list[Result]:
    pids = find_maple_pids()
    if len(pids) != 1:
        return [Result("FAIL", "exactly one Maple process", str(pids))]
    status = parse_proc_status(Path(f"/proc/{pids[0]}/status").read_text(encoding="utf-8"))
    return [Result("INFO", "Maple pid", str(pids[0])), *evaluate_process(status, uid, gid)]


def check_sockets(uid: int) -> list[Result]:
    listeners = []
    for name, v6 in (("tcp", False), ("tcp6", True)):
        try:
            listeners += parse_listeners(
                Path(f"/proc/net/{name}").read_text(encoding="utf-8"), ipv6=v6
            )
        except OSError:
            pass
    return evaluate_listeners(listeners, uid)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> None:
        return None


def _get(path: str, headers: Mapping[str, str] | None = None) -> tuple[int, dict[str, str], bytes]:
    if path not in {"/api/health", "/", "/api/docs", "/api/snapshot"}:
        raise ValueError("not an allowlisted read-only endpoint")
    request = urllib.request.Request(BASE + path, headers=dict(headers or {}), method="GET")  # noqa: S310
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        with opener.open(request, timeout=10) as response:
            return (
                response.status,
                {k.lower(): v for k, v in response.headers.items()},
                response.read(),
            )
    except urllib.error.HTTPError as err:
        with err:
            return err.code, {k.lower(): v for k, v in err.headers.items()}, b""


def check_http() -> tuple[list[Result], dict[str, Any] | None]:
    results = []
    try:
        code, _, _ = _get("/api/health")
        results.append(ok("GET /api/health", code == 200, str(code)))
        code, headers, body = _get("/", {"Origin": "https://evil.example"})
        results.append(
            ok(
                "frontend served by the backend",
                code == 200 and b"<" in body[:64],
            )
        )
        for name, value in REQUIRED_HEADERS.items():
            results.append(ok(f"header {name}", headers.get(name) == value))
        results.append(
            ok(
                "header content-security-policy",
                "default-src 'self'" in headers.get("content-security-policy", ""),
            )
        )
        # GET does NOT prove POST Origin rejection. Isolated tests cover that:
        # test_untrusted_origins_are_refused_without_side_effects
        # test_production_origin_is_the_configured_one_only
        results.append(
            ok(
                "untrusted Origin receives no CORS permission headers",
                not any(k.startswith("access-control-") for k in headers),
            )
        )
        code, _, body = _get("/api/docs")
        results.append(ok("no API docs in production", code == 404, str(code)))
        code, _, body = _get("/api/snapshot")
        snapshot: dict[str, Any] = json.loads(body)
        results.append(ok("GET /api/snapshot", code == 200))
        return results, snapshot
    except (OSError, ValueError):
        results.append(Result("FAIL", "HTTP on 127.0.0.1:8470", "request or decoding failed"))
        return results, None


def run_all(record: Path | None, compare: Path | None) -> list[Result]:
    passwd = parse_passwd(Path("/etc/passwd").read_text(encoding="utf-8"))
    groups = parse_group(Path("/etc/group").read_text(encoding="utf-8"))
    results = evaluate_account(passwd, groups)
    account = passwd.get(ACCOUNT)
    if account is None:
        return results
    results += check_files(account.uid, account.gid)
    results += check_release()
    results += check_process(account.uid, account.gid)
    results += check_sockets(account.uid)
    http, snapshot = check_http()
    results += http
    if snapshot is not None:
        results += evaluate_snapshot(snapshot)
        # Identity is private evidence for explicit record/compare work only.
        # Do not print its fields during an ordinary production boundary check.
        current = identity_record(snapshot) if record is not None or compare is not None else {}
        if record is not None:
            record.write_text(json.dumps(current), encoding="utf-8")
            results.append(Result("INFO", "recorded identity", str(record)))
        if compare is not None:
            results += compare_identity(json.loads(compare.read_text(encoding="utf-8")), current)
    return results


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="check_boundaries")
    parser.add_argument("--record", type=Path, help="save identity/revision to this file")
    parser.add_argument("--compare", type=Path, help="compare with a previously recorded file")
    args = parser.parse_args(argv)
    if not IS_LINUX:
        print("check_boundaries runs on paolo-core (Linux) only", file=sys.stderr)
        return 2
    results = run_all(args.record, args.compare)
    for result in results:
        print(result)
    failed = [r for r in results if r.status == "FAIL"]
    owner_checks = sum(r.status == "OWNER_CHECK" for r in results)
    print(
        f"\n{len(results)} checks, {len(failed)} failed, "
        f"{sum(r.status == 'WARN' for r in results)} warnings, {owner_checks} owner checks"
    )
    command = owner_stat_command(results)
    if command is not None:
        cmd, lines = command
        print("\nOWNER_CHECK: these paths are protected from this user by design. Run:")
        print(f"  {cmd}")
        print("and confirm the output is exactly:")
        for line in lines:
            print(f"  {line}")
    print("Also run by hand: tailscale serve status; tailscale funnel status; sandbox_probe.sh")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
