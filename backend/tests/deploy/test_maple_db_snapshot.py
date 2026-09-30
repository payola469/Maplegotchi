"""The backup helper stages a verified, self-contained copy of a LIVE Maple database."""

from __future__ import annotations

import hashlib
import importlib.util
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from tests.persistence_support import new_life, run_ticks
from tests.security.forbidden_apis import FORBIDDEN_BUILTINS, FORBIDDEN_MODULES

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "deploy" / "backup" / "maple_db_snapshot.py"


def load() -> Any:
    spec = importlib.util.spec_from_file_location("maple_db_snapshot", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


snapshot = load()


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_stages_a_live_wal_database_consistently(tmp_path: Path) -> None:
    data_dir, clock, runtime = new_life(tmp_path)
    run_ticks(runtime, clock, 5)  # the runtime stays open: a live WAL database
    source = data_dir.root / "maple.db"
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    dest = run_dir / "maple.db"
    try:
        assert snapshot.main(["stage", "--source", str(source), "--dest", str(dest)]) == 0
        run_ticks(runtime, clock, 2)  # Maple keeps living while/after the copy is taken
    finally:
        runtime.close()

    # Self-contained single file: rollback-journal mode, no sidecars, private.
    assert sorted(p.name for p in run_dir.iterdir()) == ["maple.db"]
    with dest.open("rb") as f:
        header = f.read(20)
    assert header[:16] == b"SQLite format 3\x00" and header[18:20] == b"\x01\x01"
    summary = snapshot.verify(dest)
    assert summary["integrity"] == "ok" and summary["name"] == "Maple"
    assert summary["user_version"] >= 3 and summary["journal_mode"] == "delete"
    # The copy is the life as of the snapshot, and it opens independently.
    conn = sqlite3.connect(f"{dest.as_uri()}?mode=ro", uri=True)
    try:
        (ticks,) = conn.execute("SELECT tick_counter FROM life_state").fetchone()
    finally:
        conn.close()
    assert ticks == 5  # the copy is the life as of the snapshot, not the later ticks
    assert snapshot.main(["verify", str(dest)]) == 0


def test_source_is_never_modified(tmp_path: Path) -> None:
    data_dir, clock, runtime = new_life(tmp_path)
    run_ticks(runtime, clock, 3)
    runtime.close()  # quiescent, so bytes can be compared
    source = data_dir.root / "maple.db"
    before = {p.name: digest(p) for p in data_dir.root.iterdir() if p.is_file()}
    dest = tmp_path / "maple-staged.db"
    assert snapshot.main(["stage", "--source", str(source), "--dest", str(dest)]) == 0
    after = {p.name: digest(p) for p in data_dir.root.iterdir() if p.is_file()}
    assert after["maple.db"] == before["maple.db"]


def test_not_deployed_is_a_distinct_exit_code(tmp_path: Path) -> None:
    dest = tmp_path / "maple.db"
    code = snapshot.main(
        ["stage", "--source", str(tmp_path / "absent" / "maple.db"), "--dest", str(dest)]
    )
    assert code == snapshot.EXIT_NOT_DEPLOYED
    assert not dest.exists()


def test_deployed_but_missing_database_fails(tmp_path: Path) -> None:
    (tmp_path / "maple").mkdir()
    dest = tmp_path / "maple.db"
    code = snapshot.main(
        ["stage", "--source", str(tmp_path / "maple" / "maple.db"), "--dest", str(dest)]
    )
    assert code == snapshot.EXIT_FAILED
    assert not dest.exists()


@pytest.mark.parametrize("kind", ["garbage", "foreign", "unmigrated"])
def test_bad_sources_fail_and_leave_nothing(tmp_path: Path, kind: str) -> None:
    src_dir = tmp_path / "maple"
    src_dir.mkdir()
    source = src_dir / "maple.db"
    if kind == "garbage":
        source.write_bytes(b"not a database" * 200)
    else:
        conn = sqlite3.connect(source)
        conn.execute("CREATE TABLE t (x)")
        if kind == "unmigrated":
            conn.execute(f"PRAGMA application_id = {snapshot.APPLICATION_ID:d}")
        conn.commit()
        conn.close()
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    code = snapshot.main(["stage", "--source", str(source), "--dest", str(run_dir / "maple.db")])
    assert code == snapshot.EXIT_FAILED
    assert list(run_dir.iterdir()) == []


def test_existing_destination_is_never_overwritten(tmp_path: Path) -> None:
    data_dir, _clock, runtime = new_life(tmp_path)
    runtime.close()
    dest = tmp_path / "maple.db"
    dest.write_bytes(b"previous")
    code = snapshot.main(
        ["stage", "--source", str(data_dir.root / "maple.db"), "--dest", str(dest)]
    )
    assert code == snapshot.EXIT_FAILED
    assert dest.read_bytes() == b"previous"


def test_verify_detects_corruption(tmp_path: Path) -> None:
    data_dir, clock, runtime = new_life(tmp_path)
    run_ticks(runtime, clock, 3)
    runtime.close()
    dest = tmp_path / "copy.db"
    assert (
        snapshot.main(["stage", "--source", str(data_dir.root / "maple.db"), "--dest", str(dest)])
        == 0
    )
    raw = bytearray(dest.read_bytes())
    page_size = int.from_bytes(raw[16:18], "big")
    for i in range(page_size + 100, min(len(raw), 3 * page_size)):  # scribble on page 2..3
        raw[i] = 0xA5
    dest.write_bytes(bytes(raw))
    assert snapshot.main(["verify", str(dest)]) == snapshot.EXIT_FAILED


def test_helper_uses_no_process_execution() -> None:
    import ast

    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert not {a.name.split(".")[0] for a in node.names} & FORBIDDEN_MODULES
        elif isinstance(node, ast.ImportFrom) and node.module:
            assert node.module.split(".")[0] not in FORBIDDEN_MODULES
        elif isinstance(node, ast.Name):
            assert node.id not in FORBIDDEN_BUILTINS
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            assert f"{node.value.id}.{node.attr}" not in {"os.system", "os.popen"}
