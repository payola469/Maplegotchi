// Original neutral programmer art. Explicit authoring command; never run by build/validator.
import { mkdirSync, writeFileSync, readFileSync, existsSync } from 'node:fs';
import { resolve, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { encodePNG } from './png.mjs';
import { json } from './pack.mjs';
const root = resolve(fileURLToPath(new URL('../../../', import.meta.url)));
if (existsSync(join(root, 'art/export'))) throw new Error('Refusing to overwrite existing source art');
const palette = ['#493e38', '#8b715b', '#d6b385', '#729482', '#ebc49b', '#b9af91', '#897e68', '#688f98', '#000000', '#c4cbb8'];
mkdirSync(join(root, 'art/palette'), { recursive: true }); writeFileSync(join(root, 'art/palette/maple-master.hex'), palette.join('\n') + '\n');
function image(width, height, draw) {
  const pixels = Buffer.alloc(width * height * 4);
  const rect = (x, y, w, h, color, alpha = 255) => { const c = palette[color].slice(1).match(/../g).map((s) => parseInt(s, 16)); for (let yy = y; yy < y + h; yy++) for (let xx = x; xx < x + w; xx++) if (xx >= 0 && yy >= 0 && xx < width && yy < height) pixels.set([...c, alpha], (yy * width + xx) * 4); };
  draw(rect); return encodePNG({ width, height, pixels });
}
function deliver(meta, files) {
  const dir = join(root, 'art/export', meta.id.split('.')[0], meta.id); mkdirSync(dir, { recursive: true });
  writeFileSync(join(dir, meta.id + '.meta.json'), json(meta)); for (const [name, data] of Object.entries(files)) writeFileSync(join(dir, name), data);
}
function common(id, kind, canvas, anchor, pack = 'shared') { return { id, kind, canvas, art_revision: 1, geometry_version: 1, pack, orientations: ['south'], states: ['default'], fallback: id, parts: [{ part: 'base', anchor }] }; }
const catalog = JSON.parse(readFileSync(join(root, 'backend/src/maplegotchi/world_catalog/initial_catalog.json'), 'utf8'));
for (const t of catalog.types) {
  if (!t.art_id) continue;
  const window = t.id.startsWith('window.'), wall = t.surface === 'north_band';
  const w = t.footprint[0] * 16, h = window ? 32 : wall ? 16 : t.footprint[1] * 16 + (t.id.includes('rug') ? 0 : 16);
  const m = { ...common(t.art_id, wall ? 'wall_object' : 'floor_object', [w, h], [0, h]), footprint: { w: t.footprint[0], h: t.footprint[1] }, blocks: t.blocks, orientations: t.orientations, states: t.states, catalog_points: t.points, catalog_slots: t.slots, mount_y_px: t.mount_y_px, hit: [[0, 1], [w, 1], [w, h], [0, h]] };
  if (window) m.role = 'structural';
  if (/bed_single|writing_desk|computer_desk|sofa|armchair/.test(t.id)) m.parts.push({ part: 'cover', anchor: [0, h], sort: 'above_occupant' });
  if (/window|computer_desk|lamp_floor/.test(t.id)) {
    m.parts.push({ part: 'emissive', anchor: [0, h], layer: 'emissive' });
    m.parts.push({ part: 'light', anchor: [Math.floor(w / 2), Math.floor(h / 2)], anchor_role: 'light_source_center', layer: 'light' });
  }
  m.parts.push({ part: 'shadow', anchor: [Math.floor(w / 2), Math.floor(h / 2)], anchor_role: 'floor_center', layer: 'shadow' });
  const files = {};
  for (const p of m.parts) files[`${m.id}--default--south${p.part === 'base' ? '' : '--' + p.part}.png`] = image(w, h, (r) => {
    if (p.part === 'base') {
      if (window) { r(0, 0, 2, h, 0); r(w - 2, 0, 2, h, 0); r(0, 0, w, 2, 0); r(0, h - 2, w, 2, 0); r(w / 2, 0, 1, h, 0); }
      else { r(0, 1, w, h - 1, 1); r(2, 3, w - 4, 4, 2); r(0, h - 1, w, 1, 0); }
    } else if (p.part === 'cover') r(1, h - 5, w - 2, 4, 1);
    else if (p.part === 'emissive') r(3, 4, Math.max(1, w - 6), 1, 9);
    else if (p.part === 'light') r(Math.floor(w / 2) - 2, 3, 4, 2, 2, 128);
    else r(1, h - 3, w - 2, 2, 8, 128);
  });
  deliver(m, files);
}
const directions = ['down', 'left', 'right', 'up'];
const poses = [...new Set(['idle', 'walk', 'sit_idle', 'react_greet', 'react_pet', ...catalog.types.flatMap((t) => t.points.map((p) => p.pose).filter(Boolean))])];
const body = { ...common('char.maple', 'character', [32, 48], [16, 47], 'character'), orientations: directions, animations: {} }, bodyFiles = {};
for (const pose of poses) {
  const frames = ['idle', 'walk'].includes(pose) ? 4 : 2;
  body.animations[pose] = { file: `char.maple--${pose}.png`, rows: directions, frames, ms: Array(frames).fill(pose === 'walk' ? 125 : 400), loop: pose.startsWith('react_') ? 'once' : 'loop', face_anchor: directions.map((d) => Array.from({ length: frames }, (_, f) => d === 'up' ? null : [10, 12 + f % 2])) };
  bodyFiles[`char.maple--${pose}.png`] = image(32 * frames, 48 * 4, (r) => {
    for (let row = 0; row < 4; row++) for (let f = 0; f < frames; f++) { const x = f * 32, y = row * 48, bob = f % 2; r(x + 7, y + 3 + bob, 18, 18, 0); r(x + 9, y + 10 + bob, 14, 12, 4); r(x + 7, y + 23 + bob, 18, 15, 3); r(x + 9 + (f === 1 ? 2 : 0), y + 38, 5, 9, 0); r(x + 18 - (f === 3 ? 2 : 0), y + 38, 5, 9, 0); if (row === 1 || row === 2) r(x + (row === 1 ? 19 : 7), y + 10 + bob, 6, 12, 0); }
  });
}
deliver(body, bodyFiles);
const faces = { ...common('char.faces', 'character', [12, 6], [0, 0], 'character'), role: 'face_overlay', orientations: directions.slice(0, 3), animations: {} }, faceFiles = {};
for (const [index, expression] of ['calm', 'happy', 'curious', 'sleepy', 'focused'].entries()) {
  const key = `face_${expression}`; faces.animations[key] = { file: `char.faces--${key}.png`, rows: directions.slice(0, 3), frames: 1, ms: [400], loop: 'loop' };
  faceFiles[`char.faces--${key}.png`] = image(12, 18, (r) => { for (let row = 0; row < 3; row++) { r(1, row * 6 + 1, 4, expression === 'curious' ? 2 : 1, 0); r(7, row * 6 + 1, 4, expression === 'focused' ? 2 : 1, 0); r(5, row * 6 + 4, 2 + index % 2, 1, 0); } });
}
deliver(faces, faceFiles);
for (const edge of [false, true]) {
  const id = edge ? 'tile.floor_edge' : 'tile.floor_wood', m = { ...common(id, 'tile', [16, 16], [0, 0]), tiles: { columns: 4, rows: edge ? 4 : 1 } };
  deliver(m, { [`${id}--sheet.png`]: image(64, edge ? 64 : 16, (r) => { for (let i = 0; i < (edge ? 16 : 4); i++) { const x = i % 4 * 16, y = Math.floor(i / 4) * 16; if (edge) { if (i & 1) r(x, y, 16, 1, 6); if (i & 2) r(x + 15, y, 1, 16, 6); if (i & 4) r(x, y + 15, 16, 1, 6); if (i & 8) r(x, y, 1, 16, 6); } else { r(x, y, 16, 16, 5); r(x + i + 2, y + 5, 1, 1, 6); } } }) });
}
for (const [id, canvas] of [['wall.north', [16, 48]], ['wall.cap', [16, 16]], ['wall.side', [16, 16]], ['wall.south', [16, 16]], ['door.north_2w', [32, 48]], ['door.closed', [32, 48]], ['backdrop.window', [32, 32]]]) {
  const m = { ...common(id, id.startsWith('backdrop') ? 'backdrop' : 'tile', canvas, [0, 0]), role: 'structural' };
  deliver(m, { [`${id}--default--south.png`]: image(...canvas, (r) => { const [w, h] = canvas; if (id === 'door.north_2w') { r(0, 0, 1, h, 0); r(w - 1, 0, 1, h, 0); } else if (id === 'door.closed') r(2, h - 3, w - 4, 2, 9); else r(0, 0, w, id === 'wall.cap' ? 8 : id === 'wall.side' ? 3 : id === 'wall.south' ? 2 : h, id === 'backdrop.window' ? 7 : 0); }) });
}
