// SVG layer over the Pixi room: Maple's speech bubble and the furniture hotspots.
// Everything shown comes from the backend: the bubble text from `maple.bubble`, the
// furniture and what each piece is for from /api/room, "in use" from the activity.
// The hotspots explain; they do not act (there is no furniture action to take).
// Positions are SVG attributes in room units, so no inline styles are needed (CSP).

import type { RoomOut, SnapshotOut } from "../../api/types";
import type { VisualState } from "../../room/visual";

const ACTION_WORDS: Readonly<Record<string, string>> = {
  write: "writing",
  observe_server: "checking the server",
  read: "reading",
  rest: "resting",
  sleep: "sleeping",
  think: "thinking",
  walk: "walking",
  idle: "idling",
};

interface Hotspot {
  id: string;
  label: string;
  x: number;
  y: number;
  uses: string[];
}

export function hotspots(room: RoomOut): Hotspot[] {
  const byFurniture = new Map<string, Hotspot>();
  for (const point of room.points) {
    const existing = byFurniture.get(point.furniture);
    const uses = point.allowed_actions.map((a) => ACTION_WORDS[a] ?? a.replace(/_/g, " "));
    if (existing) {
      for (const use of uses) if (!existing.uses.includes(use)) existing.uses.push(use);
      continue;
    }
    const label = room.furniture.find((f) => f.id === point.furniture)?.label ?? point.furniture;
    byFurniture.set(point.furniture, { id: point.furniture, label, x: point.x, y: point.y, uses });
  }
  return [...byFurniture.values()];
}

const BUBBLE_CHAR_WIDTH = 9; // room units per character at the bubble's font size

export function RoomOverlay({
  snapshot,
  visual,
  room,
}: {
  snapshot: SnapshotOut;
  visual: VisualState;
  room: RoomOut | null;
}) {
  const bubble = snapshot.maple.bubble;
  const activity = snapshot.maple.activity;
  const width = room?.width ?? 1000;
  const height = room?.height ?? 600;
  const bubbleWidth = bubble ? Math.min(width * 0.6, bubble.text.length * BUBBLE_CHAR_WIDTH + 24) : 0;
  const bubbleX = Math.max(4, Math.min(width - bubbleWidth - 4, visual.restPosition.x - bubbleWidth / 2));
  const bubbleY = Math.max(4, visual.restPosition.y - 190);
  return (
    <svg class="room-overlay" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="xMidYMid meet">
      {room
        ? hotspots(room).map((spot) => {
            const inUse = activity.furniture === spot.id && activity.phase === "performing";
            const text = `${spot.label}: for ${spot.uses.join(", ")}${inUse ? " — in use now" : ""}`;
            return (
              <g
                key={spot.id}
                class={`hotspot${inUse ? " hotspot--active" : ""}`}
                tabIndex={0}
                role="img"
                aria-label={text}
                data-testid={`hotspot-${spot.id}`}
              >
                <title>{text}</title>
                <circle cx={spot.x} cy={spot.y - 30} r={10} />
              </g>
            );
          })
        : null}
      {bubble && !visual.walking ? (
        <g class={`speech speech--${bubble.kind}`} role="status" data-testid="speech-bubble">
          <rect x={bubbleX} y={bubbleY} width={bubbleWidth} height={36} rx={12} />
          <text x={bubbleX + bubbleWidth / 2} y={bubbleY + 24} text-anchor="middle">
            {bubble.text}
          </text>
        </g>
      ) : null}
    </svg>
  );
}
