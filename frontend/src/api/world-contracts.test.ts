import { describe, expect, it } from "vitest";
import catalogJson from "../../../docs/fixtures/maple-room/r1a-10/catalog.json?raw";
import idleJson from "../../../docs/fixtures/maple-room/r1a-10/world-idle.json?raw";
import walkingJson from "../../../docs/fixtures/maple-room/r1a-10/world-walking.json?raw";
import emptyJson from "../../../docs/fixtures/maple-room/r1a-10/placements-empty.json?raw";
import displayJson from "../../../docs/fixtures/maple-room/r1a-10/placements-display.json?raw";
import type { WorldOut, WorldCatalogOut, WorldPlacementsOut } from "./world.generated";

// JSON is validated by the backend exporter/DTO tests. This verifies the consumer
// can use generated contracts without an alternate schema or world implementation.
const idle = JSON.parse(idleJson) as WorldOut;
const walking = JSON.parse(walkingJson) as WorldOut;
const catalog = JSON.parse(catalogJson) as WorldCatalogOut;
const empty = JSON.parse(emptyJson) as WorldPlacementsOut;
const display = JSON.parse(displayJson) as WorldPlacementsOut;

describe("R1A-10 synthetic handoff", () => {
  it("labels every response and shares canonical identities", () => {
    for (const value of [idle, walking, catalog, empty, display]) {
      expect(value.source).toBe("development_fixture");
      expect(value.status).toBe("synthetic");
      expect(value.layout_revision).toBe(idle.layout_revision);
      expect(value.catalog_version).toBe(catalog.catalog_version);
    }
  });
  it("receives canonical geometry and references without frontend derivation", () => {
    expect(idle.regions).toHaveLength(8);
    expect(idle.doors).toHaveLength(7);
    expect(idle.objects).toHaveLength(28);
    expect(idle.points).toHaveLength(17);
    expect(idle.slots).toHaveLength(12);
    expect(idle.walkable).toHaveLength(431);
    expect(catalog.types).toHaveLength(15);
    for (const object of idle.objects) {
      expect(catalog.types.some((type) => type.id === object.type_id)).toBe(true);
    }
  });
  it("distinguishes tile position from an exact edge and retains server timing", () => {
    const actor = walking.snapshot.maple;
    expect(idle.snapshot.maple.position.kind).toBe("tile");
    expect(idle.snapshot.maple.route).toBeNull();
    if (actor.position.kind !== "edge") throw new Error("expected backend edge");
    expect(actor.position.edge.progress_us).toBe(125000);
    expect(actor.route?.arrives_at).toBe("2026-10-11T00:00:02.750000Z");
    expect(actor.destination_point.instance_id).toBe("idle.hall_east");
  });
  it("keeps empty displays empty and names a synthetic existing-item relationship", () => {
    expect(empty.items).toEqual([]);
    expect(empty.placements).toEqual([]);
    expect(empty.storage_item_ids).toEqual([]);
    expect(display.placements).toHaveLength(1);
    expect(display.placements[0]?.item_id).toBe(display.items[0]?.id);
    expect(display.placements[0]?.host_id).toBe("bedside.bedroom");
  });
});
