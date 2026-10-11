import { describe, expect, it } from "vitest";
const sources = import.meta.glob<string>(["./*.{ts,tsx}", "!./*.test.{ts,tsx}"], { query: "?raw", import: "default", eager: true });
import main from "../main.tsx?raw";

describe("R1A-11 presentation-only architecture", () => {
  it.each([
    ["pathfinding", /\b(?:findPath|find_route|aStar|heuristic|bfs|dijkstra)\s*\(/i],
    ["world validation", /\b(?:validatePlacement|validateWalkability|validateLayout|resolveCapabilities)\s*\(/],
    ["mutation and live connections", /\b(?:fetch|WebSocket|EventSource|createApiClient|createStreamOpener|localStorage)\s*[.(]/],
    ["world coordinate authority", /\b(?:FEET_IN_TILE|GRID_WIDTH|GRID_HEIGHT|ROOM_FLOORS|DOOR_POSITIONS)\s*=/],
    ["canvas text/controls", /\b(?:Text|BitmapText|HTMLText)\s*\(|\.eventMode\s*=|\.on\(["'](?:click|pointer)/],
  ])("forbids %s", (_name, pattern) => {
    expect(Object.entries(sources).filter(([, code]) => pattern.test(code)).map(([name]) => name)).toEqual([]);
  });
  it("uses generated DTOs, no legacy world geometry imports or hardcoded layout", () => {
    const all = Object.values(sources).join("\n");
    expect(all).toContain("api/world.generated");
    expect(all).not.toMatch(/room\/layout\/anchors|room\/animation|room\/maple|readonly.*\[\[\s*\d+,\s*\d+/);
    expect(sources["./scene.ts"]).toContain("world.structure");
    expect(sources["./scene.ts"]).toContain("world.passages");
  });
  it("isolates preview before all legacy/live initialization and production dead-code eliminates it", () => {
    expect(main).toContain("root && import.meta.env.DEV && fixturePreviewEnabled");
    expect(main.indexOf('import("./world-room/Preview")')).toBeLessThan(main.indexOf("const store = new Store()"));
    expect(main).toContain("} else if (root) {");
  });
  it("retains CSP-safe loading and locked renderer/sampling flags", () => {
    expect(sources["./assets.ts"]).toContain('import "pixi.js/unsafe-eval"');
    expect(sources["./assets.ts"]).toContain("preferWorkers: false");
    expect(sources["./presentation.ts"]).toContain('preference: "webgl", resolution: 1, autoDensity: false, antialias: false, roundPixels: true');
    expect(sources["./presentation.ts"]).toContain('scaleMode: "nearest", autoGenerateMipmaps: false');
    expect(sources["./scene.ts"]).toContain("window.devicePixelRatio");
  });
});
