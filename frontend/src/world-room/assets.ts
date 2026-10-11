// Programmer test art only; not the R1A-14 atlas pipeline or a production manifest.
import "pixi.js/unsafe-eval";
import { Assets, CanvasSource, Rectangle, Texture } from "pixi.js";
import type { CharacterDirection, Expression, WorldTypeOut } from "../api/world.generated";
import { TEXTURE_OPTIONS } from "./presentation";

export const MAPLE_ART = { width: 32, height: 48, anchor: { x: 16, y: 47 } } as const; // ADR-0041 L2/L3
export interface FaceSize { width: number; height: number }
export const PROVISIONAL_FACE: FaceSize = { width: 12, height: 6 }; // owner blind test still required
export interface ObjectArt {
  texture: Texture;
  anchor: { x: number; y: number };
  sortOffsetPx: number;
  aboveOccupant?: Texture;
}
export interface RoomArt {
  body(direction: CharacterDirection, frame: number, pose?: string): Texture;
  face(expression: Expression, direction?: CharacterDirection): Texture;
  faceAnchor(direction: CharacterDirection, frame: number, pose?: string): { x: number; y: number } | null;
  object(type: WorldTypeOut, tileSize: number): ObjectArt | null;
  floor(variant: number): Texture;
  edge(mask: number): Texture;
  destroy(): void;
}
let initialization: Promise<void> | undefined;
export function initializeAssets(): Promise<void> {
  initialization ??= Assets.init({ preferences: { preferWorkers: false } }).catch((error: unknown) => { initialization = undefined; throw error; });
  return initialization;
}
export function faceAnchor(direction: CharacterDirection, frame: number, size: FaceSize) {
  return direction === "up" ? null : { x: Math.floor((MAPLE_ART.width - size.width) / 2), y: 12 + (frame % 2) };
}

export function createPlaceholderArt(tileSize: number, size: FaceSize = PROVISIONAL_FACE): RoomArt {
  if (!Number.isInteger(size.width) || !Number.isInteger(size.height) || size.width <= 0 || size.height <= 0 || size.width > 22 || size.height > 12) throw new Error("Invalid provisional test face size");
  const textures = new Map<string, Texture>();
  const sources = new Set<CanvasSource>();
  let disposed = false;
  function texture(key: string, width: number, height: number, paint: (ctx: CanvasRenderingContext2D) => void): Texture {
    if (disposed) throw new Error("Test art has been disposed");
    const cached = textures.get(key);
    if (cached) return cached;
    const canvas = document.createElement("canvas"); canvas.width = width; canvas.height = height;
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("Canvas test art is unavailable");
    ctx.imageSmoothingEnabled = false; paint(ctx);
    const source = new CanvasSource({ resource: canvas, ...TEXTURE_OPTIONS });
    sources.add(source);
    const result = new Texture({ source }); textures.set(key, result); return result;
  }
  return {
    body(direction, frame) {
      return texture(`body/${direction}/${frame}`, 32, 48, (ctx) => {
        const bob = frame % 2;
        ctx.fillStyle = "#593c32"; ctx.fillRect(7, 3 + bob, 18, 18);
        ctx.fillStyle = "#ebc49b"; ctx.fillRect(9, 10 + bob, 14, 12);
        ctx.fillStyle = "#729482"; ctx.fillRect(7, 23 + bob, 18, 15);
        ctx.fillStyle = "#493a38"; ctx.fillRect(9 + (frame === 1 ? 2 : 0), 38, 5, 9); ctx.fillRect(18 - (frame === 3 ? 2 : 0), 38, 5, 9);
        if (direction === "left" || direction === "right") { ctx.fillStyle = "#593c32"; ctx.fillRect(direction === "left" ? 19 : 7, 10 + bob, 6, 12); }
      });
    },
    face(expression) {
      return texture(`face/${expression}`, size.width, size.height, (ctx) => {
        ctx.fillStyle = "#302f36";
        const eyeY = expression === "sleepy" ? 2 : 1;
        ctx.fillRect(2, eyeY, 2, expression === "curious" ? 3 : 1);
        ctx.fillRect(size.width - 4, eyeY, 2, expression === "focused" ? 2 : 1);
        ctx.fillRect(Math.floor(size.width / 2) - 1, size.height - 2, expression === "happy" ? 3 : 2, 1);
      });
    },
    faceAnchor(direction, frame) { return faceAnchor(direction, frame, size); },
    object(type, t) {
      if (type.art_id === null) return null; // structural markers have no artwork
      const window = type.art_id.startsWith("window.");
      const flat = type.blocks.every((row) => !row.includes("#")) && type.surface === "floor";
      const width = type.footprint.w * t;
      const height = window ? 2 * t : type.surface === "north_band" ? t : type.footprint.h * t + (flat ? 0 : t);
      const image = texture(`object/${type.id}/${t}`, width, height, (ctx) => {
        ctx.fillStyle = flat ? "#a9b3a5" : "#8b715b"; if (!window) ctx.fillRect(0, 1, width, height - 1);
        ctx.strokeStyle = "#463e38"; ctx.lineWidth = 1; ctx.strokeRect(0.5, 1.5, width - 1, height - 2);
        ctx.fillStyle = window ? "#c4cbb8" : "#d6b385"; ctx.fillRect(2, 3, Math.max(1, width - 4), window ? 2 : 4);
        if (window) { ctx.fillRect(Math.floor(width / 2), 1, 1, height - 1); }
      });
      return { texture: image, anchor: { x: 0, y: height }, sortOffsetPx: 0 };
    },
    floor(variant) {
      return texture(`floor/${variant}`, tileSize, tileSize, (ctx) => {
        ctx.fillStyle = ["#b9af91", "#b7ad8e", "#bcb294", "#b8ae90"][variant] ?? "#b9af91";
        ctx.fillRect(0, 0, tileSize, tileSize); ctx.fillStyle = "#a39a80"; ctx.fillRect(0, tileSize - 1, tileSize, 1);
      });
    },
    edge(mask) {
      const key = `edge/${mask}`;
      const cached = textures.get(key); if (cached) return cached;
      const atlas = texture("edge-atlas", tileSize * 4, tileSize * 4, (ctx) => {
        ctx.fillStyle = "#897e68";
        for (let index = 0; index < 16; index++) {
          const x = (index % 4) * tileSize, y = Math.floor(index / 4) * tileSize;
          if (index & 1) ctx.fillRect(x, y, tileSize, 1);
          if (index & 2) ctx.fillRect(x + tileSize - 1, y, 1, tileSize);
          if (index & 4) ctx.fillRect(x, y + tileSize - 1, tileSize, 1);
          if (index & 8) ctx.fillRect(x, y, 1, tileSize);
        }
      });
      const part = new Texture({ source: atlas.source, frame: new Rectangle((mask % 4) * tileSize, Math.floor(mask / 4) * tileSize, tileSize, tileSize) });
      textures.set(key, part); return part;
    },
    destroy() { if (disposed) return; disposed = true; for (const value of textures.values()) value.destroy(false); for (const source of sources) source.destroy(); textures.clear(); sources.clear(); },
  };
}
