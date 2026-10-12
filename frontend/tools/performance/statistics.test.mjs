import { test } from 'node:test';
import assert from 'node:assert/strict';
import { percentile, distribution, budgets, residency, framePacing } from './statistics.mjs';
test('nearest-rank p95 includes the correct individual sample without mutation', () => { const a = Array.from({ length: 100 }, (_, i) => 100 - i); assert.equal(percentile(a, .95), 95); assert.equal(a[0], 100); });
test('small samples and outliers are retained', () => { assert.equal(percentile([0, 1, 99], .95), 99); assert.equal(distribution([1, 1, 40]).max, 40); });
test('invalid/empty samples fail closed', () => { for (const a of [[], [NaN], [-1], [Infinity]]) assert.throws(() => percentile(a, .95)); });
test('locked CPU and draw thresholds reject a failing scenario', () => { const rows = [{ environment: 'desktop', draws: { count: 100, max: 40 }, renderMs: { p95: 4 } }, { environment: 'phone-emulated-4x', draws: { count: 100, max: 40 }, renderMs: { p95: 8 } }]; assert.deepEqual(budgets(rows), { drawCalls: true, desktopCpu: true, phoneCpu: true }); rows[0].draws.max = 41; rows[1].renderMs.p95 = 8.01; assert.deepEqual(budgets(rows), { drawCalls: false, desktopCpu: true, phoneCpu: false }); });

test('missing environment samples cannot pass', () => { assert.deepEqual(budgets([]), {drawCalls:false,desktopCpu:false,phoneCpu:false}); });

test('invalid percentile fractions fail closed', () => { for (const f of [NaN, Infinity, 0, -1, 1.1]) assert.throws(() => percentile([1,2], f)); });

test('resident bound includes the 16-byte capability framebuffer and excludes disposed contexts', () => {
  const active = { lost: false, width: 1074, height: 645, allocations: [{bytes: 1572872}] };
  const capability = { lost: false, width: 1, height: 1, allocations: [] };
  assert.equal(residency([active, capability]), 12656568);
  assert.equal(residency([active, capability, {...active, lost: true}]), 12656568);
});
test('frame gates require two full interval windows and retain slow outliers', () => {
  const window = {elapsedMs: 70000, intervals: Array(4000).fill(15)};
  assert.equal(framePacing([window, window]), true);
  assert.equal(framePacing([]), false);
  assert.equal(framePacing([window]), false);
  assert.equal(framePacing([window, {...window, intervals: [15]}]), false);
  assert.equal(framePacing([window, {...window, intervals: [...window.intervals, 34]}]), false);
});
