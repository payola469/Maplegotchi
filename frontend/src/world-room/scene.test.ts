// @vitest-environment happy-dom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fixtureCatalog, fixtureWorlds } from "./fixtures";
import { createWorldScene } from "./scene";
import { createPlaceholderArt } from "./assets";
vi.mock("./atlas", () => ({ loadAtlasArt: async () => createPlaceholderArt(16) }));
import { depth } from "./presentation";

const record = vi.hoisted(() => ({ apps: [] as unknown[], artDestroy: vi.fn(), failArt: false, failInit: false, initWait: null as Promise<void> | null, observers: [] as { disconnect: ReturnType<typeof vi.fn>; observe: ReturnType<typeof vi.fn>; callback: ResizeObserverCallback }[] }));
vi.mock("pixi.js/unsafe-eval", () => ({}));
vi.mock("pixi.js", () => {
  class Position {
    x = 0; y = 0;
    set(x: number, y = x) { this.x = x; this.y = y; }
    copyFrom(other: Position) { this.set(other.x, other.y); }
  }
  class Container {
    children: Container[] = []; position = new Position(); scale = new Position(); label: string; zIndex = 0; visible = true; sortableChildren = false; blendMode = "normal";
    constructor(options?: { label?: string }) { this.label = options?.label ?? ""; this.scale.set(1); }
    get x() { return this.position.x; } get y() { return this.position.y; }
    addChild(...values: Container[]) { this.children.push(...values); return values[0]; }
    destroy = vi.fn();
  }
  class Graphics extends Container {
    rects: number[][] = [];
    rect(...args: number[]) { this.rects.push(args); return this; }
    fill() { return this; }
  }
  class Sprite extends Container {
    tint = 0xffffff;
    constructor(public texture: { width: number; height: number }) { super(); }
    get width() { return this.texture.width; } get height() { return this.texture.height; }
  }
  class Application {
    stage = new Container(); canvas = document.createElement("canvas"); ticker = { add: vi.fn(), remove: vi.fn() }; renderer = { resize: vi.fn() };
    init = vi.fn(async () => { if (record.initWait) await record.initWait; if (record.failInit) throw new Error("WebGL unavailable"); }); start = vi.fn(); stop = vi.fn();
    destroy = vi.fn(() => this.canvas.remove());
    constructor() { record.apps.push(this); }
  }
  return { Application, Container, Graphics, Sprite };
});
vi.mock("./assets", () => ({
  MAPLE_ART: { width: 32, height: 48, anchor: { x: 16, y: 47 } },
  initializeAssets: vi.fn(async () => undefined),
  createPlaceholderArt: vi.fn(() => {
    if (record.failArt) throw new Error("Missing asset");
    return {
      body: () => ({ width: 32, height: 48 }), face: () => ({ width: 12, height: 6 }),
      faceAnchor: (direction: string) => direction === "up" ? null : { x: 10, y: 12 },
      floor: () => ({ width: 16, height: 16 }), edge: () => ({ width: 16, height: 16 }),
      object: (type: { art_id: string | null; footprint: { w: number; h: number } }, t: number) => type.art_id === null ? null : ({ texture: { width: type.footprint.w * t, height: type.art_id.startsWith("window.") ? 2 * t : type.footprint.h * t }, anchor: { x: 0, y: type.footprint.h * t }, sortOffsetPx: 0, aboveOccupant: { width: 2, height: 2 } }),
      structural: (id: string, clip?: { w: number; h: number }) => ({ width: clip?.w ?? (id.startsWith("door") || id.startsWith("backdrop") ? 32 : 16), height: clip?.h ?? (id.startsWith("door") ? 48 : id.startsWith("backdrop") ? 32 : 16), assetId: id }),
      destroy: record.artDestroy,
    };
  }),
}));
interface Node { label: string; children: Node[]; zIndex: number; visible: boolean; position: { x: number; y: number }; rects?: number[][]; texture?: { assetId?: string; width: number; height: number } }
interface FakeApp { stage: Node; canvas: HTMLCanvasElement; ticker: { add: ReturnType<typeof vi.fn>; remove: ReturnType<typeof vi.fn> }; renderer: { resize: ReturnType<typeof vi.fn> }; init: ReturnType<typeof vi.fn>; destroy: ReturnType<typeof vi.fn> }
function app(): FakeApp { return record.apps.at(-1) as FakeApp; }
function layer(name: string) { const value = app().stage.children[0]?.children.find((c) => c.label === name); if (!value) throw new Error(`Missing ${name}`); return value; }
function setup() {
  const host = document.createElement("div"); document.body.appendChild(host);
  vi.spyOn(host, "getBoundingClientRect").mockReturnValue({ width: 1000, height: 600 } as DOMRect);
  const controller = new AbortController(), fallback = vi.fn();
  return { host, controller, fallback, options: { frame: { world: fixtureWorlds.idle, timeMs: Date.parse(fixtureWorlds.idle.snapshot.generated_at) }, catalog: fixtureCatalog, signal: controller.signal, onOverviewUnavailable: fallback } };
}
beforeEach(() => {
  record.apps.length = 0; record.observers.length = 0; record.failArt = false; record.failInit = false; record.initWait = null; record.artDestroy.mockClear();
  vi.stubGlobal("ResizeObserver", class {
    observe = vi.fn(); disconnect = vi.fn();
    constructor(public callback: ResizeObserverCallback) { record.observers.push(this); }
  });
});
afterEach(() => { document.body.replaceChildren(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe("Pixi scene lifecycle and structured coverage (recording renderer)", () => {
  it("boots one renderer with locked flags, draws all layers and frees owned resources exactly once", async () => {
    const s = setup(), handle = await createWorldScene(s.host, s.options);
    expect(app().init).toHaveBeenCalledWith(expect.objectContaining({ preference: "webgl", antialias: false, resolution: 1, autoDensity: false, roundPixels: true }));
    expect(app().stage.children[0]?.children).toHaveLength(12);
    const count = fixtureWorlds.idle.regions.reduce((n, r) => n + r.floor.w * r.floor.h, 0);
    expect(layer("floor").children).toHaveLength(count * 2 + 7 * 6); // base+edge per floor, six atlas floor cells per passage
    expect(layer("backdrop").children).toHaveLength(4); // four canonical exterior windows
    expect(layer("entities").children.filter((v) => v.label === "maple")).toHaveLength(1);
    expect(app().ticker.add).toHaveBeenCalledTimes(1);
    expect(s.host.querySelector("canvas")?.getAttribute("aria-hidden")).toBe("true");
    handle.destroy(); s.controller.abort(); handle.destroy();
    expect(app().destroy).toHaveBeenCalledTimes(1); expect(record.artDestroy).toHaveBeenCalledTimes(1);
    expect(record.observers[0]?.disconnect).toHaveBeenCalledTimes(1); expect(app().ticker.remove).toHaveBeenCalledTimes(1); expect(s.host.querySelector("canvas")).toBeNull();
  });
  it("carves all supplied passage cells and does not cap any doorway", async () => {
    const s = setup(), handle = await createWorldScene(s.host, s.options);
    const capRects = layer("occluders").children.map((v) => [v.position.x, v.position.y]);
    expect(capRects.length).toBeGreaterThan(0);
    for (const door of fixtureWorlds.idle.doors) {
      const r = door.passage;
      expect(capRects.some(([x, y]) => x !== undefined && y !== undefined && x >= r.x * 16 && x < (r.x + r.w) * 16 && y >= r.y * 16 && y < (r.y + r.h) * 16)).toBe(false);
    }
    handle.destroy();
  });
  it("leaves the exterior window pane transparent through the wall face to its backdrop", async () => {
    const s = setup(), handle = await createWorldScene(s.host, s.options);
    const window = fixtureWorlds.idle.objects.find((o) => o.type_id === "window.north_2w");
    if (!window) throw new Error("Missing window");
    const x = window.origin.tx * 16 + 5, y = 20;
    const walls = layer("walls_back").children.filter((v) => v.texture?.assetId === "wall.north").map((v) => [v.position.x, v.position.y, v.texture?.width, v.texture?.height]);
    expect(walls.length).toBeGreaterThan(0);
    expect(walls.some(([rx, ry, rw, rh]) => rx !== undefined && ry !== undefined && rw !== undefined && rh !== undefined && x >= rx && x < rx + rw && y >= ry && y < ry + rh)).toBe(false);
    handle.destroy();
  });
  it("positions Maple at the locked anchor and updates depth/face without a remount", async () => {
    const s = setup(), handle = await createWorldScene(s.host, s.options);
    const maple = layer("entities").children.find((v) => v.label === "maple");
    expect(maple?.position).toMatchObject({ x: 344 - 16, y: 253 - 47 }); expect(maple?.zIndex).toBe(depth(256, 3));
    handle.update({ world: fixtureWorlds.walking, timeMs: Date.parse(fixtureWorlds.walking.snapshot.generated_at) });
    expect(maple?.position.x).toBe(352 - 16); expect(record.apps).toHaveLength(1);
    const up = { ...fixtureWorlds.idle, snapshot: { ...fixtureWorlds.idle.snapshot, maple: { ...fixtureWorlds.idle.snapshot.maple, facing: "up" as const } } };
    handle.update({ world: up, timeMs: s.options.frame.timeMs }); expect(maple?.children[1]?.visible).toBe(false);
    handle.destroy(); handle.update(s.options.frame); expect(record.artDestroy).toHaveBeenCalledTimes(1);
  });
  it("preserves above-occupant ordering and occupant object depth", async () => {
    const s = setup(), handle = await createWorldScene(s.host, s.options);
    const bed = fixtureWorlds.idle.objects.find((o) => o.id === "bed.bedroom"); if (!bed) throw new Error("Missing bed");
    const occupied = { ...fixtureWorlds.idle, snapshot: { ...fixtureWorlds.idle.snapshot, maple: { ...fixtureWorlds.idle.snapshot.maple, destination_point: { instance_id: bed.id, point_id: "sleep" }, pose: "lie_sleep" as const } } };
    handle.update({ world: occupied, timeMs: s.options.frame.timeMs });
    const maple = layer("entities").children.find((v) => v.label === "maple"); expect(maple?.zIndex).toBe(depth(96, 3));
    expect(layer("entities").children.some((v) => v.zIndex === depth(96, 4))).toBe(true); handle.destroy();
  });
  it("checks DPR on every render and changes backing without CSS scaling artifacts", async () => {
    const s = setup(), handle = await createWorldScene(s.host, s.options);
    vi.stubGlobal("devicePixelRatio", 1.5); handle.update(s.options.frame);
    expect(app().renderer.resize).toHaveBeenLastCalledWith(1500, 900); handle.destroy();
  });
  it("cleans up on missing catalog/assets and initialization failure", async () => {
    const s = setup(); record.failArt = true;
    await expect(createWorldScene(s.host, s.options)).rejects.toThrow("Missing asset"); expect(record.apps).toHaveLength(0);
    record.failArt = false; record.failInit = true;
    await expect(createWorldScene(s.host, s.options)).rejects.toThrow("WebGL unavailable"); expect(s.host.querySelector("canvas")).toBeNull();
    expect(record.artDestroy).toHaveBeenCalledTimes(1); record.artDestroy.mockClear();
    record.failInit = false;
    await expect(createWorldScene(s.host, { ...s.options, catalog: { ...fixtureCatalog, types: [] } })).rejects.toThrow(/Missing fixture catalog/); expect(record.artDestroy).toHaveBeenCalledTimes(1);
  });
  it("aborts safely before or during async GPU initialization", async () => {
    const s = setup(); s.controller.abort();
    await expect(createWorldScene(s.host, s.options)).rejects.toMatchObject({ name: "AbortError" }); expect(record.apps).toHaveLength(0);
    const s2 = setup(); let resolve: () => void = () => undefined;
    record.initWait = new Promise<void>((done) => { resolve = done; });
    const pending = createWorldScene(s2.host, s2.options); await Promise.resolve(); await Promise.resolve(); s2.controller.abort(); resolve();
    await expect(pending).rejects.toMatchObject({ name: "AbortError" }); expect(app().destroy).toHaveBeenCalledTimes(1); expect(s2.host.querySelector("canvas")).toBeNull();
  });
});
