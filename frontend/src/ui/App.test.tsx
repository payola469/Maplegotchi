// @vitest-environment happy-dom
import { act, cleanup, fireEvent, render, screen } from "@testing-library/preact";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { CreateRoomScene, RoomSceneHandle } from "../room/scene/RoomScene";
import type { VisualState } from "../room/visual";
import { Store } from "../state/store";
import { T0_MS, iso, makeSnapshot, observation } from "../test/fixtures";
import { App } from "./App";

// The Pixi scene is replaced by a recording fake: DOM tests never load Pixi and
// never compare pixels.
function fakeScene() {
  const updates: VisualState[] = [];
  const handle: RoomSceneHandle & { reduced: boolean[]; destroyed: number } = {
    reduced: [],
    destroyed: 0,
    update: (v) => void updates.push(v),
    setReducedMotion: (r) => void handle.reduced.push(r),
    destroy: () => void (handle.destroyed += 1),
  };
  const create = vi.fn<CreateRoomScene>(async () => handle);
  return { create, handle, updates };
}

let now = T0_MS;
let reducedMotion = false;
const mediaListeners = new Set<() => void>();

beforeEach(() => {
  now = T0_MS;
  reducedMotion = false;
  mediaListeners.clear();
  vi.stubGlobal("matchMedia", (query: string) => ({
    get matches() {
      return query.includes("reduce") ? reducedMotion : false;
    },
    media: query,
    addEventListener: (_: string, fn: () => void) => mediaListeners.add(fn),
    removeEventListener: (_: string, fn: () => void) => mediaListeners.delete(fn),
  }));
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

function mount(store = new Store(() => now)) {
  const scene = fakeScene();
  const onInteract = vi.fn();
  const onRefresh = vi.fn();
  const utils = render(<App store={store} createScene={scene.create} onInteract={onInteract} onRefresh={onRefresh} />);
  return { store, scene, onInteract, onRefresh, ...utils };
}

const flush = () => act(async () => {});
// A snapshot arriving over a live connection.
const load = (store: Store, snap: ReturnType<typeof makeSnapshot>) => {
  store.applySnapshot(snap);
  store.setStatus("live");
};
// act() wants void; store methods return booleans.
const run = (fn: () => unknown) =>
  act(() => {
    fn();
  });

describe("explicit states", () => {
  it("loading", () => {
    mount();
    expect(screen.getByRole("heading", { name: /waking maple up/i })).toBeTruthy();
  });

  it("API unavailable before any snapshot", async () => {
    const { store } = mount();
    await run(() => store.setStatus("offline", "down"));
    expect(screen.getByRole("heading", { name: /can't reach maple/i })).toBeTruthy();
  });

  it("disconnected keeps the last Maple, says so in text, and disables interactions while not live", async () => {
    const { store } = mount();
    await run(() => {
      load(store, makeSnapshot());
      store.setStatus("reconnecting");
    });
    expect(screen.getByTestId("connection-status").textContent).toBe("Reconnecting…");
    expect(screen.getByRole("alert").textContent).toMatch(/not connected/i);
    const greet = screen.getByRole("button", { name: /greet maple/i }) as HTMLButtonElement;
    expect(greet.disabled).toBe(true); // availability may be out of date
    await run(() => store.setStatus("live"));
    expect(greet.disabled).toBe(false);
    await run(() => store.setStatus("offline"));
    expect(greet.disabled).toBe(true);
  });

  it("stale heartbeat is announced even while connected", async () => {
    const { store } = mount();
    const snap = makeSnapshot();
    snap.freshness = { ...snap.freshness, heartbeat_status: "stale" };
    await run(() => {
      load(store, snap);
      store.setStatus("live");
    });
    expect(screen.getByRole("alert").textContent).toMatch(/heartbeat is late/i);
  });
});

describe("room", () => {
  it("creates the scene once and updates it on new snapshots (no recreation)", async () => {
    const { store, scene } = mount();
    await run(() => load(store, makeSnapshot()));
    await flush();
    await run(() =>
      load(
        store,
        makeSnapshot({}, { revision: 11, activity: { kind: "sleep", location: "bed", started_at: iso(0), until: iso(900) } }),
      ),
    );
    expect(scene.create).toHaveBeenCalledOnce();
    expect(scene.updates.at(-1)?.pose).toBe("sleep");
    expect(screen.getByTestId("room-summary").textContent).toMatch(/Maple is sleeping by the bed/);
  });

  it("ends the reaction at `until` without a heartbeat, then asks the backend", async () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    const reaction = { kind: "greet_happy", variant: 0, started_at: iso(0), until: iso(8) };
    const { store, onRefresh } = mount();
    await run(() => load(store, makeSnapshot({}, { reaction, expression: "happy" })));
    expect(screen.getByTestId("room-summary").textContent).toMatch(/waves hello/);
    now = T0_MS + 8000;
    await run(() => vi.advanceTimersByTime(8100));
    expect(screen.getByTestId("room-summary").textContent).not.toMatch(/waves hello/);
    expect(onRefresh).toHaveBeenCalled();
  });

  it("passes prefers-reduced-motion to the scene and follows changes", async () => {
    reducedMotion = true;
    const { store, scene } = mount();
    await run(() => load(store, makeSnapshot()));
    await flush();
    expect(scene.create.mock.calls[0]?.[1]).toEqual({ reducedMotion: true });
    reducedMotion = false;
    await run(() => mediaListeners.forEach((fn) => fn()));
    expect(scene.handle.reduced.at(-1)).toBe(false);
  });
});

describe("Greet/Pet", () => {
  it("uses backend availability, shows the countdown, and asks the backend when it runs out", async () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    const { store, onInteract, onRefresh } = mount();
    await run(() =>
      load(
        store,
        makeSnapshot(
          {},
          {
            interactions: [
              { kind: "greet", available: false, reason: "cooldown", retry_after_seconds: 3 },
              { kind: "pet", available: true, reason: null, retry_after_seconds: null },
            ],
          },
        ),
      ),
    );
    const greet = screen.getByRole("button", { name: /greet maple/i }) as HTMLButtonElement;
    const pet = screen.getByRole("button", { name: /pet maple/i }) as HTMLButtonElement;
    expect(greet.disabled).toBe(true);
    expect(greet.textContent).toMatch(/in 3 s/);
    expect(pet.disabled).toBe(false);
    fireEvent.click(pet);
    expect(onInteract).toHaveBeenCalledWith("pet");

    now = T0_MS + 3000;
    await run(() => vi.advanceTimersByTime(3000));
    expect(greet.textContent).toMatch(/in 0 s/);
    expect(greet.disabled).toBe(true); // still disabled until the backend says otherwise
    expect(onRefresh).toHaveBeenCalled();
  });

  it("shows accepted, cooldown and rate-limit feedback from the backend", async () => {
    const { store } = mount();
    const reaction = { kind: "pet_happy", variant: 0, started_at: iso(0), until: iso(8) };
    await run(() => {
      load(store, makeSnapshot({}, { reaction }));
      store.setFeedback({ kind: "pet", accepted: true, reason: null, retryAfterSeconds: null, at: 0 });
    });
    const feedback = screen.getByTestId("interaction-feedback");
    expect(feedback.textContent).toBe("Maple enjoys the pat.");
    await run(() => store.setFeedback({ kind: "greet", accepted: false, reason: "cooldown", retryAfterSeconds: 41.2, at: 0 }));
    expect(feedback.textContent).toBe("Maple needs a moment. Try again in 42 s.");
    await run(() => store.setFeedback({ kind: "greet", accepted: false, reason: "rate_limit", retryAfterSeconds: 300, at: 0 }));
    expect(feedback.textContent).toMatch(/lot of attention.*300 s/);
  });

  it("disables a button while its request is pending", async () => {
    const { store } = mount();
    await run(() => {
      load(store, makeSnapshot());
      store.setPending("greet", true);
    });
    const greet = screen.getByRole("button", { name: /greet maple/i }) as HTMLButtonElement;
    expect(greet.disabled).toBe(true);
    expect(greet.textContent).toMatch(/waiting/i);
  });
});

describe("panels", () => {
  it("shows Maple's facts and needs as numbers, not colour alone", async () => {
    const { store } = mount();
    await run(() => load(store, makeSnapshot()));
    expect(screen.getByRole("heading", { level: 2, name: "Maple" })).toBeTruthy();
    expect(screen.getByText("3 days, 1 h")).toBeTruthy();
    expect(screen.getByLabelText(/energy/i).getAttribute("value")).toBe("71");
    expect(screen.getByText("71")).toBeTruthy();
  });

  it("shows host readings and honest unknowns — never fake healthy values", async () => {
    const { store } = mount();
    const snap = makeSnapshot();
    snap.server = {
      ...snap.server,
      sensor_status: "stale",
      host: [
        observation({ metric: "cpu_usage", value: 18 }),
        observation({ id: 3, metric: "disk_usage", subject: "/", status: "unavailable", value: null, reason: "permission" }),
      ],
    };
    await run(() => load(store, snap));
    expect(screen.getByText("18%")).toBeTruthy();
    expect(screen.getByText("unavailable (permission)")).toBeTruthy();
    expect(screen.getAllByText("no data")).toHaveLength(2); // RAM and temperature absent
    expect(screen.getByText(/^stale — last observed/)).toBeTruthy();
  });

  it("shows journal and timeline entries (newest first)", async () => {
    const { store } = mount();
    const snap = makeSnapshot();
    const entry = (id: number, text: string) => ({
      id,
      revision: id,
      tick_id: id,
      created_at: iso(id),
      category: "reflection",
      trigger: "t",
      topic: "t",
      text,
      importance: "normal",
      brain: snap.brain,
      activity: "idle",
      expression: "calm",
      observation_ids: [],
    });
    snap.journal = [entry(1, "First line."), entry(2, "Second line.")];
    snap.timeline = [
      ...snap.timeline,
      { id: 2, revision: 11, tick_id: null, kind: "interaction_accepted", at: iso(5), details: { kind: "pet" } },
    ];
    await run(() => load(store, snap));
    const items = screen.getAllByText(/line\.$/).map((el) => el.textContent);
    expect(items).toEqual(["Second line.", "First line."]);
    expect(screen.getByText(/Was petted\./)).toBeTruthy();
  });
});

describe("layout", () => {
  it("navigates to existing sections only, with one current section", async () => {
    const { store } = mount();
    await run(() => load(store, makeSnapshot()));
    const nav = screen.getByRole("navigation", { name: "Sections" });
    const links = Array.from(nav.querySelectorAll("a"));
    expect(links.map((a) => a.getAttribute("href"))).toEqual(["#room", "#status", "#journal", "#activity", "#system"]);
    for (const a of links) expect(document.querySelector(a.getAttribute("href") ?? "")).not.toBeNull();
    expect(nav.querySelectorAll('[aria-current="location"]')).toHaveLength(1);

    await run(() => fireEvent.click(links[2] as HTMLAnchorElement));
    expect(links[2]?.getAttribute("aria-current")).toBe("location");
    expect(nav.querySelectorAll('[aria-current="location"]')).toHaveLength(1);
  });

  it("renders the room and the Greet/Pet bar exactly once", async () => {
    const { store, scene } = mount();
    await run(() => load(store, makeSnapshot()));
    await flush();
    expect(scene.create).toHaveBeenCalledTimes(1);
    expect(screen.getAllByTestId("room-summary")).toHaveLength(1);
    expect(screen.getAllByTestId("interaction-feedback")).toHaveLength(1);
  });

  it("opens Recent Activity by default and keeps Runtime collapsed", async () => {
    const { store } = mount();
    await run(() => load(store, makeSnapshot()));
    const details = (name: string) => screen.getByRole("heading", { name }).closest("details");
    expect(details("Recent Activity")?.open).toBe(true);
    expect(details("Runtime")?.open).toBe(false);
  });
});

describe("mobile smoke", () => {
  it("renders the room, both buttons and all panels at phone width", async () => {
    vi.stubGlobal("innerWidth", 390);
    const { store } = mount();
    await run(() => load(store, makeSnapshot()));
    expect(screen.getAllByRole("button")).toHaveLength(2);
    for (const name of ["Maple", "Journal", "Server", "Recent Activity", "Runtime"]) {
      expect(screen.getByRole("heading", { name })).toBeTruthy();
    }
    expect(screen.getByTestId("room-summary").textContent).not.toBe("");
  });
});
