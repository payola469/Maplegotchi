// Test-only snapshot builders shaped exactly like the backend DTOs.

import type { ActivityOut, InteractionOut, MapleOut, ObservationOut, SnapshotOut } from "../api/types";

export const T0 = "2026-09-30T10:00:00.000Z";
export const T0_MS = Date.parse(T0);

export function iso(offsetSeconds: number): string {
  return new Date(T0_MS + offsetSeconds * 1000).toISOString();
}

// Backend points (core/room.py) per location, for building realistic activities.
const POINTS: Readonly<Record<string, { point: string; furniture: string; x: number; y: number; pose: string; facing: string }>> = {
  bed: { point: "bed.side", furniture: "bed", x: 150, y: 455, pose: "sleep", facing: "right" },
  sofa: { point: "sofa.seat", furniture: "sofa", x: 150, y: 560, pose: "rest", facing: "front" },
  bookshelf: { point: "bookshelf.front", furniture: "bookshelf", x: 330, y: 500, pose: "read", facing: "back" },
  window: { point: "window.view", furniture: "window_plant_corner", x: 500, y: 470, pose: "think", facing: "back" },
  desk: { point: "writing_desk.chair", furniture: "writing_desk", x: 640, y: 470, pose: "sit_write", facing: "back" },
  terminal: { point: "computer_desk.chair", furniture: "computer_desk", x: 840, y: 470, pose: "sit_monitor", facing: "back" },
  rug: { point: "open_area.center", furniture: "open_area", x: 480, y: 545, pose: "stand", facing: "front" },
};

/** A performing (arrived) activity at its location's point, shaped like the backend's. */
export function activityAt(
  kind: string,
  location: string,
  startedAt: string = iso(-60),
  until: string = iso(600),
  overrides: Partial<ActivityOut> = {},
): ActivityOut {
  const p = POINTS[location] ?? { point: "unknown", furniture: "unknown", x: 480, y: 545, pose: "stand", facing: "front" };
  return {
    kind,
    location,
    started_at: startedAt,
    until,
    phase: "performing",
    point: p.point,
    furniture: p.furniture,
    pose: p.pose,
    facing: p.facing,
    position: { x: p.x, y: p.y },
    route: null,
    ...overrides,
  };
}

export function makeMaple(overrides: Partial<MapleOut> = {}): MapleOut {
  return {
    revision: 10,
    generated_at: T0,
    identity: { name: "Maple", born_at: iso(-3 * 86400), age_seconds: 3 * 86400 + 3600, ticks_lived: 860 },
    needs: { mood: 62, energy: 71, curiosity: 55, social: 48 },
    activity: activityAt("idle", "rug"),
    expression: "calm",
    reaction: null,
    interactions: [
      { kind: "greet", available: true, reason: null, retry_after_seconds: null },
      { kind: "pet", available: true, reason: null, retry_after_seconds: null },
    ],
    goal: null,
    suspended_goal: null,
    action_priority: "normal",
    ...overrides,
  };
}

export function observation(overrides: Partial<ObservationOut>): ObservationOut {
  return {
    id: 1,
    tick_id: 1,
    metric: "cpu_usage",
    subject: "cpu",
    status: "available",
    value: 18,
    state: null,
    unit: "percent",
    source: "fake",
    reason: null,
    observed_at: iso(-10),
    ...overrides,
  };
}

export function makeSnapshot(overrides: Partial<SnapshotOut> = {}, maple: Partial<MapleOut> = {}): SnapshotOut {
  const m = makeMaple(maple);
  return {
    revision: m.revision,
    generated_at: m.generated_at,
    maple: m,
    day: {
      local_time: "2026-09-30T17:00:00+07:00",
      local_hour: 17,
      phase: "afternoon",
      is_night: false,
      timezone: "Asia/Bangkok",
      utc_offset_minutes: 420,
    },
    server: {
      observed_at: iso(-10),
      sensor_status: "fresh",
      summary: "calm",
      attention_level: 0,
      attention_reasons: [],
      counts: { available: 5 },
      services: [
        { service_id: "grafana", status: "available", state: "active", source: "fake", reason: null, observed_at: iso(-10) },
      ],
      host: [
        observation({ id: 1, metric: "cpu_usage", subject: "cpu", value: 18 }),
        observation({ id: 2, metric: "memory_usage", subject: "memory", value: 51 }),
        observation({ id: 3, metric: "disk_usage", subject: "/", value: 62 }),
        observation({ id: 4, metric: "temperature", subject: "cpu", value: 54, unit: "celsius" }),
      ],
    },
    journal: [],
    timeline: [{ id: 1, revision: 1, tick_id: null, kind: "born", at: iso(-3 * 86400), details: { name: "Maple" } }],
    freshness: {
      server_time: T0,
      last_heartbeat_at: iso(-20),
      next_heartbeat_due_at: iso(280),
      heartbeat_interval_seconds: 300,
      heartbeat_age_seconds: 20,
      heartbeat_status: "fresh",
      life_loop_running: true,
      life_loop_error: null,
      sensor_status: "fresh",
      observations_at: iso(-10),
      sse_keepalive_seconds: 15,
    },
    brain: { kind: "rule", name: "rule_brain", version: "1" },
    ...overrides,
  };
}

export function makeInteraction(overrides: Partial<InteractionOut> = {}, maple: Partial<MapleOut> = {}): InteractionOut {
  return {
    interaction: "greet",
    accepted: true,
    reason: null,
    retry_after_seconds: null,
    reaction: null,
    revision: 11,
    maple: makeMaple({ revision: 11, ...maple }),
    ...overrides,
  };
}
