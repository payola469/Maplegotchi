"""The exact Maple block + restic argument, run inside a replica of paolo-core-backup.

The replica has the real script's shape (bash, `set -Eeuo pipefail`, an ERR trap,
`RUN_DIR` from mktemp under STAGING_BASE, existing SQLite staging for n8n /
Grafana / metrics, a final restic call with explicit path arguments). The Maple
text is inserted verbatim from deploy/backup/maple-block.bash, and `check_patch.sh`
must accept the result. Needs bash (Linux CI; Git Bash on Windows).
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess  # noqa: TID251 - tests drive the owner's bash backup script
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

from tests.persistence_support import new_life, run_ticks

REPO = Path(__file__).resolve().parents[3]
BACKUP = REPO / "deploy" / "backup"
BLOCK = (BACKUP / "maple-block.bash").read_text(encoding="utf-8")
HELPER = BACKUP / "maple_db_snapshot.py"
CHECK_PATCH = BACKUP / "check_patch.sh"
RESTIC_ARG = '    ${MAPLE_DB_STAGED:+"$MAPLE_DB_STAGED"} \\\n'
BASH = shutil.which("bash")

pytestmark = pytest.mark.skipif(BASH is None, reason="bash is not available")

ORIGINAL = """#!/usr/bin/env bash
set -Eeuo pipefail
trap 'echo "backup FAILED at line $LINENO" >&2' ERR

REPO="/data/backups/paolo-core-restic"
PASSWORD_FILE="/etc/paolo-core/backup/restic-password"
STAGING_BASE="@STAGING@"
mkdir -p "$STAGING_BASE"
RUN_DIR="$(mktemp -d "$STAGING_BASE/run.XXXXXX")"
echo "RUN_DIR=$RUN_DIR"

# existing SQLite backup API staging (stand-ins)
printf 'n8n' > "$RUN_DIR/n8n.sqlite"
printf 'grafana' > "$RUN_DIR/grafana.db"
printf 'metrics' > "$RUN_DIR/metrics.db"
@INSERT@
restic() { printf '%s\\n' "$@" > "@ARGS@"; }
restic -r "$REPO" --password-file "$PASSWORD_FILE" backup \\
    "$RUN_DIR/n8n.sqlite" \\
    "$RUN_DIR/grafana.db" \\
    "$RUN_DIR/metrics.db" \\
@ARG@    /etc/paolo-core
echo "backup finished"
"""


def posix(path: Path) -> str:
    return path.as_posix()


@dataclass
class Scripts:
    original: Path
    patched: Path
    args: Path
    staging: Path


def write_scripts(tmp_path: Path, source: Path) -> Scripts:
    staging = tmp_path / "staging"
    args = tmp_path / "restic-args.txt"
    common = ORIGINAL.replace("@STAGING@", posix(staging)).replace("@ARGS@", posix(args))
    original = tmp_path / "paolo-core-backup.pre-maple"
    original.write_bytes(common.replace("@INSERT@\n", "").replace("@ARG@", "").encode())
    patched = tmp_path / "paolo-core-backup"
    patched.write_bytes(common.replace("@INSERT@\n", BLOCK).replace("@ARG@", RESTIC_ARG).encode())
    # For the run only: point the block at the test database and this helper.
    runnable = tmp_path / "run-backup"
    helper = f'"{posix(Path(sys.executable))}" "{posix(HELPER)}"'
    text = patched.read_text(encoding="utf-8")
    text = text.replace(
        'MAPLE_DB_SOURCE="/data/maple/maple.db"', f'MAPLE_DB_SOURCE="{posix(source)}"'
    )
    text = text.replace("/usr/local/sbin/maple-db-snapshot stage", f"{helper} stage")
    runnable.write_bytes(text.encode())
    return Scripts(original, patched, args, staging)


def run(script: Path) -> subprocess.CompletedProcess[str]:
    assert BASH is not None
    return subprocess.run(  # noqa: S603 - fixed argv, test-owned script
        [BASH, posix(script)], capture_output=True, text=True, timeout=120, check=False
    )


def run_dir(out: str) -> Path:
    line = next(line for line in out.splitlines() if line.startswith("RUN_DIR="))
    return Path(line.removeprefix("RUN_DIR="))


def test_missing_maple_db_is_skipped_and_the_backup_still_succeeds(tmp_path: Path) -> None:
    s = write_scripts(tmp_path, tmp_path / "maple" / "maple.db")  # never created
    result = run(tmp_path / "run-backup")
    assert result.returncode == 0, result.stderr
    assert "Maple not deployed" in result.stdout and "backup finished" in result.stdout
    args = s.args.read_text(encoding="utf-8").splitlines()
    assert not any(a.endswith("maple.db") for a in args)
    assert [a.rsplit("/", 1)[-1] for a in args if "/run." in a] == [
        "n8n.sqlite", "grafana.db", "metrics.db",
    ]  # fmt: skip


def test_live_maple_db_is_staged_verified_and_backed_up(tmp_path: Path) -> None:
    data_dir, clock, runtime = new_life(tmp_path)
    run_ticks(runtime, clock, 4)  # runtime stays open: a live WAL database
    try:
        s = write_scripts(tmp_path, data_dir.root / "maple.db")
        result = run(tmp_path / "run-backup")
    finally:
        runtime.close()
    assert result.returncode == 0, result.stderr
    staged = run_dir(result.stdout) / "maple.db"
    args = s.args.read_text(encoding="utf-8").splitlines()
    assert args[-2:] == [posix(staged), "/etc/paolo-core"]  # added only on success
    # The staged artifact: integrity exactly ok, private, self-contained, a Maple life.
    conn = sqlite3.connect(f"{staged.as_uri()}?mode=ro", uri=True)
    try:
        assert conn.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
        assert conn.execute("SELECT name FROM maple").fetchone()[0] == "Maple"
        assert conn.execute("SELECT tick_counter FROM life_state").fetchone()[0] == 4
    finally:
        conn.close()
    assert sorted(p.name for p in staged.parent.iterdir()) == [
        "grafana.db", "maple.db", "metrics.db", "n8n.sqlite",
    ]  # fmt: skip
    if sys.platform != "win32":
        assert staged.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("damage", ["corrupt", "not_a_database", "directory"])
def test_existing_but_bad_maple_db_fails_the_whole_backup(tmp_path: Path, damage: str) -> None:
    data_dir, clock, runtime = new_life(tmp_path)
    run_ticks(runtime, clock, 3)
    runtime.close()
    source = data_dir.root / "maple.db"
    if damage == "corrupt":
        raw = bytearray(source.read_bytes())
        page = int.from_bytes(raw[16:18], "big")
        raw[page + 100 : 3 * page] = b"\xa5" * (3 * page - page - 100)
        source.write_bytes(bytes(raw))
    elif damage == "not_a_database":
        source.write_bytes(b"this is not sqlite" * 300)
    else:
        source = tmp_path / "dir-instead" / "maple.db"
        source.mkdir(parents=True)
    s = write_scripts(tmp_path, source)
    result = run(tmp_path / "run-backup")
    assert result.returncode != 0
    assert "backup FAILED" in result.stderr  # the script's own ERR path fired
    assert "backup finished" not in result.stdout
    assert not s.args.exists()  # restic never ran
    assert not (run_dir(result.stdout) / "maple.db").exists()


def test_check_patch_accepts_exactly_this_patch(tmp_path: Path) -> None:
    s = write_scripts(tmp_path, tmp_path / "absent.db")
    helper = tmp_path / "maple-db-snapshot"
    helper.write_text("#!/bin/sh\n", encoding="utf-8")
    helper.chmod(0o755)
    assert BASH is not None
    env_helper = {"MAPLE_DB_SNAPSHOT": posix(helper)}

    def check(patched: Path) -> subprocess.CompletedProcess[str]:
        cmd = [
            BASH,
            posix(CHECK_PATCH),
            posix(patched),
            posix(s.original),
            posix(BACKUP / "maple-block.bash"),
        ]
        return subprocess.run(  # noqa: S603 - fixed argv
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
            env={**os.environ, **env_helper},
        )

    good = check(s.patched)
    assert good.returncode == 0, good.stdout
    assert "[FAIL]" not in good.stdout

    tampered = tmp_path / "tampered"
    tampered.write_bytes(s.patched.read_bytes().replace(b'"$RUN_DIR/grafana.db" \\\n', b""))
    bad = check(tampered)
    assert bad.returncode == 1 and "no original line removed" in bad.stdout

    misplaced = tmp_path / "misplaced"
    text = s.patched.read_text(encoding="utf-8").replace(RESTIC_ARG, "")
    misplaced.write_bytes((text + RESTIC_ARG).encode())
    assert check(misplaced).returncode == 1
