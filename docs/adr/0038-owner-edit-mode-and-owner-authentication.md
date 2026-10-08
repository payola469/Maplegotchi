# ADR-0038: Owner Edit Mode and owner authentication

- **Status:** Accepted — FIXED design (CLAUDE.md D37). **NOT IMPLEMENTED.** Implementation is not yet authorized (roadmap R4). A **technical spike** on Tailscale Serve identity headers is required (§3).
- **Date:** 2026-10-08
- **Decided by:** owner, Maple Room review decision **B3** (owner authentication), and **B13** (baseline A11, A12), together with **B8** (geometry validation) and **B11** (slots only).
- **Amends:** D3 / D31 (the mutation surface). It adds owner-only layout endpoints and, later, owner approvals. The rule that Greet/Pet are the only *browser interactions with Maple* is unchanged: Live Mode never commands Maple. **Related:** ADR-0013, ADR-0016, ADR-0032, ADR-0035, ADR-0037, ADR-0039.

## Context

Today the only browser mutations are Greet and Pet. Their protection is the tailnet plus an exact `Origin` match (ADR-0013). The Discord gateway uses a separate bearer token (ADR-0032). The roadmap (R4) asks for a light room-builder for Paolo. That makes the browser's first *privileged* mutations, and the pattern will be reused for future owner approvals.

Local processes on paolo-core can reach `127.0.0.1:8470`. That includes `maple-brain`, which runs an external AI provider CLI with outbound internet. A Tailscale identity header alone could therefore be forged by a local process.

## Decision

### 1. Live Mode (A11)
- Live Mode stays available **without** owner authentication.
- Hover and click show **information only**. They never command Maple.

### 2. Owner authentication: defense in depth (B3)
1. **Exact `Origin` validation remains mandatory** for every owner request.
2. A **dedicated owner secret** is the **primary authenticator**.
   - It is new and used for nothing else: never the Brain, Gateway, Discord or any other token.
   - It lives only in root-owned host configuration and is never in the repository.
3. **After a successful unlock** the server issues a **Secure, HttpOnly, SameSite=Strict owner session cookie**.
4. **When a request arrives through Tailscale Serve,** the Tailscale identity must **also** match Paolo's configured owner identity.
5. **Edit, save, revert and future owner-only approvals require the owner session.**

**Security requirements:**
- The owner secret is never stored in `localStorage`. After authentication it is never reachable from frontend JavaScript.
- Secret comparison is constant-time, and unlock attempts are rate-limited.
- Owner sessions expire and support explicit **Lock / Logout**.
- The owner secret is never logged and never included in any API response.
- Owner mutations are limited to **core-validated domain operations** (layout and placement data). Authentication grants no host, system, service, configuration or code access.

### 3. Technical spike: Tailscale identity headers
Verify how Tailscale Serve treats client-supplied identity headers, including whether `Tailscale-User-Login` is stripped or overwritten before it reaches Maple. **Until the spike passes**, the owner secret and session are the authoritative mechanism. The Tailscale identity check is additional defense only, never the sole boundary.

### 4. Edit Mode workflow (A12)
- **The frontend edits a local *draft*:** grid overlay, drag/drop, snap and rotate.
- **Undo/redo** is a client-side command stack on the draft. It may persist per browser as a best-effort convenience.
- **Preview:** the server validates the draft and returns errors, Storage displacements (ADR-0039) and any Maple relocation (ADR-0035 §3). It changes no state.
- **Save:** the draft is sent with `base_revision`. Core re-validates and commits a new layout revision (ADR-0037). A stale base gets **409 + rebase**, never last-writer-wins.
- **Revert:** a new revision that copies an earlier one.
- **Core validation** (pure) covers:
  - catalog types and orientations exist;
  - footprints lie inside room floors and blocking masks don't overlap;
  - wall objects sit on walls;
  - **room geometry is non-overlapping and valid (B8)**;
  - doors join adjacent rooms, and door and approach tiles are walkable;
  - every functional approach tile is reachable from the open doors;
  - existing display placements keep a valid slot, or move to Storage and are shown in the preview;
  - Maple's tile stays walkable, or the recorded recovery applies;
  - size bounds hold.
- **A saved layout is applied as a transition:**
  - Maple's route is replanned from her current position.
  - If her current point disappears, the action is interrupted (`layout_changed`) and a decision becomes due.

## PROVISIONAL / [PROPOSED]
- The owner session expiry duration and the unlock rate-limit values are tuning (PROVISIONAL).
- Endpoint names and DTO shapes are [PROPOSED].
- How the owner secret is provisioned on the host (root-owned file and env name) is fixed in the implementation PR, never in the repository.

## Deferred
- All Edit Mode features belong to roadmap R4. They are **not** required for the default-view switch (ADR-0040).
- Room add, remove and resize, and moving doors, come with R4. Opening placeholder rooms follows ADR-0035 / ADR-0040.
- Owner approvals beyond layout (e.g. Workspace projects) only reuse this authentication; their semantics belong to future ADRs.

## Consequences
- The owner gets a safe, revertible room editor. Invalid layouts cannot be saved.
- A local process (including the AI provider CLI) cannot perform owner actions without the owner secret.
- New endpoints are added to the approved route table deliberately, with tests: unlock, session, lock/logout, header handling, rate limits, 409, validation.
