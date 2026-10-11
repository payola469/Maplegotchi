import { encodePNG } from './png.mjs';
import { createHash } from 'node:crypto';
export const digest = (b) => createHash('sha256').update(b).digest('hex');
export function canonical(value) {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === 'object') return Object.fromEntries(Object.keys(value).sort().map((k) => [k, canonical(value[k])]));
  return value;
}
export const json = (v) => JSON.stringify(canonical(v), null, 2) + '\n';
export function trim(image) {
  let x0 = image.width, y0 = image.height, x1 = -1, y1 = -1;
  for (let y = 0; y < image.height; y++) for (let x = 0; x < image.width; x++) if (image.pixels[(y * image.width + x) * 4 + 3]) { x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y); }
  return x1 < 0 ? { x: 0, y: 0, w: 1, h: 1 } : { x: x0, y: y0, w: x1 - x0 + 1, h: y1 - y0 + 1 };
}
// MaxRects BSSF: stable asset order; min(short-side, long-side, y, x, page).
// All intersecting free rectangles are split, then contained rectangles are pruned.
export function place(frames, cap) {
  const pages = [], placements = [];
  const sorted = [...frames].map((f) => ({ ...f, box: trim(f.image) })).sort((a, b) => Math.max(b.box.w, b.box.h) - Math.max(a.box.w, a.box.h) || b.box.w * b.box.h - a.box.w * a.box.h || (a.key < b.key ? -1 : a.key > b.key ? 1 : 0));
  for (const f of sorted) {
    const w = f.box.w + 4, h = f.box.h + 4;
    if (w > cap || h > cap) throw new Error(`L18 ${f.key}: trimmed frame plus extrusion exceeds ${cap}`);
    let best;
    for (const [page, free] of pages.entries()) for (const r of free) if (w <= r.w && h <= r.h) {
      const score = [Math.min(r.w - w, r.h - h), Math.max(r.w - w, r.h - h), r.y, r.x, page];
      if (!best || score.some((n, i) => n !== best.score[i] && score.slice(0, i).every((v, j) => v === best.score[j]) && n < best.score[i])) best = { page, x: r.x, y: r.y, score };
    }
    if (!best) { best = { page: pages.length, x: 0, y: 0 }; pages.push([{ x: 0, y: 0, w: cap, h: cap }]); }
    const used = { x: best.x, y: best.y, w, h }, split = [];
    for (const r of pages[best.page]) {
      if (used.x >= r.x + r.w || used.x + w <= r.x || used.y >= r.y + r.h || used.y + h <= r.y) { split.push(r); continue; }
      if (used.x > r.x) split.push({ ...r, w: used.x - r.x });
      if (used.x + w < r.x + r.w) split.push({ ...r, x: used.x + w, w: r.x + r.w - used.x - w });
      if (used.y > r.y) split.push({ ...r, h: used.y - r.y });
      if (used.y + h < r.y + r.h) split.push({ ...r, y: used.y + h, h: r.y + r.h - used.y - h });
    }
    pages[best.page] = split.filter((r, i) => !split.some((s, j) => j !== i && r.x >= s.x && r.y >= s.y && r.x + r.w <= s.x + s.w && r.y + r.h <= s.y + s.h && (j < i || r.x !== s.x || r.y !== s.y || r.w !== s.w || r.h !== s.h))).sort((a, b) => a.y - b.y || a.x - b.x || a.w - b.w || a.h - b.h);
    placements.push({ ...f, page: best.page, x: used.x + 2, y: used.y + 2 });
  }
  return { count: pages.length, placements };
}
export function pack(frames, packName) {
  const cap = (['character', 'fx'].includes(packName) || frames.some((f) => ['character', 'fx'].includes(f.kind))) ? 512 : 1024;
  const { count, placements } = place(frames, cap), pages = [];
  for (let page = 0; page < count; page++) {
    const entries = placements.filter((p) => p.page === page);
    const power = (v) => 2 ** Math.ceil(Math.log2(v));
    const width = power(Math.max(...entries.map((p) => p.x + p.box.w + 2))), height = power(Math.max(...entries.map((p) => p.y + p.box.h + 2)));
    const pixels = Buffer.alloc(width * height * 4), records = {};
    for (const p of entries) {
      const b = p.box;
      for (let y = -2; y < b.h + 2; y++) for (let x = -2; x < b.w + 2; x++) {
        const sx = b.x + Math.max(0, Math.min(b.w - 1, x)), sy = b.y + Math.max(0, Math.min(b.h - 1, y));
        p.image.pixels.copy(pixels, ((p.y + y) * width + p.x + x) * 4, (sy * p.image.width + sx) * 4, (sy * p.image.width + sx) * 4 + 4);
      }
      records[p.key] = { frame: { x: p.x, y: p.y, w: b.w, h: b.h }, rotated: false, trimmed: b.x !== 0 || b.y !== 0 || b.w !== p.image.width || b.h !== p.image.height, spriteSourceSize: b, sourceSize: { w: p.image.width, h: p.image.height }, anchor_px: p.anchor, face_anchor: p.faceAnchor ?? null };
    }
    const png = encodePNG({ width, height, pixels }), name = `${packName}-${page}`;
    pages.push({ name, png, metadata: { frames: records, meta: { image: `${name}.png`, scale: '1', size: { w: width, h: height } } }, sha256: digest(png), bytes: width * height * 4 });
  }
  return pages;
}
export function budget(pages, runtimeBytes = 4 * 1024 * 1024) {
  const staticBytes = pages.reduce((n, p) => n + p.bytes, 0), totalBytes = staticBytes + runtimeBytes;
  if (staticBytes > 28 * 1024 * 1024 || runtimeBytes > 4 * 1024 * 1024 || runtimeBytes < 0 || totalBytes > 32 * 1024 * 1024) throw new Error('L20: texture budget exceeded');
  const ceil8 = (v) => Math.ceil(v / (8 * 1024 * 1024)) * 8 * 1024 * 1024;
  return { format: 'RGBA8', mipmaps: false, staticBytes, runtimeAllowanceBytes: runtimeBytes, residentUpperBoundBytes: totalBytes, realisticProjectionBytes: staticBytes, budgetRuleBytes: Math.max(ceil8(totalBytes), ceil8(1.5 * staticBytes)) };
}
