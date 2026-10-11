// Pure presentation math. All world extents and character positions come from DTOs.
import type { WorldOut } from "../api/world.generated";

export type LogicalZoom = 1 | 2 | 3 | 4;
export type CameraMode = "overview" | "follow" | "focus";
export interface Point { readonly x: number; readonly y: number }
export interface Bounds extends Point { readonly w: number; readonly h: number }
export interface Viewport { readonly width: number; readonly height: number }
export interface CameraRequest { readonly mode: CameraMode; readonly level: LogicalZoom; readonly regionId: string; readonly reducedMotion: boolean }
export interface CameraView extends Point {
  readonly zoom: number; readonly level: LogicalZoom; readonly fits: boolean;
  readonly visible: boolean; readonly mode: CameraMode; readonly regionId: string;
  readonly rawX: number; readonly rawY: number; readonly signature: string;
}
const LEVELS: readonly LogicalZoom[] = [4, 3, 2, 1];
function positive(value: number, name: string) {
  if (!Number.isFinite(value) || value <= 0) throw new RangeError(`Invalid ${name}`);
}
export function deviceZoom(level: number, dpr: number): number {
  if (!LEVELS.includes(level as LogicalZoom)) throw new RangeError("Logical zoom must be L1–L4");
  positive(dpr, "DPR");
  return Math.min(12, Math.max(1, Math.floor(level * dpr + 0.25)));
}
export function backingSize(cssW: number, cssH: number, dpr: number, box?: { inlineSize: number; blockSize: number }): Viewport {
  positive(cssW, "CSS width"); positive(cssH, "CSS height"); positive(dpr, "DPR");
  const width = Math.max(1, Math.round(cssW * dpr)), height = Math.max(1, Math.round(cssH * dpr));
  return box && Number.isFinite(box.inlineSize) && Number.isFinite(box.blockSize) && box.inlineSize >= 1 && box.blockSize >= 1 && Math.abs(box.inlineSize - width) <= 1 && Math.abs(box.blockSize - height) <= 1
    ? { width: Math.round(box.inlineSize), height: Math.round(box.blockSize) } : { width, height };
}
export function visibleTiles(viewport: Viewport, zoom: number, tileSize: number) {
  positive(zoom, "device zoom"); positive(tileSize, "tile size");
  return { x: viewport.width / (zoom * tileSize), y: viewport.height / (zoom * tileSize) };
}
export function worldToDevice(point: Point, view: Pick<CameraView, "zoom" | "x" | "y">): Point {
  return { x: point.x * view.zoom + view.x, y: point.y * view.zoom + view.y };
}
export function deviceToWorld(point: Point, view: Pick<CameraView, "zoom" | "x" | "y">): Point {
  return { x: (point.x - view.x) / view.zoom, y: (point.y - view.y) / view.zoom };
}
export function houseBounds(world: WorldOut): Bounds {
  return { x: 0, y: 0, w: world.grid.width_tiles * world.grid.tile_size_px, h: world.grid.height_tiles * world.grid.tile_size_px };
}
/** Include supplied north band, both bordering side columns (even shared), and exterior cutaway. */
export function regionBounds(world: WorldOut, id: string): Bounds | null {
  const region = world.regions.find((r) => r.id === id);
  if (!region) return null;
  const f = region.floor, t = world.grid.tile_size_px;
  const north = world.structure.filter((c) => c.region_id === id && c.kind === "north_band");
  const top = Math.min(f.y, ...north.map((c) => c.tile.ty));
  const cells = world.structure.filter((c) => c.kind !== "floor" && c.tile.tx >= f.x - 1 && c.tile.tx <= f.x + f.w && c.tile.ty >= top && (c.tile.ty < f.y + f.h || c.kind === "south_cutaway" && c.tile.ty === f.y + f.h));
  const x = Math.min(f.x, ...cells.map((c) => c.tile.tx));
  const y = Math.min(f.y, ...cells.map((c) => c.tile.ty));
  const right = Math.max(f.x + f.w, ...cells.map((c) => c.tile.tx + 1));
  const bottom = Math.max(f.y + f.h, ...cells.map((c) => c.tile.ty + 1));
  return { x: x * t, y: y * t, w: (right - x) * t, h: (bottom - y) * t };
}
/** Presentation room label only: floors then explicitly supplied passage ownership. */
export function currentRegion(world: WorldOut, point: Point): string | null {
  const t = world.grid.tile_size_px;
  const tx = Math.floor((point.x - world.grid.feet_in_tile_px[0]) / t), ty = Math.floor((point.y - world.grid.feet_in_tile_px[1]) / t);
  return world.regions.find((r) => tx >= r.floor.x && tx < r.floor.x + r.floor.w && ty >= r.floor.y && ty < r.floor.y + r.floor.h)?.id
    ?? world.passages.find((p) => p.cells.some((c) => c.tx === tx && c.ty === ty))?.region_id ?? null;
}
function clampAxis(value: number, viewport: number, world: number) {
  return world <= viewport ? (viewport - world) / 2 : Math.min(0, Math.max(viewport - world, value));
}
export function clampTranslation(point: Point, viewport: Viewport, house: Bounds, zoom: number): Point {
  return { x: Math.round(clampAxis(point.x, viewport.width, house.w * zoom)), y: Math.round(clampAxis(point.y, viewport.height, house.h * zoom)) };
}
function centre(target: Point, viewport: Viewport, zoom: number): Point {
  return { x: viewport.width / 2 - target.x * zoom, y: viewport.height / 2 - target.y * zoom };
}
function fitting(bounds: Bounds, viewport: Viewport, dpr: number): LogicalZoom | null {
  return LEVELS.find((l) => bounds.w * deviceZoom(l, dpr) <= viewport.width && bounds.h * deviceZoom(l, dpr) <= viewport.height) ?? null;
}
export function cameraView(world: WorldOut, viewport: Viewport, dpr: number, request: CameraRequest, maple: Point, previous?: CameraView, deltaMs = 0): CameraView {
  positive(viewport.width, "viewport width"); positive(viewport.height, "viewport height");
  if (!Number.isFinite(maple.x) || !Number.isFinite(maple.y) || !Number.isFinite(deltaMs) || deltaMs < 0) throw new RangeError("Invalid camera target/time");
  const house = houseBounds(world), region = request.mode === "focus" ? regionBounds(world, request.regionId) : null;
  const bounds = request.mode === "focus" ? region : house;
  const fit = bounds ? fitting(bounds, viewport, dpr) : null;
  const level = request.mode === "follow" ? request.level : fit ?? 1;
  const zoom = deviceZoom(level, dpr);
  const signature = `${viewport.width}/${viewport.height}/${dpr}/${zoom}/${request.mode}/${request.regionId}`;
  const canContinue = previous?.signature === signature && previous.visible;
  const inside = currentRegion(world, maple) === request.regionId;
  const target = request.mode === "follow" || request.mode === "focus" && !fit && inside ? maple
    : { x: (bounds?.x ?? 0) + (bounds?.w ?? house.w) / 2, y: (bounds?.y ?? 0) + (bounds?.h ?? house.h) / 2 };
  let desired = centre(target, viewport, zoom);
  if (request.mode === "follow" && canContinue && previous) {
    // Central 25% rectangle: move only when Maple leaves its +/-12.5% half extents.
    const p = worldToDevice(maple, previous);
    const dx = p.x - Math.max(viewport.width * .375, Math.min(viewport.width * .625, p.x));
    const dy = p.y - Math.max(viewport.height * .375, Math.min(viewport.height * .625, p.y));
    desired = { x: previous.rawX - dx, y: previous.rawY - dy };
  }
  desired = clampTranslation(desired, viewport, house, zoom);
  // Provisional presentation easing: 18% per nominal 60-Hz frame; injected elapsed time.
  const weight = request.reducedMotion || !canContinue || request.mode !== "follow" ? 1 : 1 - Math.pow(.82, Math.min(deltaMs, 100) / (1000 / 60));
  const rawX = canContinue && previous ? previous.rawX + (desired.x - previous.rawX) * weight : desired.x;
  const rawY = canContinue && previous ? previous.rawY + (desired.y - previous.rawY) * weight : desired.y;
  const output = clampTranslation({ x: rawX, y: rawY }, viewport, house, zoom);
  return { ...output, rawX, rawY, zoom, level, fits: fit !== null, visible: (request.mode !== "overview" || fit !== null) && (request.mode !== "focus" || region !== null), mode: request.mode, regionId: request.regionId, signature };
}
