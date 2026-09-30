"""Phase 3 boundaries: sensors read only; the external datasource cannot write (D18)."""

from __future__ import annotations

import ast
import importlib.util
import re
from pathlib import Path
from typing import Any

import pytest

from tests.security.forbidden_apis import is_external_path, is_storage_path, scan_source

SRC = Path(__file__).resolve().parents[2] / "src"
SENSORS = SRC / "maplegotchi" / "sensors"
EXTERNAL = SRC / "maplegotchi" / "storage" / "external"
REPO = Path(__file__).resolve().parents[3]
SURVEY = REPO / "deploy" / "survey" / "survey_paolo_core.py"

WRITE_SQL = re.compile(
    r"\b(INSERT|UPDATE|DELETE|REPLACE|CREATE|DROP|ALTER|ATTACH|DETACH|VACUUM|REINDEX)\b",
    re.IGNORECASE,
)


def imported_modules(path: Path) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            modules.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.add(node.module)
    return modules


def code_strings(path: Path) -> list[tuple[int, str]]:
    """String constants that are not docstrings."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                docstrings.add(id(body[0].value))
    return [
        (node.lineno, node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
    ]


def test_sensors_never_import_sqlite3_subprocess_or_writable_storage() -> None:
    files = sorted(SENSORS.rglob("*.py"))
    assert len(files) >= 10
    banned_prefixes = (
        "sqlite3",
        "subprocess",
        "pty",
        "multiprocessing",
        "shutil",
        "tempfile",
        "socket",
        "maplegotchi.storage.db",
        "maplegotchi.storage.repositories",
        "maplegotchi.storage.migrations",
        "maplegotchi.storage.datadir",
        "maplegotchi.storage.external.sqlite_metrics",
    )
    for path in files:
        for module in imported_modules(path):
            assert not module.startswith(banned_prefixes), f"{path.name} imports {module}"


def test_sensor_code_would_be_flagged_for_sqlite3_or_writes() -> None:
    sensor = SENSORS / "service_health" / "monitor_db.py"
    assert not is_storage_path(sensor) and not is_external_path(sensor)
    for source in ("import sqlite3", "import subprocess", "open('x', 'w')", "p.write_text('x')"):
        assert scan_source(source, str(sensor)), source


def test_external_package_may_read_sqlite_but_never_write() -> None:
    external = EXTERNAL / "sqlite_metrics.py"
    assert is_external_path(external) and not is_storage_path(external)
    assert scan_source("import sqlite3", str(external), external=True) == []
    for source in ("import shutil", "open('x', 'w')", "p.unlink()", "import os\nos.remove('x')"):
        assert scan_source(source, str(external), external=True), source


def test_external_package_contains_no_write_sql() -> None:
    files = sorted(EXTERNAL.rglob("*.py"))
    assert len(files) >= 4
    for path in files:
        for line, text in code_strings(path):
            assert not WRITE_SQL.search(text), f"{path.name}:{line}: {text!r}"


def test_write_sql_detector_detects() -> None:
    assert WRITE_SQL.search("insert into cpu values (1)")
    assert WRITE_SQL.search("ATTACH DATABASE 'x' AS y")
    assert not WRITE_SQL.search("SELECT name FROM pragma_table_info(?)")
    assert not WRITE_SQL.search("PRAGMA query_only = ON")


def test_no_systemctl_anywhere_in_executable_text() -> None:
    for path in sorted(SRC.rglob("*.py")):
        for line, text in code_strings(path):
            assert "systemctl" not in text.lower(), f"{path.name}:{line}"


# ---------------------------------------------------------------- survey script


def test_survey_script_uses_no_forbidden_or_writing_apis() -> None:
    violations = scan_source(SURVEY.read_text(encoding="utf-8"), str(SURVEY), external=True)
    assert violations == [], "\n".join(map(str, violations))
    for line, text in code_strings(SURVEY):
        assert "systemctl" not in text.lower(), f"survey:{line}"
        if text.lstrip().upper().startswith(("SELECT", "PRAGMA", "WITH")):
            assert not WRITE_SQL.search(text), f"survey:{line}: {text!r}"


def _load_survey() -> Any:
    spec = importlib.util.spec_from_file_location("survey_paolo_core", SURVEY)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_survey_reads_metrics_db_without_changing_it(tmp_path: Path) -> None:
    import hashlib
    import sqlite3

    db = tmp_path / "metrics.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE samples (ts TEXT, name TEXT, value REAL)")
    rows = [("t1", "cpu", 1.0), ("t2", "cpu", 2.0)]
    conn.executemany("INSERT INTO samples VALUES (?, ?, ?)", rows)
    conn.commit()
    conn.close()
    before = hashlib.sha256(db.read_bytes()).hexdigest()

    report = _load_survey().survey_metrics_db(db, samples=2)
    assert report["opened_read_only"] is True
    [table] = report["tables"]
    assert table["name"] == "samples" and table["rows"] == 2
    assert [c["name"] for c in table["columns"]] == ["ts", "name", "value"]
    assert len(table["sample_rows"]) == 2
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before
    assert sorted(p.name for p in tmp_path.iterdir()) == ["metrics.db"]


def test_survey_reports_missing_metrics_db(tmp_path: Path) -> None:
    report = _load_survey().survey_metrics_db(tmp_path / "absent.db", samples=0)
    assert report["exists"] is False
    assert not (tmp_path / "absent.db").exists()


@pytest.mark.parametrize("keyword", ["grafana", "jellyfin", "qbittorrent", "lycan", "backup"])
def test_survey_looks_for_every_intended_service(keyword: str) -> None:
    assert keyword in _load_survey().UNIT_KEYWORDS


# ---------------------------------------------------------------- Phase 7: D-Bus transport


def test_only_the_transport_module_touches_dbus() -> None:
    """dbus_fast is imported in exactly one place, which re-checks the call allowlist."""
    importers = sorted(
        path.relative_to(SRC).as_posix()
        for path in SRC.rglob("*.py")
        if any(m.startswith("dbus_fast") for m in imported_modules(path))
    )
    transport = "maplegotchi/sensors/service_health/dbus_transport.py"
    assert importers == [transport]
    source = (SRC / transport).read_text(encoding="utf-8")
    tree = ast.parse(source)
    lazy = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == "dbus_fast.aio"
        for alias in node.names
    }
    assert lazy == {"MessageBus"}
    # The transport never names a mutating systemd method.
    for word in (
        "StartUnit",
        "StopUnit",
        "RestartUnit",
        "ReloadUnit",
        "KillUnit",
        "Enable",
        "Disable",
        "SetProperties",
        "GetAll",
        "LoadUnit",
        "Reboot",
        "PowerOff",
    ):
        assert word not in source, word  # fmt: skip
