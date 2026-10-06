"""Entry point: `maple-brain` (systemd: deploy/brain/maple-brain.service)."""

from __future__ import annotations

import os
import sys

from maple_brain.config import BrainConfigError, settings_from_env
from maple_brain.provider import build_provider
from maple_brain.server import serve


def main() -> int:
    try:
        settings = settings_from_env(os.environ)
    except (BrainConfigError, ValueError) as exc:
        print(f"maple-brain: {exc}", file=sys.stderr)
        return 2
    server = serve(settings, build_provider(settings))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
