"""STEP175 test-only fresh declarations; never a migration or runtime entry point.

Frozen v10 DDL was statically folded from checked-in SQL without SQL execution.
Only CREATE statements run, only on a newly owned in-memory database.
SQL JSON/UTC checks do not establish semantic validity or payload approval.
"""

# Preserve frozen SQL spelling for source audit and fingerprint.
# ruff: noqa: E501
import sqlite3

SOURCE_SHA256 = "0898afdb50124e08630d68b4dacf183d7ab0700001b2af352c4b30d31a27a8b4"
V10_TABLES = {
    "maple": """CREATE TABLE maple (
 id INTEGER PRIMARY KEY CHECK (id = 1),
 name TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 32),
 born_at TEXT NOT NULL CHECK (born_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*+00:00'),
 life_seed TEXT NOT NULL CHECK (length(life_seed) = 64 AND life_seed NOT GLOB '*[^0-9a-f]*')
) STRICT;""",
    "interaction_ledger": """CREATE TABLE interaction_ledger (
 maple_id INTEGER NOT NULL REFERENCES maple (id),
 position INTEGER NOT NULL CHECK (position BETWEEN 0 AND 9),
 kind TEXT NOT NULL CHECK (kind IN ('greet', 'pet')),
 at TEXT NOT NULL CHECK (at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*+00:00'),
 PRIMARY KEY (maple_id, position)
) STRICT;""",
    "observation": """CREATE TABLE observation (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 maple_id INTEGER NOT NULL REFERENCES maple (id),
 revision INTEGER NOT NULL CHECK (revision >= 1),
 tick_id INTEGER NOT NULL CHECK (tick_id >= 1),
 observed_at TEXT NOT NULL CHECK (observed_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*+00:00'),
 metric TEXT NOT NULL CHECK (metric IN ('cpu_usage', 'memory_usage', 'disk_usage', 'load_1m', 'load_5m', 'load_15m', 'cpu_count', 'temperature', 'service_state')),
 subject TEXT NOT NULL CHECK (length(subject) BETWEEN 1 AND 64),
 status TEXT NOT NULL CHECK (status IN ('available', 'unavailable', 'unknown', 'error')),
 value REAL,
 state TEXT CHECK (state IN ('active', 'reloading', 'inactive', 'failed', 'activating', 'deactivating', 'maintenance', 'refreshing')),
 unit TEXT NOT NULL CHECK (unit IN ('percent', 'celsius', 'load', 'count', 'state')),
 source TEXT NOT NULL CHECK (length(source) BETWEEN 1 AND 32),
 reason TEXT CHECK (length(reason) BETWEEN 1 AND 200),
 CHECK ((status = 'available') = (reason IS NULL)),
 CHECK (status = 'available' OR (value IS NULL AND state IS NULL)),
 CHECK (status <> 'available' OR ((value IS NULL) <> (state IS NULL))),
 UNIQUE (tick_id, metric, subject)
) STRICT;""",
    "journal_entry_observation": """CREATE TABLE journal_entry_observation (
 entry_id INTEGER NOT NULL REFERENCES journal_entry (id),
 observation_id INTEGER NOT NULL REFERENCES observation (id),
 position INTEGER NOT NULL CHECK (position >= 0),
 PRIMARY KEY (entry_id, position),
 UNIQUE (entry_id, observation_id)
) STRICT;""",
    "journal_state": """CREATE TABLE journal_state (
 maple_id INTEGER PRIMARY KEY REFERENCES maple (id),
 journal_day TEXT CHECK (journal_day GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
 daily_seen TEXT NOT NULL CHECK (json_valid(daily_seen)),
 interactions_today INTEGER NOT NULL CHECK (interactions_today >= 0),
 notices_today INTEGER NOT NULL CHECK (notices_today >= 0),
 last_interaction_entry_at TEXT CHECK (last_interaction_entry_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*+00:00'),
 active_alerts TEXT NOT NULL CHECK (json_valid(active_alerts)),
 last_reflection_day TEXT CHECK (last_reflection_day GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
 milestones TEXT NOT NULL CHECK (json_valid(milestones))
) STRICT;""",
    "goal": """CREATE TABLE goal (
 id INTEGER PRIMARY KEY CHECK (id >= 1),
 maple_id INTEGER NOT NULL REFERENCES maple (id),
 revision INTEGER NOT NULL CHECK (revision >= 1),
 goal_type TEXT NOT NULL CHECK (goal_type IN ('learn', 'create', 'recover', 'reflect', 'monitor', 'socialize', 'explore', 'organize', 'maintain', 'practice', 'plan', 'wait', 'play', 'help', 'investigate', 'remember')),
 summary TEXT NOT NULL CHECK (length(summary) BETWEEN 1 AND 120 AND instr(summary, char(10)) = 0 AND instr(summary, char(13)) = 0),
 source TEXT NOT NULL CHECK (source IN ('rule', 'external')),
 decision_id INTEGER REFERENCES decision (id),
 started_at TEXT NOT NULL CHECK (started_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*+00:00'),
 horizon_until TEXT NOT NULL CHECK (horizon_until GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*+00:00')
) STRICT;""",
    "decision": """CREATE TABLE decision (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 maple_id INTEGER NOT NULL REFERENCES maple (id),
 revision INTEGER NOT NULL CHECK (revision >= 1),
 at TEXT NOT NULL CHECK (at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*+00:00'),
 trigger TEXT NOT NULL CHECK (trigger IN ('action_completed', 're_evaluate', 'no_plan', 'overdue', 'critical')),
 priority TEXT CHECK (priority IN ('critical', 'high', 'normal', 'low')),
 director_kind TEXT NOT NULL CHECK (director_kind IN ('rule', 'external')),
 director_name TEXT NOT NULL CHECK (length(director_name) BETWEEN 1 AND 32),
 director_version TEXT NOT NULL CHECK (length(director_version) BETWEEN 1 AND 16),
 context_summary TEXT NOT NULL CHECK (length(context_summary) BETWEEN 1 AND 400 AND instr(context_summary, char(10)) = 0 AND instr(context_summary, char(13)) = 0),
 proposed_goal_op TEXT CHECK (proposed_goal_op IN ('keep', 'new', 'complete', 'resume', 'abandon')),
 proposed_goal_type TEXT CHECK (proposed_goal_type IN ('learn', 'create', 'recover', 'reflect', 'monitor', 'socialize', 'explore', 'organize', 'maintain', 'practice', 'plan', 'wait', 'play', 'help', 'investigate', 'remember')),
 proposed_goal_summary TEXT CHECK (length(proposed_goal_summary) BETWEEN 1 AND 120 AND instr(proposed_goal_summary, char(10)) = 0 AND instr(proposed_goal_summary, char(13)) = 0),
 proposed_horizon_minutes REAL,
 proposed_abandon_reason TEXT CHECK (length(proposed_abandon_reason) BETWEEN 1 AND 40),
 proposed_action TEXT CHECK (proposed_action IN ('idle', 'walk', 'sleep', 'read', 'write', 'observe_server', 'rest', 'think')),
 proposed_duration_minutes REAL,
 proposed_reason TEXT CHECK (length(proposed_reason) BETWEEN 1 AND 240 AND instr(proposed_reason, char(10)) = 0 AND instr(proposed_reason, char(13)) = 0),
 verdict TEXT NOT NULL CHECK (verdict IN ('accepted', 'clamped', 'rejected', 'fallback', 'stale')),
 reason_code TEXT CHECK (length(reason_code) BETWEEN 1 AND 40),
 clamped TEXT CHECK (clamped IS NULL OR json_valid(clamped)),
 executed_by TEXT CHECK (executed_by IN ('rule', 'external')),
 executed_reason TEXT CHECK (length(executed_reason) BETWEEN 1 AND 240 AND instr(executed_reason, char(10)) = 0 AND instr(executed_reason, char(13)) = 0),
 goal_id INTEGER CHECK (goal_id >= 1),
 action_id INTEGER CHECK (action_id >= 0),
 executed_action TEXT CHECK (executed_action IN ('idle', 'walk', 'sleep', 'read', 'write', 'observe_server', 'rest', 'think')),
 executed_point TEXT CHECK (length(executed_point) BETWEEN 1 AND 40),
 executed_duration_minutes INTEGER CHECK (executed_duration_minutes >= 1),
 latency_ms INTEGER CHECK (latency_ms >= 0)
) STRICT;""",
    "action_event": """CREATE TABLE action_event (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 maple_id INTEGER NOT NULL REFERENCES maple (id),
 revision INTEGER NOT NULL CHECK (revision >= 1),
 action_id INTEGER NOT NULL CHECK (action_id >= 0),
 goal_id INTEGER CHECK (goal_id >= 1),
 kind TEXT NOT NULL CHECK (kind IN ('destination_selected', 'walking_started', 'walking_cancelled', 'arrived', 'activity_started', 'activity_completed', 'activity_interrupted', 'activity_resumed', 'needs_attention')),
 at TEXT NOT NULL CHECK (at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*+00:00'),
 priority TEXT CHECK (priority IN ('critical', 'high', 'normal', 'low')),
 payload TEXT NOT NULL CHECK (json_valid(payload))
) STRICT;""",
    "life_state": """CREATE TABLE life_state (
 maple_id INTEGER PRIMARY KEY REFERENCES maple (id),
 revision INTEGER NOT NULL CHECK (revision >= 1),
 mood REAL NOT NULL CHECK (mood BETWEEN 0 AND 100),
 energy REAL NOT NULL CHECK (energy BETWEEN 0 AND 100),
 curiosity REAL NOT NULL CHECK (curiosity BETWEEN 0 AND 100),
 social REAL NOT NULL CHECK (social BETWEEN 0 AND 100),
 activity TEXT NOT NULL CHECK (activity IN ('idle', 'walk', 'sleep', 'read', 'write', 'observe_server', 'rest', 'think')),
 location TEXT NOT NULL CHECK (location IN ('bed', 'desk', 'bookshelf', 'window', 'terminal', 'rug', 'sofa')),
 activity_started_at TEXT NOT NULL CHECK (activity_started_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*+00:00'),
 activity_until TEXT NOT NULL CHECK (activity_until GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*+00:00'),
 last_tick_at TEXT NOT NULL CHECK (last_tick_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*+00:00'),
 last_updated_at TEXT NOT NULL CHECK (last_updated_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*+00:00'),
 tick_counter INTEGER NOT NULL CHECK (tick_counter >= 0),
 interaction_counter INTEGER NOT NULL CHECK (interaction_counter >= 0),
 reaction_kind TEXT CHECK (reaction_kind IN ('greet_happy', 'greet_sleepy', 'pet_happy', 'pet_sleepy')),
 reaction_variant INTEGER CHECK (reaction_variant >= 0),
 reaction_started_at TEXT CHECK (reaction_started_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*+00:00'),
 reaction_until TEXT CHECK (reaction_until GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*+00:00'),
 point_id TEXT CHECK (length(point_id) BETWEEN 1 AND 40),
 route_departed_at TEXT CHECK (route_departed_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*+00:00'),
 route_from_activity TEXT CHECK (route_from_activity IN ('idle', 'walk', 'sleep', 'read', 'write', 'observe_server', 'rest', 'think')),
 route_path TEXT CHECK (route_path IS NULL OR json_valid(route_path)),
 needs_at TEXT CHECK (needs_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*+00:00'),
 decision_counter INTEGER NOT NULL DEFAULT 0 CHECK (decision_counter >= 0),
 action_counter INTEGER NOT NULL DEFAULT 0 CHECK (action_counter >= 0),
 goal_counter INTEGER NOT NULL DEFAULT 0 CHECK (goal_counter >= 0),
 action_priority TEXT NOT NULL DEFAULT 'normal' CHECK (action_priority IN ('critical', 'high', 'normal', 'low')),
 active_goal_id INTEGER REFERENCES goal (id),
 suspended_goal_id INTEGER REFERENCES goal (id),
 suspended_action TEXT CHECK (suspended_action IN ('idle', 'walk', 'sleep', 'read', 'write', 'observe_server', 'rest', 'think')),
 decision_due_since TEXT CHECK (decision_due_since GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*+00:00'),
 critical_since TEXT CHECK (critical_since GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*+00:00'),
 task_tool TEXT CHECK (task_tool IN ('reader', 'writer')),
 task_target TEXT CHECK (length(task_target) BETWEEN 1 AND 60),
 task_title TEXT CHECK (length(task_title) BETWEEN 1 AND 80),
 task_category TEXT CHECK (length(task_category) BETWEEN 1 AND 40),
 CHECK ((reaction_kind IS NULL) = (reaction_variant IS NULL) AND (reaction_kind IS NULL) = (reaction_started_at IS NULL) AND (reaction_kind IS NULL) = (reaction_until IS NULL)),
 CHECK ((route_path IS NULL) = (route_departed_at IS NULL) AND (route_path IS NULL) = (route_from_activity IS NULL)),
 CHECK (active_goal_id IS NULL OR suspended_goal_id IS NULL OR active_goal_id <> suspended_goal_id),
 CHECK ((suspended_goal_id IS NULL) = (suspended_action IS NULL))
) STRICT;""",
    "timeline_event": """CREATE TABLE timeline_event (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 maple_id INTEGER NOT NULL REFERENCES maple (id),
 revision INTEGER NOT NULL CHECK (revision >= 1),
 tick_id INTEGER CHECK (tick_id >= 1),
 kind TEXT NOT NULL CHECK (kind IN ('born', 'activity_changed', 'interaction_accepted', 'downtime_gap', 'goal_started', 'goal_suspended', 'goal_resumed', 'goal_completed', 'goal_abandoned')),
 at TEXT NOT NULL CHECK (at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*+00:00'),
 payload TEXT NOT NULL CHECK (json_valid(payload))
) STRICT;""",
    "journal_entry": """CREATE TABLE journal_entry (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 maple_id INTEGER NOT NULL REFERENCES maple (id),
 revision INTEGER NOT NULL CHECK (revision >= 1),
 tick_id INTEGER CHECK (tick_id >= 1),
 created_at TEXT NOT NULL CHECK (created_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*+00:00'),
 category TEXT NOT NULL CHECK (category IN ('daily_life', 'server_notice', 'interaction', 'reflection', 'milestone')),
 trigger_kind TEXT NOT NULL CHECK (trigger_kind IN ('activity', 'interaction', 'server_problem', 'server_recovery', 'daily_reflection', 'milestone')),
 topic TEXT NOT NULL CHECK (length(topic) BETWEEN 1 AND 80),
 text TEXT NOT NULL CHECK (length(text) BETWEEN 1 AND 240 AND instr(text, char(10)) = 0 AND instr(text, char(13)) = 0),
 importance TEXT NOT NULL CHECK (importance IN ('low', 'normal', 'high')),
 brain_kind TEXT NOT NULL CHECK (brain_kind IN ('rule', 'external')),
 brain_name TEXT NOT NULL CHECK (length(brain_name) BETWEEN 1 AND 32),
 brain_version TEXT NOT NULL CHECK (length(brain_version) BETWEEN 1 AND 16),
 template_id TEXT NOT NULL CHECK (length(template_id) BETWEEN 1 AND 80),
 activity TEXT NOT NULL CHECK (activity IN ('idle', 'walk', 'sleep', 'read', 'write', 'observe_server', 'rest', 'think')),
 expression TEXT NOT NULL CHECK (expression IN ('calm', 'happy', 'curious', 'sleepy', 'focused'))
) STRICT;""",
    "document": """CREATE TABLE document (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 maple_id INTEGER NOT NULL REFERENCES maple (id),
 revision INTEGER NOT NULL CHECK (revision >= 1),
 kind TEXT NOT NULL CHECK (kind IN ('note', 'summary', 'reflection', 'research')),
 title TEXT NOT NULL CHECK (length(title) BETWEEN 1 AND 80 AND instr(title, char(10)) = 0),
 body TEXT NOT NULL CHECK (length(body) BETWEEN 1 AND 4000),
 created_at TEXT NOT NULL CHECK (created_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*+00:00'),
 action_id INTEGER NOT NULL CHECK (action_id >= 0),
 goal_id INTEGER CHECK (goal_id >= 1),
 sources TEXT NOT NULL CHECK (json_valid(sources))
) STRICT;""",
    "tool_use": """CREATE TABLE tool_use (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 maple_id INTEGER NOT NULL REFERENCES maple (id),
 revision INTEGER NOT NULL CHECK (revision >= 1),
 at TEXT NOT NULL CHECK (at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*+00:00'),
 action_id INTEGER NOT NULL CHECK (action_id >= 0),
 goal_id INTEGER CHECK (goal_id >= 1),
 tool TEXT NOT NULL CHECK (tool IN ('reader', 'writer')),
 operation TEXT NOT NULL CHECK (operation IN ('read_started', 'read_completed', 'read_failed', 'write_started', 'write_completed', 'write_failed')),
 target TEXT NOT NULL CHECK (length(target) BETWEEN 1 AND 60),
 title TEXT NOT NULL CHECK (length(title) BETWEEN 1 AND 80),
 category TEXT NOT NULL CHECK (length(category) BETWEEN 1 AND 40),
 status TEXT NOT NULL CHECK (status IN ('success', 'failure')),
 detail TEXT CHECK (length(detail) BETWEEN 1 AND 200 AND instr(detail, char(10)) = 0),
 chars INTEGER CHECK (chars >= 0),
 document_id INTEGER REFERENCES document (id)
) STRICT;""",
    "memory": """CREATE TABLE memory (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 maple_id INTEGER NOT NULL REFERENCES maple (id),
 revision INTEGER NOT NULL CHECK (revision >= 1),
 kind TEXT NOT NULL CHECK (kind IN ('event', 'goal_outcome', 'reading', 'writing', 'interaction', 'conversation', 'knowledge', 'moment', 'preference')),
 tier TEXT NOT NULL CHECK (tier IN ('short_term', 'long_term', 'archive')),
 status TEXT NOT NULL CHECK (status IN ('active', 'candidate', 'accepted', 'rejected')),
 key TEXT CHECK (length(key) BETWEEN 1 AND 120),
 text TEXT NOT NULL CHECK (length(text) BETWEEN 1 AND 240 AND instr(text, char(10)) = 0),
 source TEXT CHECK (length(source) BETWEEN 1 AND 60),
 importance REAL NOT NULL CHECK (importance BETWEEN 0 AND 1),
 evidence_days TEXT NOT NULL CHECK (json_valid(evidence_days)),
 created_at TEXT NOT NULL CHECK (created_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*+00:00'),
 last_seen_at TEXT NOT NULL CHECK (last_seen_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*+00:00'),
 CHECK ((kind = 'preference') = (status <> 'active'))
) STRICT;""",
    "memory_event": """CREATE TABLE memory_event (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 maple_id INTEGER NOT NULL REFERENCES maple (id),
 revision INTEGER NOT NULL CHECK (revision >= 1),
 memory_id INTEGER NOT NULL REFERENCES memory (id),
 kind TEXT NOT NULL CHECK (kind IN ('created', 'reinforced', 'promoted', 'archived', 'confirmed', 'rejected')),
 at TEXT NOT NULL CHECK (at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*+00:00'),
 detail TEXT CHECK (length(detail) BETWEEN 1 AND 200)
) STRICT;""",
    "daily_reflection": """CREATE TABLE daily_reflection (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 maple_id INTEGER NOT NULL REFERENCES maple (id),
 revision INTEGER NOT NULL CHECK (revision >= 1),
 day TEXT NOT NULL UNIQUE CHECK (day GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
 created_at TEXT NOT NULL CHECK (created_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*+00:00'),
 recovered INTEGER NOT NULL CHECK (recovered IN (0, 1)),
 summary TEXT NOT NULL CHECK (length(summary) BETWEEN 1 AND 1000),
 learned TEXT NOT NULL CHECK (json_valid(learned)),
 moments TEXT NOT NULL CHECK (json_valid(moments)),
 memory_candidates TEXT NOT NULL CHECK (json_valid(memory_candidates)),
 promoted TEXT NOT NULL CHECK (json_valid(promoted)),
 preference_candidates TEXT NOT NULL CHECK (json_valid(preference_candidates)),
 intent_type TEXT NOT NULL CHECK (intent_type IN ('learn', 'create', 'recover', 'reflect', 'monitor', 'socialize', 'explore', 'organize', 'maintain', 'practice', 'plan', 'wait', 'play', 'help', 'investigate', 'remember')),
 intent_summary TEXT NOT NULL CHECK (length(intent_summary) BETWEEN 1 AND 120),
 needs TEXT NOT NULL CHECK (json_valid(needs))
) STRICT;""",
    "conversation_message": """CREATE TABLE conversation_message (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 maple_id INTEGER NOT NULL REFERENCES maple (id),
 revision INTEGER NOT NULL CHECK (revision >= 1),
 at TEXT NOT NULL CHECK (at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*+00:00'),
 channel TEXT NOT NULL CHECK (channel IN ('discord')),
 direction TEXT NOT NULL CHECK (direction IN ('in', 'out')),
 speaker TEXT NOT NULL CHECK (speaker IN ('paolo', 'maple')),
 external_id TEXT CHECK (length(external_id) BETWEEN 1 AND 64),
 reply_to INTEGER REFERENCES conversation_message (id),
 text TEXT NOT NULL CHECK (length(text) BETWEEN 1 AND 2000),
 replier_kind TEXT CHECK (replier_kind IN ('rule', 'external')),
 replier_name TEXT CHECK (length(replier_name) BETWEEN 1 AND 32),
 fallback_code TEXT CHECK (length(fallback_code) BETWEEN 1 AND 40),
 latency_ms INTEGER CHECK (latency_ms BETWEEN 0 AND 600000),
 CHECK ((direction = 'in') = (speaker = 'paolo')),
 CHECK ((direction = 'in') = (external_id IS NOT NULL)),
 CHECK ((direction = 'out') = (replier_kind IS NOT NULL))
) STRICT;""",
}

V10_OBJECTS = (
    "CREATE TRIGGER maple_immutable_update BEFORE UPDATE ON maple BEGIN SELECT RAISE(ABORT, 'maple identity is immutable'); END;",
    "CREATE TRIGGER maple_immutable_delete BEFORE DELETE ON maple BEGIN SELECT RAISE(ABORT, 'maple identity is immutable'); END;",
    "CREATE TRIGGER observation_append_only_update BEFORE UPDATE ON observation BEGIN SELECT RAISE(ABORT, 'observations are append-only'); END;",
    "CREATE TRIGGER observation_append_only_delete BEFORE DELETE ON observation BEGIN SELECT RAISE(ABORT, 'observations are append-only'); END;",
    "CREATE TRIGGER journal_entry_observation_append_only_update BEFORE UPDATE ON journal_entry_observation BEGIN SELECT RAISE(ABORT, 'journal references are immutable'); END;",
    "CREATE TRIGGER journal_entry_observation_append_only_delete BEFORE DELETE ON journal_entry_observation BEGIN SELECT RAISE(ABORT, 'journal references are immutable'); END;",
    "CREATE TRIGGER journal_state_no_delete BEFORE DELETE ON journal_state BEGIN SELECT RAISE(ABORT, 'journal state cannot be deleted'); END;",
    "CREATE INDEX decision_by_time ON decision (at);",
    "CREATE INDEX action_event_by_action ON action_event (action_id);",
    "CREATE TRIGGER life_state_no_delete BEFORE DELETE ON life_state BEGIN SELECT RAISE(ABORT, 'life state cannot be deleted'); END;",
    "CREATE TRIGGER life_state_revision_advances BEFORE UPDATE ON life_state WHEN NEW.revision <> OLD.revision + 1 BEGIN SELECT RAISE(ABORT, 'life state revision must advance by exactly one'); END;",
    "CREATE TRIGGER life_state_counters_never_decrease BEFORE UPDATE ON life_state WHEN NEW.tick_counter < OLD.tick_counter OR NEW.interaction_counter < OLD.interaction_counter OR NEW.decision_counter < OLD.decision_counter OR NEW.action_counter < OLD.action_counter OR NEW.goal_counter < OLD.goal_counter BEGIN SELECT RAISE(ABORT, 'RNG counters never decrease'); END;",
    "CREATE INDEX timeline_event_by_time ON timeline_event (at);",
    "CREATE UNIQUE INDEX timeline_event_one_birth ON timeline_event (maple_id) WHERE kind = 'born';",
    "CREATE TRIGGER timeline_event_append_only_update BEFORE UPDATE ON timeline_event BEGIN SELECT RAISE(ABORT, 'timeline is append-only'); END;",
    "CREATE TRIGGER timeline_event_append_only_delete BEFORE DELETE ON timeline_event BEGIN SELECT RAISE(ABORT, 'timeline is append-only'); END;",
    "CREATE INDEX journal_entry_by_time ON journal_entry (created_at);",
    "CREATE TRIGGER journal_entry_append_only_update BEFORE UPDATE ON journal_entry BEGIN SELECT RAISE(ABORT, 'journal entries are immutable'); END;",
    "CREATE TRIGGER journal_entry_append_only_delete BEFORE DELETE ON journal_entry BEGIN SELECT RAISE(ABORT, 'journal entries are immutable'); END;",
    "CREATE TRIGGER goal_append_only_update BEFORE UPDATE ON goal BEGIN SELECT RAISE(ABORT, 'goals are immutable'); END;",
    "CREATE TRIGGER goal_append_only_delete BEFORE DELETE ON goal BEGIN SELECT RAISE(ABORT, 'goals are immutable'); END;",
    "CREATE TRIGGER decision_append_only_update BEFORE UPDATE ON decision BEGIN SELECT RAISE(ABORT, 'decisions are append-only'); END;",
    "CREATE TRIGGER decision_append_only_delete BEFORE DELETE ON decision BEGIN SELECT RAISE(ABORT, 'decisions are append-only'); END;",
    "CREATE TRIGGER action_event_append_only_update BEFORE UPDATE ON action_event BEGIN SELECT RAISE(ABORT, 'action events are append-only'); END;",
    "CREATE TRIGGER action_event_append_only_delete BEFORE DELETE ON action_event BEGIN SELECT RAISE(ABORT, 'action events are append-only'); END;",
    "CREATE INDEX tool_use_by_action ON tool_use (action_id);",
    "CREATE TRIGGER document_append_only_update BEFORE UPDATE ON document BEGIN SELECT RAISE(ABORT, 'documents are append-only'); END;",
    "CREATE TRIGGER document_append_only_delete BEFORE DELETE ON document BEGIN SELECT RAISE(ABORT, 'documents are append-only'); END;",
    "CREATE TRIGGER tool_use_append_only_update BEFORE UPDATE ON tool_use BEGIN SELECT RAISE(ABORT, 'tool provenance is append-only'); END;",
    "CREATE TRIGGER tool_use_append_only_delete BEFORE DELETE ON tool_use BEGIN SELECT RAISE(ABORT, 'tool provenance is append-only'); END;",
    "CREATE UNIQUE INDEX memory_by_key ON memory (key) WHERE key IS NOT NULL;",
    "CREATE INDEX memory_by_tier ON memory (tier, last_seen_at);",
    "CREATE TRIGGER memory_no_delete BEFORE DELETE ON memory BEGIN SELECT RAISE(ABORT, 'memories are never deleted'); END;",
    "CREATE TRIGGER memory_identity_is_fixed BEFORE UPDATE ON memory WHEN NEW.kind <> OLD.kind OR NEW.text <> OLD.text OR NEW.created_at <> OLD.created_at OR NEW.key IS NOT OLD.key BEGIN SELECT RAISE(ABORT, 'a memory keeps its kind, text, key and birth'); END;",
    "CREATE TRIGGER memory_event_append_only_update BEFORE UPDATE ON memory_event BEGIN SELECT RAISE(ABORT, 'memory events are append-only'); END;",
    "CREATE TRIGGER memory_event_append_only_delete BEFORE DELETE ON memory_event BEGIN SELECT RAISE(ABORT, 'memory events are append-only'); END;",
    "CREATE TRIGGER daily_reflection_append_only_update BEFORE UPDATE ON daily_reflection BEGIN SELECT RAISE(ABORT, 'daily reflections are append-only'); END;",
    "CREATE TRIGGER daily_reflection_append_only_delete BEFORE DELETE ON daily_reflection BEGIN SELECT RAISE(ABORT, 'daily reflections are append-only'); END;",
    "CREATE UNIQUE INDEX conversation_message_external ON conversation_message (channel, external_id) WHERE external_id IS NOT NULL;",
    "CREATE TRIGGER conversation_message_append_only_update BEFORE UPDATE ON conversation_message BEGIN SELECT RAISE(ABORT, 'conversations are append-only'); END;",
    "CREATE TRIGGER conversation_message_append_only_delete BEFORE DELETE ON conversation_message BEGIN SELECT RAISE(ABORT, 'conversations are append-only'); END;",
)


UTC = "GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]*+00:00'"
ACTIVITIES = "'idle', 'walk', 'sleep', 'read', 'write', 'observe_server', 'rest', 'think'"
IMMUTABLE = (
    "layout_revision",
    "layout_host",
    "layout_room",
    "layout_point",
    "layout_slot",
    "world_event",
)
NEW_TABLES = {
    "activity_kind": """CREATE TABLE activity_kind (
 id TEXT NOT NULL PRIMARY KEY CHECK(length(CAST(unhex(replace(hex(id), '0', '1')) AS TEXT)) BETWEEN 1 AND 128)
) STRICT;""",
    "room_kind": """CREATE TABLE room_kind (
 id TEXT NOT NULL PRIMARY KEY CHECK(length(CAST(unhex(replace(hex(id), '0', '1')) AS TEXT)) BETWEEN 1 AND 128)
) STRICT;""",
    "layout_revision": f"""CREATE TABLE layout_revision (
 id INTEGER PRIMARY KEY CHECK(id >= 1),
 created_at TEXT NOT NULL CHECK(created_at {UTC}),
 author TEXT NOT NULL CHECK(author IN ('paolo','migration')),
 base_revision INTEGER REFERENCES layout_revision(id)
   CHECK(base_revision >= 1 AND base_revision < id),
 catalog_version INTEGER NOT NULL CHECK(catalog_version >= 1),
 catalog_hash TEXT NOT NULL CHECK(length(catalog_hash)=64 AND catalog_hash NOT GLOB '*[^0-9a-f]*' AND instr(catalog_hash, char(0)) = 0),
 document TEXT NOT NULL CHECK(json_valid(document) AND length(CAST(document AS BLOB)) <= 262144),
 validation_digest TEXT NOT NULL
   CHECK(length(validation_digest)=64 AND validation_digest NOT GLOB '*[^0-9a-f]*' AND instr(validation_digest, char(0)) = 0)
) STRICT;""",
    "world_state": """CREATE TABLE world_state (
 id INTEGER PRIMARY KEY CHECK(id=1),
 active_revision INTEGER NOT NULL REFERENCES layout_revision(id) CHECK(active_revision >= 1)
) STRICT;""",
    "layout_host": """CREATE TABLE layout_host (
 revision INTEGER NOT NULL REFERENCES layout_revision(id) CHECK(revision >= 1),
 id TEXT NOT NULL CHECK(length(CAST(unhex(replace(hex(id), '0', '1')) AS TEXT)) BETWEEN 1 AND 128), PRIMARY KEY(revision,id)
) STRICT;""",
    "layout_room": """CREATE TABLE layout_room (
 revision INTEGER NOT NULL REFERENCES layout_revision(id) CHECK(revision >= 1),
 id TEXT NOT NULL CHECK(length(CAST(unhex(replace(hex(id), '0', '1')) AS TEXT)) BETWEEN 1 AND 128),
 kind TEXT NOT NULL REFERENCES room_kind(id) CHECK(length(CAST(unhex(replace(hex(kind), '0', '1')) AS TEXT)) BETWEEN 1 AND 128),
 PRIMARY KEY(revision,id)
) STRICT;""",
    "layout_point": """CREATE TABLE layout_point (
 revision INTEGER NOT NULL CHECK(revision >= 1),
 host_id TEXT NOT NULL CHECK(length(CAST(unhex(replace(hex(host_id), '0', '1')) AS TEXT)) BETWEEN 1 AND 128),
 id TEXT NOT NULL CHECK(length(CAST(unhex(replace(hex(id), '0', '1')) AS TEXT)) BETWEEN 1 AND 128), PRIMARY KEY(revision,host_id,id),
 FOREIGN KEY(revision,host_id) REFERENCES layout_host(revision,id)
) STRICT;""",
    "layout_slot": """CREATE TABLE layout_slot (
 revision INTEGER NOT NULL CHECK(revision >= 1),
 host_id TEXT NOT NULL CHECK(length(CAST(unhex(replace(hex(host_id), '0', '1')) AS TEXT)) BETWEEN 1 AND 128),
 id TEXT NOT NULL CHECK(length(CAST(unhex(replace(hex(id), '0', '1')) AS TEXT)) BETWEEN 1 AND 128), PRIMARY KEY(revision,host_id,id),
 FOREIGN KEY(revision,host_id) REFERENCES layout_host(revision,id)
) STRICT;""",
    "world_event": f"""CREATE TABLE world_event (
 id INTEGER PRIMARY KEY AUTOINCREMENT CHECK(id >= 1),
 maple_id INTEGER NOT NULL REFERENCES maple(id) CHECK(maple_id >= 1),
 type TEXT NOT NULL CHECK(length(CAST(unhex(replace(hex(type), '0', '1')) AS TEXT)) BETWEEN 1 AND 80),
 at TEXT NOT NULL CHECK(at {UTC}), revision INTEGER NOT NULL CHECK(revision >= 1),
 layout_revision INTEGER REFERENCES layout_revision(id), goal_id INTEGER REFERENCES goal(id),
 action_id INTEGER CHECK(action_id >= 0), decision_id INTEGER REFERENCES decision(id),
 priority TEXT CHECK(priority IN ('critical','high','normal','low')),
 payload TEXT NOT NULL CHECK(json_valid(payload))
) STRICT;""",
    "display_placement": """CREATE TABLE display_placement (
 id TEXT NOT NULL PRIMARY KEY CHECK(length(CAST(unhex(replace(hex(id), '0', '1')) AS TEXT)) BETWEEN 1 AND 128),
 item_id TEXT NOT NULL CHECK(length(CAST(unhex(replace(hex(item_id), '0', '1')) AS TEXT)) BETWEEN 1 AND 128),
 layout_revision INTEGER NOT NULL CHECK(layout_revision >= 1),
 host_id TEXT NOT NULL CHECK(length(CAST(unhex(replace(hex(host_id), '0', '1')) AS TEXT)) BETWEEN 1 AND 128),
 slot_id TEXT NOT NULL CHECK(length(CAST(unhex(replace(hex(slot_id), '0', '1')) AS TEXT)) BETWEEN 1 AND 128),
 active INTEGER NOT NULL CHECK(active IN (0,1)), link TEXT,
 origin_event INTEGER REFERENCES world_event(id),
 FOREIGN KEY(layout_revision,host_id,slot_id) REFERENCES layout_slot(revision,host_id,id)
) STRICT;""",
}


def replace_once(sql: str, before: str, after: str) -> str:
    """Refuse drift in frozen target declarations; does not convert data."""
    assert sql.count(before) == 1, before
    return sql.replace(before, after)


def target_tables() -> dict[str, str]:
    """Fresh CREATE-only targets. Never ALTER/DROP/INSERT source rows."""
    tables = V10_TABLES | NEW_TABLES
    for table, columns in {
        "life_state": ("activity", "route_from_activity", "suspended_action"),
        "journal_entry": ("activity",),
        "decision": ("proposed_action", "executed_action"),
    }.items():
        for column in columns:
            tables[table] = replace_once(
                tables[table],
                f"CHECK ({column} IN ({ACTIVITIES}))",
                "REFERENCES activity_kind(id)",
            )
    life = replace_once(
        tables["life_state"],
        " location TEXT NOT NULL CHECK (location IN ('bed', 'desk', 'bookshelf', 'window', 'terminal', 'rug', 'sofa')),\n",
        "",
    )
    life = replace_once(
        life,
        "point_id TEXT CHECK (length(point_id) BETWEEN 1 AND 40)",
        "point_id TEXT NOT NULL CHECK (length(CAST(unhex(replace(hex(point_id), '0', '1')) AS TEXT)) BETWEEN 1 AND 128)",
    )
    life = replace_once(
        life,
        "AND (route_path IS NULL) = (route_from_activity IS NULL))",
        "AND (route_path IS NULL) = (route_from_activity IS NULL) "
        "AND (route_path IS NULL) = (route_arrives_at IS NULL))",
    )
    life = replace_once(
        life,
        "\n CHECK ((reaction_kind",
        f"""
 layout_revision INTEGER NOT NULL REFERENCES layout_revision(id) CHECK(layout_revision >= 1),
 point_host TEXT NOT NULL CHECK(length(CAST(unhex(replace(hex(point_host), '0', '1')) AS TEXT)) BETWEEN 1 AND 128),
 tx INTEGER NOT NULL CHECK(tx BETWEEN 0 AND 43),
 ty INTEGER NOT NULL CHECK(ty BETWEEN 0 AND 25),
 route_arrives_at TEXT CHECK(route_arrives_at {UTC}),
 CHECK ((reaction_kind""",
    )
    tables["life_state"] = replace_once(
        life,
        "\n) STRICT;",
        """,
 FOREIGN KEY(layout_revision,point_host,point_id) REFERENCES layout_point(revision,host_id,id)
) STRICT;""",
    )
    tables["decision"] = replace_once(
        tables["decision"],
        "\n) STRICT;",
        """,
 executed_layout_revision INTEGER REFERENCES layout_revision(id),
 executed_point_host TEXT CHECK(executed_point_host IS NULL OR length(CAST(unhex(replace(hex(executed_point_host), '0', '1')) AS TEXT)) BETWEEN 1 AND 128),
 executed_point_id TEXT CHECK(executed_point_id IS NULL OR length(CAST(unhex(replace(hex(executed_point_id), '0', '1')) AS TEXT)) BETWEEN 1 AND 128),
 CHECK((executed_layout_revision IS NULL) = (executed_point_host IS NULL)
   AND (executed_layout_revision IS NULL) = (executed_point_id IS NULL)),
 FOREIGN KEY(executed_layout_revision,executed_point_host,executed_point_id)
   REFERENCES layout_point(revision,host_id,id)
) STRICT;""",
    )
    return tables


def fresh_database() -> sqlite3.Connection:
    """Own a new memory DB. No connection or path can be supplied by callers."""
    if sqlite3.sqlite_version_info < (3, 41, 0):
        version = ".".join(map(str, sqlite3.sqlite_version_info))
        raise RuntimeError(f"Schema v11 requires SQLite >=3.41.0; linked SQLite is {version}")
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        for sql in target_tables().values():
            conn.execute(sql)
        for sql in V10_OBJECTS:
            conn.execute(sql)
        conn.execute(
            "CREATE UNIQUE INDEX one_active_display_per_item "
            "ON display_placement(item_id) WHERE active=1"
        )
        for table in IMMUTABLE:
            for op in ("UPDATE", "DELETE"):
                conn.execute(
                    f"CREATE TRIGGER {table}_{op.lower()}_immutable BEFORE {op} ON {table} "
                    "BEGIN SELECT RAISE(ABORT,'immutable structural history'); END"
                )
    except BaseException:
        conn.close()
        raise
    return conn
