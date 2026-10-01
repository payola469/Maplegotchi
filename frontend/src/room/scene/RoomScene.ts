// The Pixi scene. Created once per mount; later snapshots only call update().
// One ticker drives all motion; destroy() stops it and frees every GPU resource.

import "pixi.js/unsafe-eval"; // CSP: the backend forbids eval (script-src 'self')
import { Application, Assets, Container, Graphics, Sprite, type Texture } from "pixi.js";
import { FURNITURE_ASSETS, type FurnitureKey } from "../assets/manifest";
import { ANCHORS, FURNITURE, NEUTRAL_ANCHOR, ROOM_HEIGHT, ROOM_WIDTH } from "../layout/anchors";
import { Motion, approach } from "../animation/motion";
import { MapleFigure } from "../maple/figure";
import { PALETTE, drawFurniture, drawWallsAndFloor, drawWindowFrame } from "../objects/furniture";
import { NEUTRAL_VISUAL, type VisualState } from "../visual";

export interface RoomSceneHandle {
  update(visual: VisualState): void;
  setReducedMotion(reduced: boolean): void;
  destroy(): void;
}

export type CreateRoomScene = (
  host: HTMLElement,
  options: { reducedMotion: boolean },
) => Promise<RoomSceneHandle>;

const FURNITURE_ORDER: Exclude<FurnitureKey, "window">[] = [
  "rug", "bookshelf", "lamp", "bed", "desk", "chair", "computerDesk", "monitor", "plant",
];

function mixColor(a: number, b: number, t: number): number {
  const ch = (c: number, s: number) => (c >> s) & 0xff;
  const mix = (s: number) => Math.round(ch(a, s) + (ch(b, s) - ch(a, s)) * t);
  return (mix(16) << 16) | (mix(8) << 8) | mix(0);
}

async function furnitureObject(key: Exclude<FurnitureKey, "window">): Promise<Container> {
  const asset = FURNITURE_ASSETS[key];
  if (asset.texture) {
    try {
      const texture = await Assets.load<Texture>(asset.texture);
      const box = FURNITURE[key];
      const sprite = new Sprite(texture);
      sprite.position.set(box.x, box.y);
      sprite.width = box.width;
      sprite.height = box.height;
      return sprite;
    } catch {
      // fall back to the original vector drawing
    }
  }
  const g = new Graphics();
  drawFurniture(key, g);
  return g;
}

/** Soft edge shading for depth (static; drawn above the room, below the lighting). */
function vignette(): Graphics {
  const g = new Graphics();
  const bands = 8;
  for (let i = 0; i < bands; i++) {
    const inset = i * 6;
    const alpha = 0.035 * (1 - i / bands);
    g.rect(inset, inset, ROOM_WIDTH - inset * 2, 6).fill({ color: PALETTE.outline, alpha });
    g.rect(inset, ROOM_HEIGHT - inset - 6, ROOM_WIDTH - inset * 2, 6).fill({ color: PALETTE.outline, alpha: alpha * 1.6 });
    g.rect(inset, inset + 6, 6, ROOM_HEIGHT - inset * 2 - 12).fill({ color: PALETTE.outline, alpha });
    g.rect(ROOM_WIDTH - inset - 6, inset + 6, 6, ROOM_HEIGHT - inset * 2 - 12).fill({ color: PALETTE.outline, alpha });
  }
  return g;
}

/** A soft radial light: stacked faint discs (no filters, no textures to leak). */
function softGlow(x: number, y: number, radius: number, color: number, alphaPerRing: number): Graphics {
  const g = new Graphics();
  const rings = 18;
  for (let i = rings; i >= 1; i--) g.circle(x, y, (radius * i) / rings).fill({ color, alpha: alphaPerRing });
  g.blendMode = "add";
  return g;
}

export const createRoomScene: CreateRoomScene = async (host, options) => {
  const app = new Application();
  await app.init({
    width: ROOM_WIDTH,
    height: ROOM_HEIGHT,
    background: PALETTE.wall,
    antialias: true,
    autoDensity: true,
    resolution: Math.min(window.devicePixelRatio || 1, 2),
  });
  app.canvas.setAttribute("aria-hidden", "true"); // the DOM summary describes the room
  host.appendChild(app.canvas);

  let reducedMotion = options.reducedMotion;
  const world = new Container();
  app.stage.addChild(world);

  const background = new Graphics();
  drawWallsAndFloor(background);
  const sky = new Graphics();
  const windowFrame = new Graphics();
  drawWindowFrame(windowFrame);
  world.addChild(background, sky, windowFrame);
  for (const key of FURNITURE_ORDER) world.addChild(await furnitureObject(key));

  const maple = new MapleFigure();
  world.addChild(maple.root);

  // Night tints the room navy instead of greying it: a multiply layer darkens,
  // a thin navy wash shifts the hue. Both alphas follow the eased
  // `lighting.darkness` from the mapping; nothing else decides them.
  const darkness = new Graphics().rect(0, 0, ROOM_WIDTH, ROOM_HEIGHT).fill(0x1a2350);
  darkness.blendMode = "multiply";
  const nightWash = new Graphics().rect(0, 0, ROOM_WIDTH, ROOM_HEIGHT).fill(0x1c2a5e);
  const lampGlow = softGlow(FURNITURE.lamp.x + 20, FURNITURE.lamp.y + 22, 210, 0xffa94d, 0.034);
  const screenGlow = softGlow(FURNITURE.monitor.x + 45, FURNITURE.monitor.y + 30, 110, PALETTE.screenText, 0.02);
  world.addChild(vignette(), darkness, nightWash, lampGlow, screenGlow);

  let target: VisualState = NEUTRAL_VISUAL;
  const motion = new Motion(ANCHORS[NEUTRAL_ANCHOR], "stand");
  let placed = false;
  let shownDarkness = 0;
  let shownLamp = 0;
  let shownSky = NEUTRAL_VISUAL.lighting.sky;
  let skyDrawn = -1;
  let time = 0;

  function drawSky(color: number, night: number): void {
    if (color === skyDrawn) return;
    skyDrawn = color;
    const w = FURNITURE.window;
    sky.clear();
    // Pixel sky: the mapped colour in the middle, darker bands above, lighter at the horizon.
    const bandH = w.height / 6;
    const bands = [0.3, 0.18, 0.08, 0, 0, -0.12];
    bands.forEach((shade, i) => {
      const c = shade >= 0 ? mixColor(color, 0x0e1430, shade) : mixColor(color, 0xffffff, -shade);
      sky.rect(w.x, w.y + i * bandH, w.width, bandH + 1).fill(c);
    });
    const disc = (cx: number, cy: number, r: number, fill: number, alpha = 1) => {
      for (let y = -r; y < r; y += 4) {
        const mid = y + 2;
        const half = Math.round(Math.sqrt(Math.max(0, r * r - mid * mid)) / 4) * 4;
        if (half > 0) sky.rect(cx - half, cy + y, half * 2, 4).fill({ color: fill, alpha });
      }
    };
    if (night > 0.5) {
      disc(w.x + 126, w.y + 38, 16, 0xf5f1dc); // moon
      disc(w.x + 134, w.y + 32, 14, mixColor(color, 0x0e1430, 0.18)); // crescent cut-out
      for (const [sx, sy] of [[28, 28], [62, 66], [96, 22], [146, 96], [40, 104], [110, 84]] as const) {
        sky.rect(w.x + sx - 1, w.y + sy - 3, 2, 6).fill({ color: 0xffffff, alpha: 0.9 });
        sky.rect(w.x + sx - 3, w.y + sy - 1, 6, 2).fill({ color: 0xffffff, alpha: 0.9 });
      }
    } else {
      disc(w.x + 128, w.y + 42, 18, 0xffe08a, 1 - night * 2); // sun
      if (night < 0.1) {
        for (const [cx, cy] of [[24, 30], [70, 56]] as const) {
          sky.rect(w.x + cx, w.y + cy, 36, 8).fill({ color: 0xffffff, alpha: 0.85 });
          sky.rect(w.x + cx + 8, w.y + cy - 6, 18, 6).fill({ color: 0xffffff, alpha: 0.85 });
        }
      }
    }
    // Distant hills and trees on the horizon, tinted by the sky.
    const hill = mixColor(color, 0x1b2a2a, 0.62);
    const tree = mixColor(color, 0x14201c, 0.75);
    sky.rect(w.x, w.y + w.height - 22, w.width, 22).fill(hill);
    sky.rect(w.x + 20, w.y + w.height - 30, 60, 8).fill(hill);
    sky.rect(w.x + 96, w.y + w.height - 34, 50, 12).fill(hill);
    for (const tx of [12, 58, 120, 152] as const) {
      sky.rect(w.x + tx, w.y + w.height - 44, 10, 22).fill(tree);
      sky.rect(w.x + tx - 4, w.y + w.height - 36, 18, 10).fill(tree);
    }
  }

  function layout(): void {
    // Fit the logical room into the host width, keep aspect ratio.
    const scale = Math.max(0.1, host.clientWidth / ROOM_WIDTH);
    app.canvas.style.width = `${ROOM_WIDTH * scale}px`;
    app.canvas.style.height = `${ROOM_HEIGHT * scale}px`;
    maple.setDisplayScale(scale, app.renderer.resolution); // a little larger when the room is small
  }
  const resizeObserver = new ResizeObserver(layout);
  resizeObserver.observe(host);
  layout();

  const tick = (ticker: { deltaMS: number }) => {
    const dt = Math.min(ticker.deltaMS / 1000, 0.1);
    time += dt;
    const frame = motion.step(dt);
    maple.root.position.set(frame.position.x, frame.position.y);
    maple.apply(frame.pose, target.face, target.reaction?.symbol ?? null);
    maple.animate(frame.pose, frame.facing, time, reducedMotion ? 0 : 1);

    const lighting = target.lighting;
    shownDarkness = approach(shownDarkness, lighting.darkness, dt, reducedMotion);
    shownLamp = approach(shownLamp, lighting.lampGlow, dt, reducedMotion);
    const skyMix = reducedMotion ? 1 : Math.min(1, dt * 1.5);
    shownSky = shownSky === lighting.sky ? shownSky : mixColor(shownSky, lighting.sky, skyMix);
    if (Math.abs(shownSky - lighting.sky) < 0x000102) shownSky = lighting.sky;
    darkness.alpha = shownDarkness;
    nightWash.alpha = shownDarkness * 0.4;
    lampGlow.alpha = shownLamp;
    screenGlow.alpha = shownDarkness * 1.6; // the screen only glows noticeably in the dark
    drawSky(shownSky, lighting.darkness);
  };
  app.ticker.add(tick);

  return {
    update(visual) {
      target = visual;
      // First placement snaps; later location changes walk (presentation only).
      motion.setTarget(ANCHORS[visual.anchor], visual.pose, reducedMotion || !placed);
      placed = true;
    },
    setReducedMotion(reduced) {
      reducedMotion = reduced;
      if (reduced) motion.setTarget(ANCHORS[target.anchor], target.pose, true);
    },
    destroy() {
      resizeObserver.disconnect();
      app.ticker.remove(tick);
      maple.destroy();
      app.destroy(true, { children: true, texture: true });
    },
  };
};
