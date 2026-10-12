import type { WorldOut, WorldCatalogOut } from "../api/world.generated";
export function assertFixture(world: WorldOut, catalog: WorldCatalogOut): void {
  if (world.source !== "development_fixture" || world.status !== "synthetic" || catalog.source !== "development_fixture" || catalog.status !== "synthetic" || world.catalog_version !== catalog.catalog_version || world.layout_revision !== catalog.layout_revision || world.contract_version !== "r1a-10.v1" || catalog.contract_version !== world.contract_version) throw new Error("Expected matching labeled R1A-10 development fixtures");
}
export function fixturePreviewEnabled(dev: boolean, search: string): boolean {
  const values = new URLSearchParams(search).getAll("room");
  return dev && values.length === 1 && values[0] === "fixture";
}
