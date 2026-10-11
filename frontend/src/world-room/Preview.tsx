import { useEffect, useMemo, useRef, useState } from "preact/hooks";
import { useReducedMotion } from "../ui/hooks";
import { fixtureCatalog, fixtureWorlds } from "./fixtures";
import { currentRegion, type CameraMode, type CameraRequest, type LogicalZoom } from "./camera";
import { DAY_PHASES } from "./lighting";
import type { DayPhase } from "../api/world.generated";
import { actorSample } from "./presentation";
import type { CreateWorldScene, WorldScene } from "./scene";
import "./preview.css";

// Provisional development test setting; no product default is selected here.
export const PREVIEW_FOLLOW_LEVEL: LogicalZoom = 2;
const defaultScene: CreateWorldScene = async (host, options) => (await import("./scene")).createWorldScene(host, options);
export function WorldPreview({ createScene = defaultScene }: { createScene?: CreateWorldScene }) {
  const [scenario, setScenario] = useState<"idle" | "walking">("idle");
  const [phase, setPhase] = useState<DayPhase>(fixtureWorlds.idle.snapshot.day_phase);
  const sourceWorld = fixtureWorlds[scenario];
  const world = useMemo(() => ({ ...sourceWorld, snapshot: { ...sourceWorld.snapshot, day_phase: phase } }), [sourceWorld, phase]);
  const [elapsed, setElapsed] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [status, setStatus] = useState("Loading fixture renderer…");
  const [unavailable, setUnavailable] = useState(false);
  const reduced = useReducedMotion();
  const [mode, setMode] = useState<CameraMode>("overview");
  const [level, setLevel] = useState<LogicalZoom>(PREVIEW_FOLLOW_LEVEL);
  const [regionId, setRegionId] = useState("central_hall");
  const camera: CameraRequest = { mode, level, regionId, reducedMotion: reduced };
  const host = useRef<HTMLDivElement>(null), scene = useRef<WorldScene | null>(null);
  const route = world.snapshot.maple.route;
  const start = route ? Date.parse(route.departed_at) : Date.parse(world.snapshot.generated_at);
  const duration = route ? Date.parse(route.arrives_at) - start : 0;
  const timeMs = start + Math.min(elapsed, duration);
  const latest = useRef({ world, timeMs, camera }); latest.current = { world, timeMs, camera };
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
  useEffect(() => { scene.current?.update({ world, timeMs, camera }); }, [world, timeMs, mode, level, regionId, reduced]);
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
  const roomId = currentRegion(world, sample);
  const room = world.regions.find((r) => r.id === roomId);
  return <main class="world-preview">
    <h1>Maple Room development preview</h1>
    <p class="world-preview__disclosure"><strong>FIXTURE / DEMO DATA — not live Maple.</strong> Checked-in R1A-10 synthetic data only. No API, database or SSE connection.</p>
    <nav><a href="/">Return to legacy Room</a></nav>
    <fieldset><legend>Deterministic fixture controls (DOM)</legend>
      <label>Fixture lighting phase (provisional) <select value={phase} onChange={(e) => setPhase(e.currentTarget.value as DayPhase)}>{DAY_PHASES.map((p) => <option value={p} key={p}>{p}</option>)}</select></label>
      <label>Scenario <select value={scenario} onChange={(e) => { setScenario(e.currentTarget.value as "idle" | "walking"); setElapsed(0); setPlaying(false); }}><option value="idle">Idle</option><option value="walking">Walking</option></select></label>
      <label>Route time (milliseconds) <input type="range" min="0" max={duration} step="1" value={elapsed} disabled={!route} onInput={(e) => { setElapsed(Number(e.currentTarget.value)); setPlaying(false); }} /></label>
      <button type="button" disabled={!route || reduced || elapsed >= duration} onClick={() => setPlaying(!playing)}>{playing ? "Pause" : "Play fixture route"}</button>
      <button type="button" onClick={() => { setElapsed(0); setPlaying(false); }}>Reset time</button>
    </fieldset>
    <fieldset><legend>Camera controls (presentation only)</legend>
      <label>Camera mode <select value={mode} onChange={(e) => setMode(e.currentTarget.value as CameraMode)}><option value="overview">Overview</option><option value="follow">Follow</option><option value="focus">Focus</option></select></label>
      <label>Follow zoom — provisional test setting <select value={level} disabled={mode !== "follow"} onChange={(e) => setLevel(Number(e.currentTarget.value) as LogicalZoom)}>{([1, 2, 3, 4] as const).map((l) => <option key={l} value={l}>L{l}</option>)}</select></label>
      <label>Focus region <select value={regionId} disabled={mode !== "focus"} onChange={(e) => setRegionId(e.currentTarget.value)}>{world.regions.map((r) => <option key={r.id} value={r.id}>{r.id} — {r.status}</option>)}</select></label>
    </fieldset>
    <p>Overview and Focus select the largest fitting L1–L4. Default zoom by form factor is undecided.</p>
    <p role="status">{status}</p>
    {reduced && <p>Reduced motion: playback is disabled. Select a fixed route time to inspect a snapped frame.</p>}
    <div class={`world-preview__viewport${unavailable && mode === "overview" ? " world-preview__viewport--fallback" : ""}`}>
      <div ref={host} class="world-preview__host" />
      <nav aria-label="Room navigation">
        <ul aria-label="Canonical rooms">{world.regions.map((r) => <li key={r.id}><button type="button" aria-label={`Focus ${r.id} (${r.status})`} aria-current={r.id === room?.id ? "location" : undefined} onClick={() => { setRegionId(r.id); setMode("focus"); }}>{r.id} — {r.status}{r.id === room?.id ? " — Maple is here" : ""}</button></li>)}</ul>
      </nav>
    </div>
    {unavailable && <p>Overview cannot fit at locked integer zoom. Use the room list; select a room to Focus or switch to Follow.</p>}
    <section aria-label="Accessible fixture description">
      <h2>Canonical house fixture</h2>
      <p>{world.grid.width_tiles} × {world.grid.height_tiles} tiles; {world.regions.length} regions; {world.doors.length} doors; {world.objects.length} objects; {world.points.length} interaction points; {world.slots.length} slots; {world.walkable.length} backend walkable cells.</p>
      <p>Maple: {room?.id ?? "backend passage"}; {sample.facing}; {world.snapshot.maple.expression}; {sample.moving ? "walking" : "stationary"}; feet ({sample.x.toFixed(2)}, {sample.y.toFixed(2)}), frame {sample.moving ? sample.frame : 0}. Fixture time {new Date(timeMs).toISOString()}. Synthetic lighting phase {phase}; provisional presets.</p>
      <p>Placeholder sprites, face size and palette are provisional. Final production art, lighting and interaction behavior remain separate workstreams.</p>
    </section>
  </main>;
}
