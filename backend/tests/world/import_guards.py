"""Static isolation proof for the explicitly approved, dormant canonical boundary.

ADR-0036 pure resolution and ADR-0037 validation/projection permit these exact
STEP 224-225 dependencies and STEP 247's exact opt-in read module. They do not
authorize default runtime/API activation.
Parse source only: never import the modules being checked or open a database.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from pathlib import Path, PurePosixPath

WORLD = "maplegotchi.core.world."
SENSITIVE = frozenset(
    WORLD + name for name in ("legacy_projection", "layout_validation", "resolution")
)
# Exact source paths, deliberately not directory or future-module permissions.
APPROVED = frozenset(
    {
        "maplegotchi/core/world/legacy_projection.py",
        "maplegotchi/core/world/layout_validation.py",
        "maplegotchi/core/world/resolution.py",
        "maplegotchi/core/world/canonical_lifecycle.py",
        "maplegotchi/persistence/__init__.py",
        "maplegotchi/persistence/boundary.py",
        "maplegotchi/persistence/layout_codec.py",
        "maplegotchi/persistence/layout_keys.py",
        "maplegotchi/persistence/revision_snapshot.py",
        "maplegotchi/persistence/life_record.py",
        "maplegotchi/persistence/travel_codec.py",
        "maplegotchi/persistence/legacy_admission.py",
        "maplegotchi/storage/canonical_v11.py",
        "maplegotchi/runtime/canonical_persistence.py",
        "maplegotchi/runtime/canonical_polling.py",
    }
)
# Named imports only: permitting requirement_for does not permit live resolve().
DIRECT = {
    ("maplegotchi/core/world/canonical_lifecycle.py", WORLD + "resolution"): frozenset(
        {
            "DecisionContext",
            "PointKey",
            "ResolutionSnapshot",
            "candidates_for",
            "resolve",
            "resolve_urgent",
        }
    ),
    ("maplegotchi/runtime/canonical_persistence.py", WORLD + "resolution"): frozenset(
        {"PointKey", "ResolutionSnapshot"}
    ),
    ("maplegotchi/core/world/layout_validation.py", WORLD + "legacy_projection"): frozenset(
        {"DevelopmentWorld", "PointRef", "project_point"}
    ),
    ("maplegotchi/core/world/layout_validation.py", WORLD + "resolution"): frozenset(
        {"ResolutionSnapshot", "requirement_for", "validate_activity_coverage"}
    ),
    ("maplegotchi/persistence/layout_codec.py", WORLD + "layout_validation"): frozenset(
        {"ArtGeometry", "LayoutCandidate", "validate_layout"}
    ),
    ("maplegotchi/persistence/life_record.py", WORLD + "resolution"): frozenset(
        {"requirement_for"}
    ),
    ("maplegotchi/persistence/legacy_admission.py", WORLD + "legacy_projection"): frozenset(
        {
            "DevelopmentWorld",
            "LegacyProjection",
            "PointRef",
            "Presentation",
            "project",
            "project_point",
        }
    ),
    ("maplegotchi/runtime/canonical_persistence.py", WORLD + "legacy_projection"): frozenset(
        {"DevelopmentWorld", "LegacyProjection", "PointRef", "Presentation", "project_point"}
    ),
}


def module_name(path: str) -> str:
    parts = PurePosixPath(path).with_suffix("").parts
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def restricted(module: str) -> bool:
    return (
        module == WORLD + "canonical_lifecycle"
        or module in SENSITIVE
        or module == "maplegotchi.persistence"
        or module.startswith("maplegotchi.persistence.")
        or module
        in {
            "maplegotchi.storage.canonical_v11",
            "maplegotchi.runtime.canonical_persistence",
            "maplegotchi.runtime.canonical_polling",
        }
    )


def imports(path: str, source: str, modules: set[str]) -> tuple[tuple[str, str | None], ...]:
    """Resolve absolute/relative and package imports, ignoring aliases/comments."""
    caller = module_name(path)
    package = caller if path.endswith("/__init__.py") else caller.rpartition(".")[0]
    result: list[tuple[str, str | None]] = []
    for node in ast.walk(ast.parse(source, filename=path)):
        if isinstance(node, ast.Import):
            result.extend((alias.name, None) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                parts = package.split(".")
                if node.level > len(parts):
                    raise ValueError(f"invalid relative import: {path}:{node.lineno}")
                base = ".".join((*parts[: len(parts) - node.level + 1], *filter(None, (base,))))
            for alias in node.names:
                child = f"{base}.{alias.name}"
                result.append(
                    (child, None)
                    if child in modules
                    or child in SENSITIVE
                    or child
                    in {
                        "maplegotchi.storage.canonical_v11",
                        "maplegotchi.runtime.canonical_persistence",
                        "maplegotchi.runtime.canonical_polling",
                    }
                    or base == "maplegotchi.persistence"
                    else (base, alias.name)
                )
    return tuple(result)


def dependency_graph(sources: Mapping[str, str]) -> dict[str, set[str]]:
    modules = {module_name(path) for path in sources}
    graph: dict[str, set[str]] = {module: set() for module in modules}
    for path, source in sources.items():
        for target, _ in imports(path, source, modules):
            # Importing a submodule executes its package initializers as well.
            parts = target.split(".")
            graph[module_name(path)].update(
                name
                for i in range(1, len(parts) + 1)
                if (name := ".".join(parts[:i])) in modules and name != module_name(path)
            )
    return graph


def violations(sources: Mapping[str, str]) -> tuple[str, ...]:
    modules = {module_name(path) for path in sources}
    graph = dependency_graph(sources)
    approved_modules = {module_name(path) for path in APPROVED}
    errors: set[str] = set()
    for path, source in sources.items():
        caller = module_name(path)
        for target, symbol in imports(path, source, modules):
            if target in SENSITIVE and symbol not in DIRECT.get((path, target), frozenset()):
                errors.add(f"{path}: unapproved import {target}:{symbol}")
            if restricted(target) and target not in approved_modules:
                errors.add(f"{path}: unapproved canonical module {target}")
            if path not in APPROVED and restricted(target):
                errors.add(f"{path}: forbidden activation of {target}")
        seen: set[str] = set()
        todo = list(graph[caller])
        while todo:
            target = todo.pop()
            if target in seen:
                continue
            seen.add(target)
            todo.extend(graph[target] - seen)
        if caller in seen and (restricted(caller) or any(restricted(t) for t in seen)):
            errors.add(f"{path}: circular canonical dependency")
        if path not in APPROVED:
            for target in sorted(seen):
                if restricted(target):
                    errors.add(f"{path}: indirect activation of {target}")
    return tuple(sorted(errors))


def repository_sources(root: Path) -> dict[str, str]:
    source_root = root / "backend/src"
    return {
        path.relative_to(source_root).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(source_root.rglob("*.py"))
    }
