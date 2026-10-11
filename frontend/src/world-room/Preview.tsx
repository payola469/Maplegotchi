import { useEffect, useRef, useState } from "preact/hooks";
import { useReducedMotion } from "../ui/hooks";
import { fixtureCatalog, fixtureWorlds } from "./fixtures";
import { actorSample } from "./presentation";
import type { CreateWorldScene, WorldScene } from "./scene";
import "./preview.css";

const defaultScene: CreateWorldScene = async (host, options) => (await import("./scene")).createWorldScene(host, options);
export function WorldPreview({ createScene = defaultScene }: { createScene?: CreateWorldScene }) {
  const [scenario, setScenario] = useState<"idle" | "walking">("idle");
  const world = fixtureWorlds[scenario];
  const [elapsed, setElapsed] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [status, setStatus] = useState("Loading fixture renderer…");
  const [unavailable, setUnavailable] = useState(false);
  const reduced = useReducedMotion();
  const host = useRef<HTMLDivElement>(null), scene = useRef<WorldScene | null>(null);
  const route = world.snapshot.maple.route;
  const start = route ? Date.parse(route.departed_at) : Date.parse(world.snapshot.generated_at);
  const duration = route ? Date.parse(route.arrives_at) - start : 0;
  const timeMs = start + Math.min(elapsed, duration);
  const latest = useRef({ world, timeMs }); latest.current = { world, timeMs };
  useEffect(() => {
    const element = host.current;
    if (!element) return;
    const controller = new AbortController();
    let owned: WorldScene | null = null;
    void createScene(element, { frame: latest.current, catalog: fixtureCatalog, signal: controller.signal, onOverviewUnavailable: setUnavailable }).then((handle) => {
      if (controller.signal.aborted) { handle.destroy(); return; }
      owned = handle; scene.current = handle; handle.update(latest.current); setStatus("Synthetic fixture renderer ready — packed placeholder atlases; owner acceptance pending.");
    }).catch(() => {
      if (!controller.signal.aborted) {
        owned?.destroy(); scene.current = null; controller.abort();
        setStatus("Renderer unavailable. Use the accessible fixture summary below; WebGL or test assets could not initialize.");
      }
    });
    return () => { controller.abort(); owned?.destroy(); if (scene.current === owned) scene.current = null; };
  }, [createScene]);
  useEffect(() => { scene.current?.update({ world, timeMs }); }, [world, timeMs]);
  useEffect(() => {
    if (!playing || reduced || !route) return;
    const began = performance.now(), offset = elapsed;
    let id = 0;
    const tick = (now: number) => {
      const next = Math.min(duration, offset + now - began);
      setElapsed(next);
      if (next < duration) id = requestAnimationFrame(tick); else setPlaying(false);
    };
    id = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(id);
    // Playback clock begins once per explicit Play; time updates do not restart it.
  }, [playing, reduced, scenario, duration, route]);
  const sample = actorSample(world, timeMs);
  const room = world.regions.find((r) => sample.x >= r.floor.x * world.grid.tile_size_px && sample.x < (r.floor.x + r.floor.w) * world.grid.tile_size_px && sample.y >= r.floor.y * world.grid.tile_size_px && sample.y < (r.floor.y + r.floor.h) * world.grid.tile_size_px);
  return <main class="world-preview">
    <h1>Maple Room development preview</h1>
    <p class="world-preview__disclosure"><strong>FIXTURE / DEMO DATA — not live Maple.</strong> Checked-in R1A-10 synthetic data only. No API, database or SSE connection.</p>
    <nav><a href="/">Return to legacy Room</a></nav>
    <fieldset><legend>Deterministic fixture controls (DOM)</legend>
      <label>Scenario <select value={scenario} onChange={(e) => { setScenario(e.currentTarget.value as "idle" | "walking"); setElapsed(0); setPlaying(false); }}><option value="idle">Idle</option><option value="walking">Walking</option></select></label>
      <label>Route time (milliseconds) <input type="range" min="0" max={duration} step="1" value={elapsed} disabled={!route} onInput={(e) => { setElapsed(Number(e.currentTarget.value)); setPlaying(false); }} /></label>
      <button type="button" disabled={!route || reduced || elapsed >= duration} onClick={() => setPlaying(!playing)}>{playing ? "Pause" : "Play fixture route"}</button>
      <button type="button" onClick={() => { setElapsed(0); setPlaying(false); }}>Reset time</button>
    </fieldset>
    <p role="status">{status}</p>
    {reduced && <p>Reduced motion: playback is disabled. Select a fixed route time to inspect a snapped frame.</p>}
    <div ref={host} class="world-preview__host" />
    {unavailable && <p>Overview cannot fit at locked integer zoom. Use the room list below; camera navigation belongs to R1A-12.</p>}
    <section aria-label="Accessible fixture description">
      <h2>Canonical house fixture</h2>
      <p>{world.grid.width_tiles} × {world.grid.height_tiles} tiles; {world.regions.length} regions; {world.doors.length} doors; {world.objects.length} objects; {world.points.length} interaction points; {world.slots.length} slots; {world.walkable.length} backend walkable cells.</p>
      <p>Maple: {room?.id ?? "backend passage"}; {sample.facing}; {world.snapshot.maple.expression}; {sample.moving ? "walking" : "stationary"}; feet ({sample.x.toFixed(2)}, {sample.y.toFixed(2)}), frame {sample.moving ? sample.frame : 0}. Fixture time {new Date(timeMs).toISOString()}.</p>
      <ul>{world.regions.map((r) => <li key={r.id} aria-current={r.id === room?.id ? "location" : undefined}>{r.id} — {r.status}{r.id === room?.id ? " — Maple is here" : ""}</li>)}</ul>
      <p>Placeholder sprites, face size and palette are provisional. Final production art, camera modes, lighting and interaction behavior remain separate workstreams.</p>
    </section>
  </main>;
}
