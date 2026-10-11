import { describe, expect, it } from "vitest";
import { backingSize, cameraView, clampTranslation, currentRegion, deviceToWorld, deviceZoom, houseBounds, regionBounds, visibleTiles, worldToDevice, type CameraRequest, type LogicalZoom } from "./camera";
import { fixtureWorlds } from "./fixtures";
import { actorSample } from "./presentation";
const world = fixtureWorlds.idle, house = houseBounds(world), maple = actorSample(world, Date.parse(world.snapshot.generated_at));
const request: CameraRequest = { mode: "follow", level: 2, regionId: "central_hall", reducedMotion: false };
const dprs = [1, 1.25, 1.5, 2, 3];
const levels: readonly LogicalZoom[] = [1, 2, 3, 4];
const cases = dprs.flatMap((dpr) => levels.map((level) => ({ dpr, level })));
describe("L13/L14 pure camera", () => {
  it.each(cases)("DPR $dpr L$level exact integer zoom and transform repeatability", ({ dpr, level }) => {
    const v = backingSize(806, 484, dpr), zoom = deviceZoom(level, dpr);
    expect(zoom).toBe(Math.min(12, Math.max(1, Math.floor(level * dpr + .25))));
    const c = cameraView(world, v, dpr, { ...request, level }, maple);
    expect(c).toEqual(cameraView(world, v, dpr, { ...request, level }, maple));
    expect([c.x, c.y, c.zoom].every(Number.isInteger)).toBe(true);
    const p = { x: 17.5, y: 20.25 };
    expect(deviceToWorld(worldToDevice(p, c), c)).toEqual(p);
  });
  it.each([.749999, .75, .750001, 1.749999, 1.75, 1.750001, 3, 10])("formula boundary/cap DPR %s", (dpr) => {
    for (const l of levels) expect(deviceZoom(l, dpr)).toBe(Math.min(12, Math.max(1, Math.floor(l * dpr + .25))));
  });
  it.each([0, -1, NaN, Infinity])("rejects invalid DPR/viewport %s", (value) => {
    expect(() => backingSize(806, 484, value)).toThrow(RangeError);
    expect(() => backingSize(value, 484, 1)).toThrow(RangeError);
    expect(() => cameraView(world, { width: 806, height: value }, 1, request, maple)).toThrow(RangeError);
  });
  it.each([0, 1.5, 5, NaN])("rejects unsupported logical level %s", (l) => expect(() => deviceZoom(l, 1)).toThrow(RangeError));
  it("accepts validated device box and rejects invalid or CSS-sized emulation boxes", () => {
    expect(backingSize(806, 484, 1.25, { inlineSize: 1007, blockSize: 605 })).toEqual({ width: 1007, height: 605 });
    for (const box of [{ inlineSize: 806, blockSize: 484 }, { inlineSize: NaN, blockSize: 605 }, { inlineSize: -1, blockSize: 0 }, { inlineSize: Infinity, blockSize: 605 }]) expect(backingSize(806, 484, 1.25, box)).toEqual({ width: 1008, height: 605 });
  });
  it.each([
    [1, 2, 25.1875, 15.125], [1, 3, 16.7916666667, 10.0833333333],
    [1.25, 2, 31.5, 18.90625], [1.25, 3, 15.75, 9.453125],
    [1.5, 2, 25.1875, 15.125], [1.5, 3, 18.890625, 11.34375],
  ])("approved Follow reference DPR %s L%s", (dpr, l, x, y) => {
    const span = visibleTiles(backingSize(806, 484, dpr), deviceZoom(l, dpr), 16);
    expect(span.x).toBeCloseTo(x ?? 0, 8); expect(span.y).toBeCloseTo(y ?? 0, 8);
  });
});
describe("L15 Overview, Follow and Focus", () => {
  it.each([1, 1.25, 1.5, 1.75, 2, 2.25, 2.5, 2.75, 3])("spec Overview matrix DPR %s", (dpr) => {
    const r = { ...request, mode: "overview" as const };
    expect(cameraView(world, backingSize(806, 484, dpr), dpr, r, maple).visible).toBe(true);
    expect(cameraView(world, backingSize(654, 392, dpr), dpr, r, maple).visible).toBe([1.25, 1.5, 2.25, 2.5].includes(dpr));
    expect(cameraView(world, backingSize(348, 209, dpr), dpr, r, maple).visible).toBe(false);
  });
  it("covers continuous desktop DPR1–3 and a shrunken desktop fallback without cropping", () => {
    for (let step = 100; step <= 300; step++) {
      const dpr = step / 100, size = backingSize(806, 484, dpr), c = cameraView(world, size, dpr, { ...request, mode: "overview" }, maple);
      expect(c.visible).toBe(true); expect(house.w * c.zoom).toBeLessThanOrEqual(size.width); expect(house.h * c.zoom).toBeLessThanOrEqual(size.height);
    }
    expect(cameraView(world, backingSize(700, 400, 1), 1, { ...request, mode: "overview" }, maple).visible).toBe(false);
  });
  it.each([[806, 484, 25.1875, 15.125, 16.791667, 10.083333], [654, 392, 20.4375, 12.25, 13.625, 8.166667], [348, 209, 10.875, 6.53125, 7.25, 4.354167]])("spec baseline visible spans %s×%s", (w, h, x2, y2, x3, y3) => {
    const size = backingSize(w, h, 1);
    const a = visibleTiles(size, 2, 16), b = visibleTiles(size, 3, 16);
    expect(a.x).toBeCloseTo(x2 ?? 0, 5); expect(a.y).toBeCloseTo(y2 ?? 0, 5); expect(b.x).toBeCloseTo(x3 ?? 0, 5); expect(b.y).toBeCloseTo(y3 ?? 0, 5);
  });
  it.each(world.regions.map((r) => ({ id: r.id, floor: r.floor })))("Focus $id includes shared walls and largest fitting zoom at every DPR", ({ id, floor }) => {
    const bounds = regionBounds(world, id); expect(bounds).not.toBeNull();
    expect(bounds?.x).toBe((floor.x - 1) * 16); expect(bounds?.w).toBe((floor.w + 2) * 16);
    for (const dpr of dprs) for (const [w, h] of [[806, 484], [654, 392], [348, 209]] as const) {
      const size = backingSize(w, h, dpr), c = cameraView(world, size, dpr, { ...request, mode: "focus", regionId: id }, maple);
      if (c.fits && bounds) { expect(bounds.w * c.zoom).toBeLessThanOrEqual(size.width); expect(bounds.h * c.zoom).toBeLessThanOrEqual(size.height); }
      if (c.level < 4 && bounds) expect(bounds.w * deviceZoom(c.level + 1, dpr) > size.width || bounds.h * deviceZoom(c.level + 1, dpr) > size.height).toBe(true);
      if (!c.fits) expect(c.level).toBe(1);
    }
  });
  it.each([[654, 392], [348, 209]])("oversize Hall %s×%s centers Maple inside, region otherwise", (w, h) => {
    const r = { ...request, mode: "focus" as const }, size = backingSize(w, h, 1);
    const a = cameraView(world, size, 1, r, maple), bounds = regionBounds(world, "central_hall");
    expect(a.level).toBe(1); expect(a.fits).toBe(false);
    expect(a.x).toBe(clampTranslation({ x: size.width / 2 - maple.x, y: size.height / 2 - maple.y }, size, house, 1).x);
    if (!bounds) throw new Error("Missing bounds");
    const b = cameraView(world, size, 1, r, { x: 56, y: 93 });
    expect(b.x).toBe(Math.round((size.width - house.w) / 2));
  });
  it.each([{ x: 0, y: 0 }, { x: 704, y: 0 }, { x: 0, y: 416 }, { x: 704, y: 416 }, { x: 352, y: 0 }, { x: 352, y: 416 }, { x: 0, y: 208 }, { x: 704, y: 208 }])("Follow clamps edge/corner $x,$y", (p) => {
    const size = backingSize(348, 209, 1), c = cameraView(world, size, 1, request, p);
    expect(c.x).toBeLessThanOrEqual(0); expect(c.x).toBeGreaterThanOrEqual(size.width - house.w * c.zoom);
    expect(c.y).toBeLessThanOrEqual(0); expect(c.y).toBeGreaterThanOrEqual(size.height - house.h * c.zoom);
  });
  it("holds central25% dead-zone; eases outside it; reduced motion snaps", () => {
    const size = backingSize(348, 209, 1), initial = cameraView(world, size, 1, request, maple);
    expect(cameraView(world, size, 1, request, { x: maple.x + 10, y: maple.y }, initial, 16).x).toBe(initial.x);
    const moved = { x: maple.x + 60, y: maple.y };
    const eased = cameraView(world, size, 1, request, moved, initial, 16);
    const snapped = cameraView(world, size, 1, { ...request, reducedMotion: true }, moved, initial, 16);
    expect(eased.x).toBeLessThan(initial.x); expect(eased.x).toBeGreaterThan(snapped.x);
    expect(cameraView(world, size, 1, request, moved, initial, 16)).toEqual(eased);
  });
  it("stationary camera converges without subpixel output or static drift", () => {
    const size = backingSize(348, 209, 1.25), p = { x: 450.5, y: 253 };
    let c = cameraView(world, size, 1.25, request, maple);
    for (let i = 0; i < 300; i++) { c = cameraView(world, size, 1.25, request, p, c, 16); expect(Number.isInteger(c.x) && Number.isInteger(c.y)).toBe(true); }
    const final = c;
    for (let i = 0; i < 60; i++) c = cameraView(world, size, 1.25, request, p, c, 16);
    expect({ x: c.x, y: c.y }).toEqual({ x: final.x, y: final.y });
  });
  it("tracks supplied walking route without modifying fixtures", () => {
    const before = JSON.stringify(fixtureWorlds.walking), size = backingSize(348, 209, 2);
    const start = Date.parse(fixtureWorlds.walking.snapshot.maple.route?.departed_at ?? "");
    let previous;
    for (let ms = 0; ms <= 2750; ms += 25) {
      const sample = actorSample(fixtureWorlds.walking, start + ms);
      previous = cameraView(fixtureWorlds.walking, size, 2, request, sample, previous, 25);
      expect(Number.isInteger(previous.x)).toBe(true);
    }
    expect(JSON.stringify(fixtureWorlds.walking)).toBe(before);
  });
  it("missing region is explicit unavailable, passage uses supplied ownership", () => {
    expect(cameraView(world, backingSize(806, 484, 1), 1, { ...request, mode: "focus", regionId: "missing" }, maple).visible).toBe(false);
    expect(currentRegion(world, { x: 88, y: 189 })).toBe("central_hall");
    expect(() => cameraView(world, backingSize(806, 484, 1), 1, request, { x: NaN, y: 1 })).toThrow();
  });
});

it("spec Focus worst-DPR levels use exact canonical extents", () => {
  const minimum = (id: string, w: number, h: number) => Math.min(...[1,1.25,1.5,1.75,2,2.25,2.5,2.75,3].map((dpr) => cameraView(world, backingSize(w,h,dpr),dpr,{...request,mode:"focus",regionId:id},maple).level));
  for (const id of ["bedroom","living_room","library","work_studio"]) {
    expect(minimum(id,806,484)).toBe(2); expect(minimum(id,654,392)).toBe(2); expect(minimum(id,348,209)).toBe(1);
  }
  for (const id of ["creation_room","future_space","system_room"]) {
    expect([2,3]).toContain(minimum(id,806,484)); expect(minimum(id,654,392)).toBe(2); expect(minimum(id,348,209)).toBe(1);
  }
});
