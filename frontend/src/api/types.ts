// Mirrors backend/src/maplegotchi/api/models.py. The backend is the source of truth;
// these types only describe what it sends. Enum-like fields are plain strings on
// purpose: the UI must tolerate values it does not recognise (see room/visual.ts).

export interface BrainOut {
  kind: string;
  name: string;
  version: string;
}

export interface IdentityOut {
  name: string;
  born_at: string;
  age_seconds: number;
  ticks_lived: number;
}

export interface NeedsOut {
  mood: number;
  energy: number;
  curiosity: number;
  social: number;
}

export interface ActivityOut {
  kind: string;
  location: string;
  started_at: string;
  until: string;
}

export interface ReactionOut {
  kind: string;
  variant: number;
  started_at: string;
  until: string;
}

export interface InteractionAvailabilityOut {
  kind: string;
  available: boolean;
  reason: string | null;
  retry_after_seconds: number | null;
}

export interface MapleOut {
  revision: number;
  generated_at: string;
  identity: IdentityOut;
  needs: NeedsOut;
  activity: ActivityOut;
  expression: string;
  reaction: ReactionOut | null;
  interactions: InteractionAvailabilityOut[];
}

export interface DayOut {
  local_time: string;
  local_hour: number;
  phase: string;
  is_night: boolean;
  timezone: string;
  utc_offset_minutes: number;
}

export interface ObservationOut {
  id: number;
  tick_id: number;
  metric: string;
  subject: string;
  status: string;
  value: number | null;
  state: string | null;
  unit: string;
  source: string;
  reason: string | null;
  observed_at: string;
}

export interface ServiceHealthOut {
  service_id: string;
  status: string;
  state: string | null;
  source: string;
  reason: string | null;
  observed_at: string;
}

export interface ServerOut {
  observed_at: string | null;
  sensor_status: string;
  summary: string;
  attention_level: number;
  attention_reasons: string[];
  counts: Record<string, number>;
  services: ServiceHealthOut[];
  host: ObservationOut[];
}

export interface JournalEntryOut {
  id: number;
  revision: number;
  tick_id: number | null;
  created_at: string;
  category: string;
  trigger: string;
  topic: string;
  text: string;
  importance: string;
  brain: BrainOut;
  activity: string;
  expression: string;
  observation_ids: number[];
}

export interface TimelineEventOut {
  id: number;
  revision: number;
  tick_id: number | null;
  kind: string;
  at: string;
  details: Record<string, string>;
}

export interface FreshnessOut {
  server_time: string;
  last_heartbeat_at: string;
  next_heartbeat_due_at: string;
  heartbeat_interval_seconds: number;
  heartbeat_age_seconds: number;
  heartbeat_status: string;
  life_loop_running: boolean;
  life_loop_error: string | null;
  sensor_status: string;
  observations_at: string | null;
  sse_keepalive_seconds: number;
}

export interface SnapshotOut {
  revision: number;
  generated_at: string;
  maple: MapleOut;
  day: DayOut;
  server: ServerOut;
  journal: JournalEntryOut[];
  timeline: TimelineEventOut[];
  freshness: FreshnessOut;
  brain: BrainOut;
}

export interface InteractionOut {
  interaction: string;
  accepted: boolean;
  reason: string | null;
  retry_after_seconds: number | null;
  reaction: ReactionOut | null;
  revision: number;
  maple: MapleOut;
}

export type InteractionKind = "greet" | "pet";
