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

export interface PositionOut {
  x: number;
  y: number;
}

export interface PathPointOut {
  x: number;
  y: number;
  distance: number;
  node: string | null;
}

export interface RouteOut {
  departed_at: string;
  arrives_at: string; // the activity begins here (ADR-0027)
  from_activity: string;
  path: PathPointOut[];
}

export interface ActivityOut {
  kind: string;
  location: string;
  started_at: string; // while walking: the planned start, i.e. arrival
  until: string;
  phase: string; // walking | performing
  point: string;
  furniture: string;
  pose: string;
  facing: string;
  position: PositionOut; // at generated_at
  route: RouteOut | null;
  task: TaskOut | null; // what is being read/written (ADR-0029)
}

export interface TaskOut {
  tool: string; // reader | writer
  target: string;
  title: string;
  category: string;
}

export interface DocumentSummaryOut {
  id: number;
  kind: string; // note | summary | reflection | research
  title: string;
  created_at: string;
  chars: number;
  action_id: number;
  goal_id: number | null;
}

export interface DocumentOut extends DocumentSummaryOut {
  body: string;
  sources: string[];
}

export interface InteractionPointOut {
  id: string;
  location: string;
  furniture: string;
  x: number;
  y: number;
  facing: string;
  pose: string;
  allowed_actions: string[];
}

export interface FurnitureOut {
  id: string;
  label: string;
  location: string;
}

export interface RoomOut {
  width: number;
  height: number;
  floor_y: number;
  walk_speed: number;
  furniture: FurnitureOut[];
  points: InteractionPointOut[];
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

export interface GoalOut {
  id: number;
  type: string; // one of the 16 goal types (ADR-0026)
  summary: string;
  source: string; // rule | external
  started_at: string;
  horizon_until: string;
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
  goal: GoalOut | null;
  suspended_goal: GoalOut | null;
  action_priority: string; // critical | high | normal | low
  bubble: BubbleOut | null; // the speech bubble, derived by the backend from real state
}

export interface BubbleOut {
  kind: string; // needs_attention | thinking | reading | writing | waiting_for_paolo | approval_required
  text: string;
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
  director: BrainOut; // who proposes goals and actions (ADR-0026)
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

// Decision audit and the one life-event model (ADR-0026 §8, ADR-0028 §2).

export interface DecisionOut {
  id: number;
  revision: number;
  at: string;
  trigger: string;
  priority: string | null;
  director: { kind: string; name: string; version: string };
  context_summary: string; // written by core, not by a Director
  proposal: {
    goal_op: string | null;
    goal_type: string | null;
    goal_summary: string | null;
    horizon_minutes: number | null;
    abandon_reason: string | null;
    action: string | null;
    duration_minutes: number | null;
    reason: string | null; // concise and validated; never model reasoning
  } | null;
  verdict: string; // accepted | clamped | rejected | fallback | stale
  reason_code: string | null;
  clamped: Record<string, number>;
  executed: {
    by: string;
    reason: string;
    goal_id: number | null;
    action_id: number;
    action: string;
    point: string;
    duration_minutes: number;
  } | null;
  latency_ms: number | null;
}

export interface LifeEventOut {
  id: string; // "<timeline|action|decision>:<row id>"
  type: string;
  at: string;
  revision: number;
  goal_id: number | null;
  action_id: number | null;
  priority: string | null;
  payload: Record<string, string | number | null>;
}

export interface LifeEventsOut {
  events: LifeEventOut[];
  last_revision: number;
}

// Maple's memory (ADR-0030).
export interface MemoryOut {
  id: number;
  kind: string;
  tier: string; // short_term | long_term | archive
  status: string; // active, or candidate | accepted | rejected (preferences)
  text: string;
  key: string | null;
  source: string | null;
  importance: number;
  evidence_days: string[];
  created_at: string;
  last_seen_at: string;
}

// Daily Reflection (ADR-0031).
export interface ReflectionOut {
  day: string;
  created_at: string;
  recovered: boolean;
  summary: string;
  learned: string[];
  moments: string[];
  memory_candidates: { memory_id: number; text: string; reason: string }[];
  promoted: number[];
  preference_candidates: string[][];
  intent: { type: string; summary: string };
}

// GET /api/brain-health (ADR-0034): read-only; unknown values are null, never guessed.
export interface AiCallOut {
  at: string;
  ok: boolean;
  code: string | null;
  latency_ms: number | null;
}

export interface CallerHealthOut {
  mode: string; // rule | external
  name: string;
  last_call: AiCallOut | null;
  last_success_at: string | null;
  fallbacks_today: number;
  timeouts_today: number; // timeouts or transport errors
}

export interface BrainHealthOut {
  as_of: string;
  status: string; // healthy | degraded | offline | unknown
  status_reason: string;
  provider: string | null;
  model: string | null;
  companion: { probed: boolean; reachable: boolean | null; error: string | null };
  journal_brain: string;
  director: CallerHealthOut;
  replier: CallerHealthOut;
  last_success_at: string | null;
  today: { day: string; start: string; end: string };
}
