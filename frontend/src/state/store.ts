// The UI's single state container. It holds backend truth plus connection
// status; it never computes Maple rules.
//
// Revision rule: the displayed revision never moves backwards. A snapshot or
// interaction result older than what is shown is ignored.

import type { InteractionKind, MapleOut, SnapshotOut } from "../api/types";

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
