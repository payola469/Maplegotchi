#!/usr/bin/env python3
"""Read-only survey of paolo-core for Maplegotchi Phase 3 (D11, D12, D15).

What it does: reads files under /etc, /proc, /sys, /usr/lib and /run, and opens
the monitoring database read-only (SQLite `mode=ro` + `query_only`). It prints
one JSON report to stdout.

What it never does: write, create, delete, or chmod anything; run commands or
subprocesses; start, stop, or restart services; install anything; use the
network. Standard library only; runs as an ordinary (non-root) user.

Usage:
    python3 survey_paolo_core.py [--metrics-db /data/monitor/metrics.db] [--samples 3] > survey.json

Review the output before sharing: sample rows may contain values you consider
private. Use --samples 0 to omit them.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import sqlite3
import stat
import sys
from pathlib import Path
from typing import Any

UNIT_DIRS = (
    "/etc/systemd/system",
    "/run/systemd/system",
    "/usr/local/lib/systemd/system",
    "/usr/lib/systemd/system",
    "/lib/systemd/system",
)
# D12 intent, as search keywords (matched case-insensitively against unit file names).
UNIT_KEYWORDS = (
    "maple",
    "metric",
    "monitor",
    "collector",
    "grafana",
    "lycan",
    "qbittorrent",
    "jellyfin",
    "backup",
    "integrity",
    "borg",
    "restic",
    "rsync",
    "snapshot",
    "scrub",
)
DATA_PATHS = ("/data", "/data/maple", "/data/monitor", "/data/monitor/metrics.db")
MAX_SAMPLES = 10
MAX_TEXT = 200


def _read(path: str | Path, limit: int = 4096) -> str | None:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")[:limit].strip()
    except OSError:
        return None


def _safe(value: object) -> object:
    if isinstance(value, bytes):
        return f"<{len(value)} bytes> {value[:32].hex()}"
    if isinstance(value, str) and len(value) > MAX_TEXT:
        return value[:MAX_TEXT] + "..."
    return value


def _stat(path: str) -> dict[str, Any]:
    try:
        st = Path(path).stat()
    except OSError as exc:
        return {"exists": False, "error": type(exc).__name__}
    return {
        "exists": True,
        "type": "dir" if stat.S_ISDIR(st.st_mode) else "file",
        "uid": st.st_uid,
        "gid": st.st_gid,
        "mode": oct(stat.S_IMODE(st.st_mode)),
        "size": st.st_size,
    }


def survey_host() -> dict[str, Any]:
    os_release = {}
    for line in (_read("/etc/os-release") or "").splitlines():
        key, _, value = line.partition("=")
        if key in {"NAME", "VERSION", "ID", "VERSION_ID", "PRETTY_NAME"}:
            os_release[key] = value.strip('"')
    try:
        localtime = str(Path("/etc/localtime").readlink())
    except OSError:
        localtime = None
    return {
        "platform": platform.platform(),
        "kernel": platform.release(),
        "machine": platform.machine(),
        "python": sys.version.split()[0],
        "sqlite": sqlite3.sqlite_version,
        "os_release": os_release,
        "cpu_count": os.cpu_count(),
        "loadavg": _read("/proc/loadavg"),
        "uptime_seconds": (_read("/proc/uptime") or "").split(" ")[0] or None,
        "mem_total": next(
            (
                line
                for line in (_read("/proc/meminfo") or "").splitlines()
                if line.startswith("MemTotal")
            ),
            None,
        ),
        "timezone": _read("/etc/timezone"),
        "localtime_link": localtime,
        "psutil_installed": importlib.util.find_spec("psutil") is not None,
    }


def survey_filesystems() -> dict[str, Any]:
    mounts = []
    for line in (_read("/proc/mounts", limit=1_000_000) or "").splitlines():
        parts = line.split()
        if len(parts) >= 3:
            mounts.append((parts[1], parts[2], parts[0]))
    result: dict[str, Any] = {}
    for path in DATA_PATHS:
        info = _stat(path)
        matching = [m for m in mounts if path == m[0] or path.startswith(m[0].rstrip("/") + "/")]
        if matching:
            mount_point, fs_type, device = max(matching, key=lambda m: len(m[0]))
            info["mount"] = {"mount_point": mount_point, "fs_type": fs_type, "device": device}
        if hasattr(os, "statvfs") and info.get("type") == "dir":
            vfs = os.statvfs(path)
            info["free_percent"] = (
                round(100 * vfs.f_bavail / vfs.f_blocks, 1) if vfs.f_blocks else None
            )
        result[path] = info
    return result


def survey_temperatures() -> dict[str, Any]:
    hwmon = []
    for chip in sorted(Path("/sys/class/hwmon").glob("hwmon*")):
        sensors = []
        for reading in sorted(chip.glob("temp*_input")):
            raw = _read(reading)
            label = _read(str(reading).replace("_input", "_label"))
            sensors.append({"input": reading.name, "label": label, "millicelsius": raw})
        hwmon.append({"path": str(chip), "name": _read(chip / "name"), "sensors": sensors})
    zones = [
        {"path": str(z), "type": _read(z / "type"), "millicelsius": _read(z / "temp")}
        for z in sorted(Path("/sys/class/thermal").glob("thermal_zone*"))
    ]
    return {"hwmon": hwmon, "thermal_zones": zones}


def survey_units() -> dict[str, Any]:
    found: dict[str, dict[str, Any]] = {}
    for directory in UNIT_DIRS:
        base = Path(directory)
        if not base.is_dir():
            continue
        for entry in sorted(base.iterdir()):
            name = entry.name
            if not name.endswith((".service", ".timer")):
                continue
            if not any(k in name.lower() for k in UNIT_KEYWORDS):
                continue
            item = found.setdefault(name, {"files": [], "enabled_in": [], "has_cgroup": False})
            item["files"].append(
                {
                    "path": str(entry),
                    "symlink_to": str(entry.readlink()) if entry.is_symlink() else None,
                }
            )
    wants_root = Path("/etc/systemd/system")
    if wants_root.is_dir():
        for wants in sorted(wants_root.glob("*.wants")):
            for entry in wants.iterdir():
                if entry.name in found:
                    found[entry.name]["enabled_in"].append(wants.name)
    for name, item in found.items():
        item["has_cgroup"] = Path("/sys/fs/cgroup/system.slice", name).exists()
        if name.endswith(".timer"):
            stamp = Path("/var/lib/systemd/timers", f"stamp-{name}")
            item["timer_stamp_mtime"] = stamp.stat().st_mtime if stamp.exists() else None
    return {"keywords": list(UNIT_KEYWORDS), "units": found}


def _quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def survey_metrics_db(path: Path, samples: int = 3) -> dict[str, Any]:
    report: dict[str, Any] = {"path": str(path), **_stat(str(path))}
    report["sidecars"] = {s: Path(f"{path}{s}").exists() for s in ("-wal", "-shm", "-journal")}
    if not report["exists"]:
        return report
    samples = max(0, min(samples, MAX_SAMPLES))
    try:
        conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True, isolation_level=None)
    except sqlite3.Error as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
        return report
    try:
        conn.execute("PRAGMA query_only = ON")
        report["opened_read_only"] = conn.execute("PRAGMA query_only").fetchone()[0] == 1
        report["journal_mode"] = conn.execute("PRAGMA journal_mode").fetchone()[0]
        report["user_version"] = conn.execute("PRAGMA user_version").fetchone()[0]
        report["application_id"] = conn.execute("PRAGMA application_id").fetchone()[0]
        report["objects"] = [
            {"type": t, "name": n, "table": tbl, "sql": _safe(sql)}
            for t, n, tbl, sql in conn.execute(
                "SELECT type, name, tbl_name, sql FROM sqlite_master ORDER BY type, name"
            )
        ]
        tables = []
        for (name,) in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            " ORDER BY name"
        ).fetchall():
            columns = [
                {"name": c, "type": t, "not_null": bool(nn), "pk": bool(pk)}
                for c, t, nn, pk in conn.execute(
                    'SELECT name, type, "notnull", pk FROM pragma_table_info(?) ORDER BY cid',
                    (name,),
                )
            ]
            table: dict[str, Any] = {"name": name, "columns": columns}
            table["rows"] = conn.execute(f"SELECT count(*) FROM {_quote(name)}").fetchone()[0]  # noqa: S608 - quoted identifier from sqlite_master
            time_like = [
                c["name"]
                for c in columns
                if any(k in c["name"].lower() for k in ("time", "ts", "date"))
            ]
            table["time_ranges"] = {
                col: list(conn.execute(
                    f"SELECT min({_quote(col)}), max({_quote(col)}) FROM {_quote(name)}"  # noqa: S608
                ).fetchone())
                for col in time_like
            }  # fmt: skip
            if samples:
                try:
                    newest = f"SELECT * FROM {_quote(name)} ORDER BY rowid DESC LIMIT ?"  # noqa: S608
                    rows = conn.execute(newest, (samples,)).fetchall()
                except sqlite3.OperationalError:  # WITHOUT ROWID table
                    any_rows = f"SELECT * FROM {_quote(name)} LIMIT ?"  # noqa: S608
                    rows = conn.execute(any_rows, (samples,)).fetchall()
                table["sample_rows"] = [[_safe(v) for v in row] for row in rows]
            tables.append(table)
        report["tables"] = tables
    except sqlite3.Error as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        conn.close()
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--metrics-db", type=Path, default=Path("/data/monitor/metrics.db"))
    parser.add_argument("--samples", type=int, default=3, help=f"rows per table, 0..{MAX_SAMPLES}")
    args = parser.parse_args(argv)
    report = {
        "survey_version": 1,
        "host": survey_host(),
        "filesystems": survey_filesystems(),
        "temperatures": survey_temperatures(),
        "systemd_units": survey_units(),
        "metrics_db": survey_metrics_db(args.metrics_db, samples=args.samples),
    }
    json.dump(report, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
