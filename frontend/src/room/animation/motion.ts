// Room motion helpers. Since v0.2 (ADR-0027) walking is backend state:
// `routeFrame` interpolates the backend's route (departed_at -> arrives_at along
// its path) on the estimated server clock. `Motion` is the older presentation-only
// walker between points; RoomScene now always calls it with snap = true, so it
// only places Maple at the backend position (it does not walk on its own).
// Nothing here changes logical state; reduced motion snaps straight to the target.

import type { Point } from "../layout/anchors";
import type { Pose } from "../visual";

export const WALK_SPEED = 220; // logical units per second (fallback walker only; backend routes set real travel time)

export interface MotionFrame {
  position: Point;
  moving: boolean;
  pose: Pose; // "walk" while moving, otherwise the backend's pose
  facing: 1 | -1; // 1 = right, -1 = left
}

export class Motion {
  private position: Point;
  private target: Point;
  private targetPose: Pose;
  private facing: 1 | -1 = 1;

  constructor(start: Point, pose: Pose = "stand") {
    this.position = { ...start };
    this.target = { ...start };
    this.targetPose = pose;
  }

  /** Aim at a new anchor/pose. Reduced motion (or first placement) snaps immediately. */
  setTarget(target: Point, pose: Pose, snap: boolean): void {
    this.target = { ...target };
    this.targetPose = pose;
    if (target.x !== this.position.x) this.facing = target.x > this.position.x ? 1 : -1;
    if (snap) this.position = { ...target };
  }

  step(dtSeconds: number): MotionFrame {
    const dx = this.target.x - this.position.x;
    const dy = this.target.y - this.position.y;
    const distance = Math.hypot(dx, dy);
    const travel = WALK_SPEED * Math.max(0, dtSeconds);
    if (distance <= travel || distance < 0.5) {
      this.position = { ...this.target };
    } else {
      this.position = {
        x: this.position.x + (dx / distance) * travel,
        y: this.position.y + (dy / distance) * travel,
      };
    }
    const moving = this.position.x !== this.target.x || this.position.y !== this.target.y;
    return {
      position: { ...this.position },
      moving,
      pose: moving ? "walk" : this.targetPose,
      facing: this.facing,
    };
  }
}

/** Where Maple is along a backend route at server time `nowMs` (ADR-0027).
 * The route's own timing decides everything; the room never picks a speed or path. */
export function routeFrame(
  route: { departedMs: number; arrivesMs: number; path: { x: number; y: number; distance: number }[] },
  nowMs: number,
): MotionFrame {
  const path = route.path;
  const last = path[path.length - 1] ?? { x: 0, y: 0, distance: 0 };
  const total = last.distance;
  const span = route.arrivesMs - route.departedMs;
  const ratio = span > 0 ? Math.min(1, Math.max(0, (nowMs - route.departedMs) / span)) : 1;
  const walked = total * ratio;
  for (let i = 1; i < path.length; i++) {
    const a = path[i - 1];
    const b = path[i];
    if (a && b && walked <= b.distance) {
      const len = b.distance - a.distance;
      const f = len > 0 ? (walked - a.distance) / len : 1;
      const moving = nowMs < route.arrivesMs;
      return {
        position: { x: a.x + (b.x - a.x) * f, y: a.y + (b.y - a.y) * f },
        moving,
        pose: moving ? "walk" : "stand",
        facing: b.x < a.x ? -1 : 1,
      };
    }
  }
  return { position: { x: last.x, y: last.y }, moving: false, pose: "stand", facing: 1 };
}

/** Ease a number toward a target (lighting transitions); reduced motion snaps. */
export function approach(current: number, target: number, dtSeconds: number, snap: boolean): number {
  if (snap) return target;
  const rate = 1.5; // per second
  const next = current + (target - current) * Math.min(1, rate * dtSeconds);
  return Math.abs(next - target) < 0.002 ? target : next;
}
