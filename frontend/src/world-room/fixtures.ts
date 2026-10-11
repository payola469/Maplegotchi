// Imported only by the development preview. No API, live store or SSE dependency.
import idleJson from "../../../docs/fixtures/maple-room/r1a-10/world-idle.json?raw";
import walkingJson from "../../../docs/fixtures/maple-room/r1a-10/world-walking.json?raw";
import catalogJson from "../../../docs/fixtures/maple-room/r1a-10/catalog.json?raw";
import type { WorldOut, WorldCatalogOut } from "../api/world.generated";
export const fixtureWorlds = { idle: JSON.parse(idleJson) as WorldOut, walking: JSON.parse(walkingJson) as WorldOut };
export const fixtureCatalog = JSON.parse(catalogJson) as WorldCatalogOut;
