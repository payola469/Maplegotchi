// @vitest-environment happy-dom
import { act, waitFor } from "@testing-library/preact";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { makeSnapshot } from "../test/fixtures";
import { mountLegacy } from "./legacy";
const mocks = vi.hoisted(() => ({
  snapshot: vi.fn(), room: vi.fn(), lifeEvents: vi.fn(), close: vi.fn(), open: vi.fn(),
  update: vi.fn(), destroy: vi.fn(), create: vi.fn(),
}));
vi.mock("../api/client", () => ({ createApiClient: () => ({ snapshot: mocks.snapshot }) }));
vi.mock("../api/read", () => ({ createReadApi: () => ({ room: mocks.room, lifeEvents: mocks.lifeEvents }) }));
vi.mock("../api/sse", () => ({ createStreamOpener: () => mocks.open }));
vi.mock("../room/scene/RoomScene", () => ({ createRoomScene: mocks.create }));
let root: HTMLDivElement;
let stop: (() => void) | undefined;
beforeEach(() => {
  vi.clearAllMocks();
  vi.stubGlobal("matchMedia", () => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() }));
  mocks.snapshot.mockResolvedValue(makeSnapshot()); mocks.room.mockResolvedValue(null);
  mocks.lifeEvents.mockResolvedValue({ events: [] }); mocks.open.mockReturnValue({ close: mocks.close });
  mocks.create.mockResolvedValue({ update: mocks.update, destroy: mocks.destroy, setReducedMotion: vi.fn() });
  root = document.createElement("div"); document.body.append(root);
});
afterEach(() => { stop?.(); stop = undefined; root.remove(); vi.unstubAllGlobals(); });
it("preserves Legacy bootstrap reads and Pixi initialization; disposal closes SSE, destroys the scene and removes pagehide", async () => {
  const remove = vi.spyOn(window, "removeEventListener");
  let resolve: (value: ReturnType<typeof makeSnapshot>) => void = () => undefined;
  mocks.snapshot.mockReturnValue(new Promise((done) => { resolve = done; }));
  await act(async () => { stop = mountLegacy(root); });
  await act(async () => resolve(makeSnapshot()));
  await waitFor(() => expect(mocks.update).toHaveBeenCalled());
  expect(mocks.snapshot).toHaveBeenCalledTimes(1); expect(mocks.room).toHaveBeenCalledTimes(1);
  expect(mocks.lifeEvents).toHaveBeenCalledWith(makeSnapshot().revision - 40);
  expect(mocks.create).toHaveBeenCalledTimes(1); expect(root.querySelector('.room__stage')).toBeTruthy();
  if (!stop) throw new Error("Legacy mount did not return its disposer");
  stop(); stop();
  expect(mocks.close).toHaveBeenCalledTimes(1); expect(mocks.destroy).toHaveBeenCalledTimes(1);
  expect(root.childNodes.length).toBe(0);
  expect(remove).toHaveBeenCalledWith("pagehide", expect.any(Function)); remove.mockRestore();
});
it("unsubscribes bootstrap reads before a pending snapshot resolves after rollback", async () => {
  let resolve: (value: ReturnType<typeof makeSnapshot>) => void = () => undefined;
  mocks.snapshot.mockReturnValue(new Promise((done) => { resolve = done; }));
  stop = mountLegacy(root); stop();
  await act(async () => resolve(makeSnapshot()));
  expect(mocks.lifeEvents).not.toHaveBeenCalled(); expect(mocks.create).not.toHaveBeenCalled();
  expect(root.childNodes.length).toBe(0);
});
