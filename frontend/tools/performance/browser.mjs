import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { installProbe } from './probe.mjs';
import { distribution, budgets, residency, framePacing } from './statistics.mjs';
import { browserRuntime } from './runtime.mjs';
const runtime = browserRuntime();
const root = fileURLToPath(new URL('../../../', import.meta.url));
const args = process.argv.slice(2), arg = (name, fallback) => args.includes(name) ? args[args.indexOf(name) + 1] : fallback;
const quick = args.includes('--quick');
const output = path.resolve(arg('--output', path.join(root, 'var/r1a19/browser.json')));
const { chromium } = runtime;
const fixture = JSON.parse(fs.readFileSync(path.join(root, 'docs/fixtures/maple-room/r1a-17/scripted-room-states.json')));
const state = (name) => fixture.states.find((s) => s.name === name).snapshot;
const worlds = { idle: { ...fixture.base_world, snapshot: state('initial') }, walking: { ...fixture.base_world, snapshot: state('distant_departure') } };
const report = { started: new Date().toISOString(), quick, playwright: runtime.version, node: process.version, fixture: { grid: worlds.idle.grid, regions: worlds.idle.regions.length, doors: worlds.idle.doors.length, objects: worlds.idle.objects.length, route: worlds.walking.snapshot.maple.route }, rows: [], frameWindows: [], soak: [], switches: [], environments: [], errors: [] };
const save = () => { fs.mkdirSync(path.dirname(output), { recursive: true }); fs.writeFileSync(output, JSON.stringify(report, null, 2) + '\n'); };
const hash = (b) => createHash('sha256').update(b).digest('hex');
const browser = await chromium.launch(runtime.launch);
report.chrome = browser.version();
const pause = (page, ms) => page.evaluate((ms) => new Promise((resolve) => setTimeout(resolve, ms)), ms);
async function prepare(environment, instrument = true) {
  const phone = environment.startsWith('phone');
  const context = await browser.newContext({ viewport: phone ? { width: 390, height: 844 } : { width: 1440, height: 1000 }, deviceScaleFactor: phone ? 3 : 1, isMobile: phone, hasTouch: phone });
  await context.addInitScript(installProbe, { instrument });
  const page = await context.newPage(), cdp = await context.newCDPSession(page);
  const errors = [];
  page.on('pageerror', (e) => errors.push({ type: 'pageerror', message: e.message }));
  page.on('console', (m) => { if (m.type() === 'error') errors.push({ type: 'console', message: m.text() }); });
  page.on('response', (r) => { if (r.status() >= 400) errors.push({ type: 'response', status: r.status(), url: r.url() }); });
  page.on('requestfailed', (r) => { if (!r.failure()?.errorText.includes('ERR_ABORTED')) errors.push({ type: 'request', url: r.url(), error: r.failure() }); });
  await page.route('**/src/world-room/fixtures.ts*', async (route) => route.fulfill({ contentType: 'application/javascript', body: `export const fixtureWorlds=${JSON.stringify(worlds)}; export const fixtureCatalog=${JSON.stringify(fixture.catalog)};` }));
  await page.route('**/src/world-room/scene.ts*', async (route) => {
    const response = await route.fetch(); let body = await response.text();
    report.sceneResponseSha256 ??= hash(body);
    const replace = (a, b) => { if (body.split(a).length !== 2) throw new Error(`Instrumentation anchor mismatch: ${a}`); body = body.replace(a, b); };
    replace('initialized = true;', 'initialized = true; window.__r1a19.attach(app);');
    replace('disposed = true;', 'disposed = true; if (initialized) window.__r1a19.detached();');
    replace('const tick = () => draw?.(app.ticker.deltaMS ?? 0);', 'const tick = () => window.__r1a19.update(() => draw?.(app.ticker.deltaMS ?? 0));');
    await route.fulfill({ response, body });
  });
  await page.goto('http://127.0.0.1:5179/?room=fixture');
  await page.getByRole('status', { name: 'Fixture renderer' }).filter({ hasText: 'renderer ready' }).waitFor({ timeout: 30000 });
  await page.evaluate(async () => { window.__r1a19.legacySnapshot = (await import('/src/test/fixtures.ts')).makeSnapshot(); });
  await pause(page, 2100);
  const details = await page.evaluate(() => ({ dpr: devicePixelRatio, screen: { width: screen.width, height: screen.height }, viewport: { width: innerWidth, height: innerHeight }, focus: document.hasFocus(), resources: window.__r1a19.resources(), label: document.querySelector('.world-preview__disclosure').textContent, api: window.__r1a19.apiRequests }));
  const calibration = async () => page.evaluate(() => { const out = []; for (let trial = 0; trial < 10; trial++) { const began = performance.now(); let sum = 0; for (let n = 0; n < 2000000; n++) sum = (sum + Math.imul(n, n ^ 91)) | 0; if (trial >= 5) out.push({ ms: performance.now() - began, sum }); } return out; });
  const normal = await calibration();
  if (phone) await cdp.send('Emulation.setCPUThrottlingRate', { rate: 4 });
  const throttled = phone ? await calibration() : normal;
  report.environments.push({ environment, instrument, ...details, cdpCpuRate: phone ? 4 : 1, calibration: { normal, throttled } }); save();
  return { page, cdp, context, errors, environment };
}
async function configure(page, { mode = 'overview', level = 1, moving = false, activity = false, phase = 'morning' } = {}) {
  if (activity) await page.evaluate(async (snapshot) => { (await import('/src/world-room/fixtures.ts')).fixtureWorlds.idle.snapshot = snapshot; }, state('activity_observe'));
  else await page.evaluate(async (snapshot) => { (await import('/src/world-room/fixtures.ts')).fixtureWorlds.idle.snapshot = snapshot; }, state('initial'));
  await page.evaluate(({ mode, level, moving, phase, activity }) => { const q = window.__r1a19; q.set('Scenario', activity ? 'walking' : 'idle'); q.set('Scenario', moving ? 'walking' : 'idle'); q.set('Camera mode', mode); q.set('Follow zoom', level); q.set('Focus region', 'living_room'); q.set('lighting phase', phase); q.moving = moving; }, { mode, level, moving, phase, activity });
  await pause(page, 50);
  await page.evaluate(({ level, activity, moving }) => { const q = window.__r1a19; q.set('Follow zoom', level); q.set('Focus region', 'living_room'); if (activity) q.set('Scenario', 'walking'); else q.set('Scenario', moving ? 'walking' : 'idle'); }, { level, activity, moving });
  await pause(page, 50);
  if (activity) await page.evaluate(() => window.__r1a19.set('Scenario', 'idle'));
  await pause(page, quick ? 300 : 2100);
}
async function sample(page, duration, frameIntervals = false) {
  return page.evaluate(async ({ duration, frameIntervals }) => {
    const q = window.__r1a19; q.samples = []; q.updates = []; q.measuring = true;
    const intervals = [], began = performance.now(); let previous, first;
    await new Promise((resolve) => { const tick = (now) => { first ??= now; if (previous !== undefined && frameIntervals) intervals.push(now - previous); previous = now; if (now - (frameIntervals ? first : began) >= duration) resolve(); else requestAnimationFrame(tick); }; requestAnimationFrame(tick); });
    q.measuring = false; const raw = q.samples; const update = q.updates; q.samples = []; q.updates = [];
    return { elapsedMs: performance.now() - began, raw, update, intervals, resources: q.resources(), camera: JSON.parse(document.querySelector('[data-camera]').dataset.camera), lighting: JSON.parse(document.querySelector('[data-lighting]').dataset.lighting) };
  }, { duration, frameIntervals });
}
function summarize(raw) { return { renderMs: distribution(raw.raw.map((r) => r[0])), draws: distribution(raw.raw.map((r) => r[1])), updateMs: distribution(raw.update) }; }
async function roundTrip(run, label) {
  const { page, cdp } = run;
  await page.evaluate(() => window.__r1a19.endDriver());
  await page.getByRole('button', { name: 'Return to legacy Room', exact: true }).click();
  await page.waitForSelector('.world-preview__canvas', { state: 'detached' });
  await pause(page, 900);
  const legacy = await page.evaluate(() => ({ ...window.__r1a19.resources(), focus: document.activeElement?.outerHTML }));
  await page.locator('.room-switcher select').selectOption('fixture');
  await page.getByRole('status', { name: 'Fixture renderer' }).filter({ hasText: 'renderer ready' }).waitFor();
  await pause(page, 900);
  await cdp.send('HeapProfiler.collectGarbage');
  const newRoom = await page.evaluate(() => window.__r1a19.resources());
  report.switches.push({ environment: run.environment, label, legacy, newRoom }); save();
  await page.evaluate(() => window.__r1a19.beginDriver());
}
try {
  // Static pixels must be identical with and without the renderer timing wrapper.
  const plain = await prepare('desktop', false);
  report.calibrationScreenshot = { plain: hash(await plain.page.locator('.world-preview__canvas').screenshot()) };
  report.errors.push(...plain.errors); await plain.context.close();
  for (const environment of ['desktop', 'phone-emulated-4x']) {
    const run = await prepare(environment); const { page, cdp } = run;
    if (environment === 'desktop') { report.calibrationScreenshot.instrumented = hash(await page.locator('.world-preview__canvas').screenshot()); report.calibrationScreenshot.equal = report.calibrationScreenshot.plain === report.calibrationScreenshot.instrumented; }
    await page.evaluate(() => window.__r1a19.beginDriver());
    const scenarios = [ { name: 'overview-idle' }, ...[1,2,3,4].map((level) => ({ name: `follow-long-L${level}`, mode: 'follow', moving: true, level })), { name: 'focus-long', mode: 'focus', moving: true }, { name: 'activity-observe', mode: 'follow', activity: true }, { name: 'lighting-transitions', mode: environment === 'desktop' ? 'overview' : 'follow', moving: true, transitions: true } ];
    for (const scenario of scenarios) {
      await configure(page, scenario);
      const camera = await page.evaluate(() => JSON.parse(document.querySelector('[data-camera]').dataset.camera));
      if (!camera.visible) { report.rows.push({ environment, scenario: scenario.name, fallback: true, camera }); save(); continue; }
      for (let trial = 1; trial <= (quick ? 1 : 2); trial++) {
        if (scenario.transitions) await page.evaluate(() => { window.__r1a19.phaseTimer = setInterval(() => { const q = window.__r1a19; q.phaseIndex = (q.phaseIndex ?? 0) + 1; q.set('lighting phase', ['morning','afternoon','evening','night'][q.phaseIndex % 4]); }, 750); });
        const raw = await sample(page, quick ? 400 : 5000);
        if (scenario.transitions) await page.evaluate(() => clearInterval(window.__r1a19.phaseTimer));
        report.rows.push({ environment, scenario: scenario.name, trial, ...summarize(raw), ...raw }); save();
        console.log(environment, scenario.name, trial, JSON.stringify(summarize(raw)));
      }
    }
    await roundTrip(run, 'scenario-cleanup');
    if (environment === 'desktop') {
      await configure(page, { mode: 'overview', moving: true });
      for (let trial = 1; trial <= (quick ? 1 : 2); trial++) {
        const raw = await sample(page, quick ? 1000 : 60000, true);
        report.frameWindows.push({ trial, ...summarize(raw), over33: raw.intervals.filter((x) => x > 33).length, ...raw }); save();
        console.log('desktop frame window', trial, report.frameWindows.at(-1).over33);
      }
      await page.evaluate(() => window.__r1a19.endDriver()); await configure(page);
      await cdp.send('HeapProfiler.collectGarbage');
      report.heapStart = { heap: await cdp.send('Runtime.getHeapUsage'), dom: await cdp.send('Memory.getDOMCounters'), resources: await page.evaluate(() => window.__r1a19.resources()) };
      const started = Date.now(); await page.evaluate(() => window.__r1a19.beginDriver());
      for (let segment = 0; segment < (quick ? 1 : 10); segment++) {
        await configure(page, { mode: ['overview','follow','focus'][segment % 3], level: segment % 4 + 1, moving: true, phase: ['morning','afternoon','evening','night'][segment % 4] });
        const raw = await sample(page, quick ? 1000 : 60000);
        report.soak.push({ segment, elapsedWallMs: Date.now() - started, heap: await cdp.send('Runtime.getHeapUsage'), dom: await cdp.send('Memory.getDOMCounters'), ...summarize(raw), ...raw }); save();
        console.log('soak', segment + 1, 'elapsed', Date.now() - started);
        if (segment > 0 && segment % 2 === 0) await roundTrip(run, `soak-${segment}`);
      }
      report.soakElapsedMs = Date.now() - started;
      await page.evaluate(() => window.__r1a19.endDriver()); await configure(page);
      await cdp.send('HeapProfiler.collectGarbage');
      report.heapEnd = { heap: await cdp.send('Runtime.getHeapUsage'), dom: await cdp.send('Memory.getDOMCounters'), resources: await page.evaluate(() => window.__r1a19.resources()) };
      report.retainedGrowthBytes = report.heapEnd.heap.usedSize - report.heapStart.heap.usedSize;
    }
    await page.evaluate(() => window.__r1a19.endDriver());
    report.errors.push(...run.errors.map((e) => ({ environment, ...e })));
    await run.context.close();
  }
  const rows = report.rows.filter((r) => !r.fallback).concat(report.frameWindows.map((r) => ({ environment: 'desktop', ...r })), report.soak.map((r) => ({ environment: 'desktop', ...r })));
  const allResources = rows.map((r) => r.resources);
  report.texture = { unknown: allResources.flatMap((r) => r.unknownAllocations), peakBoundBytes: Math.max(...allResources.map((r) => residency(r.contexts))), framebufferAllowanceBytesPerPixel: 16 };
  report.budgets = { ...budgets(rows), framePacing: framePacing(report.frameWindows), heap: report.soakElapsedMs >= 600000 && report.retainedGrowthBytes < 5000000, texture: report.texture.unknown.length === 0 && report.texture.peakBoundBytes <= 32 * 1024 * 1024 };
  if (!quick && (!Object.values(report.budgets).every(Boolean) || report.errors.length || !report.calibrationScreenshot.equal)) process.exitCode = 1;
  report.finished = new Date().toISOString(); save(); console.log(JSON.stringify({ output, budgets: report.budgets, retainedGrowthBytes: report.retainedGrowthBytes, texture: report.texture, errors: report.errors }, null, 2));
} catch (error) { report.failure = error.stack; save(); console.error(error); process.exitCode = 1; }
finally { await browser.close(); }
