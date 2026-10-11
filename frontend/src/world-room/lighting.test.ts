import { describe, expect, it } from "vitest";
import { fixtureWorlds, fixtureCatalog } from "./fixtures";
import { DAY_PHASES, PLACEHOLDER_LIGHTING, phaseLighting, lightingZones, lightingHooks, hookAlpha, contrast } from "./lighting";
import type { WorldOut } from "../api/world.generated";
const world = fixtureWorlds.idle;
describe("backend-owned lighting partition", () => {
  it("covers all1144 cells once with exact supplied identities and deterministic order", () => {
    const zones = lightingZones(world), cells = new Map<string,number>();
    expect(zones).toHaveLength(8);
    for (const z of zones) for(let y=z.bounds.y;y<z.bounds.y+z.bounds.h;y++) for(let x=z.bounds.x;x<z.bounds.x+z.bounds.w;x++){ const key=`${x},${y}`;cells.set(key,(cells.get(key)??0)+1); }
    expect(cells.size).toBe(1144);expect([...cells.values()].every(c=>c===1)).toBe(true);
    expect(lightingZones({...world,lighting_zones:[...world.lighting_zones].reverse()})).toEqual(zones);
    expect(zones.map(z=>z.region_id)).toEqual(["bedroom","living_room","library","work_studio","central_hall","future_space","creation_room","system_room"]);
    expect(zones.map(z=>z.bounds)).toEqual([{x:0,y:0,w:10,h:10},{x:10,y:0,w:11,h:10},{x:21,y:0,w:11,h:10},{x:32,y:0,w:12,h:10},{x:0,y:10,w:44,h:7},{x:0,y:17,w:15,h:9},{x:15,y:17,w:15,h:9},{x:30,y:17,w:14,h:9}]);
  });
  it.each(["gap","overlap","overlap-plus-gap","outside","fractional","duplicate","identity","grid"])("rejects malformed supplied partition: %s", kind=>{
    const data=structuredClone(world) as unknown as {lighting_zones:{region_id:string;bounds:{x:number;y:number;w:number;h:number}}[];grid:{width_tiles:number}};
    const a=data.lighting_zones[0];if(!a)throw Error("Missing zone");
    if(kind==="gap")a.bounds.w--;
    if(kind==="overlap")a.bounds.w++;
    if(kind==="overlap-plus-gap"){a.bounds.w++;a.bounds.h--;}
    if(kind==="outside")a.bounds.x=-1;
    if(kind==="fractional")a.bounds.x=.5;
    if(kind==="duplicate")data.lighting_zones.push(a);
    if(kind==="identity")a.region_id="unknown";
    if(kind==="grid")data.grid.width_tiles=0;
    expect(()=>lightingZones(data as unknown as WorldOut)).toThrow();
  });
});
describe("typed provisional phase settings",()=>{
  it.each(DAY_PHASES)("%s is deterministic and replaceable",phase=>{
    expect(phaseLighting(phase)).toEqual(PLACEHOLDER_LIGHTING[phase]);
    const custom={...PLACEHOLDER_LIGHTING,[phase]:{tint:0x123456,artificialTint:0xffffff,daylight:.5,lamp:.75}};
    expect(phaseLighting(phase,custom)).toEqual(custom[phase]);
    expect(phaseLighting(phase,custom)).toEqual(phaseLighting(phase,custom));
  });
  it.each([-1,0x1000000,NaN,Infinity,.5])("rejects invalid color %s",tint=>expect(()=>phaseLighting("night",{...PLACEHOLDER_LIGHTING,night:{...PLACEHOLDER_LIGHTING.night,tint}})).toThrow());
  it.each([-1,2,NaN,Infinity])("rejects invalid alpha %s",lamp=>expect(()=>phaseLighting("night",{...PLACEHOLDER_LIGHTING,night:{...PLACEHOLDER_LIGHTING.night,lamp}})).toThrow());
});
describe("source-linked atlas emitter hooks",()=>{
  it("has four windows, two lamps and one screen, with no placeholder daylight or mutations",()=>{
    const before=JSON.stringify(world),hooks=lightingHooks(world,fixtureCatalog);
    expect(hooks.filter(h=>h.kind==="daylight").map(h=>h.sourceId)).toEqual(["window.bedroom","window.library","window.living","window.studio"]);
    expect(hooks.filter(h=>h.kind==="lamp").map(h=>h.sourceId)).toEqual(["lamp.library","lamp.living"]);
    expect(hooks.filter(h=>h.kind==="screen").map(h=>h.sourceId)).toEqual(["desk.computer"]);
    expect(hooks.some(h=>["future_space","creation_room","system_room"].includes(h.regionId))).toBe(false);
    expect(lightingHooks({...world,objects:[...world.objects].reverse()},fixtureCatalog)).toEqual(hooks);
    expect(JSON.stringify(world)).toBe(before);
    expect(()=>lightingHooks(world,{...fixtureCatalog,types:[]})).toThrow();
  });
  it.each(DAY_PHASES)("%s phase drives daylight/lamp but leaves screen exact",phase=>{
    const p=phaseLighting(phase),hooks=lightingHooks(world,fixtureCatalog);
    for(const h of hooks)expect(hookAlpha(h,p)).toBe(h.kind==="daylight"?p.daylight:h.kind==="lamp"?p.lamp:1);
    if(phase==="night")expect(p.daylight).toBe(0);
  });
  it("uses reproducible sRGB relative luminance contrast",()=>{expect(contrast([0,0,0],[255,255,255])).toBeCloseTo(21);expect(contrast([128,128,128],[128,128,128])).toBe(1);});
});

describe('approved provisional-art contrast regression', () => {
  const tint = (rgb: readonly number[], color: number) => rgb.map((v, i) => Math.round(v * ((color >> (16 - i * 8)) & 255) / 255));
  it.each(DAY_PHASES)('%s keeps required body/background pairs above 1.5 in both preset families', phase => {
    const preset = phaseLighting(phase);
    for (const color of [preset.tint, preset.artificialTint]) {
      for (const [body, background] of [
        [[0,0,0], [185,175,145]], // hair / floor
        [[139,113,91], [185,175,145]], // skin / floor
        [[73,62,56], [139,113,91]], // shirt and pants / furniture
        [[0,0,0], [73,62,56]], // hair / north band during doorway crossings
        [[73,62,56], [139,113,91]], // face ink / corrected skin
      ] as const) expect(contrast(tint(body, color), tint(background, color))).toBeGreaterThanOrEqual(1.5);
    }
  });
});
