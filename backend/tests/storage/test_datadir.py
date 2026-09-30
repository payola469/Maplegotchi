"""The writable data-directory guard: adversarial path tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from maplegotchi.storage.datadir import DataDir
from maplegotchi.storage.errors import UnsafePathError
from tests.persistence_support import make_data_dir, make_dir_link, make_file_link

REJECTED = [
    "",
    ".",
    "..",
    "../x",
    "../maple-data-evil/x",
    "a/../b",
    "a/../../x",
    "./maple.db",
    "a/./b",
    "a//b",
    "a/",
    "/",
    "/etc/passwd",
    "/tmp/x",  # noqa: S108 - an escape attempt, not a temp file
    "C:\\Windows\\x",
    "C:x",
    "c:/x",
    "\\\\server\\share\\x",
    "a\\b",
    "..\\x",
    "x\x00y",
    "maple.db\x00.txt",
    "CON",
    "con.txt",
    "NUL",
    "aux.db",
    "COM1",
    "lpt9.log",
    "maple.db.",
    "maple ",
    " maple",
    ".hidden",
    "-rf",
    "~",
    "~/x",
    "$HOME",
    "%APPDATA%",
    "a:b",
    "maple.db:stream",
    "ma\u2025ple",  # two-dot leader, looks like ".."
    "\u202emaple",  # right-to-left override
    "é",
    "x" * 201,
]


@pytest.fixture
def data_dir(tmp_path: Path) -> DataDir:
    return make_data_dir(tmp_path)


@pytest.mark.parametrize("name", REJECTED)
def test_rejects_malformed_or_escaping_names(data_dir: DataDir, name: str) -> None:
    with pytest.raises(UnsafePathError):
        data_dir.path(name)


@pytest.mark.parametrize("name", [None, b"maple.db", Path("maple.db"), 3])
def test_rejects_non_strings(data_dir: DataDir, name: object) -> None:
    with pytest.raises(UnsafePathError):
        data_dir.path(name)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "name", ["maple.db", "maple.db-wal", "maple.db.birth-0a1b", "sub/file.txt", "a.b.c", "x" * 200]
)
def test_accepts_plain_names_inside(data_dir: DataDir, name: str) -> None:
    resolved = data_dir.path(name)
    assert resolved.is_relative_to(data_dir.root)
    assert resolved != data_dir.root


def test_root_must_be_absolute_existing_directory(tmp_path: Path) -> None:
    with pytest.raises(UnsafePathError):
        DataDir(Path("relative/dir"))
    with pytest.raises(UnsafePathError):
        DataDir(tmp_path / "missing")
    file = tmp_path / "file"
    file.write_text("x")
    with pytest.raises(UnsafePathError):
        DataDir(file)


def test_sibling_with_common_prefix_is_outside(tmp_path: Path) -> None:
    data_dir = make_data_dir(tmp_path)  # .../maple-data
    evil = tmp_path / "maple-data-evil"
    evil.mkdir()
    make_dir_link(data_dir.root / "link", evil)
    with pytest.raises(UnsafePathError):
        data_dir.path("link/x")


def test_directory_link_escape_is_rejected(tmp_path: Path) -> None:
    data_dir = make_data_dir(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    make_dir_link(data_dir.root / "sub", outside)
    with pytest.raises(UnsafePathError):
        data_dir.path("sub/maple.db")


def test_directory_link_to_parent_is_rejected(tmp_path: Path) -> None:
    data_dir = make_data_dir(tmp_path)
    make_dir_link(data_dir.root / "up", tmp_path)
    with pytest.raises(UnsafePathError):
        data_dir.path("up/secret")
    # Judged by final location: going out and back in lands inside, which is harmless.
    assert data_dir.path("up/maple-data/x") == data_dir.root / "x"


def test_directory_link_that_stays_inside_is_allowed(tmp_path: Path) -> None:
    data_dir = make_data_dir(tmp_path)
    (data_dir.root / "real").mkdir()
    make_dir_link(data_dir.root / "alias", data_dir.root / "real")
    assert data_dir.path("alias/x") == (data_dir.root / "real" / "x").resolve()


def test_file_symlink_escape_is_rejected(tmp_path: Path) -> None:
    data_dir = make_data_dir(tmp_path)
    target = tmp_path / "victim.txt"
    target.write_text("do not touch")
    make_file_link(data_dir.root / "maple.db", target)
    with pytest.raises(UnsafePathError):
        data_dir.path("maple.db")
    assert target.read_text() == "do not touch"


def test_symlink_loop_is_rejected(tmp_path: Path) -> None:
    data_dir = make_data_dir(tmp_path)
    make_file_link(data_dir.root / "loop", data_dir.root / "loop")
    with pytest.raises(UnsafePathError):
        data_dir.path("loop")


def test_root_may_itself_be_a_link(tmp_path: Path) -> None:
    real = tmp_path / "real-data"
    real.mkdir()
    make_dir_link(tmp_path / "data-link", real)
    data_dir = DataDir(tmp_path / "data-link")
    assert data_dir.root == real.resolve()
    assert data_dir.path("maple.db") == real.resolve() / "maple.db"


def test_remove_only_files_inside(data_dir: DataDir) -> None:
    (data_dir.root / "f").write_text("x")
    data_dir.remove("f")
    assert not (data_dir.root / "f").exists()
    data_dir.remove("f")  # missing is fine
    (data_dir.root / "d").mkdir()
    with pytest.raises(UnsafePathError):
        data_dir.remove("d")
    with pytest.raises(UnsafePathError):
        data_dir.remove("../f")


def test_publish_never_overwrites(data_dir: DataDir) -> None:
    (data_dir.root / "a").write_text("new")
    (data_dir.root / "b").write_text("existing")
    with pytest.raises(FileExistsError):
        data_dir.publish("a", "b")
    assert (data_dir.root / "b").read_text() == "existing"
    data_dir.publish("a", "c")
    assert (data_dir.root / "c").read_text() == "new"
    assert not (data_dir.root / "a").exists()


def test_names_with_prefix_validates_prefix(data_dir: DataDir) -> None:
    (data_dir.root / "maple.db.birth-1").write_text("")
    (data_dir.root / "other").write_text("")
    assert data_dir.names_with_prefix("maple.db.birth-") == ["maple.db.birth-1"]
    with pytest.raises(UnsafePathError):
        data_dir.names_with_prefix("../")
