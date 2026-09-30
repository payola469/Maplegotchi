// Original v0.1 vector furniture. Each function draws into a Graphics at the
// layout box from FURNITURE. Colours are a warm, cozy palette.

import { Graphics } from "pixi.js";
import { FLOOR_Y, FURNITURE, ROOM_HEIGHT, ROOM_WIDTH } from "../layout/anchors";
import type { FurnitureKey } from "../assets/manifest";

const WOOD = 0x9c6b43;
const WOOD_DARK = 0x6f4a2d;
const WOOD_LIGHT = 0xc08a5c;

export function drawWallsAndFloor(g: Graphics): void {
  g.rect(0, 0, ROOM_WIDTH, FLOOR_Y).fill(0xf3e3c7); // wall
  for (let x = 0; x < ROOM_WIDTH; x += 50) {
    g.rect(x, 0, 25, FLOOR_Y).fill({ color: 0xeed9b6, alpha: 0.5 }); // soft stripes
  }
  g.rect(0, FLOOR_Y, ROOM_WIDTH, ROOM_HEIGHT - FLOOR_Y).fill(0xc79a6b); // floor
  for (let y = FLOOR_Y + 30; y < ROOM_HEIGHT; y += 30) {
    g.moveTo(0, y).lineTo(ROOM_WIDTH, y).stroke({ width: 2, color: 0xb88a5c, alpha: 0.6 });
  }
  g.rect(0, FLOOR_Y - 10, ROOM_WIDTH, 12).fill(0xe0c49a); // baseboard
}

/** The window frame; the sky inside is drawn by the scene (it changes with the day). */
export function drawWindowFrame(g: Graphics): void {
  const w = FURNITURE.window;
  g.roundRect(w.x - 8, w.y - 8, w.width + 16, w.height + 16, 6).stroke({ width: 10, color: 0xfaf3e6 });
  g.moveTo(w.x + w.width / 2, w.y).lineTo(w.x + w.width / 2, w.y + w.height).stroke({ width: 6, color: 0xfaf3e6 });
  g.moveTo(w.x, w.y + w.height / 2).lineTo(w.x + w.width, w.y + w.height / 2).stroke({ width: 6, color: 0xfaf3e6 });
  g.rect(w.x - 14, w.y + w.height + 8, w.width + 28, 10).fill(0xfaf3e6); // sill
}

const DRAWERS: Record<Exclude<FurnitureKey, "window">, (g: Graphics) => void> = {
  bookshelf(g) {
    const b = FURNITURE.bookshelf;
    g.rect(b.x, b.y, b.width, b.height).fill(WOOD);
    const colors = [0xd35b4a, 0x4f86c6, 0xf2c14e, 0x6aa84f, 0x9b6fb0, 0xe38b3c];
    for (let shelf = 0; shelf < 3; shelf++) {
      const y = b.y + 15 + shelf * 78;
      g.rect(b.x + 8, y + 62, b.width - 16, 8).fill(WOOD_DARK);
      let x = b.x + 12;
      for (let i = 0; x < b.x + b.width - 20; i++) {
        const width = 12 + ((i * 7 + shelf * 5) % 9);
        const height = 42 + ((i * 11 + shelf * 3) % 18);
        g.rect(x, y + 62 - height, width, height).fill(colors[(i + shelf * 2) % colors.length] ?? 0xd35b4a);
        x += width + 3;
      }
    }
  },
  bed(g) {
    const b = FURNITURE.bed;
    g.roundRect(b.x, b.y - 40, 26, b.height + 40, 6).fill(WOOD_DARK); // headboard
    g.roundRect(b.x + 10, b.y + 20, b.width, b.height - 40, 10).fill(WOOD);
    g.roundRect(b.x + 18, b.y, b.width - 12, 40, 14).fill(0xfdf6ec); // mattress
    g.roundRect(b.x + 26, b.y - 6, 60, 30, 12).fill(0xffffff); // pillow
    g.roundRect(b.x + 90, b.y + 2, b.width - 80, 42, 12).fill(0x7aa6d6); // blanket
  },
  lamp(g) {
    const l = FURNITURE.lamp;
    g.rect(l.x + l.width / 2 - 3, l.y + 30, 6, l.height - 30).fill(0x5b4a3a);
    g.ellipse(l.x + l.width / 2, l.y + l.height, 18, 5).fill(0x5b4a3a);
    g.poly([l.x, l.y + 35, l.x + l.width, l.y + 35, l.x + l.width - 8, l.y, l.x + 8, l.y]).fill(0xf6d7a0);
  },
  desk(g) {
    const d = FURNITURE.desk;
    g.rect(d.x, d.y, d.width, 14).fill(WOOD_LIGHT);
    g.rect(d.x + 8, d.y + 14, 10, d.height - 14).fill(WOOD);
    g.rect(d.x + d.width - 18, d.y + 14, 10, d.height - 14).fill(WOOD);
    g.rect(d.x + 30, d.y - 8, 50, 8).fill(0xfdf6ec); // notebook
    g.rect(d.x + 110, d.y - 22, 10, 22).fill(0x6aa84f); // pencil cup
  },
  chair(g) {
    const c = FURNITURE.chair;
    g.roundRect(c.x, c.y - 30, 12, c.height, 4).fill(WOOD_DARK);
    g.rect(c.x, c.y + 20, c.width, 10).fill(WOOD);
    g.rect(c.x + 4, c.y + 30, 6, c.height - 30).fill(WOOD_DARK);
    g.rect(c.x + c.width - 10, c.y + 30, 6, c.height - 30).fill(WOOD_DARK);
  },
  computerDesk(g) {
    const d = FURNITURE.computerDesk;
    g.rect(d.x, d.y, d.width, 14).fill(WOOD_LIGHT);
    g.rect(d.x + 8, d.y + 14, 10, d.height - 14).fill(WOOD);
    g.rect(d.x + d.width - 18, d.y + 14, 10, d.height - 14).fill(WOOD);
    g.roundRect(d.x + 40, d.y - 8, 70, 8, 3).fill(0x3d3d3d); // keyboard
  },
  monitor(g) {
    const m = FURNITURE.monitor;
    g.roundRect(m.x, m.y, m.width, m.height - 14, 6).fill(0x2f2f35);
    g.roundRect(m.x + 6, m.y + 6, m.width - 12, m.height - 26, 3).fill(0x1d3b4f);
    for (let i = 0; i < 4; i++) {
      g.rect(m.x + 12, m.y + 12 + i * 9, 20 + ((i * 17) % 40), 3).fill({ color: 0x7ee0b5, alpha: 0.9 });
    }
    g.rect(m.x + m.width / 2 - 5, m.y + m.height - 14, 10, 14).fill(0x2f2f35);
  },
  plant(g) {
    const p = FURNITURE.plant;
    g.poly([p.x, p.y + 50, p.x + p.width, p.y + 50, p.x + p.width - 6, p.y + p.height, p.x + 6, p.y + p.height]).fill(0xc8553d);
    for (const [dx, dy, r] of [[20, 30, 16], [8, 18, 13], [32, 16, 13], [20, 4, 11]] as const) {
      g.circle(p.x + dx, p.y + dy, r).fill(0x5a9e4b);
    }
  },
  rug(g) {
    const r = FURNITURE.rug;
    g.ellipse(r.x + r.width / 2, r.y + r.height / 2, r.width / 2, r.height / 2).fill(0xb5563f);
    g.ellipse(r.x + r.width / 2, r.y + r.height / 2, r.width / 2 - 14, r.height / 2 - 8).fill(0xd9825b);
  },
};

export function drawFurniture(key: Exclude<FurnitureKey, "window">, g: Graphics): void {
  DRAWERS[key](g);
}
