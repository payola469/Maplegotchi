import { test } from 'node:test';
import { execFileSync } from 'node:child_process';
import assert from 'node:assert/strict';
import { mkdtempSync, cpSync, readFileSync, writeFileSync, rmSync, readdirSync, mkdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { readInputs, validateParts, validateAnchor, validateDisplayAnchors } from './validate.mjs';
import { root, build } from './cli.mjs';
import { pack, place, digest, json, budget } from './pack.mjs';
import { decodePNG, encodePNG, crop, crc32 } from './png.mjs';
function sandbox(work) {
  const dir = mkdtempSync(join(tmpdir(), 'maple-art-'));
  for (const p of ['art', 'backend/src/maplegotchi/world_catalog', '.gitattributes']) cpSync(join(root, p), join(dir, p), { recursive: true });
  try { return work(dir); } finally { rmSync(dir, { recursive: true, force: true }); }
}
const metaPath = (dir, id = 'furniture.writing_desk') => join(dir, 'art/export', id.split('.')[0], id, id + '.meta.json');
function modify(dir, id, fn) { const path = metaPath(dir, id), m = JSON.parse(readFileSync(path)); fn(m); writeFileSync(path, json(m)); }
const object = () => ({ id: 'furniture.test', kind: 'floor_object', canvas: [48, 48], parts: [{ part: 'base', anchor: [0, 48] }, { part: 'cover', sort: 'above_occupant', anchor: [0, 48] }, { part: 'emissive', anchor: [0, 48] }, { part: 'light', anchor: [24, 8], anchor_role: 'light_source_center', layer: 'light' }, { part: 'shadow', anchor: [24, 40], anchor_role: 'floor_center', layer: 'shadow' }] });
test('owner anchor clarification: canonical, occupant, emissive, light and shadow accepted', () => validateParts(object()));
for (const [name, change] of [
  ['ordinary differing anchor', (m) => m.parts.push({ part: 'panel', anchor: [1, 48] })],
  ['occupant differing anchor', (m) => m.parts[1].anchor = [2, 48]],
  ['emissive differing anchor', (m) => m.parts[2].anchor = [2, 48]],
  ['undeclared light centre', (m) => delete m.parts[3].anchor_role],
  ['wrong shadow role', (m) => m.parts[4].anchor_role = 'light_source_center'],
  ['frame drift', (m) => m.parts[3].frame_anchors = [[24, 8], [25, 8]]],
  ['state drift', (m) => m.parts[4].state_anchors = { default: [24, 40], on: [25, 40] }],
]) test(`E8 rejects ${name}`, () => { const m = object(); change(m); assert.throws(() => validateParts(m), /E8/); });
for (const a of [[-1, 4], [49, 0], [0, 49], [0.5, 0], [0], null]) test(`E8 bounds ${JSON.stringify(a)}`, () => assert.throws(() => validateAnchor(a, [48, 48], 'fixture'), /E8/));
test('E8 inclusive pixel-corner bottom boundary', () => validateAnchor([0, 48], [48, 48], 'fixture'));
test('complete source set validates; all catalog visual types and marker exception', () => { const input = readInputs(root); assert.equal(input.frames.length, 193); assert.equal(input.manifest.filter((m) => m.footprint).length, 14); });
const negatives = [
 ['E1 duplicate/wrong sidecar', 'E1', (d) => modify(d, 'furniture.writing_desk', (m) => m.id = 'WRONG')],
 ['E6 canvas/sheet mismatch', 'E6', (d) => modify(d, 'furniture.writing_desk', (m) => { m.canvas[1] += 8; m.parts.forEach((p) => { if (!p.anchor_role) p.anchor[1] += 8; }); })],
 ['E8 canonical base', 'E8', (d) => modify(d, 'furniture.writing_desk', (m) => m.parts[0].anchor = [1, 48])],
 ['E10 mask', 'E10', (d) => modify(d, 'furniture.writing_desk', (m) => m.blocks = ['#'])],
 ['E12 directions', 'E12', (d) => modify(d, 'char.maple', (m) => m.orientations.reverse())],
 ['E13 missing state image', 'E13', (d) => modify(d, 'furniture.writing_desk', (m) => m.states.push('on'))],
 ['E18 frame cap', 'E18', (d) => modify(d, 'furniture.writing_desk', (m) => m.canvas[0] = 520)],
 ['E20 fallback reference', 'E20', (d) => modify(d, 'furniture.writing_desk', (m) => m.fallback = 'missing.art')],
 ['E20 hit polygon', 'E20', (d) => modify(d, 'furniture.writing_desk', (m) => delete m.hit)],
 ['E23 timing', 'E23', (d) => modify(d, 'char.maple', (m) => m.animations.walk.ms = [])],
 ['E25 expression', 'E25', (d) => { modify(d, 'char.faces', (m) => delete m.animations.face_calm); rmSync(join(d, 'art/export/char/char.faces/char.faces--face_calm.png')); }],
 ['E25 anchor', 'E25', (d) => modify(d, 'char.maple', (m) => m.animations.walk.face_anchor[0][0] = null)],
 ['S17 version', 'S17', (d) => modify(d, 'furniture.writing_desk', (m) => m.geometry_version++)],
 ['S17 slot drift', 'S17', (d) => modify(d, 'furniture.writing_desk', (m) => m.catalog_slots[0].capacity++)],
 ['E24 foreign source', 'E24', (d) => writeFileSync(join(d, 'art/export/test.aseprite'), 'foreign')],
 ['E24 LFS PNG pointer', 'E2', (d) => writeFileSync(join(d, 'art/export/furniture/furniture.writing_desk/furniture.writing_desk--default--south.png'), 'version https://git-lfs.github.com/spec/v1\n')],
 ['E24 filter=lfs', 'E24/C1', (d) => writeFileSync(join(d, '.gitattributes'), 'art/export/** filter=lfs\n')],
 ['C1 export-ignore', 'E24/C1', (d) => writeFileSync(join(d, '.gitattributes'), 'art/palette export-ignore\n')],
];
for (const [name, rule, mutate] of negatives) test(name, () => sandbox((d) => { mutate(d); assert.throws(() => readInputs(d), new RegExp(rule)); }));
for (const [name, rule, edit] of [
 ['transparent RGB', 'E3', (i) => { i.pixels.set([1, 0, 0, 0], 0); }],
 ['partial base alpha', 'E4', (i) => { i.pixels[3 + (5 * i.width + 5) * 4] = 128; }],
 ['palette', 'E5', (i) => { i.pixels.set([1, 2, 3, 255], (5 * i.width + 5) * 4); }],
 ['border', 'E7', (i) => { i.pixels.set([73, 62, 56, 255], 0); }],
]) test(name, () => sandbox((d) => {
  const file = join(d, 'art/export/furniture/furniture.writing_desk/furniture.writing_desk--default--south.png');
  const image = decodePNG(readFileSync(file)); edit(image); writeFileSync(file, encodePNG(image)); assert.throws(() => readInputs(d), new RegExp(rule));
}));
test('E2 CRC and forbidden profile chunk are rejected', () => { const b = readFileSync(join(root, 'art/export/char/char.maple/char.maple--walk.png')); const bad = Buffer.from(b); bad[bad.length - 1] ^= 1; assert.throws(() => decodePNG(bad), /E2/); const badType = Buffer.from(b); badType.set(Buffer.from('iCCP'), 37); const length = badType.readUInt32BE(33); badType.writeUInt32BE(crc32(badType.subarray(37, 41 + length)), 41 + length); assert.throws(() => decodePNG(badType), /forbidden PNG chunk iCCP/); });
test('E11 rejects catalog occupy pose without animation', () => sandbox((d) => { modify(d, 'char.maple', (m) => delete m.animations.sit_write); rmSync(join(d, 'art/export/char/char.maple/char.maple--sit_write.png')); assert.throws(() => readInputs(d), /E11/); }));
function frame(key, width, height) { const pixels = Buffer.alloc(width * height * 4); for (let y = 1; y < height - 1; y++) for (let x = 1; x < width - 1; x++) pixels.set([73, 62, 56, 255], (y * width + x) * 4); return { key, image: { width, height, pixels }, anchor: [width / 2, height - 1] }; }
test('MaxRects ordering, page allocation and non-overlap independent of input order', () => {
  const frames = Array.from({ length: 24 }, (_, i) => frame(`frame${i}`, 8 + i % 4 * 8, 8 + i % 3 * 8));
  const a = place(frames, 64), b = place([...frames].reverse(), 64); assert.deepEqual(a, b); assert.ok(a.count > 1);
  for (const x of a.placements) for (const y of a.placements) if (x.key !== y.key && x.page === y.page) assert.ok(x.x + x.box.w + 2 <= y.x - 2 || y.x + y.box.w + 2 <= x.x - 2 || x.y + x.box.h + 2 <= y.y - 2 || y.y + y.box.h + 2 <= x.y - 2);
});
test('L18 page cap includes extrusion', () => assert.throws(() => pack([frame('huge', 512, 512)], 'character'), /L18/));
test('all source frames round-trip after trim, sourceSize, anchor and extrusion', () => {
  const { frames } = readInputs(root);
  for (const group of [...new Set(frames.map((f) => f.pack))]) for (const page of pack(frames.filter((f) => f.pack === group), group)) {
    const png = decodePNG(page.png); for (const [key, record] of Object.entries(page.metadata.frames)) {
      const original = frames.find((f) => f.key === key); assert.deepEqual(record.anchor_px, original.anchor); const { frame: r, spriteSourceSize: s } = record;
      const visible = crop(png, r.x, r.y, r.w, r.h), restored = Buffer.alloc(original.image.pixels.length);
      for (let y = 0; y < s.h; y++) visible.pixels.copy(restored, ((s.y + y) * original.image.width + s.x) * 4, y * s.w * 4, (y + 1) * s.w * 4);
      assert.deepEqual(restored, original.image.pixels, key);
      for (let y = -2; y < r.h + 2; y++) for (let x = -2; x < r.w + 2; x++) {
        const a = ((r.y + y) * png.width + r.x + x) * 4, b = ((r.y + Math.max(0, Math.min(r.h - 1, y))) * png.width + r.x + Math.max(0, Math.min(r.w - 1, x))) * 4;
        assert.deepEqual(png.pixels.subarray(a, a + 4), png.pixels.subarray(b, b + 4));
      }
    }
  }
});
test('L20 actual RGBA sizes and negative synthetic budgets', () => { assert.equal(budget([{ bytes: 1024 }]).staticBytes, 1024); assert.throws(() => budget([{ bytes: 28 * 1024 * 1024 + 1 }]), /L20/); assert.throws(() => budget([], 4 * 1024 * 1024 + 1), /L20/); });
test('two clean offline outputs have independent byte-identical PNG and metadata hashes', () => sandbox((d) => {
  const a = join(d, 'one'), b = join(d, 'two'); const ra = build(d, a), rb = build(d, b); assert.deepEqual(ra, rb);
  for (const f of readdirSync(a)) assert.equal(digest(readFileSync(join(a, f))), digest(readFileSync(join(b, f))), f);
  assert.ok(!readFileSync(join(a, 'index.ts'), 'utf8').includes(d));
}));
test('Windows path separators never appear in generated output', () => sandbox((d) => { mkdirSync(join(d, 'output')); build(d, join(d, 'output')); assert.ok(!readFileSync(join(d, 'output/index.ts'), 'utf8').includes('\\')); }));
test('E8 ordinary part cannot borrow a light role', () => { const m = object(); m.parts[1].anchor_role = 'light_source_center'; assert.throws(() => validateParts(m), /E8/); });
test('E7 cannot bypass furniture border with a structural label', () => sandbox((d) => { modify(d, 'furniture.writing_desk', (m) => m.role = 'structural'); assert.throws(() => readInputs(d), /E7/); }));
test('E12 rejects undeclared/nonexistent mirror sources', () => sandbox((d) => { modify(d, 'furniture.writing_desk', (m) => m.mirror = { east: 'west' }); assert.throws(() => readInputs(d), /E12/); }));
test('E13 requires all idle/walk directions even when files exist', () => sandbox((d) => { modify(d, 'char.maple', (m) => delete m.animations.idle); rmSync(join(d, 'art/export/char/char.maple/char.maple--idle.png')); assert.throws(() => readInputs(d), /E13/); }));
test('L18 applies character cap regardless of artist pack name', () => { const f = { ...frame('body', 512, 512), kind: 'character' }; assert.throws(() => pack([f], 'shared'), /L18/); });
test('L17 enforces exactly 4x4 edge layout, not merely sixteen cells', () => sandbox((d) => { modify(d, 'tile.floor_edge', (m) => m.tiles = { columns: 8, rows: 2 }); assert.throws(() => readInputs(d), /E6|L17/); }));
test('L2 requires body canvas 32x48', () => sandbox((d) => { modify(d, 'char.maple', (m) => m.canvas[0] = 40); assert.throws(() => readInputs(d), /L2/); }));
test('L10 requires window canvas 32x32', () => sandbox((d) => { modify(d, 'window.north_2w', (m) => { m.canvas[1] = 40; m.parts.forEach((p) => { if (!p.anchor_role) p.anchor[1] = 40; }); }); assert.throws(() => readInputs(d), /L10/); }));
test('L7 cap rejects pixels below the 13-pixel maximum', () => sandbox((d) => { const p = join(d, 'art/export/wall/wall.cap/wall.cap--default--south.png'), image = decodePNG(readFileSync(p)); image.pixels.set([73, 62, 56, 255], (15 * 16) * 4); writeFileSync(p, encodePNG(image)); assert.throws(() => readInputs(d), /L7/); }));
test('L9 archways reject a lintel', () => sandbox((d) => { const p = join(d, 'art/export/door/door.north_2w/door.north_2w--default--south.png'), image = decodePNG(readFileSync(p)); image.pixels.set([73, 62, 56, 255], 5 * 4); writeFileSync(p, encodePNG(image)); assert.throws(() => readInputs(d), /L9/); }));
test('changed valid source pixels invalidate the relevant atlas image digest', () => sandbox((d) => { const before = build(d, join(d, 'before')); const p = join(d, 'art/export/furniture/furniture.writing_desk/furniture.writing_desk--default--south.png'), image = decodePNG(readFileSync(p)); image.pixels.set([73, 62, 56, 255], (5 * image.width + 5) * 4); writeFileSync(p, encodePNG(image)); const after = build(d, join(d, 'after')); assert.notEqual(before.pages.find((p) => p.name === 'shared-0').pngSha256, after.pages.find((p) => p.name === 'shared-0').pngSha256); assert.equal(before.pages[0].pngSha256, after.pages[0].pngSha256); }));
test('clean rebuild matches macOS reference PNG, metadata AND generated-index hashes (Windows CI gate)', () => sandbox((d) => { const actual = build(d, join(d, 'golden')); assert.deepEqual(actual, JSON.parse(readFileSync(join(root, 'frontend/tools/art/reproducibility.json')))); }));

test('declared art display anchor names a real host slot and stays in its canvas', () => validateDisplayAnchors({ id: 'fixture.slot', canvas: [48, 48], catalog_slots: [{ id: 'desktop' }], display_anchors: { desktop: [12, 18] } }));
test('unknown host slot display anchor is rejected', () => assert.throws(() => validateDisplayAnchors({ id: 'fixture.slot', canvas: [48, 48], catalog_slots: [], display_anchors: { missing: [12, 18] } }), /S17/));
test('out-of-canvas display anchor is rejected', () => assert.throws(() => validateDisplayAnchors({ id: 'fixture.slot', canvas: [48, 48], catalog_slots: [{ id: 'desktop' }], display_anchors: { desktop: [49, 18] } }), /E8/));

test('R1A-13 placeholder recolor preserves geometry/alpha and uses approved palette colors', () => {
  const palette = readFileSync(join(root, 'art/palette/maple-master.hex'), 'utf8').trim().split(/\s+/);
  assert.equal(palette[1], '#8b715b'); assert.equal(palette[0], '#493e38');
  for (const file of readdirSync(join(root, 'art/export/char/char.maple')).filter((f) => f.endsWith('.png'))) {
    const image = decodePNG(readFileSync(join(root, 'art/export/char/char.maple', file)));
    let skin = 0, shirt = 0;
    for (let row = 0; row < 4; row++) for (let frame = 0; frame < image.width / 32; frame++) {
      const pixel = (x, y) => [...image.pixels.subarray(((row * 48 + y) * image.width + frame * 32 + x) * 4, ((row * 48 + y) * image.width + frame * 32 + x) * 4 + 4)];
      assert.deepEqual(pixel(14, 11 + frame % 2), [139, 113, 91, 255]); skin++;
      assert.deepEqual(pixel(10, 27 + frame % 2), [73, 62, 56, 255]); shirt++;
      assert.deepEqual(pixel(8, 4 + frame % 2), [0, 0, 0, 255]);
      assert.deepEqual(pixel(12, 42), [73, 62, 56, 255]);
      assert.deepEqual(pixel(0, 0), [0, 0, 0, 0]);
    }
    assert.ok(skin > 0 && shirt > 0);
    for (let i = 0; i < image.pixels.length; i += 4) {
      assert.notDeepEqual([...image.pixels.subarray(i, i + 3)], [235, 196, 155]);
      assert.notDeepEqual([...image.pixels.subarray(i, i + 3)], [114, 148, 130]);
    }
  }
});

test('effective Git info attributes reject LFS on Windows and Linux', () => sandbox((d) => {
  execFileSync('git', ['init', '--quiet', d], { stdio: 'ignore' });
  writeFileSync(join(d, '.git/info/attributes'), 'art/export/** filter=lfs\n');
  assert.throws(() => readInputs(d), /E24\/C1.*forbidden effective Git attribute/);
}));
test('source palette must be a regular file', () => sandbox((d) => {
  const path = join(d, 'art/palette/maple-master.hex'); rmSync(path); mkdirSync(path);
  assert.throws(() => readInputs(d), /E24.*regular file/);
}));
