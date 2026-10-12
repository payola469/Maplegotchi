// Installed only by the Playwright harness, never imported by application code.
export function installProbe({ instrument = true } = {}) {
  const q = window.__r1a19 = { instrument, samples: [], updates: [], measuring: false, apps: 0, contexts: [], frames: new Set(), observers: new Set(), sse: 0, apiRequests: [], driver: false, moving: false, mode: 'overview', level: 1, unknownAllocations: [], activeListeners: new Map() };
  const raf = requestAnimationFrame, cancel = cancelAnimationFrame;
  window.requestAnimationFrame = (cb) => { const id = raf((t) => { q.frames.delete(id); cb(t); }); q.frames.add(id); return id; };
  window.cancelAnimationFrame = (id) => { q.frames.delete(id); cancel(id); };
  const RO = ResizeObserver;
  window.ResizeObserver = class extends RO { observe(...a) { q.observers.add(this); return super.observe(...a); } disconnect() { q.observers.delete(this); return super.disconnect(); } };
  for (const target of [window, document]) {
    const add = target.addEventListener, remove = target.removeEventListener;
    const listeners = new Map(); q.activeListeners.set(target === window ? 'window' : 'document', listeners);
    target.addEventListener = function(type, fn, options) { if (!options?.once) { let set = listeners.get(type); if (!set) listeners.set(type, set = new Set()); set.add(fn); } return add.call(this, type, fn, options); };
    target.removeEventListener = function(type, fn, options) { listeners.get(type)?.delete(fn); return remove.call(this, type, fn, options); };
  }
  const nativeFetch = fetch;
  window.fetch = async (url, options) => {
    const path = new URL(String(url), location.href).pathname;
    if (!path.startsWith('/api/')) return nativeFetch(url, options);
    q.apiRequests.push({ path, method: options?.method ?? 'GET' });
    if (options?.method && options.method !== 'GET') throw new Error('Benchmark rejects mutation requests');
    if (path === '/api/events') {
      q.sse++; let closed = false;
      const stream = new ReadableStream({ start(controller) { controller.enqueue(new TextEncoder().encode(': fixture keepalive\n\n')); options?.signal?.addEventListener('abort', () => { if (!closed) { closed = true; q.sse--; controller.close(); } }, { once: true }); }, cancel() { if (!closed) { closed = true; q.sse--; } } });
      return new Response(stream, { headers: { 'content-type': 'text/event-stream' } });
    }
    const data = path === '/api/snapshot' ? q.legacySnapshot : path === '/api/room' ? { width: 1000, height: 600, floor_y: 400, walk_speed: 120, furniture: [], points: [] } : path === '/api/life-events' ? { events: [], next_after_revision: null } : [];
    return new Response(JSON.stringify(data), { headers: { 'content-type': 'application/json' } });
  };
  const states = new WeakMap();
  const wrap = (object, name, before) => { const fn = object[name]; if (typeof fn !== 'function') return; object[name] = function(...args) { before(...args); return fn.apply(this, args); }; };
  function setup(gl, kind) {
    if (states.has(gl)) return gl;
    const extension = gl.getExtension('WEBGL_debug_renderer_info');
    const state = { kind, renderer: extension ? gl.getParameter(extension.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER), vendor: extension ? gl.getParameter(extension.UNMASKED_VENDOR_WEBGL) : gl.getParameter(gl.VENDOR), attributes: gl.getContextAttributes(), draws: 0, allocations: new Map(), lost: false, width: gl.drawingBufferWidth, height: gl.drawingBufferHeight };
    q.contexts.push(state); states.set(gl, state);
    const ids = new WeakMap(); let serial = 0, active = gl.TEXTURE0, renderbuffer = null; const bindings = new Map();
    const id = (o) => { if (!o) return 0; if (!ids.has(o)) ids.set(o, ++serial); return ids.get(o); };
    const texture = (target) => bindings.get(`${active}/${target >= 34069 && target <= 34074 ? gl.TEXTURE_CUBE_MAP : target}`);
    const bytesPerPixel = (format, type) => {
      if ([gl.RGBA, gl.RGBA8, gl.RGB, gl.RGB8, gl.DEPTH24_STENCIL8, gl.DEPTH_COMPONENT16, gl.DEPTH_COMPONENT24, gl.R8, gl.RG8].includes(format) && (!type || [gl.UNSIGNED_BYTE, gl.UNSIGNED_SHORT, gl.UNSIGNED_INT, gl.UNSIGNED_INT_24_8].includes(type))) return 4;
      if ([gl.RGBA16F, gl.RGBA32F].includes(format)) return 16;
      q.unknownAllocations.push({ format, type }); return 16;
    };
    function allocate(key, width, height, format, type, samples = 1, depth = 1) { if (!key || !Number.isFinite(width * height)) { q.unknownAllocations.push({ key, width, height }); return; } state.allocations.set(key, { width, height, format, type, samples, depth, bytes: width * height * depth * bytesPerPixel(format, type) * Math.max(1, samples) }); }
    for (const name of ['drawArrays', 'drawElements', 'drawArraysInstanced', 'drawElementsInstanced']) wrap(gl, name, () => state.draws++);
    wrap(gl, 'activeTexture', (unit) => active = unit);
    wrap(gl, 'bindTexture', (target, object) => bindings.set(`${active}/${target}`, id(object)));
    wrap(gl, 'texImage2D', (target, level, internal, ...a) => { const width = a.length >= 6 ? a[0] : a[2]?.width, height = a.length >= 6 ? a[1] : a[2]?.height, type = a.length >= 6 ? a[4] : a[1]; allocate(`t${texture(target)}/${target}/${level}`, width, height, internal, type); });
    wrap(gl, 'texStorage2D', (target, levels, internal, width, height) => { for (let level = 0; level < levels; level++) allocate(`t${texture(target)}/${target}/${level}`, Math.max(1, width >> level), Math.max(1, height >> level), internal); });
    for (const name of ['texImage3D', 'texStorage3D', 'compressedTexImage2D', 'compressedTexImage3D', 'generateMipmap']) wrap(gl, name, () => q.unknownAllocations.push({ unsupported: name }));
    wrap(gl, 'deleteTexture', (object) => { const prefix = `t${id(object)}/`; for (const key of state.allocations.keys()) if (key.startsWith(prefix)) state.allocations.delete(key); });
    wrap(gl, 'bindRenderbuffer', (_target, object) => renderbuffer = id(object));
    wrap(gl, 'renderbufferStorage', (_target, format, width, height) => allocate(`r${renderbuffer}`, width, height, format));
    wrap(gl, 'renderbufferStorageMultisample', (_target, samples, format, width, height) => allocate(`r${renderbuffer}`, width, height, format, undefined, samples));
    wrap(gl, 'deleteRenderbuffer', (object) => state.allocations.delete(`r${id(object)}`));
    gl.canvas.addEventListener('webglcontextlost', () => { state.lost = true; state.allocations.clear(); });
    return gl;
  }
  for (const T of [HTMLCanvasElement, globalThis.OffscreenCanvas].filter(Boolean)) { const get = T.prototype.getContext; T.prototype.getContext = function(kind, ...args) { const context = get.call(this, kind, ...args); return context && /webgl/.test(kind) ? setup(context, kind) : context; }; }
  q.attach = (app) => {
    q.apps++; const renderer = app.renderer, original = renderer.render, state = states.get(renderer.gl);
    if (!state) throw new Error('WebGL renderer instrumentation unavailable');
    q.inspect = () => { let children = 0; const walk = (node) => { children++; for (const child of node.children ?? []) walk(child); }; walk(app.stage); return { children, width: renderer.gl.drawingBufferWidth, height: renderer.gl.drawingBufferHeight }; };
    if (instrument) renderer.render = function(...args) { state.draws = 0; const began = performance.now(); const result = original.apply(this, args); const cost = performance.now() - began; state.width = renderer.gl.drawingBufferWidth; state.height = renderer.gl.drawingBufferHeight; if (q.measuring) q.samples.push([cost, state.draws]); return result; };
  };
  q.detached = () => { q.apps--; q.inspect = null; };
  q.update = (work) => { const began = performance.now(); const value = work(); if (q.measuring) q.updates.push(performance.now() - began); return value; };
  q.resources = () => ({ apps: q.apps, canvases: document.querySelectorAll('canvas').length, raf: q.frames.size, observers: q.observers.size, sse: q.sse, listeners: [...q.activeListeners].map(([name, types]) => [name, [...types.values()].reduce((n, set) => n + set.size, 0)]), contexts: q.contexts.map((c) => ({ kind: c.kind, renderer: c.renderer, attributes: c.attributes, lost: c.lost, width: c.width, height: c.height, allocations: [...c.allocations.values()] })), unknownAllocations: q.unknownAllocations, stage: q.inspect?.(), visibility: document.visibilityState });
  q.set = (label, value) => { const e = [...document.querySelectorAll('label')].find((l) => l.textContent.includes(label))?.querySelector('select,input'); if (!e || e.disabled) return; e.value = String(value); e.dispatchEvent(new Event(e.tagName === 'SELECT' ? 'change' : 'input', { bubbles: true })); };
  q.beginDriver = () => { q.driver = true; const began = performance.now(); const tick = (now) => { if (!q.driver) return; if (q.moving) { const input = document.querySelector('input[type=range]'); if (input && !input.disabled) { input.value = String(Math.floor((now - began) % Number(input.max))); input.dispatchEvent(new Event('input', { bubbles: true })); } } q.driverId = requestAnimationFrame(tick); }; q.driverId = requestAnimationFrame(tick); };
  q.endDriver = () => { q.driver = false; cancelAnimationFrame(q.driverId); };
}
