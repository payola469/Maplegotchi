# ADR-0039: Storage and Maple's slot placement

- **Status:** Accepted — FIXED design (CLAUDE.md D38). **NOT IMPLEMENTED.** Implementation is not yet authorized (roadmap R3–R5). The rate-limit and cooldown values are PROVISIONAL tuning.
- **Date:** 2026-10-08
- **Decided by:** owner, Maple Room review decisions **B4** (Storage), **B5** (placement autonomy), **B11** (slots only), and **B13** (baseline A10, A15).
- **Narrows:** the roadmap's "Inventory" (R3) to **Storage**. **Preserves:** D3 / CLAUDE.md §2. Currency, shops, gifts, feeding, mini-games and any game inventory remain out of scope. **Related:** ADR-0036, ADR-0037, ADR-0038.

## Context

The roadmap wants the room to grow with what Maple makes (R3, R5), and Maple to place creations and allowed decorations in valid slots (R4). "Inventory" in the roadmap would, if taken literally, conflict with the FIXED ban on game systems. The Room also needs a defined home for things that exist but are not displayed.

## Decision

### 1. Storage (B4)
- **Storage means objects that already exist but are not currently displayed in the Room.**
- **Eligible:**
  1. Maple creations that have a room representation and are not placed;
  2. decorations explicitly marked movable/displayable and not placed.
- **Not eligible:** functional furniture, structural objects, doors, walls and system-critical objects. Functional furniture is owner-controlled through Edit Mode only (ADR-0038).
- **Storage is not a game inventory.** It has none of the following:
  - acquiring items as a mechanic;
  - shops, currency or trading;
  - gifts, consumables or loot;
  - reward points or collection scoring;
  - an unlock economy.
- **Lightweight and derived:** an eligible object exists and has no active placement. There is no inventory subsystem.
- **Objects enter Storage when:**
  - a creation is completed but not displayed;
  - a movable decoration is removed from display;
  - an owner layout edit displaces an eligible display object. The preview shows this (ADR-0038).
- **Objects leave Storage only** through a core-validated placement into an allowed slot.
- A physical storage chest or similar object is **optional and deferred**.

### 2. Slot-only placement through R3–R5 (B11)
- Maple places items **only into explicit placement slots** on shelves, desks, display tables, walls or other approved objects.
- **Each slot defines** what it `accepts` (size or category class), its `capacity`, and `maple_may_place`.
  - Catalog defaults are set per type.
  - The owner may override them per instance in Edit Mode.
- **Core validates every placement.** A slot placement never affects walkability and never blocks doors or interactions.
- **Room growth:** if Maple needs more display capacity, Paolo adds or rearranges slot-bearing furniture in Edit Mode.
- **Free-standing placement zones are deferred until after R5.** They are revisited only if real usage shows slots are too restrictive.
- There is no second placement permission model.

### 3. Maple's placement autonomy (B5)
Maple may **autonomously** place her own creations and movable decorations, with **no approval step for permitted placements**, under all of these constraints:
- only into slots with `maple_may_place = true`;
- only objects marked `movable_by: maple`;
- functional furniture is **never** Maple-movable;
- every placement is **core-validated** and **audited** (decision record plus world event);
- Maple **walks to the slot before** the placement happens. Placement is a visible action whose effect is committed on completion;
- **owner overrides in Edit Mode always win;**
- if the owner removes an item from a slot, Maple respects a **cooldown** before considering that slot or item again;
- a **conservative placement rate limit** applies.

### 4. Representations: hooks only (A15)
- A domain entity appears in the Room only through a **derived representation** placed in a slot, linked back by a soft reference.
- This ADR defines only the hooks: the slot `accepts` classes, the instance or placement `link`, and the catalog `represents` metadata.
- Real project, library, creation and System-Room representations arrive with the Workspace / System Investigator phases (W2/W3/S5) under their own ADRs.

## PROVISIONAL
- The placement rate limit (proposed order of magnitude: about 3 per Maple day).
- The owner-removal cooldown (proposed: about 7 days).
- The slot `accepts` class names.

## Deferred
- Free-standing placement zones (after R5, only if needed).
- The storage chest object.
- Growth "unlock" rules.
- Real representations (W2/W3/S5).

## Consequences
- The room can grow and be rearranged without introducing any game system.
- Maple's agency is real but bounded, and it never overrides the owner's arrangement.
- Validation stays local and cheap, so a placement can never break pathfinding.
