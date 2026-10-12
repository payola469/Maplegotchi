import { render } from "preact";
import { createApiClient } from "../api/client";
import { createReadApi } from "../api/read";
import { createStreamOpener } from "../api/sse";
import type { InteractionKind } from "../api/types";
import { interact } from "../state/interactions";
import { LiveConnection } from "../state/live";
import { Store } from "../state/store";
import { App } from "./App";

/** Existing Legacy bootstrap; the disposer is used only by development coexistence. */
export function mountLegacy(root: HTMLElement): () => void {
  const store = new Store();
  const api = createApiClient();
  const readApi = createReadApi();
  const live = new LiveConnection(store, api, createStreamOpener());
  // Static room layout, and the recent shared life events once a snapshot is in.
  void readApi.room().then((room) => store.setRoom(room)).catch(() => undefined);
  const unsubscribe = store.subscribe((state) => {
    if (!state.snapshot) return;
    unsubscribe();
    void readApi
      .lifeEvents(state.snapshot.revision - 40)
      .then((page) => store.addLifeEvents(page.events))
      .catch(() => undefined);
  });
  const refresh = () => live.refresh();
  const onInteract = (kind: InteractionKind) => void interact(store, api, kind, refresh);
  // The Pixi scene is loaded on demand so the DOM UI appears first.
  const createScene = async (host: HTMLElement, options: { reducedMotion: boolean }) => {
    const { createRoomScene } = await import("../room/scene/RoomScene");
    return createRoomScene(host, options);
  };
  render(
    <App store={store} createScene={createScene} onInteract={onInteract} onRefresh={refresh} readApi={readApi} />,
    root,
  );
  live.start();
  const stop = () => live.stop();
  window.addEventListener("pagehide", stop);
  let disposed = false;
  return () => {
    if (disposed) return;
    disposed = true;
    live.stop();
    unsubscribe();
    window.removeEventListener("pagehide", stop);
    render(null, root);
  };
}
