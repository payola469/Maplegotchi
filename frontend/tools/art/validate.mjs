import { readFileSync, readdirSync, lstatSync } from 'node:fs';
import { join, relative, basename, resolve } from 'node:path';
import { execFileSync } from 'node:child_process';
import { decodePNG, crop } from './png.mjs';
import { canonical } from './pack.mjs';
const dirs = ['down', 'left', 'right', 'up'], orientations = ['south', 'east', 'west', 'north'];
const idPattern = /^[a-z][a-z0-9_]*\.[a-z0-9_]+(?:\.[a-z0-9_]+)?$/;
export function demand(ok, rule, asset, message) { if (!ok) throw new Error(`${rule} ${asset}: ${message}`); }
const integer = (n) => Number.isSafeInteger(n);
const equal = (a, b) => JSON.stringify(canonical(a)) === JSON.stringify(canonical(b));
export function validateAnchor(anchor, canvas, asset) {
  demand(Array.isArray(anchor) && anchor.length === 2 && anchor.every(integer) && anchor.every((n, i) => n >= 0 && n <= canvas[i]), 'E8', asset, 'anchor must be an integer pixel corner within inclusive canvas bounds');
}
export function validateDisplayAnchors(meta) {
  for (const [slot, anchor] of Object.entries(meta.display_anchors ?? {})) {
    demand(meta.catalog_slots?.some((s) => s.id === slot), 'S17', meta.id, 'display anchor references missing host slot');
    validateAnchor(anchor, meta.canvas, meta.id + '/' + slot);
  }
}
export function validateParts(meta) {
  const asset = meta.id, canvas = meta.canvas;
  demand(Array.isArray(meta.parts) && meta.parts.length && new Set(meta.parts.map((p) => p.part)).size === meta.parts.length, 'E1', asset, 'unique parts required');
  const base = meta.parts.find((p) => p.part === 'base'); demand(base, 'E8', asset, 'canonical base part required');
  for (const part of meta.parts) {
    demand(/^[a-z][a-z0-9_]*$/.test(part.part), 'E1', asset, 'invalid part name');
    validateAnchor(part.anchor, canvas, asset);
    const independent = part.part === 'light' || part.part === 'shadow';
    if (independent) demand(part.layer === part.part, 'E8', asset, 'centre exception requires the actual light/shadow layer');
    if (independent) demand(part.anchor_role === (part.part === 'light' ? 'light_source_center' : 'floor_center'), 'E8', asset, 'light/shadow centre anchor must be explicitly declared');
    else demand(equal(part.anchor, base.anchor) && !part.anchor_role, 'E8', asset, 'attached base/occupant/emissive/ordinary parts must share canonical anchor');
    for (const anchor of part.frame_anchors ?? []) demand(equal(anchor, part.anchor), 'E8', asset, 'anchor changes across frames');
    for (const anchor of Object.values(part.state_anchors ?? {})) demand(equal(anchor, part.anchor), 'E8', asset, 'anchor changes across states');
  }
  if (meta.kind === 'floor_object' || meta.kind === 'wall_object') demand(equal(base.anchor, [0, canvas[1]]), 'E8', asset, 'canonical SW/bottom-left anchor');
  if (meta.kind === 'slot_item') demand(equal(base.anchor, [canvas[0] / 2, canvas[1]]), 'E8', asset, 'slot-item bottom-centre anchor');
  if (meta.kind === 'character' && meta.role !== 'face_overlay') demand(equal(base.anchor, [16, 47]), 'E8', asset, 'Maple feet anchor');
}
function pixelsCheck(image, meta, part, palette) {
  const asset = meta.id, alphas = new Set(), visibleX = new Set();
  const soft = ['shadow', 'light', 'glass', 'fx'].includes(part.layer) || ['shadow', 'light', 'fx'].includes(meta.kind);
  for (let y = 0; y < image.height; y++) for (let x = 0; x < image.width; x++) {
    const i = (y * image.width + x) * 4, [r, g, b, a] = image.pixels.subarray(i, i + 4);
    demand(a !== 0 || !(r || g || b), 'E3', asset, 'transparent RGB must be zero');
    demand(soft || a === 0 || a === 255, 'E4', asset, 'binary alpha required'); alphas.add(a);
    if (!a) continue;
    if (meta.kind !== 'shadow') demand(palette.has(`${r},${g},${b}`), 'E5', asset, 'colour outside master palette');
    const full = ['character', 'slot_item', 'fx'].includes(meta.kind) && meta.role !== 'face_overlay';
    const top = ['floor_object', 'wall_object'].includes(meta.kind) && meta.role !== 'structural';
    demand(!(full && (x === 0 || y === 0 || x === image.width - 1 || y === image.height - 1)) && !(top && y === 0), 'E7', asset, 'transparent border C3');
    if (meta.kind === 'character' && meta.role !== 'face_overlay') { demand(x >= 2 && x <= 29 && y >= 1 && y <= 46, 'E7', asset, 'Maple safe area'); visibleX.add(x); }
  }
  demand(!soft || alphas.size <= 8, 'E4', asset, 'at most eight alpha levels');
  demand(!visibleX.size || Math.max(...visibleX) - Math.min(...visibleX) + 1 <= 22, 'E7', asset, 'Maple visible width exceeds 22');
}
export function repositoryAttributes(root, files) {
  const paths = ['art/export', 'art/palette', ...files];
  let top;
  try { top = execFileSync('git', ['-C', root, 'rev-parse', '--show-toplevel'], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim(); } catch { /* Clean archive: no repository metadata. */ }
  if (top && resolve(top) === resolve(root)) {
    const attrs = execFileSync('git', ['-C', root, 'check-attr', '-z', 'filter', 'export-ignore', '--', ...paths], { encoding: 'utf8' }).split('\0');
    for (let i = 0; i + 2 < attrs.length; i += 3) demand(!(attrs[i + 1] === 'filter' && attrs[i + 2] === 'lfs') && !(attrs[i + 1] === 'export-ignore' && ['set', 'true'].includes(attrs[i + 2])), 'E24/C1', attrs[i], 'forbidden effective Git attribute');
  } else {
    // Release archives include the repository attributes; fail closed on forbidden declarations.
    const attributes = readFileSync(join(root, '.gitattributes'), 'utf8');
    demand(!attributes.split('\n').filter((l) => !l.trim().startsWith('#')).some((l) => /\bfilter=lfs\b|(?:^|\s)export-ignore(?:\s|$)/.test(l)), 'E24/C1', '.gitattributes', 'forbidden archive attribute');
  }
}
export function readInputs(root) {
  const files = [];
  function walk(dir) { for (const name of readdirSync(dir).sort()) { const path = join(dir, name), stat = lstatSync(path); demand(!stat.isSymbolicLink(), 'E24', path, 'symlinks forbidden'); if (stat.isDirectory()) walk(path); else { demand(stat.isFile(), 'E24', path, 'regular source file required'); files.push(path); } } }
  walk(join(root, 'art/export'));
  for (const file of files) demand(file.endsWith('.png') || file.endsWith('.meta.json'), 'E24', relative(root, file), 'only PNG and metadata permitted');
  const paletteFile = join(root, 'art/palette/maple-master.hex');
  const paletteStat = lstatSync(paletteFile);
  demand(!paletteStat.isSymbolicLink() && paletteStat.isFile(), 'E24', 'palette', 'regular file required; symlinks forbidden');
  repositoryAttributes(root, [...files, paletteFile].map((p) => relative(root, p).split('\\').join('/')));
  const palette = new Set(readFileSync(paletteFile, 'utf8').trim().split(/\s+/).map((h) => { demand(/^#[0-9a-f]{6}$/.test(h), 'E5', 'palette', 'expected lowercase RGB hex'); return [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16)).join(','); }));
  const metas = files.filter((f) => f.endsWith('.meta.json')).map((f) => { let m; try { m = JSON.parse(readFileSync(f, 'utf8')); } catch { throw new Error(`E1 ${f}: invalid JSON metadata`); } return { meta: m, file: f }; });
  const ids = new Set(); for (const { meta, file } of metas) { demand(idPattern.test(meta.id) && !ids.has(meta.id) && basename(file) === `${meta.id}.meta.json`, 'E1', file, 'invalid/duplicate ID or sidecar filename'); ids.add(meta.id); }
  const overlayCanvas = metas.find(({ meta }) => meta.id === 'char.faces')?.meta.canvas;
  demand(Array.isArray(overlayCanvas) && overlayCanvas.length === 2, 'E25', 'char.faces', 'face overlay canvas required');
  const frames = [], used = new Set();
  for (const { meta: m, file } of metas) {
    const asset = m.id, baseDir = file.slice(0, -`${m.id}.meta.json`.length);
    demand(Array.isArray(m.canvas) && m.canvas.length === 2 && m.canvas.every((n) => integer(n) && n > 0 && n <= 512), 'E18', asset, 'frame dimensions 1..512');
    demand(m.role === 'face_overlay' || m.canvas.every((n) => n % 8 === 0), 'E6', asset, 'canvas dimensions must be multiples of eight');
    demand(['floor_object', 'wall_object', 'slot_item', 'tile', 'character', 'fx', 'light', 'shadow', 'backdrop'].includes(m.kind), 'E1', asset, 'invalid kind');
    demand(integer(m.geometry_version) && m.geometry_version > 0 && integer(m.art_revision) && m.art_revision > 0, 'S17', asset, 'positive versions');
    demand(typeof m.pack === 'string' && /^[a-z][a-z0-9_]*$/.test(m.pack) && ids.has(m.fallback), 'E20', asset, 'pack and existing explicit fallback required');
    demand(m.role === undefined || m.role === 'face_overlay' && m.id === 'char.faces' && m.kind === 'character' || m.role === 'structural' && /^(?:wall|door|window|backdrop)\./.test(m.id) && ['tile', 'wall_object', 'backdrop'].includes(m.kind), 'E7', asset, 'border exemption requires the actual independent asset kind');
    validateParts(m); validateDisplayAnchors(m);
    const lockedCanvas = { 'char.maple': [32, 48], 'wall.north': [16, 48], 'door.north_2w': [32, 48], 'window.north_2w': [32, 32] }[asset];
    if (lockedCanvas) demand(equal(m.canvas, lockedCanvas), 'E6/L2/L7/L9/L10', asset, 'locked canvas dimensions');
    if (asset === 'window.north_2w') demand(m.mount_y_px === 8, 'S17/L10', asset, 'locked window mount');
    if (m.footprint) demand(integer(m.footprint.w) && integer(m.footprint.h) && m.footprint.w > 0 && m.footprint.h > 0 && Array.isArray(m.blocks) && m.blocks.length === m.footprint.h && m.blocks.every((r) => r.length === m.footprint.w && /^[#.]+$/.test(r)), 'E10', asset, 'blocking mask dimensions/characters');
    const available = m.kind === 'character' ? dirs : orientations;
    demand(Array.isArray(m.orientations) && m.orientations.length > 0 && equal(m.orientations, available.filter((d) => m.orientations.includes(d))), 'E12', asset, 'canonical unique direction/orientation order');
    for (const [target, source] of Object.entries(m.mirror ?? {})) demand(m.orientations.includes(target) && m.orientations.includes(source) && target !== source, 'E12', asset, 'explicit mirror references invalid');
    demand(Array.isArray(m.states) && m.states.includes(m.base_state ?? 'default') && new Set(m.states).size === m.states.length && m.states.every((s) => /^[a-z][a-z0-9_]*$/.test(s)), 'E13', asset, 'base state/unique valid states');
    const add = (filename, columns, rows, labels, state, part, animation) => {
      demand(filename === filename.toLowerCase() && !filename.includes('/') && !filename.includes('\\'), 'E1', asset, 'filename must be local lowercase');
      const path = baseDir + filename; demand(files.includes(path), 'E13', asset, `missing ${filename}`); used.add(path);
      let image; try { image = decodePNG(readFileSync(path)); } catch (e) { throw new Error(`${asset}/${filename}: ${e.message}`, { cause: e }); }
      demand(integer(columns) && columns > 0 && integer(rows) && rows > 0 && image.width === columns * m.canvas[0] && image.height === rows * m.canvas[1], 'E6', asset, 'sheet/cell dimensions mismatch');
      for (let row = 0; row < rows; row++) for (let col = 0; col < columns; col++) {
        const cell = crop(image, col * m.canvas[0], row * m.canvas[1], ...m.canvas); pixelsCheck(cell, m, part, palette);
        if (asset === 'wall.cap') for (let y = 13; y < cell.height; y++) for (let x = 0; x < cell.width; x++) demand(!cell.pixels[(y * cell.width + x) * 4 + 3], 'L7', asset, 'cap exceeds 13 px');
        if (asset === 'door.north_2w') for (let y = 0; y < cell.height; y++) for (let x = 1; x < cell.width - 1; x++) demand(!cell.pixels[(y * cell.width + x) * 4 + 3], 'L9/C5', asset, 'archway interior/lintel must remain transparent');
        const face = animation?.face_anchor?.[row]?.[col];
        if (m.kind === 'character' && m.role !== 'face_overlay') {
          demand(labels[row] === 'up' ? face === null : Array.isArray(face) && face.length === 2 && face.every(integer) && face[0] >= 0 && face[1] >= 0 && face[0] + overlayCanvas[0] <= 32 && face[1] + overlayCanvas[1] <= 48, 'E25', asset, 'required integer per-frame face anchor/null up');
        }
        frames.push({ key: `${asset}/${state}/${labels[row] ?? row}/${part.part}/${col}`, pack: m.pack, image: cell, anchor: part.anchor, faceAnchor: face ?? null, kind: m.kind });
      }
    };
    if (m.animations) {
      for (const [name, anim] of Object.entries(m.animations)) {
        demand(/^[a-z][a-z0-9_]*$/.test(name) && anim.file === `${asset}--${name}.png`, 'E1', asset, 'animation filename');
        demand(Array.isArray(anim.rows) && anim.rows.length > 0 && equal(anim.rows, m.orientations.filter((d) => anim.rows.includes(d))), 'E12', asset, 'animation row order');
        demand(integer(anim.frames) && anim.frames > 0 && Array.isArray(anim.ms) && anim.ms.length === anim.frames && anim.ms.every((n) => integer(n) && n > 0) && ['loop', 'once', 'pingpong'].includes(anim.loop), 'E23', asset, 'animation timing/loop');
        if (asset === 'char.maple' && name === 'walk') demand(anim.frames === 4, 'E23/L12', asset, 'walk must have four frames');
        for (const a of anim.anchors?.flat() ?? []) demand(equal(a, m.parts[0].anchor), 'E8', asset, 'animated canonical anchor changed');
        add(anim.file, anim.frames, anim.rows.length, anim.rows, name, m.parts[0], anim);
      }
    } else if (m.tiles) {
      demand(m.kind === 'tile' && equal(m.canvas, [16, 16]), 'E6/L17', asset, 'tile size 16');
      add(`${asset}--sheet.png`, m.tiles.columns, m.tiles.rows, [], 'default', m.parts[0]);
    } else for (const state of m.states) for (const orientation of m.orientations) for (const part of m.parts) add(`${asset}--${state}--${orientation}${part.part === 'base' ? '' : '--' + part.part}.png`, 1, 1, [orientation], state, part);
  }
  demand(files.filter((f) => f.endsWith('.png')).every((f) => used.has(f)), 'E1', 'sources', 'unreferenced PNG');
  const body = metas.find(({ meta }) => meta.id === 'char.maple')?.meta, faces = metas.find(({ meta }) => meta.role === 'face_overlay')?.meta;
  demand(body && faces, 'E25', 'Maple', 'body and face assets required');
  for (const key of ['idle', 'walk']) demand(equal(body.animations?.[key]?.rows, dirs), 'E13', 'char.maple', `all four ${key} directions required`);
  for (const expression of ['calm', 'happy', 'curious', 'sleepy', 'focused']) demand(equal(faces.animations?.[`face_${expression}`]?.rows, dirs.slice(0, 3)), 'E25', faces.id, `missing face expression/directions: ${expression}`);
  const catalog = JSON.parse(readFileSync(join(root, 'backend/src/maplegotchi/world_catalog/initial_catalog.json'), 'utf8'));
  for (const { meta } of metas) if (['floor_object', 'wall_object'].includes(meta.kind)) demand(catalog.types.some((t) => t.art_id === meta.id), 'S17', meta.id, 'object art has no catalog type');
  for (const type of catalog.types) {
    if (type.art_id === null) { demand(type.category === 'structural', 'S17', type.id, 'no-art exception is structural only'); continue; }
    const meta = metas.find(({ meta }) => meta.id === type.art_id)?.meta;
    demand(meta && type.geometry_version === meta.geometry_version && equal(type.footprint, [meta.footprint?.w, meta.footprint?.h]) && equal(type.blocks, meta.blocks) && equal(type.orientations, meta.orientations) && equal(type.states, meta.states) && equal(type.points, meta.catalog_points) && equal(type.slots, meta.catalog_slots) && type.mount_y_px === meta.mount_y_px, 'S17', type.id, 'catalog identity/version/footprint/blocks/orientations/states/points/slots/mount mismatch');
    for (const point of type.points) {
      const [x, y] = point.approach;
      demand(type.blocks[y]?.[x] !== '#', 'E11', type.id, 'approach inside blocking tile');
      demand(!point.pose || body.animations[point.pose]?.rows.includes(point.occupy_direction), 'E11', type.id, 'occupy pose/direction missing');
    }
    demand(!type.points.length || Array.isArray(meta.hit) && meta.hit.length >= 3 && meta.hit.every((p) => Array.isArray(p) && p.length === 2 && p.every(integer) && p.every((n, i) => n >= 0 && n <= meta.canvas[i])), 'E20', meta.id, 'interactive object requires bounded hit polygon');
  }
  const manifest = metas.map(({ meta }) => meta);
  demand(frames.filter((f) => f.key.startsWith('tile.floor_wood/')).length >= 4, 'L17', 'tile.floor_wood', 'at least four variants');
  const edges = metas.find(({ meta }) => meta.id === 'tile.floor_edge')?.meta;
  demand(edges?.tiles?.columns === 4 && edges?.tiles?.rows === 4, 'L17', 'tile.floor_edge', 'sixteen row-major edge cells in 4x4');
  for (const id of ['wall.north', 'wall.cap', 'wall.side', 'wall.south', 'door.north_2w', 'door.closed', 'backdrop.window']) demand(ids.has(id), 'E13', id, 'required renderer visual key');
  return { frames, manifest };
}
