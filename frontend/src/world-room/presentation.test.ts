import { describe, expect, it } from "vitest";
import type { WorldRouteOut } from "../api/world.generated";
import { fixtureCatalog, fixtureWorlds } from "./fixtures";
import { assertFixture, fixturePreviewEnabled } from "./gate";
import { actorSample, backingSize, depth, deviceZoom, feet, floorEdge, floorVariant, LAYERS, mapleSouthEdge, objectSouthEdge, overview, PRIORITY, routeSample, stableDepth, walkPhase } from "./presentation";

const grid = fixtureWorlds.idle.grid;
const T0 = Date.parse(fixtureWorlds.walking.snapshot.maple.route?.departed_at ?? "");
const route: WorldRouteOut = { departed_at: new Date(T0).toISOString(), arrives_at: new Date(T0 + 2000).toISOString(), ms_per_step: 250, entry: null, waypoints: [{ tx: 2, ty: 3, cumulative_steps: 0 }, { tx: 6, ty: 3, cumulative_steps: 4 }, { tx: 6, ty: 7, cumulative_steps: 8 }] };

describe("DTO geometry and safe development entry", () => {
  it.each([[true, "?room=fixture", true], [false, "?room=fixture", false], [true, "", false], [true, "?room=live", false]] as const)("gates dev=%s search=%s", (dev, search, expected) => expect(fixturePreviewEnabled(dev, search)).toBe(expected));
  it("requires matching labeled fixture identities", () => {
    expect(() => assertFixture(fixtureWorlds.idle, fixtureCatalog)).not.toThrow();
    expect(() => assertFixture({ ...fixtureWorlds.idle, catalog_version: "different" }, fixtureCatalog)).toThrow();
    expect(() => assertFixture({ ...fixtureWorlds.idle, source: "live" } as unknown as typeof fixtureWorlds.idle, fixtureCatalog)).toThrow();
  });
  it("retains complete canonical geometry and consumes DTO feet offsets", () => {
    const w = fixtureWorlds.idle;
    expect([w.grid.width_tiles, w.grid.height_tiles, w.regions.length, w.doors.length, w.objects.length, w.points.length, w.slots.length, w.walkable.length]).toEqual([44, 26, 8, 7, 28, 17, 12, 431]);
    expect(feet({ tx: 21, ty: 15 }, grid)).toEqual({ x: 344, y: 253 });
    expect(feet({ tx: 2, ty: 3 }, { ...grid, tile_size_px: 20, feet_in_tile_px: [10, 16] })).toEqual({ x: 50, y: 76 });
    expect(actorSample(w, T0)).toMatchObject({ x: 344, y: 253, facing: "down", moving: false });
  });
});

describe("L11 independent expected-depth ring", () => {
  const cases = fixtureWorlds.idle.objects.flatMap((object) => {
    const type = fixtureCatalog.types.find((v) => v.id === object.type_id);
    if (!type || type.surface !== "floor" || type.art_id === null) return [];
    const south = object.origin.ty + type.footprint.h;
    return [-1, 0, 1].flatMap((dy) => [-1, 0, type.footprint.w].map((dx) => ({ name: `${object.id}/${dx}/${dy}`, object, h: type.footprint.h, tile: { tx: object.origin.tx + dx, ty: south - 1 + dy }, expectedAbove: dy >= 0 })));
  });
  it.each(cases)("$name", ({ object, h, tile, expectedAbove }) => {
    const maple = depth(mapleSouthEdge(feet(tile, grid).y, grid), 3);
    const furniture = depth(objectSouthEdge(object.origin, h, grid, 0), 2);
    expect(maple > furniture).toBe(expectedAbove);
  });
  it("uses tile south edge instead of pixel feet and respects art offsets", () => {
    expect(mapleSouthEdge(253, grid)).toBe(256);
    expect(objectSouthEdge({ tx: 0, ty: 3 }, 3, grid, 7)).toBe(103);
    expect(Object.values(PRIORITY)).toEqual([1, 2, 3, 4]);
  });
  it("stabilizes exact ties by insertion without mutating input", () => {
    const rows = Object.freeze([{ z: 20, insertion: 3 }, { z: 10, insertion: 4 }, { z: 20, insertion: 1 }]);
    expect(stableDepth(rows).map((v) => v.insertion)).toEqual([4, 1, 3]);
    expect(rows[0]?.insertion).toBe(3);
  });
});

describe("L12 route-distance presentation", () => {
  it.each([[-100, 2, 3, 0, false], [0, 2, 3, 0, true], [125, 2.5, 3, 1, true], [1000, 6, 3, 0, true], [1375, 6, 4.5, 3, true], [2000, 6, 7, 0, false], [5000, 6, 7, 0, false]])("samples time %s", (ms, tx, ty, frame, moving) => {
    const before = JSON.stringify(route);
    const value = routeSample(route, T0 + ms, grid, "down");
    expect(value).toMatchObject({ x: tx * 16 + 8, y: ty * 16 + 13, frame, moving });
    expect(routeSample(route, T0 + ms, grid, "down")).toEqual(value);
    expect(JSON.stringify(route)).toBe(before);
  });
  it("changes direction at the supplied corner", () => {
    expect(routeSample(route, T0 + 999, grid, "down").facing).toBe("right");
    expect(routeSample(route, T0 + 1000, grid, "right").facing).toBe("down");
  });
  it("handles zero-step and long routes", () => {
    const origin = route.waypoints[0]; if (!origin) throw new Error("Missing test origin");
    const zero = { ...route, arrives_at: route.departed_at, waypoints: [origin] };
    expect(routeSample(zero, T0, grid, "left")).toMatchObject({ moving: false, frame: 0, facing: "left" });
    const long = { ...route, arrives_at: new Date(T0 + 250000).toISOString(), waypoints: [{ tx: 0, ty: 0, cumulative_steps: 0 }, { tx: 1000, ty: 0, cumulative_steps: 1000 }] };
    expect(routeSample(long, T0 + 249875, grid, "right")).toMatchObject({ distance: 999.5, frame: 3 });
  });
  it.each([true, false])("interpolates supplied partial entry, backwards=%s", (backwards) => {
    const endpoint = backwards ? { tx: 2, ty: 3 } : { tx: 3, ty: 3 };
    const entry = { start: { a: { tx: 2, ty: 3 }, b: { tx: 3, ty: 3 }, progress_us: 125000, step_us: 250000 }, endpoint };
    const partial = { ...route, entry, arrives_at: new Date(T0 + 125).toISOString(), waypoints: [{ ...endpoint, cumulative_steps: 0 }] };
    expect(routeSample(partial, T0, grid, "down").x).toBe(48);
    expect(routeSample(partial, T0 + 62.5, grid, "down")).toMatchObject({ x: backwards ? 44 : 52, frame: 0, facing: backwards ? "left" : "right" });
    expect(routeSample(partial, T0 + 125, grid, "down").x).toBe(backwards ? 40 : 56);
  });
  it.each([0, .5, 1, 1.5, 2, 10.5])("distance phase %s", (d) => expect(walkPhase(d)).toBe(Math.floor(d * 2) % 4));
});

describe("L13/L14/L17 presentation rules", () => {
  it.each([1, 1.25, 1.5, 1.75, 2, 3])("integer zoom at DPR %s", (dpr) => {
    for (let level = 1; level <= 4; level++) expect(deviceZoom(level, dpr)).toBe(Math.max(1, Math.floor(level * dpr + .25)));
    expect(backingSize(806, 484, dpr)).toEqual({ width: Math.round(806 * dpr), height: Math.round(484 * dpr) });
  });
  it("validates device box and falls back on emulated/stale boxes", () => {
    expect(backingSize(800, 500, 1.5, { inlineSize: 1200, blockSize: 750 })).toEqual({ width: 1200, height: 750 });
    expect(backingSize(800, 500, 1.5, { inlineSize: 800, blockSize: 500 })).toEqual({ width: 1200, height: 750 });
    expect(overview(806, 484, 704, 416, 1)).toEqual({ zoom: 1, x: 51, y: 34 });
    expect(overview(348, 209, 704, 416, 1)).toBeNull();
  });
  it("uses four stable floor variants and exact N1 E2 S4 W8 boundaries", () => {
    const variants = new Set<number>();
    for (let x = 0; x < 12; x++) for (let y = 0; y < 12; y++) {
      variants.add(floorVariant("bedroom", x, y)); expect(floorVariant("bedroom", x, y)).toBe(floorVariant("bedroom", x, y));
    }
    expect([...variants].sort()).toEqual([0, 1, 2, 3]);
    const r = { x: 1, y: 3, w: 8, h: 7 };
    expect(floorEdge(r, 1, 3)).toBe(9); expect(floorEdge(r, 8, 9)).toBe(6); expect(floorEdge(r, 2, 4)).toBe(0);
    expect(LAYERS).toEqual(["backdrop", "floor", "floor_decals", "walls_back", "shadows", "entities", "occluders", "light_multiply", "light_add", "emissive", "fx_world", "editor_overlay"]);
  });
});
