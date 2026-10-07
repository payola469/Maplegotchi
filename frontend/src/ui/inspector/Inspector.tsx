// Maple Inspector: an owner-facing audit/debug view, kept apart from the living
// room UI. It shows exactly what the backend recorded: the current goal and
// action, where Maple is going and why, recent decisions with their verdicts,
// the action history, memory candidates, interruptions and rejections, and who
// the Brain/Director are, and Brain Health (ADR-0034). Read-only; it fetches GET
// endpoints only.

import { useEffect, useState } from "preact/hooks";
import type { ReadApi } from "../../api/read";
import type {
  BrainHealthOut,
  CallerHealthOut,
  DecisionOut,
  LifeEventOut,
  MemoryOut,
  ReflectionOut,
  SnapshotOut,
} from "../../api/types";
import { formatClock } from "../../state/presentation";

interface Audit {
  decisions: DecisionOut[];
  memories: MemoryOut[];
  reflections: ReflectionOut[];
  error: string | null;
}

const EMPTY: Audit = { decisions: [], memories: [], reflections: [], error: null };
const PROBLEM_VERDICTS = new Set(["rejected", "fallback", "stale"]);
const ACTION_TYPES = new Set([
  "destination_selected",
  "walking_started",
  "walking_cancelled",
  "arrived",
  "activity_started",
  "activity_completed",
  "activity_interrupted",
  "activity_resumed",
  "needs_attention",
  "read_started",
  "read_completed",
  "read_failed",
  "write_started",
  "write_completed",
  "write_failed",
]);

function useAudit(api: ReadApi, revision: number): Audit {
  const [audit, setAudit] = useState<Audit>(EMPTY);
  useEffect(() => {
    let cancelled = false;
    Promise.all([api.decisions(20), api.memory("short_term", 20), api.reflections(1)])
      .then(([decisions, memories, reflections]) => {
        if (!cancelled) setAudit({ decisions, memories, reflections, error: null });
      })
      .catch((error: unknown) => {
        if (!cancelled) setAudit((prev) => ({ ...prev, error: String(error) }));
      });
    return () => {
      cancelled = true;
    };
  }, [api, revision]);
  return audit;
}

function Row({ label, children }: { label: string; children: preact.ComponentChildren }) {
  return (
    <div class="inspector__row">
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

// ---------------------------------------------------------------- Brain Health (ADR-0034)

const UNKNOWN = "Unknown";
const STATUS_WORDS: Record<string, string> = {
  healthy: "Healthy",
  degraded: "Degraded",
  offline: "Offline",
  unknown: UNKNOWN,
};
const REASON_WORDS: Record<string, string> = {
  latest_call_ok: "the latest AI call succeeded",
  latest_call_failed: "the latest AI call fell back",
  companion_unreachable: "the brain companion did not answer",
  no_calls_yet: "no AI calls recorded yet",
  not_configured: "every mode is rule; no companion in use",
};

interface BrainHealthState {
  health: BrainHealthOut | null;
  error: string | null;
}

function useBrainHealth(api: ReadApi, revision: number): BrainHealthState {
  const [state, setState] = useState<BrainHealthState>({ health: null, error: null });
  useEffect(() => {
    let cancelled = false;
    api
      .brainHealth()
      .then((health) => {
        if (!cancelled) setState({ health, error: null });
      })
      .catch((error: unknown) => {
        if (!cancelled) setState({ health: null, error: String(error) });
      });
    return () => {
      cancelled = true;
    };
  }, [api, revision]);
  return state;
}

/** "gemini-3.8-flash-medium" -> "Gemini 3.8 Flash Medium": spacing and capitals only. */
export function modelLabel(model: string | null): string {
  if (!model) return UNKNOWN;
  return model
    .split(/[-_]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function latencyLabel(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return UNKNOWN;
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)}s`;
}

function modeLabel(caller: CallerHealthOut): string {
  return caller.mode === "external" ? "External" : caller.mode === "rule" ? "Rule" : UNKNOWN;
}

function lastCallLabel(caller: CallerHealthOut): string {
  const call = caller.last_call;
  if (!call) return "none yet";
  const outcome = call.ok ? "" : ` — fell back (${call.code ?? "unknown"})`;
  return `${latencyLabel(call.latency_ms)} at ${formatClock(call.at)}${outcome}`;
}

export function BrainHealthCard({ health, error }: BrainHealthState) {
  const status = health ? (STATUS_WORDS[health.status] ?? UNKNOWN) : UNKNOWN;
  const badge = health && health.status in STATUS_WORDS ? health.status : "unknown";
  return (
    <section class="card" data-testid="brain-health">
      <h2>Brain Health</h2>
      {error ? (
        <p class="banner banner--warn" role="alert">
          Brain Health could not be loaded: {error}
        </p>
      ) : null}
      <dl>
        <Row label="Status">
          <span class={`badge badge--${badge}`} data-testid="brain-health-status">
            {status}
          </span>
          {health ? <span class="muted"> {REASON_WORDS[health.status_reason] ?? health.status_reason}</span> : null}
        </Row>
        <Row label="Provider">{health?.provider ?? UNKNOWN}</Row>
        <Row label="Model">
          <span title={health?.model ?? undefined}>{modelLabel(health?.model ?? null)}</span>
        </Row>
        <Row label="Last success">{health?.last_success_at ? formatClock(health.last_success_at) : health ? "none yet" : UNKNOWN}</Row>
      </dl>
      {health ? (
        <>
          <h3>Director</h3>
          <dl data-testid="brain-health-director">
            <Row label="Mode">
              {modeLabel(health.director)} <span class="muted">({health.director.name})</span>
            </Row>
            <Row label="Last decision">{lastCallLabel(health.director)}</Row>
            <Row label="Fallbacks today">{health.director.fallbacks_today}</Row>
            <Row label="Timeouts today">{health.director.timeouts_today}</Row>
          </dl>
          <h3>Replier</h3>
          <dl data-testid="brain-health-replier">
            <Row label="Mode">
              {modeLabel(health.replier)} <span class="muted">({health.replier.name})</span>
            </Row>
            <Row label="Last reply">{lastCallLabel(health.replier)}</Row>
            <Row label="Fallbacks today">{health.replier.fallbacks_today}</Row>
            <Row label="Timeouts today">{health.replier.timeouts_today}</Row>
          </dl>
          <p class="muted">
            "Today" is Maple's day {health.today.day} (06:00 to 06:00 local). Timeouts include transport errors.
          </p>
        </>
      ) : null}
    </section>
  );
}

export function Inspector({
  snapshot,
  lifeEvents,
  api,
  onClose,
}: {
  snapshot: SnapshotOut;
  lifeEvents: readonly LifeEventOut[];
  api: ReadApi;
  onClose: () => void;
}) {
  const audit = useAudit(api, snapshot.revision);
  const brainHealth = useBrainHealth(api, snapshot.revision);
  const maple = snapshot.maple;
  const activity = maple.activity;
  const latest = audit.decisions[audit.decisions.length - 1] ?? null;
  const actions = lifeEvents.filter((e) => ACTION_TYPES.has(e.type)).slice(-15).reverse();
  const problems = [
    ...audit.decisions
      .filter((d) => PROBLEM_VERDICTS.has(d.verdict))
      .map((d) => ({ key: `d${d.id}`, at: d.at, text: `decision ${d.verdict} (${d.reason_code ?? "—"})` })),
    ...lifeEvents
      .filter((e) => e.type === "activity_interrupted" || e.type === "walking_cancelled")
      .map((e) => ({ key: e.id, at: e.at, text: `${e.type.replace(/_/g, " ")}: ${String(e.payload.cause ?? "")}` })),
  ].sort((a, b) => b.at.localeCompare(a.at));
  const reflection = audit.reflections[audit.reflections.length - 1] ?? null;
  return (
    <main class="inspector" data-testid="inspector">
      <header class="inspector__head">
        <h1>Maple Inspector</h1>
        <p class="muted">Owner view: audit and debugging. Read-only; values come from the backend.</p>
        <button type="button" onClick={onClose}>
          Back to the room
        </button>
      </header>
      {audit.error ? (
        <p class="banner banner--warn" role="alert">
          Some audit data could not be loaded: {audit.error}
        </p>
      ) : null}

      <section class="card">
        <h2>Now</h2>
        <dl>
          <Row label="Goal">
            {maple.goal ? `${maple.goal.type} #${maple.goal.id}: ${maple.goal.summary}` : "none"}
          </Row>
          <Row label="Suspended goal">
            {maple.suspended_goal ? `${maple.suspended_goal.type} #${maple.suspended_goal.id}` : "none"}
          </Row>
          <Row label="Action">
            {activity.kind} ({activity.phase}, priority {maple.action_priority})
            {activity.task ? ` — ${activity.task.tool}: ${activity.task.title} [${activity.task.target}]` : ""}
          </Row>
          <Row label="Destination">
            {activity.furniture} / {activity.point}
            {activity.route ? ` — arrives ${formatClock(activity.route.arrives_at)}` : ""}
          </Row>
          <Row label="Why">
            {latest ? (latest.proposal?.reason ?? latest.executed?.reason ?? "—") : "—"}
          </Row>
          <Row label="Brain">
            {snapshot.brain.kind} · {snapshot.brain.name} v{snapshot.brain.version}
          </Row>
          <Row label="Director">
            {snapshot.director.kind} · {snapshot.director.name} v{snapshot.director.version}
          </Row>
        </dl>
      </section>

      <BrainHealthCard health={brainHealth.health} error={brainHealth.error} />

      <section class="card">
        <h2>Recent decisions</h2>
        <table class="inspector__table" data-testid="inspector-decisions">
          <thead>
            <tr>
              <th>Time</th>
              <th>Trigger</th>
              <th>By</th>
              <th>Verdict</th>
              <th>Action</th>
              <th>Reason</th>
            </tr>
          </thead>
          <tbody>
            {[...audit.decisions].reverse().map((d) => (
              <tr key={d.id}>
                <td>{formatClock(d.at)}</td>
                <td>{d.trigger}</td>
                <td>{d.director.name}</td>
                <td>
                  {d.verdict}
                  {d.reason_code ? ` (${d.reason_code})` : ""}
                </td>
                <td>{d.executed ? `${d.executed.action} @ ${d.executed.point}` : "—"}</td>
                <td>{d.proposal?.reason ?? d.executed?.reason ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section class="card">
        <h2>Action history</h2>
        <ol class="inspector__list" data-testid="inspector-actions">
          {actions.map((e) => (
            <li key={e.id}>
              <time dateTime={e.at}>{formatClock(e.at)}</time> {e.type.replace(/_/g, " ")} #{e.action_id ?? "—"}{" "}
              {String(e.payload.title ?? e.payload.activity ?? e.payload.point ?? "")}
            </li>
          ))}
        </ol>
      </section>

      <section class="card">
        <h2>Interruptions and rejections</h2>
        {problems.length === 0 ? (
          <p class="muted">None recently.</p>
        ) : (
          <ul class="inspector__list" data-testid="inspector-problems">
            {problems.slice(0, 15).map((p) => (
              <li key={p.key}>
                <time dateTime={p.at}>{formatClock(p.at)}</time> {p.text}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section class="card">
        <h2>Memory candidates</h2>
        {reflection ? (
          <p>
            Last reflection ({reflection.day}{reflection.recovered ? ", recovered" : ""}): intent{" "}
            <strong>{reflection.intent.type}</strong> — {reflection.intent.summary}
          </p>
        ) : null}
        <ul class="inspector__list" data-testid="inspector-memory">
          {(reflection?.memory_candidates ?? []).map((c) => (
            <li key={`c${c.memory_id}`}>
              {c.text} <span class="muted">({c.reason}{reflection?.promoted.includes(c.memory_id) ? ", promoted" : ""})</span>
            </li>
          ))}
          {audit.memories.slice(-8).map((m) => (
            <li key={`m${m.id}`}>
              {m.text} <span class="muted">({m.kind}, {m.tier})</span>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
