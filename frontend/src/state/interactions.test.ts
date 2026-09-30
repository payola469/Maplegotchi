import { describe, expect, it, vi } from "vitest";
import { ApiError, type ApiClient } from "../api/client";
import type { InteractionOut } from "../api/types";
import { T0_MS, iso, makeInteraction, makeSnapshot } from "../test/fixtures";
import { interact } from "./interactions";
import { Store } from "./store";

function setup(result: () => Promise<InteractionOut>) {
  const store = new Store(() => T0_MS);
  store.applySnapshot(makeSnapshot());
  const api: ApiClient = { snapshot: vi.fn(), interact: vi.fn(result) };
  const refresh = vi.fn();
  return { store, api, refresh };
}

describe("interact()", () => {
  it("Greet success: shows the backend's reaction and requests a refresh", async () => {
    const reaction = { kind: "greet_happy", variant: 0, started_at: iso(0), until: iso(8) };
    const { store, api, refresh } = setup(async () =>
      makeInteraction({ reaction }, { reaction, expression: "happy" }),
    );
    await interact(store, api, "greet", refresh);
    expect(store.get().snapshot?.maple.reaction?.kind).toBe("greet_happy");
    expect(store.get().feedback).toMatchObject({ kind: "greet", accepted: true });
    expect(store.get().revision).toBe(11);
    expect(refresh).toHaveBeenCalledOnce();
  });

  it("no optimistic success: nothing changes while the request is pending", async () => {
    let resolve!: (r: InteractionOut) => void;
    const { store, api, refresh } = setup(() => new Promise((r) => (resolve = r)));
    const done = interact(store, api, "greet", refresh);
    expect(store.get().pending.greet).toBe(true);
    expect(store.get().snapshot?.maple.reaction).toBeNull();
    expect(store.get().feedback).toBeNull();
    resolve(makeInteraction());
    await done;
    expect(store.get().pending.greet).toBe(false);
  });

  it("ignores a second click while one is pending", async () => {
    let resolve!: (r: InteractionOut) => void;
    const { store, api, refresh } = setup(() => new Promise((r) => (resolve = r)));
    const first = interact(store, api, "pet", refresh);
    await interact(store, api, "pet", refresh);
    expect(api.interact).toHaveBeenCalledOnce();
    resolve(makeInteraction({ interaction: "pet" }));
    await first;
  });

  it("Greet cooldown (429): shows the backend reason and wait, and the backend's availability", async () => {
    const { store, api, refresh } = setup(async () =>
      makeInteraction(
        { accepted: false, reason: "cooldown", retry_after_seconds: 42, revision: 10 },
        {
          revision: 10,
          interactions: [
            { kind: "greet", available: false, reason: "cooldown", retry_after_seconds: 42 },
            { kind: "pet", available: true, reason: null, retry_after_seconds: null },
          ],
        },
      ),
    );
    await interact(store, api, "greet", refresh);
    expect(store.get().feedback).toMatchObject({ accepted: false, reason: "cooldown", retryAfterSeconds: 42 });
    expect(store.get().snapshot?.maple.interactions[0]?.available).toBe(false);
  });

  it("Pet success is applied from the response", async () => {
    const reaction = { kind: "pet_happy", variant: 1, started_at: iso(0), until: iso(8) };
    const { store, api, refresh } = setup(async () =>
      makeInteraction({ interaction: "pet", reaction }, { reaction }),
    );
    await interact(store, api, "pet", refresh);
    expect(store.get().snapshot?.maple.reaction?.kind).toBe("pet_happy");
    expect(store.get().feedback).toMatchObject({ kind: "pet", accepted: true });
  });

  it("a rejected request (403) or network error changes nothing but the feedback", async () => {
    const forbidden = setup(async () => Promise.reject(new ApiError("pet failed (403)", 403)));
    const before = forbidden.store.get().snapshot;
    await interact(forbidden.store, forbidden.api, "pet", forbidden.refresh);
    expect(forbidden.store.get().snapshot).toBe(before);
    expect(forbidden.store.get().feedback).toMatchObject({ accepted: false, reason: "forbidden" });
    expect(forbidden.refresh).not.toHaveBeenCalled();

    const down = setup(async () => Promise.reject(new ApiError("network", null)));
    await interact(down.store, down.api, "greet", down.refresh);
    expect(down.store.get().feedback).toMatchObject({ accepted: false, reason: "error" });
  });
});
