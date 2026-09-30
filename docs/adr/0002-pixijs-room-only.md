# ADR-0002: PixiJS renders only the Maple Room

- **Status:** Accepted — FIXED (CLAUDE.md D2)
- **Date:** 2026-09-30
- **Decided by:** owner

## Context
The room is a sprite/animation scene; vitals, journal, timeline, observations, and service health are text- and list-heavy.

## Decision
PixiJS renders only the room / sprite layer. All panels and controls are normal DOM UI components (Preact, proposed).

## Consequences
- Panels get native accessibility, text selection, and layout.
- The canvas stays a pure view of backend state (current activity, reactions).
