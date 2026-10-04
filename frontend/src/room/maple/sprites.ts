// The ONE place that says which pixel art Maple shows for a pose, an expression
// and a bubble symbol. Pure and Pixi-free (tested in sprites.test.ts); atlas.ts
// paints these grids into textures. Poses, faces and symbols are the existing
// presentation values from room/visual.ts; nothing here decides Maple's state.

import type { Face, Pose, ReactionSymbol } from "../visual";
import {
  ARMS_HOLD,
  ARMS_MUG,
  ARMS_TYPE,
  ARMS_WRITE,
  BOOK,
  FACES,
  FLOOR_LEGS,
  GLYPH_HEART,
  GLYPH_HI,
  GLYPH_SLEEPY_HI,
  GLYPH_SPARKLE,
  GLYPH_Z,
  type Grid,
  HEAD,
  LEGS_STAND,
  LEGS_WALK_A,
  LEGS_WALK_B,
  QUILT,
  SEAT_LEGS,
  TORSO_STAND,
  TORSO_TOP,
} from "./pixels";

/** Logical room units per sprite pixel (the room art uses the same 4-unit grid). */
export const PIXEL = 4;
export const FRAME_W = 24;
export const FRAME_H = 28;

export type FrameId = "stand" | "walk_a" | "walk_b" | "sleep" | "read" | "sit_write" | "sit_monitor" | "rest";
export type FaceArt = keyof typeof FACES;

interface Placed {
  grid: Grid;
  x: number;
  y: number;
}

interface FrameLayout {
  width: number;
  height: number;
  /** The figure's origin inside the frame, in pixels (between the feet when upright). */
  origin: { x: number; y: number };
  parts: readonly Placed[];
  face: { x: number; y: number };
}

const UPRIGHT = { width: FRAME_W, height: FRAME_H, origin: { x: FRAME_W / 2, y: FRAME_H } } as const;

// Head at the top for standing frames; seated frames lower the head so the feet
// stay on the frame's bottom row (the figure's origin is between the feet).
const standing = (legs: Grid): FrameLayout => ({
  ...UPRIGHT,
  parts: [
    { grid: HEAD, x: 0, y: 0 },
    { grid: TORSO_TOP, x: 0, y: 14 },
    { grid: TORSO_STAND, x: 0, y: 18 },
    { grid: legs, x: 0, y: 24 },
  ],
  face: { x: 6, y: 8 },
});

const seated = (arms: Grid): FrameLayout => ({
  ...UPRIGHT,
  parts: [
    { grid: HEAD, x: 0, y: 3 },
    { grid: TORSO_TOP, x: 0, y: 17 },
    { grid: arms, x: 0, y: 21 },
    { grid: SEAT_LEGS, x: 0, y: 23 },
  ],
  face: { x: 6, y: 11 },
});

const onFloor = (arms: Grid, extra: readonly Placed[] = []): FrameLayout => ({
  ...UPRIGHT,
  parts: [
    { grid: HEAD, x: 0, y: 4 },
    { grid: TORSO_TOP, x: 0, y: 18 },
    { grid: arms, x: 0, y: 22 },
    { grid: FLOOR_LEGS, x: 0, y: 24 },
    ...extra,
  ],
  face: { x: 6, y: 12 },
});

export const FRAME_LAYOUT: Readonly<Record<FrameId, FrameLayout>> = {
  stand: standing(LEGS_STAND),
  walk_a: standing(LEGS_WALK_A),
  walk_b: standing(LEGS_WALK_B),
  // Lying in bed: head on the pillow, the quilt over the body to the right.
  // Origin: under the middle of the head, on the mattress line.
  sleep: {
    width: 40,
    height: 18,
    origin: { x: 12, y: 18 },
    parts: [
      { grid: HEAD, x: 0, y: 0 },
      { grid: QUILT, x: 18, y: 10 },
    ],
    face: { x: 6, y: 8 },
  },
  read: onFloor(ARMS_HOLD, [{ grid: BOOK, x: 6, y: 21 }]),
  sit_write: seated(ARMS_WRITE),
  sit_monitor: seated(ARMS_TYPE),
  rest: onFloor(ARMS_MUG),
};

/** Frames per pose. Walk alternates two leg frames; every other pose has one. */
export const POSE_FRAMES: Readonly<Record<Pose, readonly FrameId[]>> = {
  stand: ["stand"],
  walk: ["walk_a", "walk_b"],
  sleep: ["sleep"],
  read: ["read"],
  sit_write: ["sit_write"],
  sit_monitor: ["sit_monitor"],
  rest: ["rest"],
};

/**
 * Fallback rules for pose/expression combinations without unique art:
 * - sleep: always the closed-eye "asleep" face, whatever the expression
 *   (as before, where a sleeping Maple was always drawn sleepy);
 * - every other pose shows all five expressions unchanged.
 */
export function faceArtFor(pose: Pose, face: Face): FaceArt {
  return pose === "sleep" ? "asleep" : face;
}

export function frameKey(frame: FrameId, face: FaceArt): string {
  return `${frame}/${face}`;
}

/** Paint grids onto a blank canvas of the given size ("." never overwrites). */
function paint(width: number, height: number, parts: readonly Placed[]): string[] {
  const rows = Array.from({ length: height }, () => Array<string>(width).fill("."));
  for (const { grid, x, y } of parts) {
    grid.forEach((line, dy) => {
      for (let dx = 0; dx < line.length; dx++) {
        const ch = line[dx];
        const row = rows[y + dy];
        if (ch !== undefined && ch !== "." && row !== undefined && x + dx < width) row[x + dx] = ch;
      }
    });
  }
  return rows.map((r) => r.join(""));
}

export function composeFrame(frame: FrameId, face: FaceArt): string[] {
  const layout = FRAME_LAYOUT[frame];
  return paint(layout.width, layout.height, [...layout.parts, { grid: FACES[face], ...layout.face }]);
}

const widthOf = (grid: Grid) => Math.max(...grid.map((l) => l.length));

/** Bubble contents, one per symbol (same meaning as the former text: "Hi!", "♥", "…hi", "♥ z", "✦"). */
export const BUBBLE_GLYPHS: Readonly<Record<ReactionSymbol, readonly string[]>> = {
  wave: GLYPH_HI,
  heart: GLYPH_HEART,
  sleepy_wave: GLYPH_SLEEPY_HI,
  sleepy_heart: paint(widthOf(GLYPH_HEART) + 1 + widthOf(GLYPH_Z), GLYPH_HEART.length, [
    { grid: GLYPH_HEART, x: 0, y: 0 },
    { grid: GLYPH_Z, x: widthOf(GLYPH_HEART) + 1, y: 2 },
  ]),
  sparkle: GLYPH_SPARKLE,
};

export const SLEEP_GLYPH: Grid = GLYPH_Z;

/** Every (frame, face) the figure can show: what the atlas must contain. */
export function allFrames(): { frame: FrameId; face: FaceArt }[] {
  const faces: readonly Face[] = ["calm", "happy", "curious", "sleepy", "focused"];
  const seen = new Set<string>();
  const out: { frame: FrameId; face: FaceArt }[] = [];
  for (const pose of Object.keys(POSE_FRAMES) as Pose[]) {
    for (const frame of POSE_FRAMES[pose]) {
      for (const f of faces) {
        const face = faceArtFor(pose, f);
        const key = frameKey(frame, face);
        if (!seen.has(key)) {
          seen.add(key);
          out.push({ frame, face });
        }
      }
    }
  }
  return out;
}

/**
 * Logical units per sprite pixel for the current display (presentation only).
 * Maple is drawn a little larger when the room is shown small (tablet, phone),
 * and snapped to whole canvas pixels when that stays close to the target, so
 * the pixel art stays even. On a full-size room it is exactly PIXEL.
 */
export function mapleUnitsPerPixel(displayScale: number, resolution: number): number {
  if (!(displayScale > 0) || displayScale >= 0.8) return PIXEL;
  const target = PIXEL * (displayScale < 0.5 ? 1.25 : 1.125);
  const perUnit = displayScale * (resolution > 0 ? resolution : 1);
  const exact = target * perUnit;
  const candidates = [Math.floor(exact), Math.ceil(exact)]
    .filter((n) => n >= 1)
    .map((n) => n / perUnit)
    .filter((u) => u >= Math.max(PIXEL, target * 0.9) && u <= target * 1.12)
    .sort((a, b) => Math.abs(a - target) - Math.abs(b - target));
  return candidates[0] ?? target;
}
