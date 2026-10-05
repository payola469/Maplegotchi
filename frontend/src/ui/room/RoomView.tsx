import { useEffect, useMemo, useRef } from "preact/hooks";
import type { SnapshotOut } from "../../api/types";
import type { CreateRoomScene, RoomSceneHandle } from "../../room/scene/RoomScene";
import { describeRoom, toVisual } from "../../room/visual";

interface Props {
  snapshot: SnapshotOut;
  serverNowMs: number;
  reducedMotion: boolean;
  stale: boolean;
  createScene: CreateRoomScene;
  onReactionEnded: () => void;
}

export function RoomView({ snapshot, serverNowMs, reducedMotion, stale, createScene, onReactionEnded }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const scene = useRef<RoomSceneHandle | null>(null);
  const visual = useMemo(
    () => toVisual(snapshot, serverNowMs, serverNowMs - Date.now()),
    [snapshot, serverNowMs],
  );
  const latest = useRef(visual);
  latest.current = visual;

  // Create the Pixi scene once; snapshots never recreate it.
  useEffect(() => {
    let cancelled = false;
    const el = host.current;
    if (!el) return undefined;
    void createScene(el, { reducedMotion }).then((handle) => {
      if (cancelled) {
        handle.destroy();
        return;
      }
      scene.current = handle;
      handle.update(latest.current);
    });
    return () => {
      cancelled = true;
      scene.current?.destroy();
      scene.current = null;
    };
    // Mount once by design: later visuals and motion settings go through update().
  }, [createScene]);

  useEffect(() => scene.current?.update(visual), [visual]);
  useEffect(() => scene.current?.setReducedMotion(reducedMotion), [reducedMotion]);

  // End the transient reaction exactly at the backend's `until` (presentation only).
  const reactionUntil = visual.reaction?.untilMs ?? null;
  useEffect(() => {
    if (reactionUntil === null) return undefined;
    const id = window.setTimeout(onReactionEnded, Math.max(0, reactionUntil - serverNowMs) + 30);
    return () => window.clearTimeout(id);
  }, [reactionUntil, serverNowMs, onReactionEnded]);

  return (
    <div class={`room${stale ? " room--stale" : ""}`}>
      <div class="room__canvas" ref={host} />
      <p class="room__summary" data-testid="room-summary">
        {describeRoom(snapshot, visual)}
        {!visual.recognised ? " (Some of Maple's state is new to this display.)" : ""}
      </p>
    </div>
  );
}
