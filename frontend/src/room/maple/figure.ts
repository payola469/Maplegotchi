// Maple: an original round, warm-coloured creature with a maple-leaf sprout.
// Drawn in code (v0.1). The figure's origin is between its feet.

import { Container, Graphics, Text } from "pixi.js";
import type { Face, Pose, ReactionSymbol } from "../visual";

const BODY = 0xf29e4c;
const BELLY = 0xfbd7a8;
const LEAF = 0xd9481f;
const INK = 0x3a2a20;
const BLUSH = 0xf07a6a;

export class MapleFigure {
  readonly root = new Container();
  private readonly body = new Container();
  private readonly shadow = new Graphics();
  private readonly feet = new Graphics();
  private readonly face = new Graphics();
  private readonly props = new Graphics();
  private readonly zzz = new Text({ text: "z z", style: { fontFamily: "system-ui, sans-serif", fontSize: 22, fill: 0x5b6fa6 } });
  private readonly bubble = new Container();
  private readonly bubbleShape = new Graphics();
  private readonly bubbleText = new Text({ text: "", style: { fontFamily: "system-ui, sans-serif", fontSize: 20, fill: INK } });
  private currentFace: Face | null = null;
  private currentPose: Pose | null = null;
  private currentReaction: ReactionSymbol | null = null;

  constructor() {
    this.shadow.ellipse(0, -2, 26, 6).fill({ color: 0x000000, alpha: 0.15 });
    this.drawFeet();
    this.body.addChild(this.feet, this.bodyShape(), this.props, this.face);
    this.zzz.position.set(18, -110);
    this.bubble.addChild(this.bubbleShape, this.bubbleText);
    this.bubble.position.set(0, -130);
    this.bubble.visible = false;
    this.root.addChild(this.shadow, this.body, this.zzz, this.bubble);
  }

  private drawFeet(): void {
    this.feet.clear();
    this.feet.ellipse(-14, -4, 11, 6).fill(0xd9823a);
    this.feet.ellipse(14, -4, 11, 6).fill(0xd9823a);
  }

  private bodyShape(): Graphics {
    const g = new Graphics();
    g.circle(0, -42, 36).fill(BODY);
    g.ellipse(0, -32, 22, 18).fill(BELLY);
    g.rect(-2, -88, 4, 12).fill(0x5a9e4b); // stem
    g.poly([0, -104, 6, -92, 16, -96, 10, -86, 18, -80, 4, -82, 0, -76, -4, -82, -18, -80, -10, -86, -16, -96, -6, -92]).fill(LEAF);
    return g;
  }

  private drawFace(face: Face): void {
    const g = this.face;
    g.clear();
    const eyeY = -50;
    switch (face) {
      case "happy":
        g.moveTo(-16, eyeY + 2).quadraticCurveTo(-11, eyeY - 6, -6, eyeY + 2).stroke({ width: 3, color: INK });
        g.moveTo(6, eyeY + 2).quadraticCurveTo(11, eyeY - 6, 16, eyeY + 2).stroke({ width: 3, color: INK });
        g.moveTo(-9, -36).quadraticCurveTo(0, -26, 9, -36).stroke({ width: 3, color: INK });
        g.ellipse(-22, -38, 6, 3.5).fill({ color: BLUSH, alpha: 0.7 });
        g.ellipse(22, -38, 6, 3.5).fill({ color: BLUSH, alpha: 0.7 });
        break;
      case "curious":
        g.circle(-11, eyeY, 5.5).fill(INK);
        g.circle(11, eyeY, 5.5).fill(INK);
        g.circle(-9, eyeY - 2, 1.8).fill(0xffffff);
        g.circle(13, eyeY - 2, 1.8).fill(0xffffff);
        g.circle(0, -33, 3.5).stroke({ width: 2.5, color: INK });
        break;
      case "sleepy":
        g.moveTo(-16, eyeY).lineTo(-6, eyeY + 1).stroke({ width: 3, color: INK });
        g.moveTo(6, eyeY + 1).lineTo(16, eyeY).stroke({ width: 3, color: INK });
        g.ellipse(0, -34, 4, 2).fill(INK);
        break;
      case "focused":
        g.rect(-15, eyeY - 1, 9, 4).fill(INK);
        g.rect(6, eyeY - 1, 9, 4).fill(INK);
        g.moveTo(-6, -34).lineTo(6, -34).stroke({ width: 3, color: INK });
        break;
      default: // calm
        g.circle(-11, eyeY, 4).fill(INK);
        g.circle(11, eyeY, 4).fill(INK);
        g.moveTo(-6, -36).quadraticCurveTo(0, -31, 6, -36).stroke({ width: 3, color: INK });
    }
  }

  private drawProps(pose: Pose): void {
    const g = this.props;
    g.clear();
    if (pose === "read") {
      g.roundRect(-24, -34, 48, 30, 3).fill(0x4f86c6);
      g.rect(-1, -34, 2, 30).fill(0xfdf6ec);
    } else if (pose === "sit_write") {
      g.rect(26, -44, 5, 26).fill(0xf2c14e);
    } else if (pose === "sit_monitor") {
      g.circle(0, -46, 42).fill({ color: 0x7ee0b5, alpha: 0.08 });
    }
  }

  private drawBubble(symbol: ReactionSymbol): void {
    const g = this.bubbleShape;
    g.clear();
    g.roundRect(-34, -26, 68, 44, 14).fill(0xffffff).stroke({ width: 2, color: 0xe5d3b8 });
    g.poly([-6, 18, 6, 18, 0, 28]).fill(0xffffff);
    const text: Record<ReactionSymbol, string> = {
      wave: "Hi!",
      heart: "♥",
      sleepy_wave: "…hi",
      sleepy_heart: "♥ z",
      sparkle: "✦",
    };
    this.bubbleText.text = text[symbol];
    this.bubbleText.style.fill = symbol === "heart" || symbol === "sleepy_heart" ? 0xd9481f : INK;
    this.bubbleText.anchor.set(0.5);
    this.bubbleText.position.set(0, -4);
  }

  /** Apply the discrete look for this frame; cheap when nothing changed. */
  apply(pose: Pose, face: Face, reaction: ReactionSymbol | null): void {
    const shownFace: Face = pose === "sleep" ? "sleepy" : face;
    if (shownFace !== this.currentFace) {
      this.drawFace(shownFace);
      this.currentFace = shownFace;
    }
    if (pose !== this.currentPose) {
      this.drawProps(pose);
      this.currentPose = pose;
    }
    if (reaction !== this.currentReaction) {
      if (reaction) this.drawBubble(reaction);
      this.bubble.visible = reaction !== null;
      this.currentReaction = reaction;
    }
  }

  /** Continuous motion for this frame. `amplitude` is 0 with reduced motion. */
  animate(pose: Pose, facing: 1 | -1, timeSeconds: number, amplitude: number): void {
    const t = timeSeconds;
    const breathe = 1 + 0.025 * Math.sin(t * 2.2) * amplitude;
    this.body.rotation = 0;
    this.body.position.set(0, 0);
    this.body.scale.set(facing, breathe);
    this.feet.position.set(0, 0);
    this.zzz.visible = pose === "sleep";
    this.shadow.visible = pose !== "sleep";
    this.root.rotation = 0;
    switch (pose) {
      case "walk": {
        const stride = Math.sin(t * 11) * amplitude;
        this.body.position.y = -Math.abs(stride) * 6;
        this.feet.position.x = stride * 4;
        this.body.rotation = stride * 0.05;
        break;
      }
      case "sleep":
        this.body.rotation = -Math.PI / 2; // lying down on the mattress
        this.body.position.set(20, -50);
        this.body.scale.set(1, 1 + 0.02 * Math.sin(t * 1.2) * amplitude);
        this.zzz.position.set(30, -70 - 6 * Math.sin(t * 1.5) * amplitude);
        this.zzz.alpha = 0.6 + 0.4 * Math.sin(t * 1.5) * amplitude;
        break;
      case "sit_write":
      case "sit_monitor":
        this.body.position.y = -12;
        this.body.rotation = 0.03 * Math.sin(t * 3) * amplitude;
        break;
      case "read":
      case "rest":
        this.body.position.y = 10;
        this.body.rotation = 0.04 * Math.sin(t * 0.9) * amplitude;
        break;
      default:
        break;
    }
    if (this.bubble.visible) this.bubble.position.y = -130 - 3 * Math.sin(t * 4) * amplitude;
  }

  destroy(): void {
    this.root.destroy({ children: true });
  }
}
