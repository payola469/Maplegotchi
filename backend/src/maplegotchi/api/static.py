"""Serve the built frontend from the same origin as the API (D13).

- `/api/...` is never answered by the frontend: unknown API paths are JSON 404.
- An existing file under the static root is served as-is (only regular files
  inside the resolved root; traversal and symlink escapes are refused).
- A path that looks like an asset (has a file extension) but does not exist is
  404, so broken asset links fail loudly.
- Any other path falls back to index.html (single-page app routing).
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response

INDEX = "index.html"


def resolve_static(root: Path, path: str) -> Path | None:
    """The file to serve for `path`, or None if it is not a file inside `root`."""
    if "\x00" in path or "\\" in path:
        return None
    try:
        candidate = (root / path).resolve()
    except (OSError, RuntimeError):
        return None
    if candidate != root and candidate.is_relative_to(root) and candidate.is_file():
        return candidate
    return None


def install_frontend(app: FastAPI, static_dir: Path) -> None:
    root = static_dir.resolve(strict=True)
    index = root / INDEX
    if not index.is_file():
        raise FileNotFoundError(f"{index} is missing; build the frontend first")

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str) -> Response:
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status_code=404, detail="not found")
        found = resolve_static(root, path) if path else None
        if found is not None:
            cache = (
                "public, max-age=31536000, immutable" if "/assets/" in f"/{path}" else "no-cache"
            )
            return FileResponse(found, headers={"cache-control": cache})
        if Path(path).suffix:
            raise HTTPException(status_code=404, detail="not found")
        return FileResponse(index, headers={"cache-control": "no-cache"})
