// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { Assets, CanvasSource, Texture, Sprite, Spritesheet } from 'pixi.js';
import { loadAtlasArt } from './atlas';
import { atlasPages } from './generated';
import { fixtureCatalog } from './fixtures';
vi.mock('./assets', () => ({ initializeAssets: async () => undefined }));
function resources() {
  const load = vi.spyOn(Assets, 'load').mockImplementation(async () => { const canvas = document.createElement('canvas'); canvas.width = 1024; canvas.height = 1024; return new Texture({ source: new CanvasSource({ resource: canvas }) }) as unknown as Record<string, unknown>; });
  const unload = vi.spyOn(Assets, 'unload').mockResolvedValue(undefined); return { load, unload };
}
afterEach(() => vi.restoreAllMocks());
describe('packed Pixi spritesheets', () => {
  it('loads all visual keys, original canvases, face anchors and sampling without raw files', async () => {
    const { load, unload } = resources(), art = await loadAtlasArt();
    expect(load).toHaveBeenCalledTimes(2);
    for (const d of ['down', 'left', 'right', 'up'] as const) for (let f = 0; f < 4; f++) {
      const body = art.body(d, f); expect([body.orig.width, body.orig.height]).toEqual([32, 48]); expect(body.source.scaleMode).toBe('nearest'); expect(body.source.autoGenerateMipmaps).toBe(false);
      expect(art.faceAnchor(d, f)).toEqual(d === 'up' ? null : { x: 10, y: 12 + f % 2 });
    }
    for (const e of ['calm', 'happy', 'curious', 'sleepy', 'focused'] as const) expect([art.face(e).width, art.face(e).height]).toEqual([12, 6]);
    for (const type of fixtureCatalog.types) expect(art.object(type, 16) === null).toBe(type.art_id === null);
    expect(new Set(Array.from({ length: 16 }, (_, i) => art.edge(i))).size).toBe(16);
    expect(new Set(Array.from({ length: 4 }, (_, i) => art.floor(i))).size).toBe(4);
    const clipped = art.structural('wall.north', { x: 0, y: 16, w: 16, h: 16 }); expect(clipped.width).toBe(16);
    for (const page of atlasPages) expect(page.url).not.toMatch(/art\/export|meta\.json|palette/);
    art.destroy(); art.destroy(); await art.closed(); expect(unload).toHaveBeenCalledTimes(2); expect(() => art.body('down', 0)).toThrow(/disposed/);
  });
  it('shares leases and unloads only after the last owner releases', async () => {
    const { load, unload } = resources(), a = await loadAtlasArt(), b = await loadAtlasArt();
    expect(a.body('down', 0)).toBe(b.body('down', 0)); expect(load).toHaveBeenCalledTimes(2);
    a.destroy(); await a.closed(); expect(unload).not.toHaveBeenCalled(); expect(b.body('down', 0).width).toBe(32);
    b.destroy(); await b.closed(); expect(unload).toHaveBeenCalledTimes(2);
  });
  it('unloads partial loads on failure and permits a clean retry', async () => {
    const { load, unload } = resources(); const texture = new Texture({ source: new CanvasSource({ resource: document.createElement('canvas') }) }); load.mockResolvedValueOnce(texture as unknown as Record<string, unknown>).mockRejectedValueOnce(new Error('Missing PNG'));
    await expect(loadAtlasArt()).rejects.toThrow('Missing PNG'); expect(unload).toHaveBeenCalledTimes(1);
    const art = await loadAtlasArt(); art.destroy(); await art.closed(); expect(unload).toHaveBeenCalledTimes(3);
  });
  it('cleans failed spritesheet parsing before retry', async () => {
    const { unload } = resources(); vi.spyOn(Spritesheet.prototype, 'parse').mockRejectedValueOnce(new Error('Parse failed'));
    await expect(loadAtlasArt()).rejects.toThrow('Parse failed'); expect(unload).toHaveBeenCalledTimes(1);
    const art = await loadAtlasArt(); art.destroy(); await art.closed(); expect(unload).toHaveBeenCalledTimes(3);
  });
  it('fails on missing required keys and geometry mismatch without an unrelated fallback', async () => {
    resources(); const art = await loadAtlasArt(); expect(() => art.structural('missing.asset')).toThrow(/Missing required/);
    const type = fixtureCatalog.types.find((t) => t.art_id !== null); if (!type) throw new Error('Missing type');
    expect(() => art.object({ ...type, geometry_version: 999 }, 16)).toThrow(/version mismatch/);
    art.destroy(); await art.closed();
  });
  it('preserves declared light/shadow centres in original canvas space after trimming', async () => {
    resources(); const art = await loadAtlasArt(), id = 'furniture.computer_desk';
    expect(art.partAnchor(id, 'base')).toEqual({ x: 0, y: 48 });
    expect(art.partAnchor(id, 'light')).toEqual({ x: 24, y: 24 });
    expect(art.partPosition(id, 'light', 100, 200)).toEqual({ x: 124, y: 176 });
    expect(art.partPosition(id, 'shadow', 100, 200)).toEqual({ x: 124, y: 176 });
    expect(art.partPosition(id, 'emissive', 100, 200)).toEqual({ x: 100, y: 200 });
    for (const name of ['light', 'shadow']) {
      const part = art.part(id, name), sprite = new Sprite(part.texture), position = art.partPosition(id, name, 100, 200); sprite.position.set(position.x - part.anchor.x, position.y - part.anchor.y);
      expect([sprite.x, sprite.y]).toEqual([100, 152]);
      expect([sprite.x + (part.texture.trim?.x ?? 0), sprite.y + (part.texture.trim?.y ?? 0)]).toEqual(name === 'light' ? [122, 155] : [101, 197]); sprite.destroy();
    }
    for (let i = 0; i < 4; i++) { art.body('down', i); expect(art.partPosition(id, 'light', 100, 200)).toEqual({ x: 124, y: 176 }); }
    art.destroy(); await art.closed();
  });
});
