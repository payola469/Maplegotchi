"""AST scanner enforcing CLAUDE.md §4.1 (no subprocess/shell/exec) and §5 (pure core).

This guards against accidental use of forbidden APIs. It is not a sandbox: a
determined bypass (e.g. getattr with computed strings) is out of its reach,
which is why the production boundary is also enforced by systemd (§4.3).
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

# Importing any of these (or a submodule) is forbidden everywhere.
FORBIDDEN_MODULES: frozenset[str] = frozenset(
    {"subprocess", "pty", "multiprocessing", "pexpect", "sh", "plumbum"}
)

# Referencing any of these dotted names is forbidden everywhere.
FORBIDDEN_NAMES: frozenset[str] = frozenset(
    {
        "os.system",
        "os.popen",
        "os.startfile",
        "os.fork",
        "os.forkpty",
        "os.posix_spawn",
        "os.posix_spawnp",
        "os.kill",
        "os.killpg",
        "signal.pthread_kill",
        "asyncio.create_subprocess_exec",
        "asyncio.create_subprocess_shell",
        "shutil.rmtree",
        "importlib.import_module",
    }
)

# Any os.exec* / os.spawn* variant.
FORBIDDEN_NAME_PREFIXES: tuple[str, ...] = ("os.exec", "os.spawn")

FORBIDDEN_BUILTINS: frozenset[str] = frozenset({"eval", "exec", "compile", "__import__"})

# Extra rules for maplegotchi.core: no I/O, no clock, no randomness, no concurrency.
CORE_FORBIDDEN_MODULES: frozenset[str] = frozenset(
    {
        "os",
        "sys",
        "io",
        "pathlib",
        "shutil",
        "tempfile",
        "glob",
        "socket",
        "ssl",
        "http",
        "urllib",
        "sqlite3",
        "random",
        "secrets",
        "time",
        "asyncio",
        "threading",
        "concurrent",
        "signal",
        "psutil",
        "fastapi",
        "starlette",
        "uvicorn",
        "httpx",
        "requests",
        "dbus_fast",
        "jeepney",
    }
)

CORE_FORBIDDEN_NAMES: frozenset[str] = frozenset(
    {
        "datetime.datetime.now",
        "datetime.datetime.utcnow",
        "datetime.datetime.today",
        "datetime.date.today",
    }
)

CORE_FORBIDDEN_BUILTINS: frozenset[str] = frozenset({"open", "input"})

# Writing files is reserved for maplegotchi.storage (CLAUDE.md §3.3, §4.4).
WRITER_ONLY_MODULES: frozenset[str] = frozenset({"sqlite3", "shutil", "tempfile"})
WRITER_ONLY_NAMES: frozenset[str] = frozenset(
    {
        "os.open",
        "os.remove",
        "os.unlink",
        "os.rename",
        "os.renames",
        "os.replace",
        "os.link",
        "os.symlink",
        "os.mkdir",
        "os.makedirs",
        "os.rmdir",
        "os.removedirs",
        "os.truncate",
        "os.chmod",
        "os.chown",
        "os.utime",
        "os.mkfifo",
    }
)
WRITER_ONLY_BUILTINS: frozenset[str] = frozenset({"open"})
# Path/file methods that write, flagged on any object outside storage.
WRITER_ONLY_METHODS: frozenset[str] = frozenset(
    {
        "write_text",
        "write_bytes",
        "touch",
        "mkdir",
        "unlink",
        "rename",
        "rmdir",
        "symlink_to",
        "hardlink_to",
        "chmod",
        "truncate",
    }
)


@dataclass(frozen=True)
class Violation:
    path: str
    line: int
    rule: str
    detail: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: [{self.rule}] {self.detail}"


def _module_forbidden(module: str, forbidden: frozenset[str]) -> bool:
    return any(module == m or module.startswith(m + ".") for m in forbidden)


class _Scanner(ast.NodeVisitor):
    def __init__(self, path: str, *, core: bool, writer: bool) -> None:
        self.path = path
        self.core = core
        self.writer = writer
        self.aliases: dict[str, str] = {}
        self.violations: list[Violation] = []

    def _flag(self, node: ast.AST, rule: str, detail: str) -> None:
        self.violations.append(Violation(self.path, getattr(node, "lineno", 0), rule, detail))

    def _check_module(self, node: ast.AST, module: str) -> None:
        if _module_forbidden(module, FORBIDDEN_MODULES):
            self._flag(node, "forbidden-module", module)
        elif self.core and _module_forbidden(module, CORE_FORBIDDEN_MODULES):
            self._flag(node, "core-impure-module", module)
        elif not self.writer and _module_forbidden(module, WRITER_ONLY_MODULES):
            self._flag(node, "write-outside-storage", module)

    def _check_name(self, node: ast.AST, dotted: str) -> None:
        if dotted in FORBIDDEN_NAMES or dotted.startswith(FORBIDDEN_NAME_PREFIXES):
            self._flag(node, "forbidden-api", dotted)
        elif self.core and dotted in CORE_FORBIDDEN_NAMES:
            self._flag(node, "core-impure-api", dotted)
        elif not self.writer and dotted in WRITER_ONLY_NAMES:
            self._flag(node, "write-outside-storage", dotted)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self._check_module(node, alias.name)
            if alias.asname:
                self.aliases[alias.asname] = alias.name
            else:
                top = alias.name.split(".", 1)[0]
                self.aliases[top] = top
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.level == 0 and node.module:
            self._check_module(node, node.module)
            for alias in node.names:
                dotted = f"{node.module}.{alias.name}"
                self._check_module(node, dotted)
                self._check_name(node, dotted)
                self.aliases[alias.asname or alias.name] = dotted
        self.generic_visit(node)

    def _resolve(self, node: ast.expr) -> str | None:
        if isinstance(node, ast.Name):
            return self.aliases.get(node.id)
        if isinstance(node, ast.Attribute):
            base = self._resolve(node.value)
            return f"{base}.{node.attr}" if base else None
        return None

    def visit_Attribute(self, node: ast.Attribute) -> None:
        dotted = self._resolve(node)
        if dotted:
            self._check_name(node, dotted)
        if not self.writer and node.attr in WRITER_ONLY_METHODS:
            self._flag(node, "write-outside-storage", f".{node.attr}")
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id not in self.aliases:
            if node.id in FORBIDDEN_BUILTINS:
                self._flag(node, "forbidden-builtin", node.id)
            elif self.core and node.id in CORE_FORBIDDEN_BUILTINS:
                self._flag(node, "core-impure-builtin", node.id)
            elif not self.writer and node.id in WRITER_ONLY_BUILTINS:
                self._flag(node, "write-outside-storage", node.id)
        self.generic_visit(node)

    def visit_keyword(self, node: ast.keyword) -> None:
        if (
            node.arg == "shell"
            and isinstance(node.value, ast.Constant)
            and node.value.value is True
        ):
            self._flag(node.value, "shell-true", "shell=True")
        self.generic_visit(node)


def scan_source(
    source: str, path: str = "<string>", *, core: bool = False, writer: bool = False
) -> list[Violation]:
    scanner = _Scanner(path, core=core, writer=writer)
    scanner.visit(ast.parse(source, filename=path))
    return scanner.violations


def _in_package(path: Path, package: str) -> bool:
    parts = path.parts
    return any(parts[i] == "maplegotchi" and parts[i + 1] == package for i in range(len(parts) - 1))


def is_core_path(path: Path) -> bool:
    return _in_package(path, "core")


def is_storage_path(path: Path) -> bool:
    return _in_package(path, "storage")


def scan_tree(root: Path) -> tuple[int, list[Violation]]:
    """Scan every .py file under root. Returns (files_scanned, violations)."""
    files = sorted(root.rglob("*.py"))
    violations: list[Violation] = []
    for file in files:
        violations.extend(
            scan_source(
                file.read_text(encoding="utf-8"),
                str(file),
                core=is_core_path(file),
                writer=is_storage_path(file),
            )
        )
    return len(files), violations
