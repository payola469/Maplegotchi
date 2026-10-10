#!/bin/sh
# Owner-run only: sudo sh sandbox_probe.sh <expected deployed 40-hex release>
# See deploy/install.md section 6. Never invokes sudo or changes a service.
set -eu
exec /usr/bin/python3 -B "$(dirname "$0")/sandbox_probe.py" "$@"
