// @vitest-environment happy-dom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Container } from "pixi.js";
import { createPlaceholderArt, faceAnchor, MAPLE_ART, PROVISIONAL_FACE } from "./assets";
import { fixtureCatalog } from "./fixtures";

beforeEach(() => {
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockImplementation(() => ({ fillRect: vi.fn(), strokeRect: vi.fn(), imageSmoothingEnabled: false, fillStyle: "", strokeStyle: "", lineWidth: 1 }) as unknown as ReturnType<HTMLCanvasElement["getContext"]>);
});
afterEach(() => vi.restoreAllMocks());
describe("placeholder resources and L6", () => {
  it.each(["down", "left", "right", "up"] as const)("has per-frame integer face anchors for %s", (direction) => {
    const art = createPlaceholderArt(16);
    for (let frame = 0; frame < 4; frame++) {
      const body = art.body(direction, frame);
      expect([body.width, body.height]).toEqual([32, 48]);
      expect(body.source.scaleMode).toBe("nearest"); expect(body.source.autoGenerateMipmaps).toBe(false);
      const anchor = art.faceAnchor(direction, frame);
      expect(anchor).toEqual(faceAnchor(direction, frame, PROVISIONAL_FACE));
      if (direction === "up") expect(anchor).toBeNull(); else expect(Number.isInteger(anchor?.y)).toBe(true);
    }
    expect(MAPLE_ART.anchor).toEqual({ x: 16, y: 47 }); art.destroy();
  });
  it("keeps faces separate from body, and size configurable/provisional", () => {
    const art = createPlaceholderArt(16, { width: 14, height: 8 });
    for (const expression of ["calm", "happy", "curious", "sleepy", "focused"] as const) expect([art.face(expression).width, art.face(expression).height]).toEqual([14, 8]);
    expect(art.face("calm")).not.toBe(art.body("down", 0)); art.destroy();
  });
  it.each([{ width: 0, height: 6 }, { width: 12.5, height: 6 }, { width: 30, height: 6 }])("rejects unusable test art dimensions %s", (size) => expect(() => createPlaceholderArt(16, size)).toThrow());
  it("has exactly sixteen 4×4 row-major edge cells, four variants and shared-source cleanup", () => {
    const art = createPlaceholderArt(16), edges = Array.from({ length: 16 }, (_, mask) => art.edge(mask));
    for (const [index, edge] of edges.entries()) {
      expect([edge.frame.x, edge.frame.y, edge.width, edge.height]).toEqual([(index % 4) * 16, Math.floor(index / 4) * 16, 16, 16]);
      expect(edge.source).toBe(edges[0]?.source);
    }
    expect(new Set([0, 1, 2, 3].map((v) => art.floor(v))).size).toBe(4);
    const source = edges[0]?.source; if (!source) throw new Error("Missing source");
    const destroy = vi.spyOn(source, "destroy"); art.destroy(); art.destroy();
    expect(destroy).toHaveBeenCalledTimes(1); expect(() => art.body("down", 0)).toThrow(/disposed/);
  });
  it("uses Pixi stable insertion ties and the declared layer priorities", () => {
    const entities = new Container({ sortableChildren: true });
    const a = new Container(), b = new Container(), character = new Container();
    a.zIndex = 160 * 8 + 2; b.zIndex = a.zIndex; character.zIndex = 160 * 8 + 3;
    entities.addChild(character, b, a); entities.sortChildren();
    expect(entities.children).toEqual([b, a, character]); entities.destroy({ children: true });
  });
  it("renders locked 2T windows and leaves marker art absent", () => {
    const art = createPlaceholderArt(16);
    const window = fixtureCatalog.types.find((type) => type.id === "window.north_2w");
    const marker = fixtureCatalog.types.find((type) => type.art_id === null);
    if (!window || !marker) throw new Error("Missing canonical test types");
    expect(art.object(window, 16)?.texture.height).toBe(32); expect(art.object(window, 16)?.texture.width).toBe(32);
    expect(art.object(marker, 16)).toBeNull(); art.destroy();
  });
});
