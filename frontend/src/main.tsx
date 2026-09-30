import { render } from "preact";
import { createApiClient } from "./api/client";
import { createStreamOpener } from "./api/sse";
import type { InteractionKind } from "./api/types";
import { interact } from "./state/interactions";
import { LiveConnection } from "./state/live";
import { Store } from "./state/store";
import "./styles.css";
import { App } from "./ui/App";

const root = document.getElementById("app");
if (root) {
  const store = new Store();
  const api = createApiClient();
  const live = new LiveConnection(store, api, createStreamOpener());
  const refresh = () => live.refresh();
  const onInteract = (kind: InteractionKind) => void interact(store, api, kind, refresh);
  // The Pixi scene is loaded on demand so the DOM UI appears first.
  const createScene = async (host: HTMLElement, options: { reducedMotion: boolean }) => {
    const { createRoomScene } = await import("./room/scene/RoomScene");
    return createRoomScene(host, options);
  };
  render(<App store={store} createScene={createScene} onInteract={onInteract} onRefresh={refresh} />, root);
  live.start();
  window.addEventListener("pagehide", () => live.stop());
}
