"""Offline test-only exporter; default checks, --write regenerates.

From backend: PYTHONPATH=src:. python -m tests.api.world_contract_export [--write]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI

from maplegotchi.api.world_fixtures import FixtureScenario, build_fixture
from maplegotchi.api.world_routes import unavailable_world_router

ROOT = Path(__file__).resolve().parents[3]


def typescript(schema: dict[str, Any]) -> str:
    """Translate only supported schema forms, rejecting unknown forms."""
    if "$ref" in schema:
        return str(schema["$ref"]).rsplit("/", 1)[1]
    if "const" in schema:
        return json.dumps(schema["const"])
    if "enum" in schema:
        return " | ".join(json.dumps(value) for value in schema["enum"])
    for key in ("anyOf", "oneOf"):
        if key in schema:
            return "(" + " | ".join(typescript(value) for value in schema[key]) + ")"
    kind = schema.get("type")
    if kind == "array":
        if "prefixItems" in schema:
            return "readonly [" + ", ".join(typescript(s) for s in schema["prefixItems"]) + "]"
        return "ReadonlyArray<" + typescript(schema["items"]) + ">"
    if kind == "object":
        required = schema.get("required", [])
        props = schema.get("properties", {})
        if not props or schema.get("additionalProperties") not in (None, False):
            raise ValueError("unsupported open object in world schema")
        return (
            "{\n"
            + "\n".join(
                f"  readonly {json.dumps(name)}{'' if name in required else '?'}: "
                f"{typescript(value)};"
                for name, value in sorted(props.items())
            )
            + "\n}"
        )
    kinds = {
        "string": "string",
        "integer": "number",
        "number": "number",
        "boolean": "boolean",
        "null": "null",
    }
    if kind in kinds:
        return kinds[kind]
    raise ValueError(f"unsupported world schema: {schema}")


def render_artifacts() -> dict[Path, str]:
    app = FastAPI(title="Maplegotchi", version="0.1.0")
    app.include_router(unavailable_world_router())
    schema = app.openapi()
    schemas = schema["components"]["schemas"]
    ts = "// Generated from docs/api/world-openapi.json; do not edit.\n"
    ts += "// Backend is authoritative. No renderer logic or legacy DTO replacement.\n\n"
    ts += (
        "\n\n".join(
            f"export type {name} = {typescript(value)};" for name, value in sorted(schemas.items())
        )
        + "\n"
    )
    idle = build_fixture()
    walking = build_fixture(FixtureScenario.WALKING)
    display = build_fixture(FixtureScenario.DISPLAY)
    payloads = {
        "world-idle": idle.world.model_dump(mode="json"),
        "world-walking": walking.world.model_dump(mode="json"),
        "catalog": idle.catalog.model_dump(mode="json"),
        "placements-empty": idle.placements.model_dump(mode="json"),
        "placements-display": display.placements.model_dump(mode="json"),
    }
    result = {
        ROOT / "docs/api/world-openapi.json": json.dumps(schema, indent=2, sort_keys=True) + "\n",
        ROOT / "frontend/src/api/world.generated.ts": ts,
    }
    result.update(
        {
            ROOT / f"docs/fixtures/maple-room/r1a-10/{name}.json": json.dumps(
                payload, indent=2, sort_keys=True
            )
            + "\n"
            for name, payload in payloads.items()
        }
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    for path, text in render_artifacts().items():
        if args.write:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        elif not path.is_file() or path.read_text(encoding="utf-8") != text:
            raise SystemExit(f"stale world contract: {path.relative_to(ROOT)}")
    print("World OpenAPI, TypeScript and five fixture exports match")


if __name__ == "__main__":
    main()
