// @vitest-environment happy-dom
import { render as mount } from "preact";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/preact";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../ui/App";
import { Store } from "../state/store";
import { makeSnapshot } from "../test/fixtures";
import { WorldPreview } from "../world-room/Preview";
import { fixturePreviewEnabled } from "../world-room/gate";
import type { CreateWorldScene, WorldScene } from "../world-room/scene";
import type { RoomSceneHandle } from "../room/scene/RoomScene";
import { RoomSwitcher, type LoadFixture } from "./RoomSwitcher";

beforeEach(() => {
  window.history.replaceState(null, "", "/");
  vi.stubGlobal("matchMedia", () => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() }));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

function harness() {
  const legacyScenes: RoomSceneHandle[] = [];
  const worldScenes: WorldScene[] = [];
  const signals: AbortSignal[] = [];
  const worldFactory = vi.fn<CreateWorldScene>(async (_host, options) => {
    signals.push(options.signal);
    const handle: WorldScene = { update: vi.fn(), destroy: vi.fn() };
    worldScenes.push(handle); return handle;
  });
  const legacyFactory = vi.fn(async () => {
    const handle = { update: vi.fn(), setReducedMotion: vi.fn(), destroy: vi.fn() };
    legacyScenes.push(handle); return handle;
  });
  const store = new Store(); store.applySnapshot(makeSnapshot()); store.setStatus("live");
  const legacy = vi.fn((host: HTMLElement) => {
    mount(<App store={store} createScene={legacyFactory} onInteract={() => undefined} onRefresh={() => undefined} />, host);
    return () => mount(null, host);
  });
  const loader = vi.fn<LoadFixture>(async () => (host, onLegacy) => {
    mount(<WorldPreview createScene={worldFactory} onReturnLegacy={onLegacy} />, host);
    return () => mount(null, host);
  });
  return { legacy, loader, legacyFactory, legacyScenes, worldFactory, worldScenes, signals, store };
}
const choose = (value: string) => fireEvent.change(screen.getByRole("combobox", { name: "Development Room view" }), { target: { value } });

describe("closed development flag", () => {
  it.each(["", "?room=legacy", "?room=off", "?room=true", "?room=Fixture", "?room=fixture%00", "?room=fixture&room=legacy", "?room=legacy&room=fixture", "?room=fixture&room=fixture", "?room=%E0%A4%A", "?preview=fixture", "?room=/world-room/Preview"]) ("defaults invalid/off %s to Legacy", (query) => {
    expect(fixturePreviewEnabled(true, query)).toBe(false);
  });
  it.each(["", "?room=fixture", "?room=fixture&dev=true", "?room=fixture&PROD=false"]) ("production rejects %s", (query) => {
    expect(fixturePreviewEnabled(false, query)).toBe(false);
  });
  it("accepts only an exact development fixture flag", () => expect(fixturePreviewEnabled(true, "?room=fixture")).toBe(true));
  it("mounts functional Legacy Pixi and identical Legacy DOM by default, without loading any new renderer", async () => {
    const h = harness();
    const directHost = document.createElement("div"); document.body.append(directHost);
    const stop = h.legacy(directHost); await waitFor(() => expect(h.legacyFactory).toHaveBeenCalledTimes(1));
    const expected = directHost.innerHTML; stop(); directHost.remove();
    const view = render(<RoomSwitcher mountLegacy={h.legacy} loadPreview={h.loader} search="" />);
    await waitFor(() => expect(h.legacyFactory).toHaveBeenCalledTimes(2));
    expect(view.container.lastElementChild?.innerHTML).toBe(expected);
    expect(h.loader).not.toHaveBeenCalled(); expect(h.worldFactory).not.toHaveBeenCalled();
    expect(h.legacyScenes.at(-1)?.update).toHaveBeenCalled();
    view.unmount(); expect(h.legacyScenes.at(-1)?.destroy).toHaveBeenCalledTimes(1);
  });
  it("cannot mount fixtures when development is false even with direct query and injected loader", async () => {
    const h = harness(); render(<RoomSwitcher development={false} search="?room=fixture" mountLegacy={h.legacy} loadPreview={h.loader} />);
    await waitFor(() => expect(h.legacyFactory).toHaveBeenCalledTimes(1));
    expect(screen.queryByRole("navigation", { name: "Development Room view" })).toBeNull();
    expect(h.loader).not.toHaveBeenCalled(); expect(h.worldFactory).not.toHaveBeenCalled();
  });
});

it.each(["", "?room=fixture"])("repeated round trips from %s own one scene, preserve selector focus and clean up each mount", async (search) => {
  const h = harness(); const view = render(<RoomSwitcher search={search} mountLegacy={h.legacy} loadPreview={h.loader} />);
  if (search) await screen.findByText(/Synthetic fixture renderer ready/);
  else await waitFor(() => expect(h.legacyFactory).toHaveBeenCalledTimes(1));
  const selector = screen.getByRole("combobox", { name: "Development Room view" }); selector.focus();
  for (let i = 0; i < 4; i++) {
    choose("fixture"); await screen.findByText(/Synthetic fixture renderer ready/);
    expect(document.activeElement).toBe(selector);
    expect(screen.getByText(/FIXTURE.*DEMO DATA/)).toBeTruthy();
    expect(screen.queryByTestId("room-summary")).toBeNull();
    choose("legacy"); await waitFor(() => expect(screen.getByTestId("room-summary")).toBeTruthy());
    expect(document.activeElement).toBe(selector);
    expect(h.signals.every((signal) => signal.aborted)).toBe(true);
    expect(h.worldScenes.every((scene) => vi.mocked(scene.destroy).mock.calls.length === 1)).toBe(true);
  }
  view.unmount();
  expect(h.legacyScenes.every((scene) => vi.mocked(scene.destroy).mock.calls.length === 1)).toBe(true);
});

it("cancels an unresolved fixture import on rollback, then safely remounts", async () => {
  const h = harness(); let resolve: (mount: Awaited<ReturnType<LoadFixture>>) => void = () => undefined;
  const pending = vi.fn<LoadFixture>(() => new Promise((done) => { resolve = done; }));
  render(<RoomSwitcher search="?room=fixture" mountLegacy={h.legacy} loadPreview={pending} />);
  await waitFor(() => expect(pending).toHaveBeenCalledTimes(1)); choose("legacy");
  const lateMount = vi.fn(() => vi.fn()); await act(async () => resolve(lateMount));
  expect(lateMount).not.toHaveBeenCalled(); expect(h.legacy).toHaveBeenCalledTimes(1);
  choose("fixture"); await waitFor(() => expect(pending).toHaveBeenCalledTimes(2));
  await act(async () => resolve(lateMount)); expect(lateMount).toHaveBeenCalledTimes(1);
});
it("returns through the DOM button and restores focus to the persistent selector", async () => {
  const h = harness(); render(<RoomSwitcher search="?room=fixture" mountLegacy={h.legacy} loadPreview={h.loader} />);
  await screen.findByText(/Synthetic fixture renderer ready/);
  fireEvent.click(screen.getByRole("button", { name: "Return to legacy Room" }));
  await waitFor(() => expect(h.legacy).toHaveBeenCalledTimes(1));
  expect(document.activeElement).toBe(screen.getByRole("combobox", { name: "Development Room view" }));
  expect(window.location.search).toBe("");
});
it("offers rollback after failed import, and removes its history listener on unmount", async () => {
  const h = harness(); const remove = vi.spyOn(window, "removeEventListener");
  const view = render(<RoomSwitcher search="?room=fixture" mountLegacy={h.legacy} loadPreview={async () => { throw new Error("offline module"); }} />);
  await screen.findByRole("alert"); choose("legacy"); await waitFor(() => expect(h.legacy).toHaveBeenCalledTimes(1));
  expect(screen.queryByRole("alert")).toBeNull();
  view.unmount(); expect(remove).toHaveBeenCalledWith("popstate", expect.any(Function)); remove.mockRestore();
});
