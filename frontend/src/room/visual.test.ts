import { describe, expect, it } from "vitest";
import { T0_MS, activityAt, iso, makeSnapshot } from "../test/fixtures";
import { MAPLE_FACES, MAPLE_POSES, REACTION_SYMBOLS } from "./assets/manifest";
import { ANCHORS, NEUTRAL_ANCHOR } from "./layout/anchors";
import {
  ACTIVITY_POSE,
  LIGHTING,
  LOCATION_ANCHOR,
  REACTION_SYMBOL,
  describeRoom,
  reactionActive,
  toVisual,
} from "./visual";

// Backend vocabularies (backend/src/maplegotchi/core). Listed here so the test
// fails loudly if the mapping forgets one.
const ACTIVITIES = ["idle", "walk", "sleep", "read", "write", "observe_server", "rest", "think"];
const EXPRESSIONS = ["calm", "happy", "curious", "sleepy", "focused"];
const LOCATIONS = ["bed", "desk", "bookshelf", "window", "terminal", "rug", "sofa"];
const REACTIONS = ["greet_happy", "greet_sleepy", "pet_happy", "pet_sleepy"];
const PHASES = ["morning", "afternoon", "evening", "night"];

describe("activity mapping", () => {
  it.each([
    ["idle", "rug", "stand"],
    ["walk", "rug", "walk"],
    ["sleep", "bed", "sleep"],
    ["read", "bookshelf", "read"],
    ["write", "desk", "sit_write"],
    ["observe_server", "terminal", "sit_monitor"],
    ["rest", "sofa", "rest"], // activity set v2: rest is on the sofa (ADR-0028)
    ["think", "window", "think"],
  ])("%s at %s -> pose %s", (kind, location, pose) => {
    const v = toVisual(makeSnapshot({}, { activity: activityAt(kind, location, iso(0), iso(60)) }), T0_MS);
    expect(v.pose).toBe(pose);
    expect(v.anchor).toBe(location);
    expect(v.recognised).toBe(true);
  });

  it("covers every backend activity and location", () => {
    for (const a of ACTIVITIES) expect(ACTIVITY_POSE[a]).toBeDefined();
    for (const l of LOCATIONS) expect(ANCHORS[LOCATION_ANCHOR[l] ?? "rug"]).toBeDefined();
    expect(Object.keys(LOCATION_ANCHOR).sort()).toEqual([...LOCATIONS].sort());
  });

  it("every pose is in the asset replacement contract", () => {
    for (const pose of Object.values(ACTIVITY_POSE)) expect(MAPLE_POSES).toContain(pose);
  });

  it("falls back safely for unknown activity and location", () => {
    const v = toVisual(
      makeSnapshot({}, { activity: activityAt("juggle", "attic", iso(0), iso(60)) }),
      T0_MS,
    );
    expect(v.pose).toBe("stand");
    expect(v.anchor).toBe(NEUTRAL_ANCHOR);
    expect(v.activityLabel).toBe("juggle");
    expect(v.recognised).toBe(false);
  });
});

describe("expression mapping", () => {
  it.each(EXPRESSIONS)("expression %s is shown as-is", (expression) => {
    const v = toVisual(makeSnapshot({}, { expression }), T0_MS);
    expect(v.face).toBe(expression);
    expect(MAPLE_FACES).toContain(v.face);
  });

  it("unknown expression falls back to calm", () => {
    const v = toVisual(makeSnapshot({}, { expression: "ecstatic" }), T0_MS);
    expect(v.face).toBe("calm");
    expect(v.recognised).toBe(false);
  });
});

describe("reactions", () => {
  const reaction = (kind: string, untilSeconds: number) => ({
    kind,
    variant: 0,
    started_at: iso(0),
    until: iso(untilSeconds),
  });

  it.each(REACTIONS)("%s shows a known symbol while active", (kind) => {
    const v = toVisual(makeSnapshot({}, { reaction: reaction(kind, 8) }), T0_MS + 1000);
    expect(v.reaction?.kind).toBe(kind);
    expect(v.reaction?.symbol).toBe(REACTION_SYMBOL[kind]?.symbol);
    expect(REACTION_SYMBOLS).toContain(v.reaction?.symbol);
    expect(v.reaction?.untilMs).toBe(T0_MS + 8000);
  });

  it("expires exactly at until, without needing a new snapshot", () => {
    const snap = makeSnapshot({}, { reaction: reaction("greet_happy", 8), expression: "happy" });
    expect(toVisual(snap, T0_MS + 7999).reaction).not.toBeNull();
    expect(toVisual(snap, T0_MS + 8000).reaction).toBeNull();
    expect(reactionActive(T0_MS + 8000, T0_MS + 8000)).toBe(false);
  });

  it("unknown reaction kind shows a neutral sparkle", () => {
    const v = toVisual(makeSnapshot({}, { reaction: reaction("hug_happy", 8) }), T0_MS);
    expect(v.reaction?.symbol).toBe("sparkle");
    expect(v.recognised).toBe(false);
  });

  it("malformed until never shows a stuck reaction", () => {
    const v = toVisual(makeSnapshot({}, { reaction: { kind: "pet_happy", variant: 0, started_at: iso(0), until: "?" } }), T0_MS);
    expect(v.reaction).toBeNull();
  });
});

describe("day/night", () => {
  it.each(PHASES)("phase %s maps to its lighting preset", (phase) => {
    const snap = makeSnapshot();
    snap.day = { ...snap.day, phase, is_night: phase === "night" };
    const v = toVisual(snap, T0_MS);
    expect(v.lighting).toBe(LIGHTING[phase as keyof typeof LIGHTING]);
  });

  it("night is darker than evening, which is darker than day", () => {
    expect(LIGHTING.night.darkness).toBeGreaterThan(LIGHTING.evening.darkness);
    expect(LIGHTING.evening.darkness).toBeGreaterThan(LIGHTING.afternoon.darkness);
    expect(LIGHTING.morning.darkness).toBe(0);
  });

  it("unknown phase falls back using is_night", () => {
    const snap = makeSnapshot();
    snap.day = { ...snap.day, phase: "dusk", is_night: true };
    expect(toVisual(snap, T0_MS).lighting).toBe(LIGHTING.night);
    snap.day = { ...snap.day, phase: "dusk", is_night: false };
    expect(toVisual(snap, T0_MS).lighting).toBe(LIGHTING.afternoon);
  });
});

describe("room description", () => {
  it("summarises activity, place, expression, phase and reaction in text", () => {
    const snap = makeSnapshot(
      {},
      {
        activity: activityAt("observe_server", "terminal", iso(0), iso(60)),
        expression: "focused",
        reaction: { kind: "greet_happy", variant: 0, started_at: iso(0), until: iso(8) },
      },
    );
    const text = describeRoom(snap, toVisual(snap, T0_MS));
    expect(text).toBe(
      "Maple is checking the server at the computer, looking focused. It is afternoon in the room. Maple waves hello.",
    );
  });

  it("is deterministic", () => {
    const snap = makeSnapshot();
    expect(toVisual(snap, T0_MS)).toEqual(toVisual(snap, T0_MS));
  });
});

describe("movement is backend truth (ADR-0027)", () => {
  const walking = activityAt("write", "desk", iso(4), iso(1804), {
    phase: "walking",
    pose: "walk",
    position: { x: 330, y: 500 },
    route: {
      departed_at: iso(0),
      arrives_at: iso(4),
      from_activity: "read",
      path: [
        { x: 330, y: 500, distance: 0, node: "bookshelf.front" },
        { x: 330, y: 520, distance: 20, node: "lane.bookshelf" },
        { x: 640, y: 470, distance: 400, node: "writing_desk.chair" },
      ],
    },
  });

  it("walks (not writes) until the backend's arrival time", () => {
    const v = toVisual(makeSnapshot({}, { activity: walking }), T0_MS + 1000);
    expect(v.walking).toBe(true);
    expect(v.pose).toBe("walk");
    expect(v.restPose).toBe("sit_write");
    expect(v.restPosition).toEqual({ x: 640, y: 470 });
    expect(v.route?.arrivesMs).toBe(T0_MS + 4000);
    expect(v.activityLabel).toMatch(/on the way to the writing desk/);
  });

  it("takes the activity's pose once the backend says Maple has arrived", () => {
    const v = toVisual(makeSnapshot({}, { activity: walking }), T0_MS + 4000);
    expect(v.walking).toBe(false);
    expect(v.pose).toBe("sit_write");
    expect(v.activityLabel).toBe("writing");
  });

  it("places a performing Maple at the backend position, not a frontend anchor", () => {
    const east = activityAt("idle", "rug", iso(0), iso(60), { point: "open_area.east", position: { x: 580, y: 550 } });
    const v = toVisual(makeSnapshot({}, { activity: east }), T0_MS);
    expect(v.restPosition).toEqual({ x: 580, y: 550 });
    expect(v.route).toBeNull();
  });

  it("ignores a malformed route instead of inventing movement", () => {
    const route = walking.route;
    if (!route) throw new Error("fixture has a route");
    const broken = { ...walking, route: { ...route, arrives_at: "not a date" } };
    const v = toVisual(makeSnapshot({}, { activity: broken }), T0_MS + 1000);
    expect(v.route).toBeNull();
    expect(v.walking).toBe(false);
  });
});
