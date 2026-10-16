#!/bin/sh
# Explicit synthetic development alpha only; never shipped startup.
set -eu
case "${1:-}" in
  init) initialize=1 ;;
  start) initialize=0 ;;
  stop) initialize=0 ;;
  *) echo "Usage: $0 init|start|stop (state is retained)" >&2; exit 2 ;;
esac
operation=$1
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo=$(CDPATH= cd -- "$script_dir/../../.." && pwd)
mkdir -p "$repo/var"
if [ "$operation" != stop ]; then
  (cd "$repo/frontend" && node tools/art/cli.mjs && ./node_modules/.bin/vite build --config tools/room-ui/vite.config.mjs)
fi
cd "$repo/backend"
export PYTHONPATH=src
module=tests.schema_v11.playable_preview
if [ "$operation" = stop ]; then module=tests.schema_v11.alpha_stop; fi
set -- --alpha-root "$repo/var/maple-local-alpha" --port 8474
if [ "$initialize" = 1 ]; then set -- "$@" --initialize; fi
if [ -n "${MAPLE_ALPHA_PYTHON:-}" ]; then
  exec "$MAPLE_ALPHA_PYTHON" -B -m "$module" "$@"
elif [ -x .venv/bin/python ]; then
  exec .venv/bin/python -B -m "$module" "$@"
else
  exec uv run --locked python -B -m "$module" "$@"
fi
