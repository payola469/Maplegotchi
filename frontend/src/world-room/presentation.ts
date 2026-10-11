// Presentation transforms only. Geometry, routes and state are supplied by the backend.
import type { CharacterDirection, GridOut, Rect, Tile, WorldOut, WorldRouteOut } from "../api/world.generated";

export const LAYERS = ["backdrop", "floor", "floor_decals", "walls_back", "shadows", "entities", "occluders", "light_multiply", "light_add", "emissive", "fx_world", "editor_overlay"] as const;
export type Layer = typeof LAYERS[number];
export const PRIORITY = { structural: 1, furniture: 2, character: 3, above_occupant: 4 } as const;
export const RENDERER_OPTIONS = { preference: "webgl", resolution: 1, autoDensity: false, antialias: false, roundPixels: true } as const;
export const TEXTURE_OPTIONS = { scaleMode: "nearest", autoGenerateMipmaps: false } as const;

export function feet(tile: Tile, grid: GridOut) {
  return { x: tile.tx * grid.tile_size_px + grid.feet_in_tile_px[0], y: tile.ty * grid.tile_size_px + grid.feet_in_tile_px[1] };
}
export function depth(sortY: number, priority: number): number { return sortY * 8 + priority; }
export function stableDepth<T extends { z: number; insertion: number }>(items: readonly T[]): T[] {
  return [...items].sort((a, b) => a.z - b.z || a.insertion - b.insertion);
}
export function mapleSouthEdge(y: number, grid: GridOut): number {
  return (Math.floor((y - grid.feet_in_tile_px[1]) / grid.tile_size_px) + 1) * grid.tile_size_px;
}
export function objectSouthEdge(origin: Tile, height: number, grid: GridOut, artSortOffset: number): number {
  return (origin.ty + height) * grid.tile_size_px + artSortOffset;
}
export function facing(a: Tile, b: Tile): CharacterDirection {
  return b.tx > a.tx ? "right" : b.tx < a.tx ? "left" : b.ty > a.ty ? "down" : "up";
}
export function walkPhase(tilesTravelled: number): number { return Math.floor(tilesTravelled * 2) % 4; }

/** Interpolate supplied compressed waypoints. Never search, validate or replace a route. */
export function routeSample(route: WorldRouteOut, nowMs: number, grid: GridOut, restFacing: CharacterDirection) {
  const first = route.waypoints[0];
  if (!first) throw new Error("Route has no supplied waypoints");
  const elapsed = Math.max(0, nowMs - Date.parse(route.departed_at));
  const moving = nowMs >= Date.parse(route.departed_at) && nowMs < Date.parse(route.arrives_at);
  let entryMs = 0;
  let entryDistance = 0;
  if (route.entry) {
    const { start, endpoint } = route.entry;
    const backwards = endpoint.tx === start.a.tx && endpoint.ty === start.a.ty;
    const remaining = backwards ? start.progress_us : start.step_us - start.progress_us;
    entryMs = remaining / 1000;
    entryDistance = remaining / start.step_us;
    if (elapsed < entryMs) {
      const progress = (start.progress_us + (backwards ? -1 : 1) * elapsed * 1000) / start.step_us;
      const a = feet(start.a, grid), b = feet(start.b, grid);
      const distance = elapsed * 1000 / start.step_us;
      return { x: a.x + (b.x - a.x) * progress, y: a.y + (b.y - a.y) * progress, facing: backwards ? facing(start.b, start.a) : facing(start.a, start.b), distance, frame: walkPhase(distance), moving };
    }
  }
  const last = route.waypoints.at(-1) ?? first;
  const steps = Math.min(last.cumulative_steps, Math.max(0, (elapsed - entryMs) / route.ms_per_step));
  let direction = restFacing;
  for (let i = 1; i < route.waypoints.length; i++) {
    const a = route.waypoints[i - 1], b = route.waypoints[i];
    if (!a || !b) continue;
    direction = facing(a, b);
    if (steps < b.cumulative_steps) {
      const fraction = (steps - a.cumulative_steps) / (b.cumulative_steps - a.cumulative_steps);
      const pa = feet(a, grid), pb = feet(b, grid);
      const distance = entryDistance + steps;
      return { x: pa.x + (pb.x - pa.x) * fraction, y: pa.y + (pb.y - pa.y) * fraction, facing: direction, distance, frame: walkPhase(distance), moving };
    }
  }
  const distance = entryDistance + steps;
  return { ...feet(last, grid), facing: direction, distance, frame: walkPhase(distance), moving };
}
export function actorSample(world: WorldOut, nowMs: number) {
  const actor = world.snapshot.maple;
  if (actor.route) return routeSample(actor.route, nowMs, world.grid, actor.facing);
  return { x: actor.derived_pixels.x_px, y: actor.derived_pixels.y_px, facing: actor.facing, frame: 0, distance: 0, moving: false };
}

/** L17 integer visual hash, independent of navigation/state. */
export function floorVariant(room: string, x: number, y: number): number {
  let hash = 2166136261;
  for (const ch of room) hash = Math.imul(hash ^ ch.charCodeAt(0), 16777619);
  hash = Math.imul(hash ^ x, 16777619);
  return (Math.imul(hash ^ y, 16777619) >>> 0) % 4;
}
export function floorEdge(r: Rect, x: number, y: number): number {
  return (y === r.y ? 1 : 0) | (x === r.x + r.w - 1 ? 2 : 0) | (y === r.y + r.h - 1 ? 4 : 0) | (x === r.x ? 8 : 0);
}
export function deviceZoom(level: number, dpr: number): number { return Math.min(12, Math.max(1, Math.floor(level * dpr + 0.25))); }
export function backingSize(cssW: number, cssH: number, dpr: number, box?: { inlineSize: number; blockSize: number }) {
  const w = Math.max(1, Math.round(cssW * dpr)), h = Math.max(1, Math.round(cssH * dpr));
  return box && Math.abs(box.inlineSize - w) <= 1 && Math.abs(box.blockSize - h) <= 1
    ? { width: Math.round(box.inlineSize), height: Math.round(box.blockSize) } : { width: w, height: h };
}
export function overview(width: number, height: number, worldW: number, worldH: number, dpr: number) {
  for (let level = 4; level >= 1; level--) {
    const zoom = deviceZoom(level, dpr);
    if (worldW * zoom <= width && worldH * zoom <= height) return { zoom, x: Math.round((width - worldW * zoom) / 2), y: Math.round((height - worldH * zoom) / 2) };
  }
  return null; // L15: DOM room list, never fractional shrinking.
}
