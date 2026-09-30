import { describe, expect, it } from "vitest";
import { T0_MS, iso, makeMaple, makeSnapshot } from "../test/fixtures";
import { Store } from "./store";

describe("Store revision rule", () => {
  it("never moves backwards for snapshots", () => {
    const store = new Store(() => T0_MS);
    expect(store.applySnapshot(makeSnapshot({}, { revision: 12 }))).toBe(true);
    expect(store.applySnapshot(makeSnapshot({}, { revision: 11 }))).toBe(false);
    expect(store.get().revision).toBe(12);
    expect(store.applySnapshot(makeSnapshot({}, { revision: 12 }))).toBe(true); // same revision: fine
    expect(store.applySnapshot(makeSnapshot({}, { revision: 13 }))).toBe(true);
    expect(store.get().revision).toBe(13);
  });

  it("applies an interaction's maple only when not older, keeping the rest of the snapshot", () => {
    const store = new Store(() => T0_MS);
    store.applySnapshot(makeSnapshot({}, { revision: 12 }));
    expect(store.applyMaple(makeMaple({ revision: 11, expression: "happy" }))).toBe(false);
    expect(store.get().snapshot?.maple.expression).toBe("calm");
    expect(store.applyMaple(makeMaple({ revision: 13, expression: "happy" }))).toBe(true);
    expect(store.get().snapshot?.maple.expression).toBe("happy");
    expect(store.get().snapshot?.server.summary).toBe("calm");
    expect(store.get().revision).toBe(13);
  });

  it("estimates server time from the snapshot for presentation timing", () => {
    let local = T0_MS - 5000; // local clock 5 s behind the server
    const store = new Store(() => local);
    store.applySnapshot(makeSnapshot());
    local += 1000;
    expect(store.serverNow()).toBe(Date.parse(iso(1)));
  });

  it("notifies subscribers and supports unsubscribe", () => {
    const store = new Store();
    const seen: string[] = [];
    const off = store.subscribe((s) => seen.push(s.status));
    store.setStatus("live");
    store.setStatus("live"); // no change -> no notification
    off();
    store.setStatus("stale");
    expect(seen).toEqual(["live"]);
  });
});
