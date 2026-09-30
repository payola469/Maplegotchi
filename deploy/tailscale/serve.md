# Tailscale Serve for Maplegotchi (D5, D13)

Maple listens on `127.0.0.1:8470` only (settings refuse any non-loopback bind; the
systemd unit adds `IPAddressAllow=localhost`). Tailscale Serve terminates HTTPS on
paolo-core's tailnet name and proxies to that loopback port. **Funnel stays off**:
nothing is reachable from the public internet. No Caddy, no nginx.

Stage A: no Serve config, no Funnel config, 8470 free.

## Preconditions (owner, read-only)

```bash
tailscale version
tailscale status --json | python3 -c 'import json,sys; s=json.load(sys.stdin)["Self"]; print(s["DNSName"])'
```
The tailnet needs MagicDNS and HTTPS certificates enabled (admin console → DNS).
The printed name (without the trailing dot) is the browser origin:
`https://paolo-core.<tailnet>.ts.net` → put it in `MAPLE_ALLOWED_ORIGINS` in
`/etc/maplegotchi/maplegotchi.env` before starting Maple.

## Enable (owner, Stage C, after Maple answers on 127.0.0.1:8470)

```bash
curl -fsS http://127.0.0.1:8470/api/health           # {"status":"ok"} first
sudo tailscale serve --bg --https=443 http://127.0.0.1:8470
tailscale serve status                                # https://paolo-core.<tailnet>.ts.net -> proxy http://127.0.0.1:8470
tailscale funnel status                               # must NOT list any Funnel
```
`--bg` persists the config across reboots. Do not use `tailscale funnel`.

## Verify

- From another tailnet device: `https://paolo-core.<tailnet>.ts.net/` shows the Maple Room;
  Greet/Pet work (the browser's Origin matches `MAPLE_ALLOWED_ORIGINS`).
- From off the tailnet: the name does not resolve / connect.
- On paolo-core: `ss -tlnp | grep 8470` shows only `127.0.0.1:8470`.

## Disable / rollback

```bash
sudo tailscale serve --https=443 off
tailscale serve status        # "No serve config"
```
