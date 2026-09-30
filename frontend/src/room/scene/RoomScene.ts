// The Pixi scene. Created once per mount; later snapshots only call update().
// One ticker drives all motion; destroy() stops it and frees every GPU resource.

import "pixi.js/unsafe-eval"; // CSP: the backend forbids eval (script-src 'self')
import { Application, Assets, Container, Graphics, Sprite, type Texture } from "pixi.js";
import { FURNITURE_ASSETS, type FurnitureKey } from "../assets/manifest";
import { ANCHORS, FURNITURE, NEUTRAL_ANCHOR, ROOM_HEIGHT, ROOM_WIDTH } from "../layout/anchors";
import { Motion, approach } from "../animation/motion";
import { MapleFigure } from "../maple/figure";
import { drawFurniture, drawWallsAndFloor, drawWindowFrame } from "../objects/furniture";
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
    background: 0xf3e3c7,
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

  const darkness = new Graphics().rect(0, 0, ROOM_WIDTH, ROOM_HEIGHT).fill(0x0b1030);
  const lampGlow = softGlow(FURNITURE.lamp.x + 20, FURNITURE.lamp.y + 18, 190, 0xffc46b, 0.028);
  const screenGlow = softGlow(FURNITURE.monitor.x + 45, FURNITURE.monitor.y + 30, 110, 0x7ee0b5, 0.02);
  world.addChild(darkness, lampGlow, screenGlow);

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
    sky.rect(w.x, w.y, w.width, w.height).fill(color);
    if (night > 0.5) {
      sky.circle(w.x + 125, w.y + 38, 14).fill(0xf5f1dc); // moon
      for (const [sx, sy] of [[30, 30], [60, 70], [95, 25], [140, 100], [40, 115]] as const) {
        sky.circle(w.x + sx, w.y + sy, 1.8).fill(0xffffff);
      }
    } else {
      sky.circle(w.x + 130, w.y + 40, 18).fill({ color: 0xffe08a, alpha: 1 - night * 2 }); // sun
    }
  }

  function layout(): void {
    // Fit the logical room into the host width, keep aspect ratio.
    const scale = Math.max(0.1, host.clientWidth / ROOM_WIDTH);
    app.canvas.style.width = `${ROOM_WIDTH * scale}px`;
    app.canvas.style.height = `${ROOM_HEIGHT * scale}px`;
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
