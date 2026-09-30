import type { InteractionKind, InteractionOut, SnapshotOut } from "./types";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number | null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export type Fetch = typeof fetch;

export interface ApiClient {
  snapshot(signal?: AbortSignal): Promise<SnapshotOut>;
  interact(kind: InteractionKind): Promise<InteractionOut>;
}

export function createApiClient(fetchImpl: Fetch = fetch.bind(globalThis)): ApiClient {
  return {
    async snapshot(signal) {
      let response: Response;
      try {
        response = await fetchImpl("/api/snapshot", {
          headers: { accept: "application/json" },
          cache: "no-store",
          ...(signal ? { signal } : {}),
        });
      } catch (error) {
        throw new ApiError(`network error: ${String(error)}`, null);
      }
      if (!response.ok) {
        throw new ApiError(`snapshot failed (${response.status})`, response.status);
      }
      return (await response.json()) as SnapshotOut;
    },

    // Accepted (200) and rejected (429) both carry an InteractionOut: the backend
    // decides; the UI never assumes success before this resolves.
    async interact(kind) {
      let response: Response;
      try {
        response = await fetchImpl(`/api/interactions/${kind}`, {
          method: "POST",
          headers: { accept: "application/json" },
          cache: "no-store",
        });
      } catch (error) {
        throw new ApiError(`network error: ${String(error)}`, null);
      }
      if (response.status === 200 || response.status === 429) {
        return (await response.json()) as InteractionOut;
      }
      throw new ApiError(`${kind} failed (${response.status})`, response.status);
    },
  };
}
