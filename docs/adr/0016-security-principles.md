# ADR-0016: Security principles

- **Status:** Accepted — FIXED (CLAUDE.md S1 / §4.1)
- **Date:** 2026-09-30
- **Decided by:** owner

## Decision
1. External system access is read-only.
2. No subprocesses, no shell, no `eval`/`exec`; no `systemctl`.
3. Maple's only writable production area is `/data/maple`.
4. Runtime code and Maple-owned writable data are separated.
5. Maple cannot modify its own security boundaries (code, config, policy, allowlists, systemd/Tailscale/polkit config).
6. The Brain is untrusted; its output is validated, never executed.
7. Tailnet-only access; no public exposure.

## Consequences
- Enforced in layers: code checks (forbidden-API scanner, ruff, import-linter, ESLint), file ownership, systemd sandboxing, polkit, and an on-host verification script (CLAUDE.md §4).
