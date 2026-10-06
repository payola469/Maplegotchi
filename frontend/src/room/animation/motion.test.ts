import { describe, expect, it } from "vitest";
import { ANCHORS } from "../layout/anchors";
import { Motion, WALK_SPEED, approach, routeFrame } from "./motion";

describe("Motion (presentation-only walking)", () => {
  it("walks to a new anchor, then takes the backend pose", () => {
    const m = new Motion(ANCHORS.rug, "stand");
    m.setTarget(ANCHORS.desk, "sit_write", false);
    const first = m.step(0.1);
    expect(first.moving).toBe(true);
    expect(first.pose).toBe("walk");
    expect(first.facing).toBe(1);
    let frame = first;
    for (let i = 0; i < 100 && frame.moving; i++) frame = m.step(0.1);
    expect(frame.moving).toBe(false);
    expect(frame.position).toEqual(ANCHORS.desk);
    expect(frame.pose).toBe("sit_write");
  });

  it("moves at WALK_SPEED", () => {
    const m = new Motion({ x: 0, y: 0 });
    m.setTarget({ x: 1000, y: 0 }, "stand", false);
    expect(m.step(0.5).position.x).toBeCloseTo(WALK_SPEED * 0.5);
  });

  it("redirects mid-walk from where Maple currently is", () => {
    const m = new Motion(ANCHORS.bed, "sleep");
    m.setTarget(ANCHORS.terminal, "sit_monitor", false);
    const mid = m.step(0.5).position;
    m.setTarget(ANCHORS.bookshelf, "read", false);
    const next = m.step(0.1);
    expect(next.facing).toBe(ANCHORS.bookshelf.x > mid.x ? 1 : -1);
    expect(Math.hypot(next.position.x - mid.x, next.position.y - mid.y)).toBeLessThanOrEqual(WALK_SPEED * 0.1 + 1e-9);
    let frame = next;
    for (let i = 0; i < 100 && frame.moving; i++) frame = m.step(0.1);
    expect(frame.position).toEqual(ANCHORS.bookshelf);
    expect(frame.pose).toBe("read");
  });

  it("snaps (reduced motion / first placement) without a walk", () => {
    const m = new Motion(ANCHORS.rug);
    m.setTarget(ANCHORS.bed, "sleep", true);
    const frame = m.step(0.016);
    expect(frame.moving).toBe(false);
    expect(frame.position).toEqual(ANCHORS.bed);
    expect(frame.pose).toBe("sleep");
  });
});

describe("approach (lighting transitions)", () => {
  it("eases gradually and settles on the target", () => {
    let v = 0;
    v = approach(v, 0.5, 0.1, false);
    expect(v).toBeGreaterThan(0);
    expect(v).toBeLessThan(0.5);
    for (let i = 0; i < 200; i++) v = approach(v, 0.5, 0.1, false);
    expect(v).toBe(0.5);
  });

  it("snaps under reduced motion", () => {
    expect(approach(0, 0.5, 0.016, true)).toBe(0.5);
  });
});

describe("routeFrame (backend-driven walking, ADR-0027)", () => {
  const route = {
    departedMs: 1000,
    arrivesMs: 3000,
    path: [
      { x: 0, y: 0, distance: 0 },
      { x: 100, y: 0, distance: 100 },
      { x: 100, y: 100, distance: 200 },
    ],
  };

  it("follows the backend path by the backend's own timing", () => {
    expect(routeFrame(route, 1000).position).toEqual({ x: 0, y: 0 });
    const quarter = routeFrame(route, 1500);
    expect(quarter.position.x).toBeCloseTo(50);
    expect(quarter.moving).toBe(true);
    expect(quarter.pose).toBe("walk");
    const mid = routeFrame(route, 2500);
    expect(mid.position).toEqual({ x: 100, y: 50 });
  });

  it("stops at the destination exactly at arrival", () => {
    const end = routeFrame(route, 3000);
    expect(end.moving).toBe(false);
    expect(end.position).toEqual({ x: 100, y: 100 });
    expect(routeFrame(route, 99999).position).toEqual({ x: 100, y: 100 });
  });

  it("faces the direction of travel", () => {
    const back = { ...route, path: [{ x: 200, y: 0, distance: 0 }, { x: 0, y: 0, distance: 200 }] };
    expect(routeFrame(back, 2000).facing).toBe(-1);
  });
});
