// Original v0.1 room art, drawn in code. Each function draws into a Graphics at
// the layout box from FURNITURE (boxes and anchors are unchanged; only the
// drawing is). Visual language: cozy pixel-art — blocky silhouettes on a 4-unit
// grid, flat colours with one highlight and one shade, dark outlines, warm wood,
// dark green and warm orange accents, navy for depth. Purely decorative: nothing
// here encodes Maple's state.

import { Graphics } from "pixi.js";
import { FLOOR_Y, FURNITURE, ROOM_HEIGHT, ROOM_WIDTH } from "../layout/anchors";
import type { FurnitureKey } from "../assets/manifest";

/** Room palette (presentation only). */
export const PALETTE = {
  outline: 0x3a2417,
  wall: 0xf0dcb8,
  wallDot: 0xe5cc9f,
  wallShade: 0xd9bf93,
  wainscot: 0x2f5d46,
  wainscotDark: 0x24493a,
  wainscotLight: 0x3c6f55,
  rail: 0x7a4b2c,
  baseboard: 0x4f3020,
  floor: 0xb27a4a,
  floorDark: 0x96623a,
  floorLight: 0xc48b57,
  wood: 0x8a5733,
  woodDark: 0x5e3a21,
  woodLight: 0xb47b4b,
  cream: 0xf6ebd6,
  creamShade: 0xe2d2b4,
  green: 0x2f5d46,
  greenLight: 0x3f7a5a,
  leaf: 0x4f8a4a,
  leafDark: 0x3a6a3a,
  orange: 0xd9773a,
  orangeDark: 0xa9542a,
  navy: 0x26345a,
  navyDark: 0x1a2440,
  mustard: 0xd9a441,
  plum: 0x6b4f7a,
  brick: 0xb5523a,
  terracotta: 0xc0613a,
  amber: 0xf2b45c,
  amberLight: 0xffdc9a,
  screen: 0x10283a,
  screenText: 0x6fd6c0,
  metal: 0x2b2f3a,
} as const;

const P = PALETTE;

/** A filled block with a 2-unit dark outline (the basic pixel-art "sprite" shape). */
function block(g: Graphics, x: number, y: number, w: number, h: number, color: number, outline: number = P.outline): void {
  g.rect(x - 2, y - 2, w + 4, h + 4).fill(outline);
  g.rect(x, y, w, h).fill(color);
}

/** An ellipse drawn as stacked rows (stepped, pixel-art edges). */
function steppedEllipse(g: Graphics, cx: number, cy: number, rx: number, ry: number, step: number, color: number): void {
  for (let y = -ry; y < ry; y += step) {
    const mid = y + step / 2;
    const half = rx * Math.sqrt(Math.max(0, 1 - (mid * mid) / (ry * ry)));
    const w = Math.round(half / step) * step;
    if (w > 0) g.rect(cx - w, cy + y, w * 2, step).fill(color);
  }
}

export function drawWallsAndFloor(g: Graphics): void {
  // Upper wall with a small pixel dot pattern.
  g.rect(0, 0, ROOM_WIDTH, FLOOR_Y).fill(P.wall);
  for (let y = 24; y < 290; y += 32) {
    for (let x = (y / 32) % 2 === 0 ? 16 : 32; x < ROOM_WIDTH; x += 32) g.rect(x, y, 4, 4).fill(P.wallDot);
  }
  // Ceiling shade for depth.
  g.rect(0, 0, ROOM_WIDTH, 14).fill(P.wallShade);
  g.rect(0, 14, ROOM_WIDTH, 4).fill({ color: P.wallShade, alpha: 0.5 });

  // Dark green wainscot with panels and a wooden rail.
  const top = 300;
  g.rect(0, top, ROOM_WIDTH, FLOOR_Y - top).fill(P.wainscot);
  for (let x = 12; x < ROOM_WIDTH; x += 64) {
    g.rect(x, top + 14, 48, FLOOR_Y - top - 30).fill(P.wainscotDark);
    g.rect(x + 4, top + 18, 40, FLOOR_Y - top - 38).fill(P.wainscotLight);
    g.rect(x + 4, top + 18, 40, 4).fill(P.wainscotDark);
  }
  g.rect(0, top - 8, ROOM_WIDTH, 10).fill(P.rail);
  g.rect(0, top - 8, ROOM_WIDTH, 3).fill(P.woodLight);

  // Floor planks: staggered seams, a highlight row and a darker band at the wall.
  g.rect(0, FLOOR_Y, ROOM_WIDTH, ROOM_HEIGHT - FLOOR_Y).fill(P.floor);
  let row = 0;
  for (let y = FLOOR_Y; y < ROOM_HEIGHT; y += 24, row++) {
    g.rect(0, y, ROOM_WIDTH, 2).fill(P.floorDark);
    g.rect(0, y + 2, ROOM_WIDTH, 2).fill({ color: P.floorLight, alpha: 0.6 });
    for (let x = (row % 3) * 70; x < ROOM_WIDTH; x += 210) g.rect(x, y, 2, 24).fill(P.floorDark);
  }
  g.rect(0, FLOOR_Y, ROOM_WIDTH, 22).fill({ color: P.outline, alpha: 0.18 });
  g.rect(0, FLOOR_Y - 12, ROOM_WIDTH, 14).fill(P.baseboard);
  g.rect(0, FLOOR_Y - 12, ROOM_WIDTH, 3).fill(P.wood);

  drawWallDecor(g);
}

/** Static decoration on the back wall (no information, no clocks or dates). */
function drawWallDecor(g: Graphics): void {
  // Framed picture over the bed: a small night landscape with a maple leaf moon.
  block(g, 84, 132, 104, 76, P.woodDark);
  g.rect(90, 138, 92, 64).fill(P.navy);
  g.rect(90, 176, 92, 26).fill(P.green);
  g.rect(110, 168, 30, 10).fill(P.green);
  g.rect(140, 172, 24, 6).fill(P.greenLight);
  g.rect(152, 146, 12, 12).fill(P.orange);
  g.rect(148, 150, 20, 4).fill(P.orange);
  for (const [sx, sy] of [[100, 146], [124, 152], [170, 166]] as const) g.rect(sx, sy, 3, 3).fill(P.cream);

  // Small wall shelf above the computer, with a pot and two books.
  g.rect(820, 214, 120, 8).fill(P.woodDark);
  g.rect(820, 214, 120, 3).fill(P.woodLight);
  g.rect(828, 222, 6, 10).fill(P.woodDark);
  g.rect(926, 222, 6, 10).fill(P.woodDark);
  block(g, 840, 190, 18, 22, P.terracotta);
  g.rect(836, 176, 10, 12).fill(P.leaf);
  g.rect(850, 172, 10, 16).fill(P.leafDark);
  block(g, 888, 182, 10, 30, P.navy);
  block(g, 902, 186, 10, 26, P.mustard);

  // Garland of warm bulbs under the ceiling (decorative; not a light source).
  for (let x = 30, i = 0; x < ROOM_WIDTH; x += 60, i++) {
    const y = 30 + ((i % 2) * 8);
    g.rect(x, y - 2, 60, 2).fill({ color: P.outline, alpha: 0.45 });
    g.rect(x + 26, y, 8, 8).fill(i % 3 === 0 ? P.orange : P.amber);
    g.rect(x + 28, y + 2, 3, 3).fill(P.amberLight);
  }
}

/** The window frame and curtains; the sky inside is drawn by the scene (it changes with the day). */
export function drawWindowFrame(g: Graphics): void {
  const w = FURNITURE.window;
  const frame = P.woodDark;
  // Outer frame (four bars so the sky stays visible) and muntins.
  g.rect(w.x - 10, w.y - 10, w.width + 20, 10).fill(frame);
  g.rect(w.x - 10, w.y + w.height, w.width + 20, 10).fill(frame);
  g.rect(w.x - 10, w.y, 10, w.height).fill(frame);
  g.rect(w.x + w.width, w.y, 10, w.height).fill(frame);
  g.rect(w.x + w.width / 2 - 3, w.y, 6, w.height).fill(frame);
  g.rect(w.x, w.y + w.height / 2 - 3, w.width, 6).fill(frame);
  g.rect(w.x - 6, w.y - 6, w.width + 12, 2).fill(P.wood);
  // Sill.
  block(g, w.x - 20, w.y + w.height + 10, w.width + 40, 10, P.woodLight);
  // Curtain rod and curtains (orange, with pixel folds and tie-backs).
  g.rect(w.x - 44, w.y - 24, w.width + 88, 6).fill(P.outline);
  g.rect(w.x - 50, w.y - 26, 10, 10).fill(P.woodDark);
  g.rect(w.x + w.width + 40, w.y - 26, 10, 10).fill(P.woodDark);
  for (const side of [-1, 1] as const) {
    const x0 = side < 0 ? w.x - 40 : w.x + w.width + 8;
    const width = 32;
    g.rect(x0, w.y - 18, width, w.height + 40).fill(P.orange);
    for (let fx = x0 + 6; fx < x0 + width; fx += 10) g.rect(fx, w.y - 18, 3, w.height + 40).fill(P.orangeDark);
    g.rect(x0, w.y + w.height + 22, width, 6).fill(P.orangeDark);
    g.rect(x0 - 2, w.y + w.height * 0.55, width + 4, 6).fill(P.mustard);
  }
}

const BOOK_COLORS = [P.brick, P.green, P.navy, P.mustard, P.orange, P.plum, P.cream] as const;

const DRAWERS: Record<Exclude<FurnitureKey, "window">, (g: Graphics) => void> = {
  bookshelf(g) {
    const b = FURNITURE.bookshelf;
    block(g, b.x, b.y, b.width, b.height, P.wood);
    g.rect(b.x + 8, b.y + 8, b.width - 16, b.height - 16).fill(P.woodDark);
    g.rect(b.x, b.y, b.width, 6).fill(P.woodLight);
    for (let shelf = 0; shelf < 3; shelf++) {
      const y = b.y + 15 + shelf * 78;
      g.rect(b.x + 8, y + 62, b.width - 16, 8).fill(P.wood);
      g.rect(b.x + 8, y + 62, b.width - 16, 2).fill(P.woodLight);
      let x = b.x + 12;
      for (let i = 0; x < b.x + b.width - 22; i++) {
        const width = 12 + ((i * 7 + shelf * 5) % 3) * 4;
        const height = 40 + ((i * 11 + shelf * 3) % 5) * 4;
        const color = BOOK_COLORS[(i + shelf * 2) % BOOK_COLORS.length] ?? P.brick;
        g.rect(x, y + 62 - height, width, height).fill(color);
        g.rect(x, y + 62 - height, 2, height).fill({ color: 0xffffff, alpha: 0.18 });
        g.rect(x + 2, y + 62 - height + 8, width - 4, 3).fill({ color: P.outline, alpha: 0.25 });
        x += width + 2;
      }
    }
    // A small plant and a box on top.
    block(g, b.x + 14, b.y - 22, 18, 20, P.terracotta);
    g.rect(b.x + 10, b.y - 38, 10, 14).fill(P.leaf);
    g.rect(b.x + 24, b.y - 42, 10, 18).fill(P.leafDark);
    block(g, b.x + 80, b.y - 18, 34, 16, P.navy);
    g.rect(b.x + 80, b.y - 18, 34, 3).fill(P.mustard);
  },
  bed(g) {
    const b = FURNITURE.bed;
    // Contact shadow.
    g.rect(b.x + 6, b.y + b.height - 6, b.width + 10, 10).fill({ color: P.outline, alpha: 0.25 });
    // Headboard with a stepped top.
    block(g, b.x, b.y - 32, 28, b.height + 32, P.woodDark);
    g.rect(b.x + 4, b.y - 40, 20, 8).fill(P.woodDark);
    g.rect(b.x + 4, b.y - 40, 20, 3).fill(P.wood);
    g.rect(b.x + 6, b.y - 24, 4, b.height + 14).fill(P.wood);
    // Frame and footboard.
    block(g, b.x + 10, b.y + 22, b.width, b.height - 42, P.wood);
    g.rect(b.x + 10, b.y + 22, b.width, 4).fill(P.woodLight);
    block(g, b.x + b.width + 2, b.y + 6, 12, b.height - 22, P.woodDark);
    // Mattress, pillow and a dark green blanket with a checker pattern.
    block(g, b.x + 20, b.y + 2, b.width - 16, 30, P.cream);
    block(g, b.x + 28, b.y - 6, 56, 24, P.cream);
    g.rect(b.x + 28, b.y + 12, 56, 6).fill(P.creamShade);
    block(g, b.x + 90, b.y - 2, b.width - 82, 42, P.green);
    for (let x = b.x + 94; x < b.x + b.width; x += 12) {
      for (let y = b.y + 2; y < b.y + 36; y += 12) {
        if (((x - b.x) / 12 + (y - b.y) / 12) % 2 < 1) g.rect(x, y, 6, 6).fill(P.greenLight);
      }
    }
    g.rect(b.x + 90, b.y - 2, b.width - 82, 6).fill(P.cream);
  },
  lamp(g) {
    const l = FURNITURE.lamp;
    const cx = l.x + l.width / 2;
    block(g, cx - 3, l.y + 34, 6, l.height - 40, P.metal);
    block(g, cx - 16, l.y + l.height - 6, 32, 6, P.metal);
    // Stepped amber shade.
    g.rect(l.x - 2, l.y + 22, l.width + 4, 16).fill(P.outline);
    g.rect(l.x + 4, l.y + 8, l.width - 8, 16).fill(P.outline);
    g.rect(l.x + 10, l.y - 2, l.width - 20, 12).fill(P.outline);
    g.rect(l.x, l.y + 24, l.width, 12).fill(P.amber);
    g.rect(l.x + 6, l.y + 10, l.width - 12, 14).fill(P.amber);
    g.rect(l.x + 12, l.y, l.width - 24, 10).fill(P.amberLight);
    g.rect(l.x, l.y + 32, l.width, 4).fill(P.orangeDark);
    g.rect(cx - 6, l.y + 36, 12, 6).fill(P.amberLight);
  },
  desk(g) {
    const d = FURNITURE.desk;
    g.rect(d.x + 4, d.y + d.height - 4, d.width, 8).fill({ color: P.outline, alpha: 0.22 });
    block(g, d.x, d.y, d.width, 14, P.woodLight);
    g.rect(d.x, d.y + 10, d.width, 4).fill(P.wood);
    block(g, d.x + 8, d.y + 16, 10, d.height - 16, P.wood);
    block(g, d.x + d.width - 18, d.y + 16, 10, d.height - 16, P.wood);
    block(g, d.x + d.width - 60, d.y + 16, 40, 22, P.wood);
    g.rect(d.x + d.width - 44, d.y + 25, 8, 3).fill(P.mustard);
    // Notebook, pencil cup with pencils, and a mug.
    block(g, d.x + 26, d.y - 8, 54, 6, P.cream);
    g.rect(d.x + 26, d.y - 8, 6, 6).fill(P.orange);
    block(g, d.x + 108, d.y - 20, 12, 18, P.green);
    g.rect(d.x + 110, d.y - 30, 3, 10).fill(P.mustard);
    g.rect(d.x + 115, d.y - 28, 3, 8).fill(P.brick);
    block(g, d.x + 132, d.y - 14, 12, 12, P.orange);
    g.rect(d.x + 146, d.y - 10, 4, 6).fill(P.outline);
  },
  chair(g) {
    const c = FURNITURE.chair;
    block(g, c.x, c.y - 30, 12, c.height, P.woodDark);
    g.rect(c.x + 2, c.y - 28, 3, c.height - 4).fill(P.wood);
    block(g, c.x, c.y + 18, c.width, 10, P.wood);
    g.rect(c.x + 2, c.y + 12, c.width - 6, 6).fill(P.green);
    block(g, c.x + 4, c.y + 30, 6, c.height - 30, P.woodDark);
    block(g, c.x + c.width - 10, c.y + 30, 6, c.height - 30, P.woodDark);
  },
  computerDesk(g) {
    const d = FURNITURE.computerDesk;
    g.rect(d.x + 4, d.y + d.height - 4, d.width, 8).fill({ color: P.outline, alpha: 0.22 });
    block(g, d.x, d.y, d.width, 14, P.woodLight);
    g.rect(d.x, d.y + 10, d.width, 4).fill(P.wood);
    block(g, d.x + 8, d.y + 16, 10, d.height - 16, P.wood);
    block(g, d.x + d.width - 18, d.y + 16, 10, d.height - 16, P.wood);
    // Keyboard and mouse.
    block(g, d.x + 40, d.y - 8, 70, 6, P.metal);
    for (let x = d.x + 44; x < d.x + 106; x += 8) g.rect(x, d.y - 7, 5, 2).fill(0x46505f);
    block(g, d.x + 122, d.y - 6, 10, 4, P.metal);
  },
  monitor(g) {
    const m = FURNITURE.monitor;
    block(g, m.x, m.y, m.width, m.height - 16, P.metal);
    g.rect(m.x + 6, m.y + 6, m.width - 12, m.height - 28).fill(P.screen);
    for (let i = 0; i < 4; i++) {
      g.rect(m.x + 12, m.y + 12 + i * 9, 20 + ((i * 17) % 40), 4).fill({ color: i === 2 ? P.orange : P.screenText, alpha: 0.95 });
    }
    g.rect(m.x + 6, m.y + 6, m.width - 12, 3).fill({ color: 0xffffff, alpha: 0.08 });
    block(g, m.x + m.width / 2 - 5, m.y + m.height - 14, 10, 8, P.metal);
    block(g, m.x + m.width / 2 - 18, m.y + m.height - 6, 36, 4, P.metal);
    g.rect(m.x + m.width - 12, m.y + m.height - 22, 4, 2).fill(P.screenText); // power light
  },
  plant(g) {
    const p = FURNITURE.plant;
    g.rect(p.x - 2, p.y + p.height - 4, p.width + 8, 8).fill({ color: P.outline, alpha: 0.22 });
    // Stepped pot with a rim.
    block(g, p.x + 2, p.y + 52, p.width - 4, 10, P.terracotta);
    block(g, p.x + 6, p.y + 62, p.width - 12, p.height - 62, P.terracotta);
    g.rect(p.x + 6, p.y + 62, 4, p.height - 62).fill({ color: 0xffffff, alpha: 0.15 });
    // Blocky leaves.
    for (const [dx, dy, w, h, c] of [
      [14, 26, 12, 28, P.leafDark],
      [2, 22, 14, 14, P.leaf],
      [24, 18, 14, 14, P.leaf],
      [10, 6, 12, 18, P.leaf],
      [26, 2, 10, 14, P.leafDark],
      [0, 36, 10, 10, P.leafDark],
    ] as const) {
      block(g, p.x + dx, p.y + dy, w, h, c);
    }
  },
  rug(g) {
    const r = FURNITURE.rug;
    const cx = r.x + r.width / 2;
    const cy = r.y + r.height / 2;
    steppedEllipse(g, cx, cy, r.width / 2, r.height / 2, 6, P.outline);
    steppedEllipse(g, cx, cy, r.width / 2 - 4, r.height / 2 - 4, 6, P.navy);
    steppedEllipse(g, cx, cy, r.width / 2 - 18, r.height / 2 - 10, 6, P.cream);
    steppedEllipse(g, cx, cy, r.width / 2 - 24, r.height / 2 - 14, 6, P.navyDark);
    steppedEllipse(g, cx, cy, r.width / 2 - 70, r.height / 2 - 24, 4, P.orange);
    for (let x = r.x + 30; x < r.x + r.width - 30; x += 24) g.rect(x, cy - 2, 6, 4).fill(P.mustard);
  },
};

export function drawFurniture(key: Exclude<FurnitureKey, "window">, g: Graphics): void {
  DRAWERS[key](g);
}
