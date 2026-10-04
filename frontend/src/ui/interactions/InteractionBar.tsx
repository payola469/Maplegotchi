import { useEffect, useRef } from "preact/hooks";
import type { InteractionKind, SnapshotOut } from "../../api/types";
import { REACTION_SYMBOL } from "../../room/visual";
import { availability, remainingSeconds } from "../../state/presentation";
import type { InteractionFeedback } from "../../state/store";

interface Props {
  snapshot: SnapshotOut;
  serverNowMs: number;
  pending: Record<InteractionKind, boolean>;
  feedback: InteractionFeedback | null;
  disabled: boolean; // not live: availability may be out of date
  onInteract: (kind: InteractionKind) => void;
  onRefresh: () => void;
}

const LABEL: Record<InteractionKind, string> = { greet: "Greet Maple", pet: "Pet Maple" };

// Decorative stroke icons (aria-hidden; the label stays the button's name).
const ICON_PATH: Record<InteractionKind, string> = {
  greet: "M5 5h14a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1h-8l-5 4v-4H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1zM9 10.5h.01M15 10.5h.01M9.5 13a3.5 3.5 0 0 0 5 0",
  pet: "M12 20.5s-7.5-4.6-7.5-10A4.3 4.3 0 0 1 12 7.6a4.3 4.3 0 0 1 7.5 2.9c0 5.4-7.5 10-7.5 10z",
};

/** Styling only: the feedback text itself always says what happened. */
function feedbackTone(feedback: InteractionFeedback | null): string {
  if (!feedback) return "";
  if (feedback.accepted) return " interactions__feedback--accepted";
  return feedback.reason === "cooldown" || feedback.reason === "rate_limit"
    ? " interactions__feedback--waiting"
    : " interactions__feedback--error";
}

function feedbackText(feedback: InteractionFeedback, snapshot: SnapshotOut): string {
  const name = snapshot.maple.identity.name;
  if (feedback.accepted) {
    const reaction = snapshot.maple.reaction;
    const label = reaction ? REACTION_SYMBOL[reaction.kind]?.label : undefined;
    return label ? `${name} ${label}.` : `${name} noticed you.`;
  }
  const wait = feedback.retryAfterSeconds !== null ? ` Try again in ${Math.ceil(feedback.retryAfterSeconds)} s.` : "";
  if (feedback.reason === "cooldown") return `${name} needs a moment.${wait}`;
  if (feedback.reason === "rate_limit") return `That's a lot of attention for now.${wait}`;
  if (feedback.reason === "forbidden") return "This page isn't allowed to interact with Maple.";
  return `Couldn't reach ${name}. Nothing changed.`;
}

export function InteractionBar({ snapshot, serverNowMs, pending, feedback, disabled, onInteract, onRefresh }: Props) {
  const asked = useRef<string | null>(null);
  const kinds: InteractionKind[] = ["greet", "pet"];
  const rows = kinds.map((kind) => {
    const a = availability(snapshot, kind);
    const remaining = a ? remainingSeconds(a.retry_after_seconds, snapshot.maple.generated_at, serverNowMs) : null;
    return { kind, a, remaining };
  });

  // When a backend-reported wait has run out, ask the backend again rather than
  // deciding locally that the interaction is available.
  const expired = rows.some((r) => r.a && !r.a.available && r.remaining === 0);
  useEffect(() => {
    if (expired && asked.current !== snapshot.maple.generated_at) {
      asked.current = snapshot.maple.generated_at;
      onRefresh();
    }
  }, [expired, snapshot.maple.generated_at, onRefresh]);

  return (
    <div class="interactions">
      <div class="interactions__buttons">
        {rows.map(({ kind, a, remaining }) => {
          const unavailable = !a || !a.available;
          const hint = pending[kind]
            ? "Waiting for Maple…"
            : !a
              ? "Unavailable"
              : !a.available
                ? `${a.reason === "rate_limit" ? "Resting from attention" : "Ready"} in ${remaining ?? "?"} s`
                : "Ready";
          return (
            <button
              key={kind}
              type="button"
              class={`interactions__button interactions__button--${kind}`}
              disabled={disabled || unavailable || pending[kind]}
              aria-describedby={`${kind}-hint`}
              onClick={() => onInteract(kind)}
            >
              <svg class="interactions__icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                <path d={ICON_PATH[kind]} />
              </svg>
              <span class="interactions__label">{LABEL[kind]}</span>
              <span class="interactions__hint" id={`${kind}-hint`}>
                {hint}
              </span>
            </button>
          );
        })}
      </div>
      <p class={`interactions__feedback${feedbackTone(feedback)}`} role="status" aria-live="polite" data-testid="interaction-feedback">
        {feedback ? feedbackText(feedback, snapshot) : ""}
      </p>
    </div>
  );
}
