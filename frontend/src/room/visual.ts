// The ONE mapping from backend snapshot to what the room shows. Deterministic,
// pure, and total: unknown backend values fall back to a neutral presentation
// instead of crashing. It decides nothing about Maple's life: activity,
// location, expression, reaction and day phase all come from the snapshot.

import type { SnapshotOut } from "../api/types";
import { ANCHORS, type AnchorName, NEUTRAL_ANCHOR, type Point } from "./layout/anchors";

export type Pose = "stand" | "walk" | "sleep" | "sit_write" | "sit_monitor" | "read" | "rest" | "think";
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

/** A backend route (ADR-0027): the room follows it; it never plans its own walks. */
export interface VisualRoute {
  departedMs: number; // server time
  arrivesMs: number; // server time; the activity begins here
  path: { x: number; y: number; distance: number }[];
}

export interface VisualState {
  pose: Pose; // what Maple looks like at the mapped time ("walk" while walking)
  anchor: AnchorName;
  restPosition: Point; // where Maple is (or will be, on arrival), from the backend
  restPose: Pose; // the activity's pose once there
  route: VisualRoute | null;
  clockOffsetMs: number; // server time minus local time, to follow `route` smoothly
  walking: boolean;
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
  think: "think",
};

const ACTIVITY_LABEL: Readonly<Record<string, string>> = {
  idle: "idling",
  walk: "walking around",
  sleep: "sleeping",
  read: "reading",
  write: "writing",
  observe_server: "checking the server",
  rest: "resting",
  think: "thinking",
};

/** Display names of the backend's furniture ids (ADR-0027). */
export const FURNITURE_LABEL: Readonly<Record<string, string>> = {
  bed: "bed",
  writing_desk: "writing desk",
  computer_desk: "computer desk",
  bookshelf: "bookshelf",
  sofa: "sofa",
  window_plant_corner: "window",
  open_area: "open floor",
};

/** Backend location -> room anchor (same names; listed so unknown ones are caught). */
export const LOCATION_ANCHOR: Readonly<Record<string, AnchorName>> = {
  bed: "bed",
  bookshelf: "bookshelf",
  window: "window",
  desk: "desk",
  terminal: "terminal",
  rug: "rug",
  sofa: "sofa",
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
  restPosition: ANCHORS[NEUTRAL_ANCHOR],
  restPose: "stand",
  route: null,
  clockOffsetMs: 0,
  walking: false,
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

function finitePoint(value: { x: number; y: number } | undefined | null): Point | null {
  if (!value || !Number.isFinite(value.x) || !Number.isFinite(value.y)) return null;
  return { x: value.x, y: value.y };
}

function routeOf(snapshot: SnapshotOut): VisualRoute | null {
  const route = snapshot.maple.activity.route;
  if (!route) return null;
  const departedMs = Date.parse(route.departed_at);
  const arrivesMs = Date.parse(route.arrives_at);
  const path = route.path.filter(
    (p) => Number.isFinite(p.x) && Number.isFinite(p.y) && Number.isFinite(p.distance),
  );
  if (!Number.isFinite(departedMs) || !(arrivesMs > departedMs) || path.length < 2) return null;
  return { departedMs, arrivesMs, path: path.map(({ x, y, distance }) => ({ x, y, distance })) };
}

export function toVisual(snapshot: SnapshotOut, serverNowMs: number, clockOffsetMs = 0): VisualState {
  const { activity, expression, reaction } = snapshot.maple;
  let recognised = true;

  const activityPose = ACTIVITY_POSE[activity.kind];
  if (activityPose === undefined) recognised = false;

  let anchor = LOCATION_ANCHOR[activity.location];
  if (anchor === undefined) {
    recognised = false;
    anchor = NEUTRAL_ANCHOR;
  }

  // Movement is backend truth (ADR-0027): position, route, and arrival time.
  const route = routeOf(snapshot);
  const walking = route !== null && serverNowMs < route.arrivesMs;
  const destination = route ? route.path[route.path.length - 1] : null;
  const restPosition =
    (destination ? { x: destination.x, y: destination.y } : finitePoint(activity.position)) ??
    ANCHORS[anchor];
  const pose: Pose | undefined = walking ? "walk" : activityPose;
  const going = FURNITURE_LABEL[activity.furniture];

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

  const doing = ACTIVITY_LABEL[activity.kind] ?? activity.kind;
  return {
    pose: pose ?? "stand",
    anchor,
    restPosition,
    restPose: activityPose ?? "stand",
    route,
    clockOffsetMs,
    walking,
    face,
    reaction: visualReaction,
    lighting,
    activityLabel: walking ? `on the way to the ${going ?? "next spot"} (to start ${doing})` : doing,
    recognised,
  };
}

/** Plain-language summary of the room for screen readers (the canvas is decorative). */
export function describeRoom(snapshot: SnapshotOut, visual: VisualState): string {
  const name = snapshot.maple.identity.name;
  const furniture = FURNITURE_LABEL[snapshot.maple.activity.furniture] ?? visual.anchor;
  const where = visual.walking
    ? "in the room"
    : visual.anchor === "terminal"
      ? "at the computer"
      : `by the ${furniture}`;
  const parts = [
    `${name} is ${visual.activityLabel || "here"} ${where}, looking ${visual.face}.`,
    `It is ${visual.lighting.phase} in the room.`,
  ];
  if (visual.reaction) parts.push(`${name} ${visual.reaction.label}.`);
  return parts.join(" ");
}
