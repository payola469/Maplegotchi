import "pixi.js/unsafe-eval";
import { Application, Container, Graphics, Sprite } from "pixi.js";
import type { WorldCatalogOut, WorldOut } from "../api/world.generated";
import { createPlaceholderArt, initializeAssets, MAPLE_ART, type RoomArt } from "./assets";
import { assertFixture } from "./gate";
import { actorSample, backingSize, depth, floorEdge, floorVariant, LAYERS, mapleSouthEdge, objectSouthEdge, overview, PRIORITY, RENDERER_OPTIONS } from "./presentation";

export interface SceneFrame { world: WorldOut; timeMs: number }
export interface WorldScene {
  update(frame: SceneFrame): void;
  destroy(): void;
}
export interface SceneOptions {
  catalog: WorldCatalogOut;
  frame: SceneFrame;
  signal: AbortSignal;
  onOverviewUnavailable(value: boolean): void;
}
export type CreateWorldScene = (host: HTMLElement, options: SceneOptions) => Promise<WorldScene>;

export const createWorldScene: CreateWorldScene = async (host, options) => {
  assertFixture(options.frame.world, options.catalog);
  if (options.signal.aborted) throw new DOMException("Preview cancelled", "AbortError");
  await initializeAssets();
  if (options.signal.aborted) throw new DOMException("Preview cancelled", "AbortError");
  const app = new Application();
  let art: RoomArt | undefined;
  let observer: ResizeObserver | undefined;
  let disposed = false, initialized = false;
  let draw: (() => void) | undefined;
  const dispose = () => {
    if (disposed) return;
    disposed = true;
    options.signal.removeEventListener("abort", dispose);
    observer?.disconnect();
    if (initialized) {
      if (draw) app.ticker.remove(draw);
      app.stop();
      app.destroy({ removeView: true }, { children: true, texture: false, textureSource: false });
    }
    if (!initialized) app.stage.destroy({ children: true });
    art?.destroy();
  };
  // init() is asynchronous: do not destroy a half-initialized Application on abort.
  try {
    await app.init({ ...RENDERER_OPTIONS, width: 1, height: 1, background: 0x292b29, autoStart: false });
    initialized = true;
    if (options.signal.aborted) throw new DOMException("Preview cancelled", "AbortError");
    options.signal.addEventListener("abort", dispose, { once: true });
    art = createPlaceholderArt(options.frame.world.grid.tile_size_px);
    const ownedArt = art;
    const viewport = new Container({ label: "world-viewport" });
    app.stage.addChild(viewport);
    const layers = Object.fromEntries(LAYERS.map((name) => {
      const layer = new Container({ label: name }); viewport.addChild(layer); return [name, layer];
    })) as Record<typeof LAYERS[number], Container>;
    layers.entities.sortableChildren = true;
    layers.light_multiply.blendMode = "multiply";
    layers.light_add.blendMode = "add";
    const world = options.frame.world, t = world.grid.tile_size_px;
    // Visual pane cutouts only: structural/walkable DTO cells remain untouched.
    const windowHoles = world.objects.flatMap((object) => {
      const type = options.catalog.types.find((value) => value.id === object.type_id);
      if (!type?.art_id?.startsWith("window.")) return [];
      const region = world.regions.find((value) => value.id === object.room_id);
      const part = ownedArt.object(type, t);
      if (!region || !part || type.mount_y_px === null) throw new Error("Missing window presentation metadata");
      return [{ x: object.origin.tx * t, y: region.floor.y * t - type.mount_y_px - part.texture.height, w: part.texture.width, h: part.texture.height }];
    });
    const passageCells = new Set(world.passages.flatMap((p) => p.cells.map((c) => `${c.tx},${c.ty}`)));
    const bandTop = new Map<string, number>();
    for (const cell of world.structure) if (cell.kind === "north_band") bandTop.set(cell.region_id, Math.min(bandTop.get(cell.region_id) ?? Infinity, cell.tile.ty));
    for (const region of world.regions) {
      const r = region.floor;
      for (let y = r.y; y < r.y + r.h; y++) for (let x = r.x; x < r.x + r.w; x++) {
        const tile = new Sprite(ownedArt.floor(floorVariant(region.id, x, y)));
        tile.position.set(x * t, y * t); if (region.status === "closed") tile.tint = 0x818b90;
        const edge = new Sprite(ownedArt.edge(floorEdge(r, x, y))); edge.position.copyFrom(tile.position);
        layers.floor.addChild(tile, edge);
      }
    }
    for (const cell of world.structure) {
      if (cell.kind === "floor" || passageCells.has(`${cell.tile.tx},${cell.tile.ty}`)) continue;
      const x = cell.tile.tx * t, y = cell.tile.ty * t;
      const g = new Graphics();
      const hole = cell.kind === "north_band" ? windowHoles.find((r) => x >= r.x && x < r.x + r.w && y < r.y + r.h && y + t > r.y) : undefined;
      if (hole) {
        if (hole.y > y) g.rect(x, y, t, hole.y - y);
        if (hole.y + hole.h < y + t) g.rect(x, hole.y + hole.h, t, y + t - hole.y - hole.h);
      } else g.rect(x, y, t, cell.kind === "south_cutaway" ? 2 : t);
      g.fill(cell.kind === "south_cutaway" ? 0x6b665d : 0x6c7167);
      layers.walls_back.addChild(g);
      if (cell.kind === "north_band" && cell.tile.ty === bandTop.get(cell.region_id)) {
        layers.occluders.addChild(new Graphics().rect(x, y, t, 8).fill(0x494f49)); // placeholder cap 8 <= L7 max 13
      } else if (cell.kind === "side_wall") {
        const cap = new Graphics().rect(x, y, t, 3).fill(0x494f49);
        cap.zIndex = depth(y + t, PRIORITY.structural); layers.entities.addChild(cap);
      }
    }
    for (const door of world.doors) {
      const r = door.passage;
      const floor = new Graphics().rect(r.x * t, r.y * t, r.w * t, r.h * t).fill(door.state === "open" ? 0xa79f89 : 0x727b80);
      layers.floor.addChild(floor);
      // Archway sides only, no lintel/cap across the opening.
      const jamb = new Graphics().rect(r.x * t, r.y * t, 1, r.h * t).rect((r.x + r.w) * t - 1, r.y * t, 1, r.h * t).fill(0x494f49);
      layers.walls_back.addChild(jamb);
      if (door.state === "closed") layers.walls_back.addChild(new Graphics().rect(r.x * t + 2, r.y * t + r.h * t - 3, r.w * t - 4, 2).fill(0xb4b7b3));
    }
    const objectDepths = new Map<string, number>();
    for (const object of world.objects) {
      const type = options.catalog.types.find((value) => value.id === object.type_id);
      if (!type) throw new Error(`Missing fixture catalog type: ${object.type_id}`);
      if (object.orientation !== "south") throw new Error("Placeholder art has only the approved initial south orientation");
      const part = ownedArt.object(type, t);
      if (!part) continue;
      const south = objectSouthEdge(object.origin, type.footprint.h, world.grid, part.sortOffsetPx);
      objectDepths.set(object.id, south);
      const sprite = new Sprite(part.texture);
      let anchorY = (object.origin.ty + type.footprint.h) * t;
      if (type.surface === "north_band") {
        const region = world.regions.find((value) => value.id === object.room_id);
        if (!region || type.mount_y_px === null) throw new Error("Missing backend wall mount metadata");
        anchorY = region.floor.y * t - type.mount_y_px;
      }
      sprite.position.set(object.origin.tx * t - part.anchor.x, anchorY - part.anchor.y);
      const window = type.art_id?.startsWith("window.") ?? false;
      if (window) {
        layers.backdrop.addChild(new Graphics().rect(sprite.x, sprite.y, sprite.width, sprite.height).fill(0x688f98));
      }
      sprite.zIndex = depth(south, PRIORITY.furniture);
      const flat = type.surface === "floor" && type.blocks.every((row) => !row.includes("#"));
      (type.surface === "north_band" ? layers.walls_back : flat ? layers.floor_decals : layers.entities).addChild(sprite);
      if (part.aboveOccupant) {
        const overlay = new Sprite(part.aboveOccupant); overlay.position.copyFrom(sprite.position);
        overlay.zIndex = depth(south, PRIORITY.above_occupant); layers.entities.addChild(overlay);
      }
    }
    const actor = new Container({ label: "maple" });
    const body = new Sprite(ownedArt.body("down", 0));
    const face = new Sprite(ownedArt.face(world.snapshot.maple.expression));
    actor.addChild(body, face); layers.entities.addChild(actor);
    let current = options.frame;
    let deviceBox: { inlineSize: number; blockSize: number } | undefined;
    let previous = "";
    app.canvas.setAttribute("aria-hidden", "true");
    app.canvas.classList.add("world-preview__canvas");
    host.appendChild(app.canvas);
    draw = () => {
      if (disposed) return;
      const dpr = window.devicePixelRatio || 1;
      const css = host.getBoundingClientRect();
      const size = backingSize(css.width, css.height, dpr, deviceBox);
      const key = `${size.width}/${size.height}/${dpr}`;
      if (key !== previous) {
        previous = key; app.renderer.resize(size.width, size.height);
        const view = overview(size.width, size.height, world.grid.width_tiles * t, world.grid.height_tiles * t, dpr);
        viewport.visible = view !== null;
        if (view) { viewport.scale.set(view.zoom); viewport.position.set(view.x, view.y); }
        options.onOverviewUnavailable(view === null);
      }
      const sample = actorSample(current.world, current.timeMs);
      const frame = sample.moving ? sample.frame : 0;
      body.texture = ownedArt.body(sample.facing, frame);
      face.texture = ownedArt.face(current.world.snapshot.maple.expression);
      const anchor = ownedArt.faceAnchor(sample.facing, frame);
      face.visible = anchor !== null;
      if (anchor) face.position.set(anchor.x, anchor.y);
      // Round only the device-pixel presentation; never alter supplied state.
      const zoom = viewport.scale.x;
      actor.position.set(Math.round(sample.x * zoom) / zoom - MAPLE_ART.anchor.x, Math.round(sample.y * zoom) / zoom - MAPLE_ART.anchor.y);
      const occupying = !sample.moving && current.world.snapshot.maple.pose !== "idle" && current.world.snapshot.maple.pose !== "walk";
      const sortY = occupying ? objectDepths.get(current.world.snapshot.maple.destination_point.instance_id) ?? mapleSouthEdge(sample.y, world.grid) : mapleSouthEdge(sample.y, world.grid);
      actor.zIndex = depth(sortY, PRIORITY.character);
    };
    observer = new ResizeObserver((entries) => {
      const entry = entries[0]; deviceBox = entry?.devicePixelContentBoxSize?.[0]; draw?.();
    });
    try { observer.observe(host, { box: "device-pixel-content-box" }); } catch { observer.observe(host); }
    draw(); app.ticker.add(draw); app.start();
    return {
      update(frame) {
        if (disposed) return;
        assertFixture(frame.world, options.catalog);
        if (frame.world.layout_revision !== world.layout_revision) throw new Error("Layout changes require a new preview mount");
        current = frame; draw?.();
      },
      destroy: dispose,
    };
  } catch (error) { dispose(); throw error; }
};
