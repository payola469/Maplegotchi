// The UI's single state container. It holds backend truth plus connection
// status; it never computes Maple rules.
//
// Revision rule: the displayed revision never moves backwards. A snapshot or
// interaction result older than what is shown is ignored.

import type { InteractionKind, LifeEventOut, MapleOut, RoomOut, SnapshotOut } from "../api/types";

/** How many recent life events the UI keeps (the backend keeps them all). */
export const LIFE_EVENTS_KEPT = 60;

export type ConnectionStatus =
  | "loading" // no snapshot yet
  | "live" // stream open and recently active
  | "reconnecting" // stream dropped; retrying
  | "stale" // stream silent for too long; data may be old
  | "offline"; // API unreachable

export interface InteractionFeedback {
  kind: InteractionKind;
  accepted: boolean;
  reason: string | null; // backend reason for rejections, or "error"
  retryAfterSeconds: number | null;
  at: number; // local ms, for display only
}

export interface UiState {
  snapshot: SnapshotOut | null;
  revision: number;
  status: ConnectionStatus;
  lastUpdateMs: number | null; // local time the last snapshot/maple update arrived
  serverOffsetMs: number; // server clock - local clock, estimated at last update
  pending: Record<InteractionKind, boolean>;
  feedback: InteractionFeedback | null;
  error: string | null;
  room: RoomOut | null; // furniture and interaction points, from /api/room
  lifeEvents: LifeEventOut[]; // recent shared life events, oldest first
}

export type Listener = (state: UiState) => void;

export class Store {
  private state: UiState = {
    snapshot: null,
    revision: 0,
    status: "loading",
    lastUpdateMs: null,
    serverOffsetMs: 0,
    pending: { greet: false, pet: false },
    feedback: null,
    error: null,
    room: null,
    lifeEvents: [],
  };
  private listeners = new Set<Listener>();

  constructor(private readonly now: () => number = () => Date.now()) {}

  get(): UiState {
    return this.state;
  }

  subscribe(listener: Listener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private set(patch: Partial<UiState>): void {
    this.state = { ...this.state, ...patch };
    for (const listener of this.listeners) listener(this.state);
  }

  /** Apply a full snapshot unless it is older than what is shown. Returns whether applied. */
  applySnapshot(snapshot: SnapshotOut): boolean {
    if (snapshot.revision < this.state.revision) return false;
    const received = this.now();
    this.set({
      snapshot,
      revision: snapshot.revision,
      lastUpdateMs: received,
      serverOffsetMs: Date.parse(snapshot.generated_at) - received,
      error: null,
    });
    return true;
  }

  /** Apply the maple part of an interaction response if it is not older than the snapshot. */
  applyMaple(maple: MapleOut): boolean {
    const current = this.state.snapshot;
    if (!current || maple.revision < this.state.revision) return false;
    const received = this.now();
    this.set({
      snapshot: { ...current, maple, revision: maple.revision, generated_at: maple.generated_at },
      revision: maple.revision,
      lastUpdateMs: received,
      serverOffsetMs: Date.parse(maple.generated_at) - received,
    });
    return true;
  }

  setStatus(status: ConnectionStatus, error: string | null = this.state.error): void {
    if (status !== this.state.status || error !== this.state.error) this.set({ status, error });
  }

  setRoom(room: RoomOut): void {
    this.set({ room });
  }

  /** Merge life events (from REST or SSE): no duplicates, backend order, newest kept. */
  addLifeEvents(events: readonly LifeEventOut[]): void {
    if (events.length === 0) return;
    const seen = new Set(this.state.lifeEvents.map((e) => e.id));
    const fresh = events.filter((e) => !seen.has(e.id));
    if (fresh.length === 0) return;
    const merged = [...this.state.lifeEvents, ...fresh].sort((a, b) => a.revision - b.revision);
    this.set({ lifeEvents: merged.slice(-LIFE_EVENTS_KEPT) });
  }

  setPending(kind: InteractionKind, pending: boolean): void {
    this.set({ pending: { ...this.state.pending, [kind]: pending } });
  }

  setFeedback(feedback: InteractionFeedback | null): void {
    this.set({ feedback });
  }

  /** Current server time as best known (for presentation timing only). */
  serverNow(): number {
    return this.now() + this.state.serverOffsetMs;
  }
}
