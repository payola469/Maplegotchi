import type { Region } from "../api/world.generated";

const names: Record<Region["kind"], string> = {
  bedroom: "Bedroom", living: "Living Room", library: "Library", studio: "Work Studio",
  hall: "Central Hall", future: "Future Space", creation: "Creation Room", system: "System Room",
};
export function RoomSummary({ region }: { region: Region | undefined }) {
  const description = region ? names[region.kind] + " — " + region.status : "Backend passage — region unavailable";
  return <section aria-label="Current fixture room" tabIndex={0}>
    <h2>Maple's current fixture room</h2>
    <p role="status" aria-live="polite" aria-atomic="true">{description}. FIXTURE / DEMO, not live Maple.</p>
  </section>;
}
