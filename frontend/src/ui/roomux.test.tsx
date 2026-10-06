// @vitest-environment happy-dom
// Phase A8: the room UX shows backend truth — bubble, furniture capabilities, the
// shared life-event feed, and the owner Inspector.
import { act, cleanup, fireEvent, render, screen } from "@testing-library/preact";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ReadApi } from "../api/read";
import type { DecisionOut, LifeEventOut, RoomOut } from "../api/types";
import type { CreateRoomScene } from "../room/scene/RoomScene";
import { toVisual } from "../room/visual";
import { LIFE_EVENTS_KEPT, Store } from "../state/store";
import { T0_MS, activityAt, iso, makeBrainHealth, makeSnapshot } from "../test/fixtures";
import { App } from "./App";
import { ActivityFeed, lifeEventText } from "./feed";
import { Inspector } from "./inspector/Inspector";
import { RoomOverlay, hotspots } from "./room/RoomOverlay";

const ROOM: RoomOut = {
  width: 1000,
  height: 600,
  floor_y: 380,
  walk_speed: 120,
  furniture: [
    { id: "writing_desk", label: "Writing Desk", location: "desk" },
    { id: "computer_desk", label: "Computer Desk", location: "terminal" },
    { id: "open_area", label: "Open Area", location: "rug" },
  ],
  points: [
    { id: "writing_desk.chair", location: "desk", furniture: "writing_desk", x: 640, y: 470,
      facing: "back", pose: "sit_write", allowed_actions: ["write"] },
    { id: "computer_desk.chair", location: "terminal", furniture: "computer_desk", x: 840, y: 470,
      facing: "back", pose: "sit_monitor", allowed_actions: ["observe_server"] },
    { id: "open_area.center", location: "rug", furniture: "open_area", x: 480, y: 545,
      facing: "front", pose: "stand", allowed_actions: ["idle", "walk"] },
    { id: "open_area.east", location: "rug", furniture: "open_area", x: 580, y: 550,
      facing: "front", pose: "stand", allowed_actions: ["idle", "walk"] },
  ],
}; // prettier-ignore

function event(id: string, type: string, revision: number, payload: LifeEventOut["payload"] = {}): LifeEventOut {
  return { id, type, at: iso(revision), revision, goal_id: null, action_id: 1, priority: null, payload };
}

beforeEach(() => {
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: false,
    media: query,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
  }));
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("furniture hotspots", () => {
  it("one per furniture, with what it is for, from /api/room", () => {
    const spots = hotspots(ROOM);
    expect(spots.map((s) => s.id)).toEqual(["writing_desk", "computer_desk", "open_area"]);
    expect(spots[2]?.uses).toEqual(["idling", "walking"]);
  });

  it("marks the furniture Maple is using now, and explains each piece", () => {
    const snap = makeSnapshot({}, { activity: activityAt("write", "desk") });
    render(<RoomOverlay snapshot={snap} visual={toVisual(snap, T0_MS)} room={ROOM} />);
    const desk = screen.getByTestId("hotspot-writing_desk");
    expect(desk.getAttribute("class")).toContain("hotspot--active");
    expect(desk.getAttribute("aria-label")).toBe("Writing Desk: for writing — in use now");
    expect(screen.getByTestId("hotspot-computer_desk").getAttribute("class")).not.toContain("hotspot--active");
  });
});

describe("speech bubble", () => {
  it("shows the backend's bubble text at Maple", () => {
    const snap = makeSnapshot({}, {
      activity: activityAt("read", "bookshelf"),
      bubble: { kind: "reading", text: "Reading “Maple's room”" },
    });
    render(<RoomOverlay snapshot={snap} visual={toVisual(snap, T0_MS)} room={ROOM} />);
    const bubble = screen.getByTestId("speech-bubble");
    expect(bubble.textContent).toBe("Reading “Maple's room”");
    expect(bubble.getAttribute("class")).toContain("speech--reading");
  });

  it("shows nothing when the backend sends no bubble, or while walking", () => {
    const quiet = makeSnapshot();
    const { unmount } = render(<RoomOverlay snapshot={quiet} visual={toVisual(quiet, T0_MS)} room={null} />);
    expect(screen.queryByTestId("speech-bubble")).toBeNull();
    unmount();
    const walking = makeSnapshot({}, {
      bubble: { kind: "thinking", text: "Thinking…" },
      activity: activityAt("think", "window", iso(4), iso(600), {
        phase: "walking",
        route: { departed_at: iso(0), arrives_at: iso(4), from_activity: "idle",
                 path: [{ x: 480, y: 545, distance: 0, node: "open_area.center" },
                        { x: 500, y: 470, distance: 80, node: "window.view" }] },
      }),
    }); // prettier-ignore
    render(<RoomOverlay snapshot={walking} visual={toVisual(walking, T0_MS + 1000)} room={null} />);
    expect(screen.queryByTestId("speech-bubble")).toBeNull();
  });
});

describe("shared life events", () => {
  it("are merged without duplicates, in order, and capped", () => {
    const store = new Store();
    store.addLifeEvents([event("action:2", "arrived", 2), event("action:1", "walking_started", 1)]);
    store.addLifeEvents([event("action:2", "arrived", 2), event("tool:1", "read_completed", 3)]);
    expect(store.get().lifeEvents.map((e) => e.id)).toEqual(["action:1", "action:2", "tool:1"]);
    store.addLifeEvents(Array.from({ length: 100 }, (_, i) => event(`action:${i + 10}`, "arrived", i + 10)));
    expect(store.get().lifeEvents).toHaveLength(LIFE_EVENTS_KEPT);
  });

  it("are worded from the payload, and unknown types are skipped", () => {
    expect(lifeEventText(event("a", "walking_started", 1, { furniture: "bookshelf" }))).toBe(
      "Walking to the bookshelf.",
    );
    expect(lifeEventText(event("t", "read_completed", 1, { title: "Maple's room" }))).toBe("Read “Maple's room”.");
    expect(lifeEventText(event("x", "arrived", 1))).toBeNull();
    render(<ActivityFeed events={[event("a", "goal_started", 1, { summary: "Learn something" })]} />);
    expect(screen.getByTestId("activity-feed").textContent).toContain("New goal: Learn something.");
  });
});

function readApi(decisions: DecisionOut[] = []): ReadApi {
  return {
    room: vi.fn(async () => ROOM),
    lifeEvents: vi.fn(async () => ({ events: [], last_revision: 0 })),
    decisions: vi.fn(async () => decisions),
    memory: vi.fn(async () => [
      { id: 4, kind: "reading", tier: "short_term", status: "active", text: "I read Maple's room.",
        key: null, source: null, importance: 0.4, evidence_days: [], created_at: iso(0),
        last_seen_at: iso(0) },
    ]),
    brainHealth: vi.fn(async () => makeBrainHealth()),
    reflections: vi.fn(async () => [
      { day: "2026-09-30", created_at: iso(0), recovered: false, summary: "A day.", learned: [], moments: [],
        memory_candidates: [{ memory_id: 4, text: "I read Maple's room.", reason: "something I learned" }],
        promoted: [4], preference_candidates: [], intent: { type: "create", summary: "Write about it" } },
    ]),
  }; // prettier-ignore
}

const DECISION: DecisionOut = {
  id: 7, revision: 9, at: iso(-30), trigger: "action_completed", priority: null,
  director: { kind: "external", name: "antigravity", version: "1" },
  context_summary: "trigger=action_completed", proposal: {
    goal_op: "keep", goal_type: null, goal_summary: null, horizon_minutes: null, abandon_reason: null,
    action: "dance", duration_minutes: 10, reason: "Felt like it." },
  verdict: "rejected", reason_code: "unknown_action", clamped: {},
  executed: { by: "rule", reason: "Rule direction: keep the learn goal with read.", goal_id: 1,
              action_id: 3, action: "read", point: "bookshelf.front", duration_minutes: 30 },
  latency_ms: 120,
}; // prettier-ignore

describe("Maple Inspector", () => {
  it("shows goal, action, destination, decisions, problems, memory and identity", async () => {
    const snap = makeSnapshot({}, {
      goal: { id: 1, type: "learn", summary: "Learn something new", source: "rule",
              started_at: iso(-60), horizon_until: iso(3600) },
      activity: activityAt("read", "bookshelf", iso(-10), iso(1800), {
        task: { tool: "reader", target: "library:the_room", title: "Maple's room", category: "home" } }),
    }); // prettier-ignore
    const api = readApi([DECISION]);
    const events = [event("action:5", "activity_interrupted", 8, { activity: "write", cause: "server_problem" })];
    render(<Inspector snapshot={snap} lifeEvents={events} api={api} onClose={() => undefined} />);
    for (let i = 0; i < 3; i++) await act(async () => {});
    const text = screen.getByTestId("inspector").textContent ?? "";
    expect(text).toContain("learn #1: Learn something new");
    expect(text).toContain("reader: Maple's room [library:the_room]");
    expect(text).toContain("bookshelf / bookshelf.front");
    expect(text).toContain("Felt like it.");
    expect(text).toContain("rule · rule_brain");
    expect(text).toContain("rule · rule_director");
    expect(screen.getByTestId("inspector-decisions").textContent).toContain("rejected (unknown_action)");
    expect(screen.getByTestId("inspector-problems").textContent).toContain("activity interrupted: server_problem");
    expect(screen.getByTestId("inspector-memory").textContent).toContain("promoted");
    expect(api.decisions).toHaveBeenCalled();
  });

  it("is a separate view opened from the room and closed back to it", async () => {
    const store = new Store();
    const create = vi.fn<CreateRoomScene>(async () => ({
      update: () => undefined,
      setReducedMotion: () => undefined,
      destroy: () => undefined,
    }));
    render(<App store={store} createScene={create} onInteract={vi.fn()} onRefresh={vi.fn()} readApi={readApi()} />);
    await act(() => {
      store.applySnapshot(makeSnapshot());
      store.setStatus("live");
    });
    fireEvent.click(screen.getByRole("button", { name: "Inspector" }));
    await act(async () => {});
    expect(screen.getByTestId("inspector")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Back to the room" }));
    expect(screen.queryByTestId("inspector")).toBeNull();
  });
});
