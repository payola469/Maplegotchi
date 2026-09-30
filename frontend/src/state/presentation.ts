// Small presentation helpers over backend values. They format and count down;
// they never decide Maple's rules.

import type {
  InteractionAvailabilityOut,
  InteractionKind,
  ObservationOut,
  SnapshotOut,
} from "../api/types";

export function availability(
  snapshot: SnapshotOut | null,
  kind: InteractionKind,
): InteractionAvailabilityOut | null {
  return snapshot?.maple.interactions.find((a) => a.kind === kind) ?? null;
}

/** Seconds left of a backend-reported wait, counted from the snapshot's own time. */
export function remainingSeconds(
  retryAfterSeconds: number | null,
  generatedAt: string,
  serverNowMs: number,
): number | null {
  if (retryAfterSeconds === null) return null;
  const elapsed = (serverNowMs - Date.parse(generatedAt)) / 1000;
  return Math.max(0, Math.ceil(retryAfterSeconds - elapsed));
}

export function formatAge(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return "unknown";
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (days > 0) return `${days} day${days === 1 ? "" : "s"}, ${hours} h`;
  if (hours > 0) return `${hours} h ${minutes} min`;
  return `${Math.max(minutes, 0)} min`;
}

export function formatClock(iso: string | null): string {
  if (!iso) return "never";
  const date = new Date(iso);
  return Number.isNaN(date.getTime())
    ? "unknown"
    : date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export interface HostReading {
  label: string;
  text: string; // "18%", "54 °C", or an honest status word
  known: boolean;
}

const HOST_METRICS: readonly { metric: string; label: string; subject?: string }[] = [
  { metric: "cpu_usage", label: "CPU" },
  { metric: "memory_usage", label: "RAM" },
  { metric: "disk_usage", label: "Disk", subject: "/" },
  { metric: "temperature", label: "Temperature" },
];

function valueText(o: ObservationOut): string {
  if (o.value === null) return o.status;
  if (o.unit === "percent") return `${Math.round(o.value)}%`;
  if (o.unit === "celsius") return `${Math.round(o.value)} °C`;
  return String(o.value);
}

/** Host readings as the backend reported them; missing ones say so, never "0%". */
export function hostReadings(snapshot: SnapshotOut): HostReading[] {
  return HOST_METRICS.map(({ metric, label, subject }) => {
    const o = snapshot.server.host.find(
      (h) => h.metric === metric && (subject === undefined || h.subject === subject),
    );
    if (!o) return { label, text: "no data", known: false };
    if (o.status !== "available") {
      return { label, text: `${o.status}${o.reason ? ` (${o.reason})` : ""}`, known: false };
    }
    return { label, text: valueText(o), known: true };
  });
}

export const SUMMARY_TEXT: Readonly<Record<string, string>> = {
  calm: "All observed services look fine.",
  unclear: "Some things could not be observed.",
  troubled_earlier: "There was a problem earlier; it has cleared.",
  still_troubled: "Something on the server needs attention.",
  no_data: "No server observations yet.",
};
