"""Owner-run OD-01 helper; only the namespace child creates probe-only files.

No application imports, database access, Docker connections, or service changes.
Root is granted manually. Child source travels via stdin, never an installed file.
"""

from __future__ import annotations

import errno
import os
import re
import secrets
import signal
import socket
import stat
import subprocess  # noqa: TID251 -- owner tooling, not application code
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import FrameType
from typing import TYPE_CHECKING

PROTECTED = tuple(
    map(
        Path,
        (
            "/opt/maplegotchi",
            "/opt/maplegotchi/current",
            "/opt/maplegotchi/current/venv/bin",
            "/opt/maplegotchi/python",
            "/etc/maplegotchi",
            "/etc/systemd/system",
            "/data/monitor",
            "/data",
            "/usr",
            "/var/lib",
            "/",
        ),
    )
)
DENIALS = {errno.EROFS, errno.EACCES, errno.EPERM}
MARKER = b"OD-01 probe-only\n"
SIGNALS = tuple(
    dict.fromkeys((signal.SIGINT, signal.SIGTERM, getattr(signal, "SIGHUP", signal.SIGTERM)))
)


@contextmanager
def creation_window() -> Iterator[None]:
    # Registration must finish before a catchable signal triggers cleanup.
    if sys.platform != "win32" and hasattr(signal, "pthread_sigmask"):
        previous = signal.pthread_sigmask(signal.SIG_BLOCK, SIGNALS)
        try:
            yield
        finally:
            signal.pthread_sigmask(signal.SIG_SETMASK, previous)
    else:  # portable unit tests only; production entry point requires Linux
        yield


def require(condition: bool, label: str) -> None:
    if not condition:
        raise RuntimeError(label)


class ProbeFiles:
    """Track successful creations only; never delete collisions or existing files."""

    def __init__(self) -> None:
        self.files: list[Path] = []
        self.directories: list[Path] = []
        self.fds: set[int] = set()
        self.identities: dict[Path, tuple[int, int]] = {}

    def create(self, path: Path) -> int:
        print(f"[PROBE-ONLY] candidate {path}", flush=True)
        with creation_window():
            fd = os.open(
                path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0), 0o600
            )
            self.files.append(path)
            self.fds.add(fd)
            metadata = os.fstat(fd)
            self.identities[path] = metadata.st_dev, metadata.st_ino
        return fd

    def close(self, fd: int) -> None:
        with creation_window():
            os.close(fd)
            self.fds.remove(fd)

    def cleanup(self) -> None:
        for fd in tuple(self.fds):
            self.close(fd)
        for path in reversed(self.files):
            if self.still_owned(path):
                path.unlink()
            require(not path.exists() and not path.is_symlink(), f"cleanup failed: {path}")
        self.files.clear()
        for path in reversed(self.directories):
            if self.still_owned(path):
                path.rmdir()
            require(not path.exists() and not path.is_symlink(), f"cleanup failed: {path}")
        self.directories.clear()
        self.identities.clear()

    def still_owned(self, path: Path) -> bool:
        try:
            metadata = path.lstat()
        except FileNotFoundError:
            return False
        require(
            not stat.S_ISLNK(metadata.st_mode)
            and self.identities.get(path) == (metadata.st_dev, metadata.st_ino),
            f"probe path replaced or identity unavailable; refusing cleanup: {path}",
        )
        return True

    def round_trip(self, parent: Path) -> None:
        directory = parent / (".od01-probe-" + secrets.token_hex(16))
        print(f"[PROBE-ONLY] candidate {directory}", flush=True)
        with creation_window():
            directory.mkdir(mode=0o700)
            self.directories.append(directory)
            metadata = directory.lstat()
            self.identities[directory] = metadata.st_dev, metadata.st_ino
        require(stat.S_IMODE(directory.stat().st_mode) == 0o700, "probe directory mode")
        path = directory / "sentinel"
        fd = self.create(path)
        try:
            require(stat.S_IMODE(os.fstat(fd).st_mode) == 0o600, "sentinel mode")
            require(os.write(fd, MARKER) == len(MARKER), "short sentinel write")
        finally:
            self.close(fd)
        require(path.read_bytes() == MARKER, "sentinel round-trip")
        self.cleanup()

    def denied(self, directory: Path) -> None:
        path = directory / (".od01-deny-" + secrets.token_hex(16))
        try:
            fd = self.create(path)
        except OSError as exc:
            if exc.errno is None or exc.errno not in DENIALS:
                raise RuntimeError(f"unexpected create errno at {directory}: {exc.errno}") from exc
            print(f"[PASS] create denied at {directory}: {errno.errorcode[exc.errno]}")
            return
        self.close(fd)
        self.cleanup()
        raise RuntimeError(f"forbidden creation succeeded at {directory}; removed")


def interrupted(signum: int, frame: FrameType | None) -> None:
    raise RuntimeError(f"interrupted by signal {signum}")


def inside(namespace: str, uid: int, gid: int) -> None:
    require(sys.platform.startswith("linux"), "Linux only")
    # Keep Unix-only APIs inside the platform boundary for static checking.
    if TYPE_CHECKING and sys.platform != "linux":
        raise RuntimeError("Linux only")
    else:
        require(os.geteuid() == uid and os.getegid() == gid, "wrong helper identity")
        require(not os.getgroups(), "helper supplementary groups are not empty")
        require(str(Path("/proc/self/ns/mnt").readlink()) == namespace, "wrong mount namespace")
        os.umask(0o077)
        owned = ProbeFiles()
        for sig in SIGNALS:
            signal.signal(sig, interrupted)
        try:
            require(
                sorted(p.name for p in Path("/data").iterdir()) == ["maple", "monitor"],
                "unexpected /data visibility",
            )
            for path in ("/home/paolo", "/root", "/run/docker.sock", "/var/run/docker.sock"):
                require(
                    not os.access(path, os.R_OK) and not os.access(path, os.W_OK),
                    f"accessible protected path: {path}",
                )
            require(not Path("/proc/1/status").exists(), "other users' processes visible")
            require(
                stat.S_ISSOCK(Path("/run/dbus/system_bus_socket").stat().st_mode),
                "system D-Bus socket missing (not a polkit denial test)",
            )
            for path in ("/data/monitor/metrics.db", "/etc/maplegotchi/maplegotchi.env"):
                require(
                    os.access(path, os.R_OK) and not os.access(path, os.W_OK),
                    f"expected read-only permission: {path}",
                )
            # EACCES alone does not prove a read-only mount.
            for directory in PROTECTED:
                require(directory.is_dir(), f"missing protected directory: {directory}")
                require(
                    bool(os.statvfs(directory).f_flag & os.ST_RDONLY),
                    f"mount not read-only: {directory}",
                )
                require(
                    not os.access(directory, os.W_OK), f"writable protected directory: {directory}"
                )
                owned.denied(directory)
            require(not (os.statvfs("/data/maple").f_flag & os.ST_RDONLY), "data mount read-only")
            owned.round_trip(Path("/data/maple"))
        finally:
            for sig in SIGNALS:
                signal.signal(sig, signal.SIG_IGN)
            owned.cleanup()
        print("[PASS] namespace checks and exact-path cleanup")


def command(args: list[str]) -> str:
    return subprocess.check_output(args, text=True).strip()  # noqa: S603


def snapshot(expected: str) -> tuple[int, str, str, str]:
    require(
        command(["/usr/bin/systemctl", "is-active", "maplegotchi.service"]) == "active",
        "service is not active",
    )
    pid = int(command(["/usr/bin/systemctl", "show", "-P", "MainPID", "maplegotchi.service"]))
    require(pid > 1, "invalid service PID")
    proc = Path(f"/proc/{pid}")
    # Field 22; comm (field 2) can contain spaces and closing parentheses.
    start = (proc / "stat").read_text().rsplit(")", 1)[1].split()[19]
    release = str(Path("/opt/maplegotchi/current").resolve(strict=True))
    require(release == f"/opt/maplegotchi/releases/{expected}", "unexpected current release")
    argv = (proc / "cmdline").read_bytes().split(b"\0")
    require(b"maplegotchi.cli" in argv and b"run" in argv, "unexpected service command")
    require(str((proc / "cwd").resolve()) == "/", "unexpected service working directory")
    return pid, start, release, str((proc / "ns/mnt").readlink())


def run_child(args: list[str], source: str) -> None:
    # subprocess.run would kill the helper on KeyboardInterrupt before cleanup.
    # Defer parent signals until the child has exited; never kill it on timeout.
    received: list[int] = []

    def defer(signum: int, frame: FrameType | None) -> None:
        received.append(signum)

    previous = {sig: signal.signal(sig, defer) for sig in SIGNALS}
    try:
        result = subprocess.run(args, input=source, text=True, check=False)  # noqa: S603
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    require(result.returncode == 0, "namespace probe failed; inspect cleanup evidence")
    require(not received, "parent interrupted; child finished, run is incomplete")


def host(expected: str) -> None:
    require(sys.platform.startswith("linux"), "Linux only")
    # Keep Unix-only APIs inside the platform boundary for static checking.
    if TYPE_CHECKING and sys.platform != "linux":
        raise RuntimeError("Linux only")
    else:
        import pwd

        import check_boundaries as cb

        require(os.geteuid() == 0, "owner must explicitly run with sudo; no automatic escalation")
        require(socket.gethostname().split(".")[0] == "paolo-core", "wrong host")
        require(
            re.fullmatch(r"[0-9a-f]{40}", expected) is not None, "expected release must be 40 hex"
        )
        account = pwd.getpwnam("maple-svc")
        before = snapshot(expected)
        print(
            f"[EVIDENCE] pid={before[0]} start={before[1]} release={before[2]} mnt={before[3]}",
            flush=True,
        )

        def runtime() -> None:
            status = cb.parse_proc_status(Path(f"/proc/{before[0]}/status").read_text())
            results = cb.evaluate_process(status, account.pw_uid, account.pw_gid)
            # evaluate_process permits only the primary GID in Groups (or an empty
            # list). The namespace helper separately requires --clear-groups.
            listeners = []
            for name, v6 in (("tcp", False), ("tcp6", True)):
                listeners.extend(cb.parse_listeners(Path(f"/proc/net/{name}").read_text(), ipv6=v6))
            results.extend(cb.evaluate_listeners(listeners, account.pw_uid))
            for port in (8470, 8471):
                addresses = [a for a, p, _ in listeners if p == port]
                require(
                    bool(addresses) and all(cb.is_loopback(a) for a in addresses),
                    f"port {port} missing or exposed beyond loopback",
                )
            for result in results:
                print(result, flush=True)
                require(result.status == "PASS", result.check)

        runtime()
        require(snapshot(expected) == before, "service changed before namespace entry")
        # Drop groups/capabilities before Python. No source file installed on the host.
        run_child(
            [
                "/usr/bin/nsenter",
                "--target",
                str(before[0]),
                "--mount",
                "--",
                "/usr/bin/setpriv",
                f"--reuid={account.pw_uid}",
                f"--regid={account.pw_gid}",
                "--clear-groups",
                "--bounding-set=-all",
                "--inh-caps=-all",
                "--ambient-caps=-all",
                "--no-new-privs",
                "/usr/bin/python3",
                "-I",
                "-B",
                "-",
                "--inside",
                before[3],
                str(account.pw_uid),
                str(account.pw_gid),
            ],
            Path(__file__).read_text(encoding="utf-8"),
        )
        require(snapshot(expected) == before, "service changed during probe")
        runtime()
        require(snapshot(expected) == before, "service changed during final checks")
        print("sandbox_probe: PASS (no polkit denial or cgroup network filtering claim)")


def main() -> int:
    try:
        require(sys.platform.startswith("linux"), "Linux only")
        if len(sys.argv) == 5 and sys.argv[1] == "--inside":
            inside(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]))
        else:
            require(len(sys.argv) == 2, "usage: sandbox_probe.sh <expected deployed release>")
            host(sys.argv[1])
        return 0
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
        print(f"[FAIL/STOP] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
