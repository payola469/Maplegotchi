import { describe, expect, it } from "vitest";
import { MAPLE_FACES, MAPLE_POSES, REACTION_SYMBOLS } from "../assets/manifest";
import { ACTIVITY_POSE, REACTION_SYMBOL } from "../visual";
import * as pixels from "./pixels";
import {
  BUBBLE_GLYPHS,
  FRAME_LAYOUT,
  PIXEL,
  POSE_FRAMES,
  allFrames,
  composeFrame,
  faceArtFor,
  frameKey,
  mapleUnitsPerPixel,
} from "./sprites";

const grids = Object.entries(pixels).filter(
  (e): e is [string, readonly string[]] => Array.isArray(e[1]) && typeof e[1][0] === "string",
);
const faceGrids = Object.entries(pixels.FACES);

describe("pixel art data", () => {
  it.each([...grids, ...faceGrids])("%s is rectangular and uses only palette colours", (_name, grid) => {
    const width = grid[0]?.length ?? 0;
    expect(width).toBeGreaterThan(0);
    for (const line of grid) {
      expect(line).toHaveLength(width);
      for (const ch of line) if (ch !== ".") expect(pixels.MAPLE_PALETTE).toHaveProperty(ch);
    }
  });

  it("every frame part fits inside the frame", () => {
    for (const layout of Object.values(FRAME_LAYOUT)) {
      for (const { grid, x, y } of layout.parts) {
        expect(x + (grid[0]?.length ?? 0)).toBeLessThanOrEqual(layout.width);
        expect(y + grid.length).toBeLessThanOrEqual(layout.height);
      }
      expect(layout.origin.x).toBeGreaterThanOrEqual(0);
      expect(layout.origin.x).toBeLessThanOrEqual(layout.width);
      expect(layout.origin.y).toBe(layout.height); // the origin is always on the bottom edge
    }
  });
});

describe("pose and expression coverage", () => {
  it("has frames for every pose the mapping produces", () => {
    expect(Object.keys(POSE_FRAMES).sort()).toEqual([...MAPLE_POSES].sort());
    for (const pose of Object.values(ACTIVITY_POSE)) expect(POSE_FRAMES[pose].length).toBeGreaterThan(0);
  });

  it.each(MAPLE_POSES.flatMap((pose) => MAPLE_FACES.map((face) => [pose, face] as const)))(
    "%s / %s composes a full frame with the character's look",
    (pose, face) => {
      for (const frame of POSE_FRAMES[pose]) {
        const { width, height } = FRAME_LAYOUT[frame];
        const grid = composeFrame(frame, faceArtFor(pose, face));
        expect(grid).toHaveLength(height);
        for (const line of grid) expect(line).toHaveLength(width);
        const art = grid.join("");
        for (const ch of ["H", "O", "G", "F"]) expect(art).toContain(ch); // hair, headphones, hoodie/quilt, glasses
        // Something rests on the bottom row (feet, or the quilt on the mattress).
        expect(grid[height - 1]).toMatch(/K/);
      }
    },
  );

  it("shows each expression differently while awake", () => {
    for (const pose of MAPLE_POSES.filter((p) => p !== "sleep")) {
      const frame = POSE_FRAMES[pose][0] ?? "stand";
      const looks = new Set(MAPLE_FACES.map((f) => composeFrame(frame, faceArtFor(pose, f)).join("\n")));
      expect(looks.size).toBe(MAPLE_FACES.length);
    }
  });

  it("falls back to the closed-eye face for every expression while asleep", () => {
    for (const face of MAPLE_FACES) expect(faceArtFor("sleep", face)).toBe("asleep");
    for (const pose of MAPLE_POSES.filter((p) => p !== "sleep")) {
      for (const face of MAPLE_FACES) expect(faceArtFor(pose, face)).toBe(face);
    }
  });

  it("sleeps lying down: a wide, low frame with the head on the left and the quilt over the body", () => {
    const layout = FRAME_LAYOUT.sleep;
    expect(layout.width).toBeGreaterThan(layout.height);
    const grid = composeFrame("sleep", "asleep");
    const art = grid.join("");
    expect(art).toContain("C"); // the quilt's folded edge
    expect(art).not.toContain("B"); // no shoes: the legs are under the quilt
    // The head (hair) is on the left, under the origin; the quilt reaches the right edge.
    const hairCols = grid.flatMap((l) => [...l].flatMap((ch, x) => (ch === "H" ? [x] : [])));
    expect(Math.max(...hairCols)).toBeLessThan(layout.width / 2);
    expect(grid.some((l) => l[layout.width - 1] === "K")).toBe(true);
    expect(layout.origin.x).toBeGreaterThanOrEqual(Math.min(...hairCols));
    expect(layout.origin.x).toBeLessThanOrEqual(Math.max(...hairCols));
  });

  it("walks with two different leg frames", () => {
    const [a, b] = POSE_FRAMES.walk;
    expect(a && b && composeFrame(a, "calm").join()).not.toBe(b && composeFrame(b, "calm").join());
  });

  it("the atlas list holds every frame the figure can ask for, once", () => {
    const keys = allFrames().map(({ frame, face }) => frameKey(frame, face));
    expect(new Set(keys).size).toBe(keys.length);
    for (const pose of MAPLE_POSES) {
      for (const frame of POSE_FRAMES[pose]) {
        for (const face of MAPLE_FACES) expect(keys).toContain(frameKey(frame, faceArtFor(pose, face)));
      }
    }
  });
});

describe("bubble glyphs", () => {
  it("has a distinct glyph for every symbol, including the fallback", () => {
    expect(Object.keys(BUBBLE_GLYPHS).sort()).toEqual([...REACTION_SYMBOLS].sort());
    for (const { symbol } of Object.values(REACTION_SYMBOL)) expect(BUBBLE_GLYPHS[symbol]).toBeDefined();
    const looks = new Set(Object.values(BUBBLE_GLYPHS).map((g) => g.join("\n")));
    expect(looks.size).toBe(REACTION_SYMBOLS.length);
  });

  it("keeps the sleepy variants sleepy and the hearts hearts", () => {
    expect(BUBBLE_GLYPHS.sleepy_heart.join("")).toContain("r");
    expect(BUBBLE_GLYPHS.sleepy_heart.join("")).toContain("Z");
    expect(BUBBLE_GLYPHS.heart.join("")).toContain("r");
    expect(BUBBLE_GLYPHS.sleepy_wave.join("")).toContain("Z");
  });
});

describe("responsive Maple scale (presentation only)", () => {
  it("is exactly the room pixel on a full-size room", () => {
    for (const res of [1, 2]) for (const scale of [0.8, 0.9, 1, 1.4]) expect(mapleUnitsPerPixel(scale, res)).toBe(PIXEL);
  });

  it("is a little larger when the room is small, never smaller, never much larger", () => {
    for (const res of [1, 1.5, 2]) {
      for (let scale = 0.2; scale < 0.8; scale += 0.01) {
        const u = mapleUnitsPerPixel(scale, res);
        expect(u).toBeGreaterThan(PIXEL);
        expect(u).toBeLessThanOrEqual(PIXEL * 1.25 * 1.12);
      }
    }
  });

  it("snaps to whole canvas pixels when that stays close to the target", () => {
    const u = mapleUnitsPerPixel(0.656, 2); // a tablet-width room on a 2x screen
    expect(Number.isInteger(Math.round(u * 0.656 * 2 * 1e6) / 1e6)).toBe(true);
  });

  it("falls back to the plain room pixel for nonsense input", () => {
    expect(mapleUnitsPerPixel(0, 1)).toBe(PIXEL);
    expect(mapleUnitsPerPixel(Number.NaN, 1)).toBe(PIXEL);
  });
});
