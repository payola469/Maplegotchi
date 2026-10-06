# maple-discord — install and update (owner-run; ADR-0032)

`maple-discord` is a separate service and account. It holds the Discord bot token;
Maplegotchi never does. It relays Paolo's messages in `#maple-chat` to Maple's
local API and posts Maple's replies; slash commands are read-only.

## 1. Discord side (once, in the Developer Portal)

1. Create an application and a bot; copy the **bot token** (keep it secret).
2. Bot → **Privileged Gateway Intents** → enable **Message Content Intent** (needed to
   read Paolo's messages in `#maple-chat`). No other privileged intent is needed.
3. OAuth2 → URL Generator → scopes `bot` and `applications.commands`; bot permissions:
   *View Channels*, *Send Messages*, *Read Message History*. Invite it to the server.
4. In Discord (Developer Mode on): copy the server id, the `#maple-chat` channel id,
   and Paolo's user id.

## 2. paolo-core (as root)

```sh
# account: no login, no home, no groups
useradd --system --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin maple-discord-svc

# code: a release per commit, root-owned, like Maplegotchi (ADR-0023)
# The gateway ships inside the verified Maplegotchi release bundle (SHA256SUMS checked
# by install_release.sh); install that release first, then copy from it.
SHA=<commit>
SRC=/opt/maplegotchi/releases/$SHA
UV=<path to the pinned install-time uv from deploy/install.md step 2>
PY=$(ls -d /opt/maplegotchi/python/cpython-3.12.*-linux-x86_64-gnu/bin/python3.12)
install -d -o root -g root -m 0755 /opt/maple-discord/releases/$SHA/companion /opt/maple-discord/releases/$SHA/deploy
cp -a "$SRC/companion/discord" /opt/maple-discord/releases/$SHA/companion/
cp -a "$SRC/deploy/discord" /opt/maple-discord/releases/$SHA/deploy/
cd /opt/maple-discord/releases/$SHA
UV_PROJECT_ENVIRONMENT=$PWD/venv UV_NO_CONFIG=1 "$UV" sync --project companion/discord \
    --locked --no-dev --no-editable --compile-bytecode --no-python-downloads --python "$PY"
chown -R root:root . && chmod -R u+rwX,go+rX,go-w .
ln -sfn releases/$SHA /opt/maple-discord/current.new && mv -Tf /opt/maple-discord/current.new /opt/maple-discord/current

# secrets: root-only files, handed to the service as systemd credentials
install -d -o root -g maple-discord-svc -m 0750 /etc/maple-discord
install -o root -g root -m 0600 /dev/null /etc/maple-discord/discord-bot-token
install -o root -g root -m 0600 /dev/null /etc/maple-discord/maple-gateway-token
# put the bot token in discord-bot-token; generate the shared gateway token:
python3 -c 'import secrets; print(secrets.token_urlsafe(48))' > /etc/maple-discord/maple-gateway-token
install -o root -g maple-discord-svc -m 0640 deploy/discord/maple-discord.env /etc/maple-discord/
# edit the three Discord ids in /etc/maple-discord/maple-discord.env

# Maple side: the SAME gateway token (not the bot token) enables the endpoint
echo "MAPLE_GATEWAY_TOKEN=$(cat /etc/maple-discord/maple-gateway-token)" >> /etc/maplegotchi/maplegotchi.env
systemctl restart maplegotchi

install -o root -g root -m 0644 deploy/discord/maple-discord.service /etc/systemd/system/
systemd-analyze verify /etc/systemd/system/maple-discord.service
systemctl daemon-reload && systemctl enable --now maple-discord
journalctl -u maple-discord -n 50
```

## 3. Verify

- Write "what are you doing?" in `#maple-chat`: Maple answers from its real state;
  someone else writing there gets no reply; `/status` works only for Paolo.
- `curl -s -X POST http://127.0.0.1:8470/api/conversation/messages` without the token → 401.
- `grep -c DISCORD /etc/maplegotchi/maplegotchi.env` → 0 (the bot token is not there).
- Stop the gateway (`systemctl stop maple-discord`): Maple keeps living (`/api/status`).

## Update / rollback / disable

- Update: new release directory, `uv sync --locked --no-dev`, switch `current`, restart.
- Rollback: point `current` at the previous release, restart. No data is involved.
- Disable the channel: `systemctl disable --now maple-discord` and remove
  `MAPLE_GATEWAY_TOKEN` from `maplegotchi.env` (the endpoint then returns 404).
