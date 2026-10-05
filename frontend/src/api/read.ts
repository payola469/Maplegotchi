// Read-only endpoints beyond the snapshot: the room's furniture, the shared life
// events, and the owner Inspector's audit views. GET only; nothing here changes Maple.

import type {
  DecisionOut,
  LifeEventsOut,
  MemoryOut,
  ReflectionOut,
  RoomOut,
} from "./types";
import { ApiError, type Fetch } from "./client";

export interface ReadApi {
  room(): Promise<RoomOut>;
  lifeEvents(afterRevision: number, limit?: number): Promise<LifeEventsOut>;
  decisions(limit?: number): Promise<DecisionOut[]>;
  memory(tier?: "short_term" | "long_term" | "archive", limit?: number): Promise<MemoryOut[]>;
  reflections(limit?: number): Promise<ReflectionOut[]>;
}

export function createReadApi(fetchImpl: Fetch = fetch.bind(globalThis)): ReadApi {
  async function get<T>(path: string): Promise<T> {
    let response: Response;
    try {
      response = await fetchImpl(path, { headers: { accept: "application/json" }, cache: "no-store" });
    } catch (error) {
      throw new ApiError(`network error: ${String(error)}`, null);
    }
    if (!response.ok) throw new ApiError(`${path} failed (${response.status})`, response.status);
    return (await response.json()) as T;
  }

  return {
    room: () => get<RoomOut>("/api/room"),
    lifeEvents: (afterRevision, limit = 200) =>
      get<LifeEventsOut>(`/api/life-events?after_revision=${Math.max(0, Math.floor(afterRevision))}&limit=${limit}`),
    decisions: (limit = 20) => get<DecisionOut[]>(`/api/decisions?limit=${limit}`),
    memory: (tier, limit = 20) =>
      get<MemoryOut[]>(`/api/memory?limit=${limit}${tier ? `&tier=${tier}` : ""}`),
    reflections: (limit = 3) => get<ReflectionOut[]>(`/api/reflections?limit=${limit}`),
  };
}
