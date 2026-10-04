# ADR-0025: External Brain via localhost runtime boundary

- **Status:** Accepted — v0.2
- **Date:** 2026-10-04
- **Decided by:** owner
- **Extends:** ADR-0010

## Context

Maple v0.2 introduces an External Brain while preserving the Brain boundary defined by ADR-0010.

The `maplegotchi.brain` package is a pure domain boundary. It must remain offline and capability-free. Maplegotchi also forbids subprocess, shell, and exec APIs in its source tree.

Antigravity therefore cannot be launched directly from Maplegotchi.

## Decision

- `RuleBrain` remains the default Brain.
- Runtime may select an External Brain when explicitly configured.
- External Brain transport is implemented in `maplegotchi.runtime`, not `maplegotchi.brain`.
- Maplegotchi communicates with the External Brain through HTTP on a loopback address only.
- `MAPLE_BRAIN_URL` must use plain HTTP with a loopback host.
- Maplegotchi never invokes Antigravity, `agy`, subprocesses, shells, or provider CLIs directly.
- Antigravity/provider execution belongs to a separate companion service and security boundary.
- The companion service is not part of Maple's core state, identity, persistence, or writable capability boundary.
- Brain output remains advisory and is converted to `JournalDraft` values that pass through Maple's existing validation before persistence.
- Replacing the external provider or model must not alter Maple's identity, canonical state schema, history, or storage ownership.

## Runtime shape

Maplegotchi runtime selects either RuleBrain or ExternalHttpBrain. ExternalHttpBrain communicates over HTTP loopback only with a separate Maple Brain companion service, which is responsible for Antigravity/provider execution.

## Security consequences

- `maplegotchi.brain` remains pure.
- No subprocess/shell exception is added to Maplegotchi.
- Existing forbidden-API tests remain unchanged.
- The main Maplegotchi service does not require outbound Internet access for the External Brain connection.
- Provider credentials and provider-specific execution stay outside the main Maplegotchi process.

## Failure behavior

If the External Brain call fails, journal wording may be unavailable for that transition, but Maple's life transition must continue according to core rules. External Brain failure must not mutate Maple's identity or authoritative state.

## Consequences

- Provider/model changes are isolated behind the companion-service boundary.
- Maplegotchi retains its existing security model.
- External Brain integration can evolve without granting tools or external-system write capabilities to Maple's Brain.
- Production deployment requires a separately hardened companion service before `MAPLE_BRAIN=antigravity` is enabled.
