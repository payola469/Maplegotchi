// Maple: an original pixel/chibi character (short black hair, glasses, orange
// headphones, dark green hoodie). The art lives in pixels.ts, the pose/face/
// bubble mapping in sprites.ts, the textures in atlas.ts. The figure's origin
// is the backend location's anchor (between the feet when upright); the public
// API is the same as the former vector figure, plus setDisplayScale().

import { Container, Graphics, Sprite } from "pixi.js";
import type { Face, Pose, ReactionSymbol } from "../visual";
import { type MapleAtlas, buildMapleAtlas } from "./atlas";
import { MAPLE_PALETTE } from "./pixels";
import {
  BUBBLE_GLYPHS,
  FRAME_LAYOUT,
  type FrameId,
  PIXEL,
  POSE_FRAMES,
  faceArtFor,
  frameKey,
  mapleUnitsPerPixel,
} from "./sprites";

const INK = MAPLE_PALETTE.K ?? 0x2a1d17;
const PAPER = 0xfffaf2;
const BUBBLE_GAP = 38; // bubble centre above the top of the frame
const SEATED_LIFT = -12; // sitting on the chair: seat height above the floor anchor
// Sleeping: the frame's origin (under the head, on the mattress line) sits on
// the pillow, relative to the bed anchor. Fixed in room units, so a larger
// Maple on small screens stays on the pillow and inside the bed.
const SLEEP_AT = { x: -54, y: -43 } as const;

/** A rectangle with stepped (pixel) corners. */
function pixelBox(g: Graphics, x: number, y: number, w: number, h: number, step: number, color: number): void {
  g.rect(x + step, y, w - step * 2, h).fill(color);
  g.rect(x, y + step, w, h - step * 2).fill(color);
}

export class MapleFigure {
  readonly root = new Container();
  private readonly atlas: MapleAtlas = buildMapleAtlas();
  private readonly body = new Container();
  private readonly sprite = new Sprite();
  private readonly shadow = new Graphics();
  private readonly glow = new Graphics();
  private readonly zzz = new Container();
  private readonly bubble = new Container();
  private readonly bubbleShape = new Graphics();
  private readonly bubbleContent = new Sprite();
  private face: Face = "calm";
  private currentKey = "";
  private currentFrame: FrameId = "stand";
  private currentSymbol: ReactionSymbol | null = null;
  private units = PIXEL; // logical units per sprite pixel (presentation only)

  constructor() {
    this.sprite.roundPixels = true;
    this.body.addChild(this.sprite);

    // Stepped floor shadow.
    this.shadow.rect(-24, -6, 48, 6).fill({ color: 0x000000, alpha: 0.16 });
    this.shadow.rect(-32, -4, 64, 4).fill({ color: 0x000000, alpha: 0.1 });

    // Soft screen light on Maple while at the computer.
    this.glow.circle(0, -56, 50).fill({ color: 0x6fd6c0, alpha: 0.08 });
    this.glow.visible = false;

    for (const [x, y, scale] of [[0, 0, 3], [18, -22, 4]] as const) {
      const z = new Sprite(this.atlas.sleepGlyph());
      z.roundPixels = true;
      z.scale.set(scale);
      z.position.set(x, y);
      this.zzz.addChild(z);
    }
    this.zzz.visible = false;

    this.bubbleContent.anchor.set(0.5);
    this.bubbleContent.roundPixels = true;
    this.bubbleContent.scale.set(PIXEL);
    this.bubble.addChild(this.bubbleShape, this.bubbleContent);
    this.bubble.visible = false;

    this.root.addChild(this.shadow, this.glow, this.body, this.zzz, this.bubble);
    this.setFrame("stand", frameKey("stand", "calm"));
  }

  /** The room's on-screen scale changed: pick Maple's pixel size for it (presentation only). */
  setDisplayScale(displayScale: number, resolution: number): void {
    this.units = mapleUnitsPerPixel(displayScale, resolution);
    const s = this.units / PIXEL;
    this.shadow.scale.set(s);
    this.glow.scale.set(s);
  }

  private setFrame(frame: FrameId, key: string): void {
    if (key === this.currentKey) return;
    const layout = FRAME_LAYOUT[frame];
    this.sprite.texture = this.atlas.frame(key);
    this.sprite.anchor.set(layout.origin.x / layout.width, layout.origin.y / layout.height);
    this.currentKey = key;
    this.currentFrame = frame;
  }

  private drawBubble(symbol: ReactionSymbol): void {
    const glyph = BUBBLE_GLYPHS[symbol];
    const w = Math.max(...glyph.map((l) => l.length)) * PIXEL + 24;
    const h = glyph.length * PIXEL + 20;
    const g = this.bubbleShape;
    g.clear();
    pixelBox(g, -w / 2 - 3, -h / 2 - 3, w + 6, h + 6, 6, INK);
    pixelBox(g, -w / 2, -h / 2, w, h, 4, PAPER);
    // Stepped tail pointing down at Maple.
    g.rect(-8, h / 2, 16, 4).fill(PAPER);
    g.rect(-4, h / 2 + 4, 8, 4).fill(PAPER);
    g.rect(-11, h / 2, 3, 4).fill(INK);
    g.rect(8, h / 2, 3, 4).fill(INK);
    g.rect(-7, h / 2 + 4, 3, 4).fill(INK);
    g.rect(4, h / 2 + 4, 3, 4).fill(INK);
    g.rect(-4, h / 2 + 8, 8, 3).fill(INK);
    this.bubbleContent.texture = this.atlas.glyph(symbol);
  }

  /** Apply the discrete look for this frame; cheap when nothing changed. */
  apply(pose: Pose, face: Face, symbol: ReactionSymbol | null): void {
    this.face = face;
    this.glow.visible = pose === "sit_monitor";
    if (symbol !== this.currentSymbol) {
      if (symbol) this.drawBubble(symbol);
      this.bubble.visible = symbol !== null;
      this.currentSymbol = symbol;
    }
  }

  /** Continuous motion for this frame. `amplitude` is 0 with reduced motion. */
  animate(pose: Pose, facing: 1 | -1, timeSeconds: number, amplitude: number): void {
    const t = timeSeconds;
    const u = this.units;
    // Small idle loops move in whole steps (pixel art never stretches or tilts).
    const bob = (speed: number, units: number) => (Math.sin(t * speed) * amplitude > 0.5 ? -units : 0);
    const frames = POSE_FRAMES[pose];
    const stride = Math.sin(t * 11) * amplitude;
    const frame = (frames.length > 1 && stride < 0 ? frames[1] : frames[0]) ?? "stand";
    this.setFrame(frame, frameKey(frame, faceArtFor(pose, this.face)));
    const layout = FRAME_LAYOUT[this.currentFrame];

    this.sprite.scale.set(u * facing, u);
    this.body.position.set(0, 0);
    this.zzz.visible = pose === "sleep";
    this.shadow.visible = pose !== "sleep";
    let headX = 0;
    switch (pose) {
      case "walk":
        this.body.position.y = Math.abs(stride) > 0.5 ? -PIXEL : 0;
        break;
      case "sleep":
        // Lying in bed (dedicated frame; never mirrored), breathing in small steps.
        this.sprite.scale.set(u, u);
        this.body.position.set(SLEEP_AT.x, SLEEP_AT.y + bob(1.2, 2));
        headX = SLEEP_AT.x;
        break;
      case "sit_write":
      case "sit_monitor":
        this.body.position.y = SEATED_LIFT + bob(3, 2);
        break;
      case "read":
      case "rest":
        this.body.position.y = bob(0.9, 2);
        break;
      default:
        this.body.position.y = bob(2.2, 2); // breathing
        break;
    }
    const frameTop = this.body.position.y - layout.origin.y * u;
    if (this.zzz.visible) {
      this.zzz.position.set(headX + 16 * u, frameTop - 6 * Math.sin(t * 1.5) * amplitude);
      this.zzz.alpha = 0.6 + 0.4 * Math.sin(t * 1.5) * amplitude;
    }
    if (this.bubble.visible) this.bubble.position.set(headX, frameTop - BUBBLE_GAP - 3 * Math.sin(t * 4) * amplitude);
  }

  destroy(): void {
    this.root.destroy({ children: true });
    this.atlas.destroy();
  }
}
