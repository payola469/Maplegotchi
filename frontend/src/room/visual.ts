// The ONE mapping from backend snapshot to what the room shows. Deterministic,
// pure, and total: unknown backend values fall back to a neutral presentation
// instead of crashing. It decides nothing about Maple's life: activity,
// location, expression, reaction and day phase all come from the snapshot.

import type { SnapshotOut } from "../api/types";
import { type AnchorName, NEUTRAL_ANCHOR } from "./layout/anchors";

export type Pose = "stand" | "walk" | "sleep" | "sit_write" | "sit_monitor" | "read" | "rest";
export type Face = "calm" | "happy" | "curious" | "sleepy" | "focused";
export type ReactionSymbol = "wave" | "heart" | "sleepy_wave" | "sleepy_heart" | "sparkle";
export type Phase = "morning" | "afternoon" | "evening" | "night";

export interface VisualReaction {
  kind: string;
  symbol: ReactionSymbol;
  label: string;
  untilMs: number; // server time; the bubble ends here (presentation only)
}

export interface Lighting {
  phase: Phase;
  darkness: number; // 0..1 overlay strength
  lampGlow: number; // 0..1
  sky: number; // window sky colour (0xRRGGBB)
}

export interface VisualState {
  pose: Pose;
  anchor: AnchorName;
  face: Face;
  reaction: VisualReaction | null;
  lighting: Lighting;
  activityLabel: string;
  recognised: boolean; // false if any backend value was unknown and a fallback was used
}

export const ACTIVITY_POSE: Readonly<Record<string, Pose>> = {
  idle: "stand",
  walk: "walk",
  sleep: "sleep",
  read: "read",
  write: "sit_write",
  observe_server: "sit_monitor",
  rest: "rest",
};

const ACTIVITY_LABEL: Readonly<Record<string, string>> = {
  idle: "idling",
  walk: "walking around",
  sleep: "sleeping",
  read: "reading",
  write: "writing",
  observe_server: "checking the server",
  rest: "resting",
};

/** Backend location -> room anchor (same names; listed so unknown ones are caught). */
export const LOCATION_ANCHOR: Readonly<Record<string, AnchorName>> = {
  bed: "bed",
  bookshelf: "bookshelf",
  window: "window",
  desk: "desk",
  terminal: "terminal",
  rug: "rug",
};

const FACES: ReadonlySet<string> = new Set<Face>(["calm", "happy", "curious", "sleepy", "focused"]);

export const REACTION_SYMBOL: Readonly<Record<string, { symbol: ReactionSymbol; label: string }>> =
  {
    greet_happy: { symbol: "wave", label: "waves hello" },
    greet_sleepy: { symbol: "sleepy_wave", label: "mumbles a sleepy hello" },
    pet_happy: { symbol: "heart", label: "enjoys the pat" },
    pet_sleepy: { symbol: "sleepy_heart", label: "smiles in their sleep" },
  };

export const LIGHTING: Readonly<Record<Phase, Lighting>> = {
  morning: { phase: "morning", darkness: 0.0, lampGlow: 0.0, sky: 0xa8d8f0 },
  afternoon: { phase: "afternoon", darkness: 0.0, lampGlow: 0.0, sky: 0x8fcbef },
  evening: { phase: "evening", darkness: 0.22, lampGlow: 0.55, sky: 0xf2a36b },
  night: { phase: "night", darkness: 0.5, lampGlow: 1.0, sky: 0x1c2550 },
};

export const NEUTRAL_VISUAL: VisualState = {
  pose: "stand",
  anchor: NEUTRAL_ANCHOR,
  face: "calm",
  reaction: null,
  lighting: LIGHTING.afternoon,
  activityLabel: "",
  recognised: true,
};

function lightingFor(phase: string, isNight: boolean): { lighting: Lighting; known: boolean } {
  if (phase in LIGHTING) return { lighting: LIGHTING[phase as Phase], known: true };
  return { lighting: isNight ? LIGHTING.night : LIGHTING.afternoon, known: false };
}

/** Is a reaction still showing at `nowMs` (server clock)? Presentation only. */
export function reactionActive(untilMs: number, nowMs: number): boolean {
  return nowMs < untilMs;
}

export function toVisual(snapshot: SnapshotOut, serverNowMs: number): VisualState {
  const { activity, expression, reaction } = snapshot.maple;
  let recognised = true;

  const pose = ACTIVITY_POSE[activity.kind];
  if (pose === undefined) recognised = false;

  let anchor = LOCATION_ANCHOR[activity.location];
  if (anchor === undefined) {
    recognised = false;
    anchor = NEUTRAL_ANCHOR;
  }

  const face: Face = FACES.has(expression) ? (expression as Face) : "calm";
  if (!FACES.has(expression)) recognised = false;

  let visualReaction: VisualReaction | null = null;
  if (reaction) {
    const untilMs = Date.parse(reaction.until);
    if (Number.isFinite(untilMs) && reactionActive(untilMs, serverNowMs)) {
      const known = REACTION_SYMBOL[reaction.kind];
      if (!known) recognised = false;
      visualReaction = {
        kind: reaction.kind,
        symbol: known?.symbol ?? "sparkle",
        label: known?.label ?? "reacts",
        untilMs,
      };
    }
  }

  const { lighting, known } = lightingFor(snapshot.day.phase, snapshot.day.is_night);
  if (!known) recognised = false;

  return {
    pose: pose ?? "stand",
    anchor,
    face,
    reaction: visualReaction,
    lighting,
    activityLabel: ACTIVITY_LABEL[activity.kind] ?? activity.kind,
    recognised,
  };
}

/** Plain-language summary of the room for screen readers (the canvas is decorative). */
export function describeRoom(snapshot: SnapshotOut, visual: VisualState): string {
  const name = snapshot.maple.identity.name;
  const where = visual.anchor === "terminal" ? "at the computer" : `by the ${visual.anchor}`;
  const parts = [
    `${name} is ${visual.activityLabel || "here"} ${where}, looking ${visual.face}.`,
    `It is ${visual.lighting.phase} in the room.`,
  ];
  if (visual.reaction) parts.push(`${name} ${visual.reaction.label}.`);
  return parts.join(" ");
}
