// Asset manifest: the only place that says how each room object is drawn.
//
// v0.1 assets are ORIGINAL vector drawings in code (room/objects/furniture.ts,
// room/maple/figure.ts) — no third-party art. A future artist can replace any
// furniture piece by adding an image under frontend/public/assets/room/ and
// setting `texture` here; the scene then shows the image instead of the vector
// drawing, placed by the same layout box and anchor. Nothing about Maple's state
// is encoded in these names: the mapping lives in room/visual.ts.
//
// Conventions: logical units (room is 1000 x 600, see layout/anchors.ts);
// `box` comes from FURNITURE; textures should be drawn at 2x the box size for
// crisp high-DPI rendering, with a transparent background.

import { FURNITURE } from "../layout/anchors";

export type FurnitureKey = keyof typeof FURNITURE;

export interface FurnitureAsset {
  key: FurnitureKey;
  description: string;
  texture?: string; // e.g. "/assets/room/bed.png" (served from frontend/public)
}

export const FURNITURE_ASSETS: Readonly<Record<FurnitureKey, FurnitureAsset>> = {
  window: { key: "window", description: "back-wall window; sky colour follows day/night" },
  bookshelf: { key: "bookshelf", description: "bookshelf with books" },
  bed: { key: "bed", description: "bed with pillow and blanket" },
  lamp: { key: "lamp", description: "floor lamp (its glow is a separate lighting layer)" },
  desk: { key: "desk", description: "writing desk with notebook" },
  chair: { key: "chair", description: "desk chair" },
  computerDesk: { key: "computerDesk", description: "desk under the computer" },
  monitor: { key: "monitor", description: "computer monitor showing paolo-core" },
  plant: { key: "plant", description: "potted plant" },
  rug: { key: "rug", description: "round rug in the middle of the floor" },
};

// Maple contract: pixel art as text grids in room/maple/pixels.ts, composed by
// room/maple/sprites.ts into one frame per pose (walk: two) — stand, walk, sleep,
// sit_write, sit_monitor, read, rest — times one face per expression — calm,
// happy, curious, sleepy, focused (sleep always uses its closed-eye face) — plus
// one bubble glyph per symbol — wave, heart, sleepy_wave, sleepy_heart, sparkle.
// Frames are 24 x 28 pixels at 4 logical units per pixel (96 x 112 units).
// Origin: between Maple's feet.
export const MAPLE_POSES = [
  "stand",
  "walk",
  "sleep",
  "sit_write",
  "sit_monitor",
  "read",
  "rest",
] as const;
export const MAPLE_FACES = ["calm", "happy", "curious", "sleepy", "focused"] as const;
export const REACTION_SYMBOLS = ["wave", "heart", "sleepy_wave", "sleepy_heart", "sparkle"] as const;
