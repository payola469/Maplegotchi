// Local production/dev default isolation with offline read-only Legacy responses.
import fs from 'node:fs';
import { browserRuntime } from './runtime.mjs';
const runtime = browserRuntime();
const browser = await runtime.chromium.launch(runtime.launch);
const args = process.argv.slice(2);
const output = args.includes('--output') ? args[args.indexOf('--output') + 1] : '../var/r1a19/isolation.json';
const rows = [];
try {
  const seed = await browser.newPage();
  await seed.goto('http://127.0.0.1:5179/?room=fixture');
  await seed.getByRole('status', { name: 'Fixture renderer' }).filter({ hasText: 'renderer ready' }).waitFor();
  const snapshot = await seed.evaluate(async () => (await import('/src/test/fixtures.ts')).makeSnapshot());
  await seed.close();
  const context = await browser.newContext();
  await context.addInitScript((snapshot) => {
    const native = fetch; window.__isolation = { api: [], contexts: [] };
    const get = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function(kind, ...args) { const gl = get.call(this, kind, ...args); if (gl && /webgl/.test(kind)) window.__isolation.contexts.push(kind); return gl; };
    window.fetch = async (url, options) => {
      const name = new URL(String(url), location.href).pathname;
      if (!name.startsWith('/api/')) return native(url, options);
      window.__isolation.api.push([name, options?.method ?? 'GET']);
      if (options?.method && options.method !== 'GET') throw Error('No mutations in isolation QA');
      if (name === '/api/events') return new Response(new ReadableStream({ start(c) { c.enqueue(new TextEncoder().encode(': synthetic keepalive\n\n')); options?.signal?.addEventListener('abort', () => c.close(), { once: true }); } }), { headers: { 'content-type': 'text/event-stream' } });
      // Allow initial Legacy passive subscriptions to mount before synthetic delivery.
      await new Promise((resolve) => setTimeout(resolve, 250));
      return new Response(JSON.stringify(name === '/api/snapshot' ? snapshot : name === '/api/room' ? { width: 1000, height: 600, floor_y: 400, walk_speed: 120, furniture: [], points: [] } : { events: [], next_after_revision: null }), { headers: { 'content-type': 'application/json' } });
    };
  }, snapshot);
  for (const url of ['http://127.0.0.1:5179/', 'http://127.0.0.1:5180/', 'http://127.0.0.1:5180/?room=fixture', 'http://127.0.0.1:5180/room/new?room=fixture']) {
    const page = await context.newPage(), errors = [], modules = [];
    page.on('pageerror', (e) => errors.push(e.message));
    page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
    page.on('response', (r) => { if (r.status() >= 400) errors.push(`${r.status()} ${r.url()}`); });
    page.on('request', (r) => { if (/world-room\/(?:scene|Preview|fixtures|atlas)\.|docs\/fixtures/.test(r.url()) || (url.includes(':5180/') && /RoomSwitcher/.test(r.url()))) modules.push(r.url()); });
    await page.goto(url);
    try { await page.waitForSelector('canvas', { timeout: 10000 }); } catch (error) { console.log(JSON.stringify({url,errors,modules,body:await page.locator('body').innerText(),api:await page.evaluate(()=>window.__isolation)},null,2)); throw error; }
    await page.waitForTimeout(1500);
    const facts = await page.evaluate(() => ({ ...window.__isolation, canvases: document.querySelectorAll('canvas').length, fixture: !!document.querySelector('.world-preview'), switcher: !!document.querySelector('.room-switcher'), horizontalOverflow: document.documentElement.scrollWidth > innerWidth }));
    rows.push({ url, ...facts, modules, errors, pass: facts.canvases === 1 && !facts.fixture && !facts.horizontalOverflow && modules.length === 0 && errors.length === 0 });
    await page.close();
  }
  fs.writeFileSync(output, JSON.stringify({ chrome: browser.version(), rows }, null, 2) + '\n');
  console.log(JSON.stringify(rows, null, 2));
  if (rows.some((r) => !r.pass)) process.exitCode = 1;
} finally { await browser.close(); }
