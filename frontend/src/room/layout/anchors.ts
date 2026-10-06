// Fixed room layout in logical units (the scene scales it to fit). No physics:
// named anchors only. Anchor names are the backend's logical room locations.

export const ROOM_WIDTH = 1000;
export const ROOM_HEIGHT = 600;
export const FLOOR_Y = 380; // where the back wall meets the floor

export type AnchorName = "bed" | "bookshelf" | "window" | "desk" | "terminal" | "rug" | "sofa";

export interface Point {
  x: number;
  y: number;
}

/** Fallback feet position per backend location. The backend sends Maple's exact position and
 * route (ADR-0027); these are used only if a snapshot lacks them. */
export const ANCHORS: Readonly<Record<AnchorName, Point>> = {
  bed: { x: 150, y: 455 },
  bookshelf: { x: 330, y: 500 },
  window: { x: 500, y: 470 },
  desk: { x: 640, y: 470 },
  terminal: { x: 840, y: 470 },
  rug: { x: 480, y: 545 },
  sofa: { x: 150, y: 560 },
};

/** Where Maple starts before the first snapshot (never shown as state). */
export const NEUTRAL_ANCHOR: AnchorName = "rug";

/** Furniture placement (top-left of each object's footprint, logical units). */
export const FURNITURE = {
  window: { x: 420, y: 90, width: 170, height: 150 },
  bookshelf: { x: 260, y: 200, width: 130, height: 250 },
  bed: { x: 40, y: 380, width: 210, height: 110 },
  lamp: { x: 398, y: 300, width: 40, height: 150 },
  desk: { x: 600, y: 360, width: 160, height: 100 },
  chair: { x: 620, y: 420, width: 60, height: 80 },
  computerDesk: { x: 780, y: 360, width: 160, height: 100 },
  monitor: { x: 815, y: 290, width: 90, height: 70 },
  plant: { x: 548, y: 388, width: 40, height: 90 }, // the Window / Plant Corner
  sofa: { x: 60, y: 505, width: 180, height: 80 },
  rug: { x: 330, y: 510, width: 300, height: 70 },
} as const;
