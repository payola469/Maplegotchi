# maple-brain — install, configure, update (owner-run; ADR-0025, ADR-0033)

The Brain companion runs the AI provider for Maple, outside Maple's process and
sandbox. Maple talks to it on `http://127.0.0.1:8471` (`MAPLE_BRAIN_URL`) using the
contracts in `docs/brain-contract.md`: `/generate` (journal wording), `/decide`
(`maple.decision.v1`), `/reply` (`maple.reply.v1`), and `GET /health`.

It replaces the hand-made bridge that existed on paolo-core. **Before switching**,
copy the old bridge's exact provider invocation (binary path, arguments, model) and
note where its provider login lives; those facts are not in this repository.

## Install (as root)

```sh
useradd --system --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin maple-brain-svc

SHA=<commit>
install -d -o root -g root -m 0755 /opt/maple-brain/releases/$SHA
# copy companion/brain and deploy/brain from the verified release bundle, then:
cd /opt/maple-brain/releases/$SHA/companion/brain
uv sync --locked --no-dev --no-editable --python /opt/maplegotchi/python/bin/python3.12
ln -sfn /opt/maple-brain/releases/$SHA/companion/brain/.venv /opt/maple-brain/releases/$SHA/venv
ln -sfn releases/$SHA /opt/maple-brain/current.new && mv -Tf /opt/maple-brain/current.new /opt/maple-brain/current

install -d -o root -g maple-brain-svc -m 0750 /etc/maple-brain
install -o root -g maple-brain-svc -m 0640 deploy/brain/maple-brain.env /etc/maple-brain/
# edit MAPLE_BRAIN_PROVIDER / MAPLE_BRAIN_COMMAND / MAPLE_BRAIN_MODEL (see below)

install -o root -g root -m 0644 deploy/brain/maple-brain.service /etc/systemd/system/
systemd-analyze verify /etc/systemd/system/maple-brain.service
systemctl daemon-reload && systemctl enable --now maple-brain
curl -s http://127.0.0.1:8471/health
```

## Provider configuration

- `MAPLE_BRAIN_PROVIDER=none` — safe default; Maple uses RuleBrain wording, rule
  direction and rule replies.
- `MAPLE_BRAIN_PROVIDER=command` with `MAPLE_BRAIN_COMMAND` as a JSON argv array, e.g.
  `["/usr/local/bin/<provider-cli>", "<print-mode flag>", "--model", "{model}"]`.
  The command must read the prompt from stdin and print the answer to stdout. It runs
  in an empty scratch directory with only `PATH`, `HOME`, locale and `XDG_*` variables.
  Flags that auto-approve tools or bypass permissions (`--yolo`,
  `--dangerously-skip-permissions`, `--approval-mode`, `-y`, `--auto-approve`, …) are
  refused at startup.
- The provider's login (OAuth) is done once as `maple-brain-svc` with
  `HOME=/var/lib/maple-brain` (e.g. `systemd-run --uid=maple-brain-svc -p
  StateDirectory=maple-brain -E HOME=/var/lib/maple-brain --pty <provider-cli> login`).
  Its tokens stay in `/var/lib/maple-brain`; never copy them into the repository.

## Enable on Maple's side

In `/etc/maplegotchi/maplegotchi.env` set any of `MAPLE_BRAIN=antigravity`,
`MAPLE_DIRECTOR=antigravity`, `MAPLE_REPLIER=antigravity` (and `MAPLE_BRAIN_URL`
if not the default), then `systemctl restart maplegotchi`. Each can be turned back to
`rule` independently; Maple falls back to rules whenever the companion fails.

## Update / rollback

New release directory → `uv sync --locked --no-dev` → switch `current` →
`systemctl restart maple-brain`. Rollback: point `current` at the previous release and
restart. The companion holds no Maple data, so there is nothing to migrate.

## Verify

- `ss -ltnp | grep 8471` shows `127.0.0.1:8471` only.
- `sudo -u maple-brain-svc test -r /data/maple/maple.db` fails (no access).
- `/api/decisions` on Maple shows `director.name = "antigravity"` and verdicts; with the
  companion stopped, decisions show `fallback` / `transport_error` and Maple keeps living.
