// Secondary DOM panels. Everything shown here is a backend value; missing or
// unknown data is shown as such, never as a healthy-looking placeholder.

import type { SnapshotOut, TimelineEventOut } from "../api/types";
import type { ConnectionStatus } from "../state/store";
import { SUMMARY_TEXT, formatAge, formatClock, hostReadings } from "../state/presentation";

export function StatusPanel({ snapshot }: { snapshot: SnapshotOut }) {
  const { identity, needs, activity, expression } = snapshot.maple;
  const bars: [string, number][] = [
    ["Mood", needs.mood],
    ["Energy", needs.energy],
    ["Curiosity", needs.curiosity],
    ["Social", needs.social],
  ];
  return (
    <section class="panel" aria-labelledby="status-heading">
      <h2 id="status-heading">{identity.name}</h2>
      <dl class="facts">
        <dt>Age</dt>
        <dd>{formatAge(identity.age_seconds)}</dd>
        <dt>Doing</dt>
        <dd>{activity.kind.replace(/_/g, " ")}</dd>
        <dt>Feeling</dt>
        <dd>{expression}</dd>
      </dl>
      <ul class="needs">
        {bars.map(([label, value]) => (
          <li key={label}>
            <label>
              <span>{label}</span>
              <meter min={0} max={100} low={25} high={75} optimum={100} value={value} />
              <span class="needs__value">{Math.round(value)}</span>
            </label>
          </li>
        ))}
      </ul>
    </section>
  );
}

const SERVICE_NAMES: Record<string, string> = {
  maplegotchi: "Maplegotchi",
  metrics_collector: "Metrics collector",
  grafana: "Grafana",
  lycan_watch: "Lycan Watch",
  qbittorrent: "qBittorrent",
  jellyfin: "Jellyfin",
  backup: "Backups",
};

export function ServerPanel({ snapshot }: { snapshot: SnapshotOut }) {
  const server = snapshot.server;
  const readings = hostReadings(snapshot);
  const sensorNote =
    server.sensor_status === "fresh"
      ? `observed ${formatClock(server.observed_at)}`
      : server.sensor_status === "stale"
        ? `stale — last observed ${formatClock(server.observed_at)}`
        : "no observations yet";
  return (
    <details class="panel" open>
      <summary>
        <h2>Server</h2>
        <span class={`badge badge--${server.sensor_status}`}>{sensorNote}</span>
      </summary>
      <p class="server__summary">{SUMMARY_TEXT[server.summary] ?? server.summary}</p>
      <dl class="facts facts--grid">
        {readings.map((r) => (
          <>
            <dt key={`${r.label}-t`}>{r.label}</dt>
            <dd key={`${r.label}-d`} class={r.known ? "" : "unknown"}>
              {r.text}
            </dd>
          </>
        ))}
      </dl>
      {server.services.length > 0 ? (
        <ul class="services">
          {server.services.map((s) => (
            <li key={s.service_id} class={`service service--${s.status}`}>
              <span>{SERVICE_NAMES[s.service_id] ?? s.service_id}</span>
              <span class="service__state">
                {s.status === "available" ? (s.state ?? "?") : s.status}
              </span>
            </li>
          ))}
        </ul>
      ) : null}
    </details>
  );
}

export function JournalPanel({ snapshot }: { snapshot: SnapshotOut }) {
  const entries = [...snapshot.journal].reverse();
  return (
    <details class="panel" open>
      <summary>
        <h2>Journal</h2>
      </summary>
      {entries.length === 0 ? (
        <p class="muted">Nothing written yet.</p>
      ) : (
        <ol class="journal">
          {entries.map((e) => (
            <li key={e.id} class={`journal__entry journal__entry--${e.importance}`}>
              <time dateTime={e.created_at}>{formatClock(e.created_at)}</time>
              <p>{e.text}</p>
            </li>
          ))}
        </ol>
      )}
    </details>
  );
}

function timelineText(e: TimelineEventOut, name: string): string {
  switch (e.kind) {
    case "born":
      return `${e.details.name ?? name} was born.`;
    case "activity_changed":
      return `Started ${(e.details.current ?? "something").replace(/_/g, " ")}.`;
    case "interaction_accepted":
      return e.details.kind === "pet" ? "Was petted." : "Was greeted.";
    case "downtime_gap":
      return "Was offline for a while.";
    default:
      return e.kind.replace(/_/g, " ");
  }
}

export function TimelinePanel({ snapshot }: { snapshot: SnapshotOut }) {
  const events = [...snapshot.timeline].reverse();
  return (
    <details class="panel">
      <summary>
        <h2>Timeline</h2>
      </summary>
      <ol class="timeline">
        {events.map((e) => (
          <li key={e.id}>
            <time dateTime={e.at}>{formatClock(e.at)}</time> {timelineText(e, snapshot.maple.identity.name)}
          </li>
        ))}
      </ol>
    </details>
  );
}

const STATUS_TEXT: Record<ConnectionStatus, string> = {
  loading: "Connecting…",
  live: "Live",
  reconnecting: "Reconnecting…",
  stale: "Connection stale",
  offline: "Offline",
};

export function ConnectionBadge({ status }: { status: ConnectionStatus }) {
  return (
    <span class={`badge badge--${status}`} role="status" data-testid="connection-status">
      {STATUS_TEXT[status]}
    </span>
  );
}

export function RuntimePanel({ snapshot, status, lastUpdateMs }: { snapshot: SnapshotOut; status: ConnectionStatus; lastUpdateMs: number | null }) {
  const f = snapshot.freshness;
  return (
    <details class="panel">
      <summary>
        <h2>Runtime</h2>
      </summary>
      <dl class="facts">
        <dt>Connection</dt>
        <dd>{STATUS_TEXT[status]}</dd>
        <dt>Last update</dt>
        <dd>{lastUpdateMs ? new Date(lastUpdateMs).toLocaleTimeString() : "never"}</dd>
        <dt>Heartbeat</dt>
        <dd>
          {f.heartbeat_status === "fresh" ? "on time" : "late"} (last {formatClock(f.last_heartbeat_at)})
        </dd>
        <dt>Brain</dt>
        <dd>
          {snapshot.brain.name} ({snapshot.brain.kind})
        </dd>
      </dl>
    </details>
  );
}
