// @vitest-environment happy-dom
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/preact";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { CreateWorldScene, SceneFrame, WorldScene } from "./scene";
import { WorldPreview } from "./Preview";

beforeEach(() => { vi.stubGlobal("matchMedia", () => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() })); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
function fake() {
  const updates: SceneFrame[] = [];
  const handle: WorldScene = { update: (value) => void updates.push(value), destroy: vi.fn() };
  const create = vi.fn<CreateWorldScene>(async () => handle);
  return { handle, create, updates };
}
describe("fixture-only DOM preview", () => {
  it("mounts once, updates selected fixtures and cleans up", async () => {
    const f = fake(); const view = render(<WorldPreview createScene={f.create} />);
    await screen.findByText(/Synthetic fixture renderer ready/);
    expect(screen.getByText(/FIXTURE \/ DEMO DATA/)).toBeTruthy();
    expect(screen.getByText(/44 × 26 tiles; 8 regions; 7 doors; 28 objects/)).toBeTruthy();
    expect(screen.getByRole("link", { name: "Return to legacy Room" }).getAttribute("href")).toBe("/");
    fireEvent.change(screen.getByRole("combobox", { name: "Scenario" }), { target: { value: "walking" } });
    fireEvent.input(screen.getByRole("slider"), { target: { value: "125" } });
    await waitFor(() => expect(f.updates.at(-1)?.timeMs).toBe(Date.parse("2026-10-11T00:00:00Z") + 125));
    expect(f.create).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "Play fixture route" })).toBeTruthy();
    expect(screen.getByText(/right; calm; walking/)).toBeTruthy();
    view.unmount(); expect(f.handle.destroy).toHaveBeenCalledTimes(1);
    expect(f.create.mock.calls[0]?.[1].signal.aborted).toBe(true);
  });
  it("disposes a renderer resolving after unmount without updating it", async () => {
    const f = fake(); let resolve: (value: WorldScene) => void = () => undefined;
    const create = vi.fn<CreateWorldScene>(() => new Promise((done) => { resolve = done; }));
    const view = render(<WorldPreview createScene={create} />); view.unmount();
    await act(async () => resolve(f.handle));
    expect(f.handle.destroy).toHaveBeenCalledTimes(1); expect(f.updates).toHaveLength(0);
  });
  it("has accessible initialization failure and preserves the full DOM description", async () => {
    render(<WorldPreview createScene={async () => { throw new Error("WebGL unavailable"); }} />);
    expect(screen.getByRole("status").textContent).toContain("Loading");
    await screen.findByText(/Renderer unavailable/);
    expect(screen.getByRole("region", { name: "Accessible fixture description" })).toBeTruthy();
  });
  it("provides the locked narrow Overview fallback with Maple highlighted", async () => {
    const f = fake(); render(<WorldPreview createScene={async (host, options) => { options.onOverviewUnavailable(true); return f.create(host, options); }} />);
    await screen.findByText(/Overview cannot fit/);
    expect(screen.getByText(/central_hall — open — Maple is here/).getAttribute("aria-current")).toBe("location");
  });
  it("disables automatic playback under reduced motion but supports fixed-time inspection", async () => {
    vi.stubGlobal("matchMedia", () => ({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() }));
    const f = fake(); render(<WorldPreview createScene={f.create} />);
    await screen.findByText(/Synthetic fixture renderer ready/);
    fireEvent.change(screen.getByRole("combobox", { name: "Scenario" }), { target: { value: "walking" } });
    expect((screen.getByRole("button", { name: "Play fixture route" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.input(screen.getByRole("slider"), { target: { value: "1000" } });
    expect(screen.getByText(/Reduced motion: playback is disabled/)).toBeTruthy();
    expect(f.updates.at(-1)?.timeMs).toBe(Date.parse("2026-10-11T00:00:01Z"));
  });
});

it("camera controls update presentation only and room buttons support keyboard activation", async () => {
  const f = fake(); render(<WorldPreview createScene={f.create} />); await screen.findByText(/Synthetic fixture renderer ready/);
  const mode = screen.getByRole("combobox", { name: "Camera mode" });
  const zoom = screen.getByRole("combobox", { name: /Follow zoom/ });
  expect((zoom as HTMLSelectElement).disabled).toBe(true);
  fireEvent.change(mode, { target: { value: "follow" } });
  fireEvent.change(zoom, { target: { value: "4" } });
  expect(f.updates.at(-1)?.camera).toMatchObject({ mode: "follow", level: 4 });
  const target = screen.getByRole("button", { name: "Focus creation_room (closed)" });
  target.focus(); fireEvent.click(target); // Native button Enter/Space activation is browser-verified.
  expect(document.activeElement).toBe(target);
  expect(f.updates.at(-1)?.camera).toMatchObject({ mode: "focus", regionId: "creation_room" });
  expect(f.create).toHaveBeenCalledTimes(1); expect(f.updates.at(-1)?.world.snapshot.maple.position).toEqual(f.updates[0]?.world.snapshot.maple.position);
  expect(screen.getByText(/Default zoom by form factor is undecided/)).toBeTruthy();
});
it("updates reduced-motion camera requests from the subscribed media query and removes listeners", async () => {
  let notify: () => void = () => undefined;
  const media = { matches: false, addEventListener: vi.fn((_event: string, cb: () => void) => { notify = cb; }), removeEventListener: vi.fn() };
  vi.stubGlobal("matchMedia", () => media);
  const f = fake(); const rendered = render(<WorldPreview createScene={f.create} />); await screen.findByText(/Synthetic fixture renderer ready/);
  await act(async () => { media.matches = true; notify(); });
  expect(f.updates.at(-1)?.camera?.reducedMotion).toBe(true);
  rendered.unmount(); expect(media.removeEventListener).toHaveBeenCalled();
});

it("selects four explicitly synthetic lighting phases without remounting",async()=>{
  const f=fake();render(<WorldPreview createScene={f.create}/>);await screen.findByText(/Synthetic fixture renderer ready/);
  for(const phase of ["night","morning","afternoon","evening"]){
    fireEvent.change(screen.getByRole("combobox",{name:/Fixture lighting phase/}),{target:{value:phase}});
    expect(f.updates.at(-1)?.world.snapshot.day_phase).toBe(phase);
    expect(f.updates.at(-1)?.world.source).toBe("development_fixture");
  }
  expect(f.create).toHaveBeenCalledTimes(1);
});
