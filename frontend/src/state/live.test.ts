import { beforeEach, describe, expect, it } from "vitest";
import type { ApiClient } from "../api/client";
import type { OpenStream, StreamHandlers } from "../api/sse";
import type { SnapshotOut } from "../api/types";
import { makeSnapshot } from "../test/fixtures";
import { BACKOFF_MS, LiveConnection, type Timers } from "./live";
import { Store } from "./store";

// Deterministic fakes: manual timers, a controllable stream and a controllable API.

class FakeTimers implements Timers {
  now = 0;
  private next = 1;
  private pending = new Map<number, { at: number; fn: () => void }>();
  setTimeout(fn: () => void, ms: number): number {
    const id = this.next++;
    this.pending.set(id, { at: this.now + ms, fn });
    return id;
  }
  clearTimeout(id: number): void {
    this.pending.delete(id);
  }
  advance(ms: number): void {
    const end = this.now + ms;
    for (;;) {
      const due = [...this.pending.entries()].filter(([, t]) => t.at <= end).sort((a, b) => a[1].at - b[1].at)[0];
      if (!due) break;
      this.pending.delete(due[0]);
      this.now = due[1].at;
      due[1].fn();
    }
    this.now = end;
  }
  get count(): number {
    return this.pending.size;
  }
}

interface Deferred {
  resolve(s: SnapshotOut): void;
  reject(e: unknown): void;
}

function setup() {
  const timers = new FakeTimers();
  const store = new Store();
  const fetches: Deferred[] = [];
  const api: ApiClient = {
    snapshot: () => new Promise<SnapshotOut>((resolve, reject) => fetches.push({ resolve, reject })),
    interact: () => Promise.reject(new Error("unused")),
  };
  const streams: { lastEventId: string | null; h: StreamHandlers; closed: boolean }[] = [];
  const openStream: OpenStream = (lastEventId, h) => {
    const s = { lastEventId, h, closed: false };
    streams.push(s);
    return {
      close() {
        if (!s.closed) {
          s.closed = true;
          h.onClose("aborted");
        }
      },
    };
  };
  const live = new LiveConnection(store, api, openStream, timers);
  const latest = () => {
    const s = streams[streams.length - 1];
    if (!s) throw new Error("no stream");
    return s;
  };
  const frame = (event: string, revision: number, id: string) =>
    latest().h.onFrame({ id, event, data: JSON.stringify({ revision }) });
  const flush = () => new Promise((r) => setTimeout(r, 0));
  return { timers, store, fetches, streams, live, latest, frame, flush };
}

let t: ReturnType<typeof setup>;
beforeEach(() => {
  t = setup();
});

describe("LiveConnection", () => {
  it("loads the snapshot, then goes live once the stream shows activity", async () => {
    t.live.start();
    expect(t.store.get().status).toBe("loading");
    expect(t.fetches).toHaveLength(1);
    t.latest().h.onOpen();
    t.fetches[0]?.resolve(makeSnapshot({}, { revision: 5 }));
    await t.flush();
    t.latest().h.onActivity();
    expect(t.store.get().status).toBe("live");
    expect(t.store.get().revision).toBe(5);
  });

  it("refreshes once per newer event and ignores events it already has", async () => {
    t.live.start();
    t.latest().h.onOpen();
    t.fetches[0]?.resolve(makeSnapshot({}, { revision: 5 }));
    await t.flush();
    t.frame("heartbeat", 5, "b-5"); // not newer
    expect(t.fetches).toHaveLength(1);
    t.frame("heartbeat", 6, "b-6");
    expect(t.fetches).toHaveLength(2);
  });

  it("coalesces events that arrive during an in-flight fetch into ONE follow-up", async () => {
    t.live.start();
    t.latest().h.onOpen();
    t.fetches[0]?.resolve(makeSnapshot({}, { revision: 5 }));
    await t.flush();
    t.frame("heartbeat", 6, "b-6");
    t.frame("journal", 6, "b-7");
    t.frame("timeline", 6, "b-8");
    t.frame("interaction", 7, "b-9");
    expect(t.fetches).toHaveLength(2); // one in flight
    t.fetches[1]?.resolve(makeSnapshot({}, { revision: 6 }));
    await t.flush();
    expect(t.fetches).toHaveLength(3); // exactly one follow-up
    t.fetches[2]?.resolve(makeSnapshot({}, { revision: 7 }));
    await t.flush();
    expect(t.fetches).toHaveLength(3); // no loop
    expect(t.store.get().revision).toBe(7);
  });

  it("an older snapshot finishing late never rolls the revision back", async () => {
    t.live.start();
    t.latest().h.onOpen();
    t.latest().h.onFrame({ id: "b-9", event: "snapshot", data: JSON.stringify(makeSnapshot({}, { revision: 9 })) });
    t.fetches[0]?.resolve(makeSnapshot({}, { revision: 4 }));
    await t.flush();
    expect(t.store.get().revision).toBe(9);
  });

  it("applies a snapshot frame (resync) directly without fetching", async () => {
    t.live.start();
    t.latest().h.onOpen();
    t.fetches[0]?.resolve(makeSnapshot({}, { revision: 5 }));
    await t.flush();
    t.latest().h.onFrame({ id: "c-1", event: "snapshot", data: JSON.stringify(makeSnapshot({}, { revision: 8 })) });
    expect(t.fetches).toHaveLength(1);
    expect(t.store.get().revision).toBe(8);
    expect(t.store.get().status).toBe("live");
  });

  it("ignores malformed frames", async () => {
    t.live.start();
    t.latest().h.onOpen();
    t.latest().h.onFrame({ id: "b-1", event: "heartbeat", data: "{not json" });
    expect(t.fetches).toHaveLength(1);
  });

  it("reconnects with backoff and the last event id, then resyncs with a snapshot", async () => {
    t.live.start();
    t.latest().h.onOpen();
    t.fetches[0]?.resolve(makeSnapshot({}, { revision: 5 }));
    await t.flush();
    t.frame("heartbeat", 6, "b-6");
    t.fetches[1]?.resolve(makeSnapshot({}, { revision: 6 }));
    await t.flush();

    t.latest().h.onClose("error"); // backend restarted
    expect(t.store.get().status).toBe("reconnecting");
    expect(t.store.get().snapshot?.revision).toBe(6); // last known Maple stays visible
    t.timers.advance(BACKOFF_MS[0] - 1);
    expect(t.streams).toHaveLength(1);
    t.timers.advance(1);
    expect(t.streams).toHaveLength(2);
    expect(t.latest().lastEventId).toBe("b-6");

    t.latest().h.onClose("error"); // still down: next backoff step
    t.timers.advance(BACKOFF_MS[1] - 1);
    expect(t.streams).toHaveLength(2);
    t.timers.advance(1);
    expect(t.streams).toHaveLength(3);

    const before = t.fetches.length;
    t.latest().h.onOpen();
    expect(t.fetches.length).toBe(before + 1); // resync snapshot after the drop
    t.fetches[before]?.resolve(makeSnapshot({}, { revision: 7 }));
    await t.flush();
    t.latest().h.onActivity();
    expect(t.store.get().status).toBe("live");
    expect(t.store.get().revision).toBe(7);
  });

  it("marks a silent stream stale (no keepalives), closes it and reconnects", async () => {
    t.live.start();
    t.latest().h.onOpen();
    t.fetches[0]?.resolve(makeSnapshot({}, { revision: 5 }));
    await t.flush();
    t.latest().h.onActivity();
    t.timers.advance(15_000 * 2 + 4_999);
    expect(t.store.get().status).toBe("live");
    t.latest().h.onActivity(); // keepalive re-arms
    t.timers.advance(15_000 * 2 + 5_000);
    expect(t.store.get().status).toBe("stale");
    expect(t.streams[0]?.closed).toBe(true);
    t.timers.advance(BACKOFF_MS[0]);
    expect(t.streams).toHaveLength(2);
  });

  it("shows offline when the API is unreachable and nothing was ever loaded", async () => {
    t.live.start();
    t.fetches[0]?.reject(new Error("ECONNREFUSED"));
    t.latest().h.onClose("error");
    await t.flush();
    expect(t.store.get().status).toBe("offline");
    expect(t.store.get().snapshot).toBeNull();
  });

  it("stop() clears timers and closes the stream", () => {
    t.live.start();
    t.latest().h.onOpen();
    expect(t.timers.count).toBeGreaterThan(0);
    t.live.stop();
    expect(t.timers.count).toBe(0);
    expect(t.streams[0]?.closed).toBe(true);
    t.timers.advance(60_000);
    expect(t.streams).toHaveLength(1); // no reconnect after stop
  });
});

describe("shared life events over SSE (Phase A8)", () => {
  it("adds the commit's life events to the store", () => {
    t.live.start();
    const events = [
      { id: "action:3", type: "walking_started", at: "2026-09-30T10:00:00Z", revision: 12,
        goal_id: 1, action_id: 4, priority: null, payload: { furniture: "bookshelf" } },
    ]; // prettier-ignore
    t.latest().h.onFrame({ id: "b-12", event: "life", data: JSON.stringify({ revision: 12, events }) });
    expect(t.store.get().lifeEvents.map((e) => e.id)).toEqual(["action:3"]);
    t.latest().h.onFrame({ id: "b-13", event: "life", data: JSON.stringify({ revision: 13, events: "nope" }) });
    expect(t.store.get().lifeEvents).toHaveLength(1);
  });
});
