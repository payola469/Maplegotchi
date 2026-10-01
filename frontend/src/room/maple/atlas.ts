// Maple's texture atlas: every frame and glyph from sprites.ts painted once
// into ONE canvas, sliced into sub-textures. The source samples with "nearest"
// so the pixel art stays crisp when the room is scaled. That setting belongs to
// this source only; the room, glows and other scene art are unaffected.

import { CanvasSource, Rectangle, Texture } from "pixi.js";
import type { ReactionSymbol } from "../visual";
import { MAPLE_PALETTE } from "./pixels";
import { BUBBLE_GLYPHS, FRAME_H, FRAME_W, SLEEP_GLYPH, allFrames, composeFrame, frameKey } from "./sprites";
// FRAME_W/FRAME_H are only the fallback frame size; cells fit the largest frame.

export interface MapleAtlas {
  frame(key: string): Texture;
  glyph(symbol: ReactionSymbol): Texture;
  sleepGlyph(): Texture;
  destroy(): void;
}

const GAP = 1; // transparent pixel between cells so sampling never bleeds
const COLUMNS = 8;

function css(color: number): string {
  return `#${color.toString(16).padStart(6, "0")}`;
}

export function buildMapleAtlas(): MapleAtlas {
  const cells: { key: string; grid: readonly string[] }[] = [
    ...allFrames().map(({ frame, face }) => ({ key: frameKey(frame, face), grid: composeFrame(frame, face) })),
    ...(Object.keys(BUBBLE_GLYPHS) as ReactionSymbol[]).map((s) => ({ key: `glyph/${s}`, grid: BUBBLE_GLYPHS[s] })),
    { key: "glyph/z", grid: SLEEP_GLYPH },
  ];
  const cellW = Math.max(...cells.map((c) => Math.max(...c.grid.map((l) => l.length)))) + GAP;
  const cellH = Math.max(...cells.map((c) => c.grid.length)) + GAP;
  const rows = Math.ceil(cells.length / COLUMNS);

  const canvas = document.createElement("canvas");
  canvas.width = COLUMNS * cellW;
  canvas.height = rows * cellH;
  const ctx = canvas.getContext("2d");
  const frames = new Map<string, Rectangle>();
  cells.forEach(({ key, grid }, i) => {
    const ox = (i % COLUMNS) * cellW;
    const oy = Math.floor(i / COLUMNS) * cellH;
    const width = Math.max(...grid.map((l) => l.length));
    grid.forEach((line, y) => {
      for (let x = 0; x < line.length; x++) {
        const color = MAPLE_PALETTE[line[x] ?? "."];
        if (color === undefined || !ctx) continue;
        ctx.fillStyle = css(color);
        ctx.fillRect(ox + x, oy + y, 1, 1);
      }
    });
    frames.set(key, new Rectangle(ox, oy, width, grid.length));
  });

  const source = new CanvasSource({ resource: canvas, scaleMode: "nearest" });
  const textures = new Map<string, Texture>();
  const get = (key: string): Texture => {
    let texture = textures.get(key);
    if (!texture) {
      const frame = frames.get(key) ?? frames.get(frameKey("stand", "calm"));
      texture = new Texture({ source, frame: frame ?? new Rectangle(0, 0, FRAME_W, FRAME_H) });
      textures.set(key, texture);
    }
    return texture;
  };

  return {
    frame: get,
    glyph: (symbol) => get(`glyph/${symbol}`),
    sleepGlyph: () => get("glyph/z"),
    destroy() {
      for (const texture of textures.values()) texture.destroy(false);
      textures.clear();
      source.destroy();
    },
  };
}
