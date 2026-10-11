// Generated metadata is bundled; only Vite PNG URLs are loaded, never raw source art.
import 'pixi.js/unsafe-eval';
import { Assets, Spritesheet, Texture, Rectangle } from 'pixi.js';
import type { CharacterDirection, Expression, WorldTypeOut } from '../api/world.generated';
import { atlasPages, artManifest } from './generated';
import { initializeAssets, type RoomArt } from './assets';
import { TEXTURE_OPTIONS } from './presentation';
interface Part { part: string; anchor: number[]; sort?: string; sort_offset_px?: number }
interface Asset { geometry_version: number; parts: Part[]; animations: Record<string, { face_anchor?: (number[] | null)[][] }> }
const manifest = artManifest as unknown as Record<string, Asset>;
let sheets: Spritesheet[] = [], users = 0;
let serial: Promise<unknown> = Promise.resolve();
function enqueue<T>(work: () => Promise<T>): Promise<T> { const next = serial.then(work); serial = next.catch(() => undefined); return next; }
async function acquire(): Promise<Spritesheet[]> {
  await initializeAssets();
  return enqueue(async () => {
    if (users) { users++; return sheets; }
    const made: Spritesheet[] = [], loaded: string[] = [];
    try {
      for (const page of atlasPages) {
        const texture = await Assets.load<Texture>(page.url); loaded.push(page.url); Object.assign(texture.source, TEXTURE_OPTIONS);
        const sheet = new Spritesheet(texture.source, page.data); made.push(sheet); await sheet.parse();
      }
      sheets = made; users = 1; return sheets;
    } catch (error) { for (const sheet of made) sheet.destroy(false); await Promise.all(loaded.map((url) => Assets.unload(url))); throw error; }
  });
}
function release(): Promise<void> { return enqueue(async () => { if (--users !== 0) return; for (const sheet of sheets) sheet.destroy(false); sheets = []; await Promise.all(atlasPages.map((page) => Assets.unload(page.url))); }); }
export interface Clip { x: number; y: number; w: number; h: number }
export interface AtlasArt extends RoomArt {
  structural(id: string, clip?: Clip): Texture;
  partAnchor(id: string, part: string): { x: number; y: number };
  partPosition(id: string, part: string, canonicalX: number, canonicalY: number): { x: number; y: number };
  part(id: string, name: string): { texture: Texture; anchor: { x: number; y: number } };
  closed(): Promise<void>;
}
export async function loadAtlasArt(): Promise<AtlasArt> {
  const acquired = await acquire(), clipped = new Map<string, Texture>(); let disposed = false, closing = Promise.resolve();
  function get(key: string): Texture { if (disposed) throw new Error('Atlas lease disposed'); for (const sheet of acquired) { const texture = sheet.textures[key]; if (texture) return texture; } throw new Error(`Missing required atlas frame: ${key}`); }
  function asset(id: string): Asset { const found = manifest[id]; if (!found) throw new Error(`Missing required manifest asset: ${id}`); return found; }
  function partAnchor(id: string, name: string) { const p = asset(id).parts.find((p) => p.part === name); if (!p || p.anchor[0] === undefined || p.anchor[1] === undefined) throw new Error(`Missing part anchor: ${id}/${name}`); return { x: p.anchor[0], y: p.anchor[1] }; }
  return {
    body(direction, frame, pose = 'walk') { return get(`char.maple/${pose}/${direction}/base/${frame}`); },
    face(expression: Expression, direction: CharacterDirection = 'down') { return get(`char.faces/face_${expression}/${direction === 'up' ? 'down' : direction}/base/0`); },
    faceAnchor(direction, frame, pose = 'walk') { const row = ['down', 'left', 'right', 'up'].indexOf(direction), value = asset('char.maple').animations[pose]?.face_anchor?.[row]?.[frame]; if (value === null) return null; if (!value || value[0] === undefined || value[1] === undefined) throw new Error(`Missing face anchor: ${pose}/${direction}/${frame}`); return { x: value[0], y: value[1] }; },
    object(type: WorldTypeOut) { if (type.art_id === null) return null; const m = asset(type.art_id); if (m.geometry_version !== type.geometry_version) throw new Error(`Asset geometry version mismatch: ${type.id}`); const base = m.parts.find((p) => p.part === 'base'), cover = m.parts.find((p) => p.sort === 'above_occupant'); return { texture: get(`${type.art_id}/default/south/base/0`), anchor: partAnchor(type.art_id, 'base'), sortOffsetPx: base?.sort_offset_px ?? 0, ...(cover ? { aboveOccupant: get(`${type.art_id}/default/south/${cover.part}/0`) } : {}) }; },
    floor(variant) { return get(`tile.floor_wood/default/0/base/${variant}`); },
    edge(mask) { return get(`tile.floor_edge/default/${Math.floor(mask / 4)}/base/${mask % 4}`); },
    structural(id, clip) {
      const texture = get(`${id}/default/south/base/0`); if (!clip) return texture;
      const key = `${id}/${clip.x}/${clip.y}/${clip.w}/${clip.h}`, prior = clipped.get(key); if (prior) return prior;
      if (texture.trim || clip.x < 0 || clip.y < 0 || clip.w <= 0 || clip.h <= 0 || clip.x + clip.w > texture.orig.width || clip.y + clip.h > texture.orig.height) throw new Error('Invalid structural atlas clip');
      const result = new Texture({ source: texture.source, frame: new Rectangle(texture.frame.x + clip.x, texture.frame.y + clip.y, clip.w, clip.h) }); clipped.set(key, result); return result;
    },
    partAnchor,
    part(id, name) { return { texture: get(`${id}/default/south/${name}/0`), anchor: partAnchor(id, name) }; },
    partPosition(id, part, canonicalX, canonicalY) { const canonical = partAnchor(id, 'base'), own = partAnchor(id, part); return { x: canonicalX - canonical.x + own.x, y: canonicalY - canonical.y + own.y }; },
    destroy() { if (disposed) return; disposed = true; for (const texture of clipped.values()) texture.destroy(false); clipped.clear(); closing = release(); void closing.catch(() => undefined); },
    closed() { return closing; },
  };
}
