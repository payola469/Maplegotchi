#!/usr/bin/env bash
# Runs every check CI runs. Usage: scripts/check.sh   (from any directory)
# Override tool paths with UV=... or PNPM=... if they are not on PATH.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UV="${UV:-uv}"
PNPM="${PNPM:-pnpm}"

step() { printf '\n==> %s\n' "$*"; }

cd "$ROOT/backend"
step "backend: uv sync --locked";   "$UV" sync --locked
step "backend: ruff check";         "$UV" run ruff check .
step "backend: ruff format --check"; "$UV" run ruff format --check .
step "survey: ruff check + format"; "$UV" run ruff check --config pyproject.toml ../deploy/survey && "$UV" run ruff format --check --config pyproject.toml ../deploy/survey
step "backend + survey: mypy --strict"; "$UV" run mypy
step "backend: import contracts";   "$UV" run lint-imports
step "backend: pytest";             "$UV" run pytest

cd "$ROOT/frontend"
step "frontend: install";   "$PNPM" install --frozen-lockfile
step "frontend: eslint";    "$PNPM" lint
step "frontend: tsc";       "$PNPM" typecheck
step "frontend: vitest";    "$PNPM" test
step "frontend: build";     "$PNPM" build

printf '\nAll checks passed.\n'
