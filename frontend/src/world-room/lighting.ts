// Presentation only: supplied backend geometry and phases; provisional, replaceable art settings.
import type { DayPhase, WorldCatalogOut, WorldOut } from "../api/world.generated";
export const DAY_PHASES: readonly DayPhase[] = ["night", "morning", "afternoon", "evening"];
export interface PhaseLighting {
  readonly tint: number;
  readonly artificialTint: number;
  readonly daylight: number;
  readonly lamp: number;
}
export type LightingPresets = Readonly<Record<DayPhase, PhaseLighting>>;
/** Provisional test colors/strengths, not owner-selected product defaults. */
export const PLACEHOLDER_LIGHTING: LightingPresets = {
  night: { tint: 0xdce4ff, artificialTint: 0xe4e0ee, daylight: 0, lamp: .3 },
  morning: { tint: 0xfff6e8, artificialTint: 0xf0ede8, daylight: .3, lamp: .08 },
  afternoon: { tint: 0xffffff, artificialTint: 0xf4f0ec, daylight: .4, lamp: 0 },
  evening: { tint: 0xffe4cc, artificialTint: 0xeee0d4, daylight: .1, lamp: .2 },
};
export function phaseLighting(phase: DayPhase, presets: LightingPresets = PLACEHOLDER_LIGHTING): PhaseLighting {
  const value = presets[phase];
  if (!value || ![value.tint, value.artificialTint].every((c) => Number.isInteger(c) && c >= 0 && c <= 0xffffff)
    || ![value.daylight, value.lamp].every((a) => Number.isFinite(a) && a >= 0 && a <= 1)) throw new Error("Invalid lighting preset");
  return value;
}
/** Reject malformed presentation input; backend remains the geometry authority. */
export function lightingZones(world: WorldOut) {
  const { width_tiles: w, height_tiles: h } = world.grid;
  if (![w, h].every((n) => Number.isInteger(n) && n > 0)) throw new Error("Invalid lighting grid");
  const cells = new Uint8Array(w * h), ids = new Set<string>();
  const zones = [...world.lighting_zones].sort((a, b) => a.bounds.y - b.bounds.y || a.bounds.x - b.bounds.x || a.region_id.localeCompare(b.region_id));
  for (const zone of zones) {
    const { x, y, w: zw, h: zh } = zone.bounds;
    if (ids.has(zone.region_id) || !world.regions.some((r) => r.id === zone.region_id) || ![x,y,zw,zh].every(Number.isInteger)
      || x < 0 || y < 0 || zw <= 0 || zh <= 0 || x + zw > w || y + zh > h) throw new Error("Invalid lighting zone");
    ids.add(zone.region_id);
    for (let ty = y; ty < y + zh; ty++) for (let tx = x; tx < x + zw; tx++) {
      const index = ty * w + tx;
      if (cells[index]) throw new Error("Overlapping lighting zones");
      cells[index] = 1;
    }
  }
  if (ids.size !== world.regions.length || cells.some((c) => c !== 1)) throw new Error("Incomplete lighting partition");
  return zones;
}
export interface LightHook { readonly sourceId: string; readonly regionId: string; readonly artId: string; readonly part: "light" | "emissive"; readonly kind: "daylight" | "lamp" | "screen" }
export function lightingHooks(world: WorldOut, catalog: WorldCatalogOut): readonly LightHook[] {
  return [...world.objects].sort((a,b) => a.id.localeCompare(b.id)).flatMap((o): LightHook[] => {
    const type = catalog.types.find((t) => t.id === o.type_id);
    if (!type) throw new Error(`Missing fixture catalog type: ${o.type_id}`);
    if (type.art_id === "window.north_2w") return [{ sourceId: o.id, regionId: o.room_id, artId: type.art_id, part: "light", kind: "daylight" }];
    if (type.art_id === "furniture.lamp_floor") return [{ sourceId: o.id, regionId: o.room_id, artId: type.art_id, part: "light", kind: "lamp" }];
    if (type.art_id === "furniture.computer_desk") return [{ sourceId: o.id, regionId: o.room_id, artId: type.art_id, part: "emissive", kind: "screen" }];
    return [];
  });
}
export function hookAlpha(hook: LightHook, phase: PhaseLighting): number { return hook.kind === "daylight" ? phase.daylight : hook.kind === "lamp" ? phase.lamp : 1; }
export function contrast(a: readonly number[], b: readonly number[]): number {
  const luminance = (rgb: readonly number[]) => rgb.reduce((sum, v, i) => {
    const s = v / 255; return sum + (s <= .04045 ? s / 12.92 : ((s + .055) / 1.055) ** 2.4) * ([.2126,.7152,.0722][i] ?? 0);
  },0);
  const x = luminance(a), y = luminance(b); return (Math.max(x,y)+.05)/(Math.min(x,y)+.05);
}
