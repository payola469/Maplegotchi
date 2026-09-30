// Greet/Pet: ask the backend, then show exactly what it answered. No optimistic
// success, no local cooldown rules.

import { ApiError, type ApiClient } from "../api/client";
import type { InteractionKind } from "../api/types";
import type { Store } from "./store";

export async function interact(
  store: Store,
  api: ApiClient,
  kind: InteractionKind,
  refresh: () => void,
): Promise<void> {
  if (store.get().pending[kind]) return;
  store.setPending(kind, true);
  try {
    const result = await api.interact(kind);
    store.applyMaple(result.maple);
    store.setFeedback({
      kind,
      accepted: result.accepted,
      reason: result.reason,
      retryAfterSeconds: result.retry_after_seconds,
      at: Date.now(),
    });
    refresh(); // journal/timeline may have changed; SSE will also tell us
  } catch (error) {
    store.setFeedback({
      kind,
      accepted: false,
      reason: error instanceof ApiError && error.status === 403 ? "forbidden" : "error",
      retryAfterSeconds: null,
      at: Date.now(),
    });
  } finally {
    store.setPending(kind, false);
  }
}
