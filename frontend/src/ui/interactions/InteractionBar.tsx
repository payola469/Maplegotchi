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
              class="interactions__button"
              disabled={disabled || unavailable || pending[kind]}
              aria-describedby={`${kind}-hint`}
              onClick={() => onInteract(kind)}
            >
              <span class="interactions__label">{LABEL[kind]}</span>
              <span class="interactions__hint" id={`${kind}-hint`}>
                {hint}
              </span>
            </button>
          );
        })}
      </div>
      <p class="interactions__feedback" role="status" aria-live="polite" data-testid="interaction-feedback">
        {feedback ? feedbackText(feedback, snapshot) : ""}
      </p>
    </div>
  );
}
