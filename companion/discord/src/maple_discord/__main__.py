"""Entry point: `maple-discord` (systemd: deploy/discord/maple-discord.service)."""

from __future__ import annotations

import logging
import os
import sys

from maple_discord.config import GatewayConfigError, settings_from_env


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    try:
        settings = settings_from_env(os.environ)
    except GatewayConfigError as exc:
        print(f"maple-discord: {exc}", file=sys.stderr)
        return 2
    from maple_discord.bot import MapleBot  # imported late: config errors need no Discord
    from maple_discord.maple_client import MapleClient

    maple = MapleClient(
        settings.maple_api_url, settings.gateway_token, timeout_seconds=settings.timeout_seconds
    )
    MapleBot(settings, maple).run(settings.bot_token, log_handler=None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
