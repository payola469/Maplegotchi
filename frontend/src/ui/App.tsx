import { useCallback, useEffect, useState } from "preact/hooks";
import type { ReadApi } from "../api/read";
import type { InteractionKind } from "../api/types";
import type { CreateRoomScene } from "../room/scene/RoomScene";
import type { Store } from "../state/store";
import { ActivityFeed } from "./feed";
import { useReducedMotion, useStore } from "./hooks";
import { Inspector } from "./inspector/Inspector";
import { InteractionBar } from "./interactions/InteractionBar";
import { AppShell } from "./layout/AppShell";
import {
  ConnectionBadge,
  JournalPanel,
  RuntimePanel,
  ServerPanel,
  StatusPanel,
  TimelinePanel,
} from "./panels";
import { RoomView } from "./room/RoomView";

export interface AppProps {
  store: Store;
  createScene: CreateRoomScene;
  onInteract: (kind: InteractionKind) => void;
  onRefresh: () => void;
  readApi?: ReadApi; // enables the owner Inspector
}

export function App({ store, createScene, onInteract, onRefresh, readApi }: AppProps) {
  const state = useStore(store);
  const [inspecting, setInspecting] = useState(false);
  const reducedMotion = useReducedMotion();
  const [serverNowMs, setServerNowMs] = useState(() => store.serverNow());
  const snapshot = state.snapshot;

  // Presentation clock: re-read on every store change; tick once a second only
  // while something time-based is on screen (a reaction or a countdown).
  useEffect(() => setServerNowMs(store.serverNow()), [state, store]);
  const ticking =
    snapshot !== null &&
    (snapshot.maple.reaction !== null || snapshot.maple.interactions.some((a) => !a.available));
  useEffect(() => {
    if (!ticking) return undefined;
    const id = window.setTimeout(() => setServerNowMs(store.serverNow()), 1000);
    return () => window.clearTimeout(id);
  }, [ticking, serverNowMs, store]);

  // The reaction ended: stop showing it now, and ask the backend for the
  // expression that follows (the UI never derives it).
  const onReactionEnded = useCallback(() => {
    setServerNowMs(store.serverNow());
    onRefresh();
  }, [store, onRefresh]);

  if (!snapshot) {
    return (
      <main class="app app--empty">
        <div class="empty" role="status">
          {state.status === "offline" ? (
            <>
              <h1>Can't reach Maple</h1>
              <p>The Maplegotchi server isn't answering. Retrying automatically…</p>
            </>
          ) : (
            <>
              <h1>Waking Maple up…</h1>
              <p>Loading Maple's room.</p>
            </>
          )}
        </div>
      </main>
    );
  }

  if (inspecting && readApi) {
    return (
      <Inspector
        snapshot={snapshot}
        lifeEvents={state.lifeEvents}
        api={readApi}
        onClose={() => setInspecting(false)}
      />
    );
  }

  const stale = state.status === "stale" || state.status === "offline" || state.status === "reconnecting";
  const overdue = snapshot.freshness.heartbeat_status !== "fresh";

  // Each component below is rendered exactly once; AppShell only places it.
  return (
    <AppShell
      header={
        <header class="topbar">
          <h1>
            {snapshot.maple.identity.name}
            <span class="topbar__sub">'s room</span>
          </h1>
          <ConnectionBadge status={state.status} />
          {readApi ? (
            <button type="button" class="topbar__inspect" onClick={() => setInspecting(true)}>
              Inspector
            </button>
          ) : null}
        </header>
      }
      banners={
        <>
          {stale ? (
            <p class="banner banner--warn" role="alert">
              Not connected — showing Maple as last seen at{" "}
              {state.lastUpdateMs ? new Date(state.lastUpdateMs).toLocaleTimeString() : "an unknown time"}.
            </p>
          ) : null}
          {!stale && overdue ? (
            <p class="banner banner--warn" role="alert">
              Maple's heartbeat is late; the room may not be current.
            </p>
          ) : null}
        </>
      }
      room={
        <section class="room-card" aria-labelledby="room-heading">
          <h2 id="room-heading" class="visually-hidden">
            Maple's room
          </h2>
          <RoomView
            snapshot={snapshot}
            serverNowMs={serverNowMs}
            reducedMotion={reducedMotion}
            stale={stale}
            createScene={createScene}
            onReactionEnded={onReactionEnded}
            room={state.room}
          />
        </section>
      }
      status={<StatusPanel snapshot={snapshot} />}
      interactions={
        <div class="card interactions-card">
          <InteractionBar
            snapshot={snapshot}
            serverNowMs={serverNowMs}
            pending={state.pending}
            feedback={state.feedback}
            disabled={state.status !== "live"}
            onInteract={onInteract}
            onRefresh={onRefresh}
          />
        </div>
      }
      journal={<JournalPanel snapshot={snapshot} />}
      activity={
        <>
          <ActivityFeed events={state.lifeEvents} />
          <TimelinePanel snapshot={snapshot} />
        </>
      }
      system={
        <div class="system">
          <ServerPanel snapshot={snapshot} />
          <RuntimePanel snapshot={snapshot} status={state.status} lastUpdateMs={state.lastUpdateMs} />
        </div>
      }
    />
  );
}
