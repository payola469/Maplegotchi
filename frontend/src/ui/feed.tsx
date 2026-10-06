// The live feed: the shared life events (the same model Discord and iOS use),
// worded for people. It shows what the backend recorded, in order; nothing is
// inferred from animations.

import type { LifeEventOut } from "../api/types";
import { formatClock } from "../state/presentation";

const FURNITURE: Readonly<Record<string, string>> = {
  bed: "the bed",
  writing_desk: "the writing desk",
  computer_desk: "the computer desk",
  bookshelf: "the bookshelf",
  sofa: "the sofa",
  window_plant_corner: "the window",
  open_area: "the open floor",
};

const str = (value: string | number | null | undefined) => (value === null || value === undefined ? "" : String(value));

/** Plain words for one life event, or null for events not worth a line in the feed. */
export function lifeEventText(e: LifeEventOut): string | null {
  const p = e.payload;
  switch (e.type) {
    case "goal_started":
      return `New goal: ${str(p.summary) || str(p.goal_type)}.`;
    case "goal_completed":
      return "Finished a goal.";
    case "goal_abandoned":
      return `Set a goal aside (${str(p.reason).replace(/_/g, " ")}).`;
    case "goal_suspended":
      return "Paused a goal for something urgent.";
    case "goal_resumed":
      return "Picked a paused goal back up.";
    case "walking_started":
      return `Walking to ${FURNITURE[str(p.furniture)] ?? "somewhere"}.`;
    case "walking_cancelled":
      return "Changed course.";
    case "activity_started":
      return `Started ${str(p.activity).replace(/_/g, " ")} at ${FURNITURE[str(p.furniture)] ?? "its spot"}.`;
    case "activity_interrupted":
      return `Stopped ${str(p.activity).replace(/_/g, " ")} (${str(p.cause).replace(/_/g, " ")}).`;
    case "needs_attention":
      return "Something needs attention.";
    case "read_completed":
      return `Read “${str(p.title)}”.`;
    case "write_completed":
      return `Wrote “${str(p.detail) || str(p.title)}”.`;
    case "read_failed":
    case "write_failed":
      return `Couldn't finish ${e.type.startsWith("read") ? "reading" : "writing"} (${str(p.detail)}).`;
    case "decision_rejected":
      return "Changed plans: a suggestion didn't fit.";
    case "daily_reflection":
      return `Reflected on the day. Tomorrow: ${str(p.intent_summary)}.`;
    case "memory_promoted":
      return `Will remember: ${str(p.text)}`;
    case "interaction_accepted":
      return p.kind === "pet" ? "Was petted." : "Was greeted.";
    default:
      return null;
  }
}

export function ActivityFeed({ events }: { events: readonly LifeEventOut[] }) {
  const lines = events
    .map((e) => ({ e, text: lifeEventText(e) }))
    .filter((x): x is { e: LifeEventOut; text: string } => x.text !== null)
    .slice(-12)
    .reverse();
  return (
    <details class="panel panel--feed" open>
      <summary>
        <h2>What Maple is doing</h2>
      </summary>
      {lines.length === 0 ? (
        <p class="muted">Nothing new yet.</p>
      ) : (
        <ol class="feed" data-testid="activity-feed">
          {lines.map(({ e, text }) => (
            <li key={e.id}>
              <time dateTime={e.at}>{formatClock(e.at)}</time>
              <span>{text}</span>
            </li>
          ))}
        </ol>
      )}
    </details>
  );
}
