// Recalculate archived STEP 152 evidence; this does not benchmark hosted CI hardware.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { gunzipSync } from 'node:zlib';
import { distribution, budgets, residency, framePacing } from './statistics.mjs';
const archive = JSON.parse(gunzipSync(fs.readFileSync(new URL('../../../docs/fixtures/maple-room/r1a-19/windows-browser-raw.json.gz', import.meta.url))));
const report = archive.browser;
const rows = report.rows.filter((r) => !r.fallback).concat([...report.frameWindows, ...report.soak].map((r) => ({environment: 'desktop', ...r})));
test('archived local evidence retains all 52244 renders and nearest-rank results', () => {
  assert.equal(rows.reduce((n,r) => n + r.raw.length, 0), 52244);
  for (const r of rows) {
    assert.deepEqual(distribution(r.raw.map((s) => s[0])), r.renderMs);
    assert.deepEqual(distribution(r.raw.map((s) => s[1])), r.draws);
  }
  assert.deepEqual(budgets(rows), {drawCalls:true, desktopCpu:true, phoneCpu:true});
});
test('archived full frame windows and comparable retained heap pass locked budgets', () => {
  assert.equal(framePacing(report.frameWindows), true);
  assert.equal(report.soakElapsedMs, 631946);
  assert.equal(report.heapEnd.heap.usedSize - report.heapStart.heap.usedSize, 621924);
  assert.deepEqual(report.heapEnd.dom, report.heapStart.dom);
  assert.equal(report.errors.length, 0);
});
test('archived corrected allocation matrix independently includes capability framebuffer', () => {
  const correction = archive['allocation-check'];
  const resources = correction.rows.filter((r) => !r.fallback).map((r) => r.resources);
  assert.equal(Math.max(...resources.map((r) => residency(r.contexts))), 12656568);
  assert.equal(resources.flatMap((r) => r.unknownAllocations).length, 0);
  assert.equal(report.texture.peakBoundBytes + 16, 12656568);
});
