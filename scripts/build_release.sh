#!/usr/bin/env bash
# Build the release bundle for one exact, committed revision (trusted build machine).
# Usage: scripts/build_release.sh [<commit>]      (default: HEAD; the tree must be clean)
#
# Output: var/release/maplegotchi-<sha>.tar.gz and its SHA-256, which the owner
# passes to deploy/install/install_release.sh on paolo-core. The bundle holds:
#   RELEASE              commit=<sha>, build metadata
#   SHA256SUMS           every file below, verified on install
#   backend/             pyproject.toml, uv.lock, src/ (from `git archive <sha>`)
#   frontend/dist/       built here from the same archive (pnpm install --frozen-lockfile)
#   deploy/              unit, env template, polkit rule, install/verify/backup tools
# Python dependencies are NOT bundled: paolo-core installs them from uv.lock
# (hash-pinned) into the release venv. Nothing here needs node/pnpm on paolo-core.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PNPM="${PNPM:-pnpm}"
cd "$ROOT"

REV="${1:-HEAD}"
SHA="$(git rev-parse --verify "$REV^{commit}")"
if [[ "$REV" == "HEAD" && -n "$(git status --porcelain)" ]]; then
    echo "build_release: working tree is not clean; commit first" >&2
    exit 1
fi

OUT="$ROOT/var/release"
WORK="$OUT/work-$SHA"
BUNDLE="$WORK/bundle"
rm -rf "$WORK"
mkdir -p "$WORK/src" "$BUNDLE"

git archive --format=tar "$SHA" backend frontend deploy | tar -x -C "$WORK/src"

(cd "$WORK/src/frontend" && "$PNPM" install --frozen-lockfile && "$PNPM" build)

mkdir -p "$BUNDLE/backend" "$BUNDLE/frontend"
cp -R "$WORK/src/backend/pyproject.toml" "$WORK/src/backend/uv.lock" "$WORK/src/backend/src" \
    "$BUNDLE/backend/"
cp -R "$WORK/src/frontend/dist" "$BUNDLE/frontend/dist"
cp -R "$WORK/src/deploy" "$BUNDLE/deploy"
find "$BUNDLE" -name '__pycache__' -prune -exec rm -rf {} +

{
    echo "commit=$SHA"
    echo "built_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "built_by=$(git config user.name || echo unknown)"
    echo "node=$(node --version)"
    echo "pnpm=$("$PNPM" --version)"
} > "$BUNDLE/RELEASE"

(cd "$BUNDLE" && find . -type f | sed 's|^\./||' | LC_ALL=C sort \
    | while IFS= read -r f; do sha256sum "$f"; done \
    | sed 's/^\([0-9a-f]\{64\}\) [*]/\1  /' > "$WORK/SHA256SUMS")  # text form on MSYS too
mv "$WORK/SHA256SUMS" "$BUNDLE/SHA256SUMS"

TARBALL="$OUT/maplegotchi-$SHA.tar.gz"
tar --owner=0 --group=0 --numeric-owner --sort=name -C "$BUNDLE" -czf "$TARBALL" .
rm -rf "$WORK"

echo "bundle:  $TARBALL"
echo "sha256:  $(sha256sum "$TARBALL" | cut -d' ' -f1)"
echo "commit:  $SHA"
