"""Static harness boundaries, alongside the existing forbidden-API scanner.

These prevent accidental coupling; they are not a sandbox against obfuscated code.
Test-only I/O is permitted here, never in the future world domain.
"""

from __future__ import annotations

import ast
from importlib.util import resolve_name
from pathlib import Path

from tests.security.forbidden_apis import scan_source
from tests.security.test_forbidden_apis import CORE_IMPORT_ALLOWLIST

SRC = Path(__file__).resolve().parents[2] / "src/maplegotchi"


def imports(tree: ast.Module, module: str, *, package: bool = False) -> tuple[str, ...]:
    """Resolve absolute, relative and from-parent imports without importing code."""
    base = module if package else module.rpartition(".")[0]
    result: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            name = "." * node.level + (node.module or "")
            resolved = resolve_name(name, base) if node.level else name
            result.extend(f"{resolved}.{alias.name}" for alias in node.names)
    return tuple(result)


def violations(source: str, module: str, *, package: bool = False) -> list[str]:
    tree = ast.parse(source)
    dependencies = imports(tree, module, package=package)
    errors = []
    if any(name == "tests" or name.startswith("tests.") for name in dependencies):
        errors.append("runtime imports test-only data")
    if any(
        isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and any(
            marker in node.value
            for marker in ("approved_tables.json", "maple-room-final-design-spec.md", "tests/world")
        )
        for node in ast.walk(tree)
    ):
        errors.append("runtime references test/spec geometry files")
    if module == "maplegotchi.world_catalog" or module.startswith("maplegotchi.world_catalog."):
        if any(
            not (
                isinstance(node, ast.Expr)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            )
            for node in tree.body
        ):
            errors.append("catalog is declarative release data, not Python behavior")
    if module == "maplegotchi.core.world" or module.startswith("maplegotchi.core.world."):
        errors.extend(str(item) for item in scan_source(source, module, core=True))
        for name in dependencies:
            if name.split(".")[0] not in CORE_IMPORT_ALLOWLIST or (
                name.startswith("maplegotchi.") and not name.startswith("maplegotchi.core.")
            ):
                errors.append(f"world import outside pure core: {name}")
    return errors


def scan_runtime(root: Path = SRC) -> list[str]:
    result: list[str] = []
    for path in sorted(root.rglob("*.py")):
        relative = path.relative_to(root).with_suffix("")
        is_package = relative.name == "__init__"
        parts = relative.parts[:-1] if is_package else relative.parts
        module = ".".join(("maplegotchi", *parts))
        result.extend(
            f"{path}: {error}"
            for error in violations(path.read_text(encoding="utf-8"), module, package=is_package)
        )
    return result
