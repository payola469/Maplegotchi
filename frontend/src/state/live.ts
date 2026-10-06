// Keeps the Store in sync with the backend: one snapshot fetch at start, then the
// SSE stream. Every event carrying a newer revision triggers ONE coalesced
// snapshot refresh (never a fetch storm); a `snapshot` event is applied directly.
//
// Reconnect: exponential backoff with the last seen event id, so the backend can
// replay missed events or send a fresh snapshot (resync). A stream that is silent
// (not even keepalives) for too long is treated as dead: the UI shows "stale" and
// reconnects. Timers are single, re-armed, and cleared on stop().

import type { ApiClient } from "../api/client";
import type { OpenStream, SseFrame, StreamHandle } from "../api/sse";
import type { LifeEventOut, SnapshotOut } from "../api/types";
import type { Store } from "./store";

export interface Timers {
  setTimeout(fn: () => void, ms: number): number;
  clearTimeout(id: number): void;
}

export const BACKOFF_MS = [1000, 2000, 5000, 10000] as const;
const DEFAULT_KEEPALIVE_SECONDS = 15;

export class LiveConnection {
  private stream: StreamHandle | null = null;
  private lastEventId: string | null = null;
  private attempt = 0;
  private reconnectTimer: number | null = null;
  private staleTimer: number | null = null;
  private refreshInFlight = false;
  private refreshAgain = false;
  private stopped = false;
  private dropped = false;

  constructor(
    private readonly store: Store,
    private readonly api: ApiClient,
    private readonly openStream: OpenStream,
    private readonly timers: Timers = {
      setTimeout: (fn, ms) => window.setTimeout(fn, ms),
      clearTimeout: (id) => window.clearTimeout(id),
    },
  ) {}

  start(): void {
    this.stopped = false;
    this.refresh();
    this.connect();
  }

  stop(): void {
    this.stopped = true;
    this.clear("reconnectTimer");
    this.clear("staleTimer");
    this.stream?.close();
    this.stream = null;
  }

  /** Fetch a snapshot; concurrent requests collapse into at most one follow-up. */
  refresh(): void {
    if (this.stopped) return;
    if (this.refreshInFlight) {
      this.refreshAgain = true;
      return;
    }
    this.refreshInFlight = true;
    this.api
      .snapshot()
      .then((snapshot) => {
        this.store.applySnapshot(snapshot);
        if (this.store.get().status === "loading" || this.store.get().status === "offline") {
          this.store.setStatus(this.stream ? "live" : "reconnecting", null);
        }
      })
      .catch((error: unknown) => {
        if (!this.store.get().snapshot) this.store.setStatus("offline", String(error));
      })
      .finally(() => {
        this.refreshInFlight = false;
        if (this.refreshAgain && !this.stopped) {
          this.refreshAgain = false;
          this.refresh();
        }
      });
  }

  private clear(which: "reconnectTimer" | "staleTimer"): void {
    const id = this[which];
    if (id !== null) this.timers.clearTimeout(id);
    this[which] = null;
  }

  private keepaliveMs(): number {
    const seconds = this.store.get().snapshot?.freshness.sse_keepalive_seconds;
    return (seconds && seconds > 0 ? seconds : DEFAULT_KEEPALIVE_SECONDS) * 1000;
  }

  private armStaleTimer(): void {
    this.clear("staleTimer");
    // Two missed keepalives plus margin: the stream is dead even if TCP says otherwise.
    this.staleTimer = this.timers.setTimeout(() => {
      this.staleTimer = null;
      this.store.setStatus("stale");
      this.stream?.close();
    }, this.keepaliveMs() * 2 + 5000);
  }

  private connect(): void {
    if (this.stopped) return;
    this.stream = this.openStream(this.lastEventId, {
      onOpen: () => {
        this.attempt = 0;
        this.armStaleTimer();
        // After a drop, resync with a fresh snapshot even if the replay is complete.
        if (this.dropped) this.refresh();
        this.dropped = false;
      },
      onActivity: () => {
        this.armStaleTimer();
        if (this.store.get().snapshot && this.store.get().status !== "live") {
          this.store.setStatus("live", null);
        }
      },
      onFrame: (frame) => this.handleFrame(frame),
      onClose: () => this.scheduleReconnect(),
    });
  }

  private scheduleReconnect(): void {
    this.stream = null;
    this.dropped = true;
    this.clear("staleTimer");
    if (this.stopped) return;
    const status = this.store.get().status;
    if (status !== "stale" && status !== "offline") {
      this.store.setStatus(this.store.get().snapshot ? "reconnecting" : "offline");
    }
    const delay = BACKOFF_MS[Math.min(this.attempt, BACKOFF_MS.length - 1)] ?? 10000;
    this.attempt += 1;
    this.clear("reconnectTimer");
    this.reconnectTimer = this.timers.setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, delay);
  }

  private handleFrame(frame: SseFrame): void {
    if (frame.id) this.lastEventId = frame.id;
    let data: unknown;
    try {
      data = JSON.parse(frame.data);
    } catch {
      return; // malformed frame: ignore; the next snapshot will correct us
    }
    if (frame.event === "snapshot") {
      this.store.applySnapshot(data as SnapshotOut);
      this.store.setStatus("live", null);
      return;
    }
    if (frame.event === "life" && typeof data === "object" && data !== null && "events" in data) {
      const events = (data as { events: unknown }).events;
      if (Array.isArray(events)) this.store.addLifeEvents(events as LifeEventOut[]);
    }
    const revision =
      typeof data === "object" && data !== null && "revision" in data
        ? Number((data as { revision: unknown }).revision)
        : NaN;
    if (!Number.isFinite(revision) || revision > this.store.get().revision) {
      this.refresh();
    }
  }
}
