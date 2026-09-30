// Presentation-only movement between anchors. When the backend's location
// changes, Maple walks there visually, then takes the backend's pose. A new
// target mid-walk redirects from the current position. The walk never changes
// any logical state; reduced motion snaps straight to the target.

import type { Point } from "../layout/anchors";
import type { Pose } from "../visual";

export const WALK_SPEED = 220; // logical units per second

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

/** Ease a number toward a target (lighting transitions); reduced motion snaps. */
export function approach(current: number, target: number, dtSeconds: number, snap: boolean): number {
  if (snap) return target;
  const rate = 1.5; // per second
  const next = current + (target - current) * Math.min(1, rate * dtSeconds);
  return Math.abs(next - target) < 0.002 ? target : next;
}
