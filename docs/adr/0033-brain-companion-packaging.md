# ADR-0033: The Maple Brain companion, version-controlled and reproducible

- **Status:** Accepted — FIXED (CLAUDE.md D32)
- **Date:** 2026-10-06
- **Decided by:** owner (v0.2 autonomy program, Phase A10: no more undocumented server
  setup; keep `maple-brain-svc`, loopback-only listener, outbound network only where
  needed, no `/data/maple` access, no dangerous auto-approved shell permissions; config
  from environment; no secrets in the repository).
- **Related:** ADR-0025 (runtime boundary), ADR-0026 (`/decide`), ADR-0032 (`/reply`).

## Context

ADR-0025 put provider execution (Antigravity) in a separate companion service. That
service was set up by hand on paolo-core; its code, unit and configuration were not in
this repository, and `/decide`/`/reply` did not exist there.

## Decision

1. **`companion/brain`** (`maple-brain`): a small, standard-library-only HTTP service
   (no third-party runtime dependencies) implementing the three contracts of
   `docs/brain-contract.md`: `POST /generate`, `POST /decide` (`maple.decision.v1`),
   `POST /reply` (`maple.reply.v1`), plus `GET /health`. It binds a loopback address
   only (refuses anything else), accepts JSON bodies ≤ 64 KB, and runs at most one
   provider call at a time per endpoint family.
2. **Provider**: the provider command is configuration, not code:
   `MAPLE_BRAIN_COMMAND` is a JSON argv array (no shell, no string splitting); the
   prompt goes to stdin; stdout is the answer; `MAPLE_BRAIN_MODEL` may fill a
   `{model}` placeholder. The companion **refuses** commands containing known
   auto-approve / permission-bypass flags (e.g. `--yolo`, `--dangerously-skip-permissions`,
   `--approval-mode=yolo`, `--auto-approve`), runs the command in an empty scratch
   directory with a minimal environment, and kills it at its timeout. The exact
   Antigravity invocation is copied by the owner from the existing server setup into
   `/etc/maple-brain/maple-brain.env` (it is not guessed here). `MAPLE_BRAIN_PROVIDER=none`
   answers "no proposal" so Maple uses its rule fallbacks.
3. **Prompts** are built in the companion from the contract context and always say: no
   tools, no commands, no workspace files, no external information, facts in the prompt
   only; answer in the contract's shape. Outputs are parsed (`/decide`: the first JSON
   object; `/reply`: trimmed text) and Maple validates them again.
4. **Deployment**: `deploy/brain/maple-brain.service` runs as `maple-brain-svc` with a
   private state directory (`StateDirectory=maple-brain`, the provider's own login /
   OAuth state lives there and is never committed), `ProtectSystem=strict`,
   `ProtectHome=yes`, `/data` and Maple's/the gateway's config inaccessible, no
   capabilities, outbound network allowed (the provider needs it), and no inbound
   listener other than 127.0.0.1:8471. Install/update/rollback are owner-run and
   documented in `deploy/brain/README.md`.

## Consequences

- The companion can be rebuilt from the repository and reviewed like Maple.
- Provider credentials remain outside the repository and outside Maple's process.
- `MemoryDenyWriteExecute` is not set for the companion because JIT-based provider CLIs
  (e.g. Node) need writable-executable memory; everything else mirrors Maple's sandbox.
