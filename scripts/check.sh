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
DEPLOY_PY=(../deploy/survey ../deploy/backup ../deploy/verify)
step "deploy tools: ruff check + format"; "$UV" run ruff check --config pyproject.toml "${DEPLOY_PY[@]}" && "$UV" run ruff format --check --config pyproject.toml "${DEPLOY_PY[@]}"
step "backend + deploy tools: mypy --strict"; "$UV" run mypy
step "backend: import contracts";   "$UV" run lint-imports
step "backend: pytest";             "$UV" run pytest

cd "$ROOT/companion/discord"
step "companion/discord: uv sync --locked"; "$UV" sync --locked
step "companion/discord: ruff + format"; "$UV" run ruff check . && "$UV" run ruff format --check .
step "companion/discord: mypy --strict"; "$UV" run mypy
step "companion/discord: pytest"; "$UV" run pytest -q

cd "$ROOT"
step "deploy + scripts: shellcheck"; "$UV" tool run --from shellcheck-py shellcheck -s sh deploy/install/*.sh deploy/verify/*.sh deploy/backup/*.sh && "$UV" tool run --from shellcheck-py shellcheck -s bash -e SC2034 deploy/backup/maple-block.bash && "$UV" tool run --from shellcheck-py shellcheck scripts/*.sh

cd "$ROOT/frontend"
step "frontend: install";   "$PNPM" install --frozen-lockfile
step "frontend: eslint";    "$PNPM" lint
step "frontend: tsc";       "$PNPM" typecheck
step "frontend: vitest";    "$PNPM" test
step "frontend: build";     "$PNPM" build

printf '\nAll checks passed.\n'
