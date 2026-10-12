// @vitest-environment happy-dom
import { cleanup, render, screen } from "@testing-library/preact";
import { afterEach, expect, it } from "vitest";
import type { Region } from "../api/world.generated";
import { RoomSummary } from "./RoomSummary";
afterEach(cleanup);
it.each([
  ["bedroom", "Bedroom"], ["living", "Living Room"], ["library", "Library"], ["studio", "Work Studio"],
  ["hall", "Central Hall"], ["future", "Future Space"], ["creation", "Creation Room"], ["system", "System Room"],
] as const)("displays canonical %s name and supplied status", (kind, name) => {
  const region: Region = { id: "supplied-id", kind, status: "closed", floor: { x: 0, y: 0, w: 1, h: 1 } };
  render(<RoomSummary region={region} />);
  expect(screen.getByRole("status").textContent).toBe(name + " — closed. FIXTURE / DEMO, not live Maple.");
});
it("keeps the fallback truthful when the backend region is unavailable", () => {
  render(<RoomSummary region={undefined} />);
  expect(screen.getByRole("status").textContent).toContain("region unavailable");
});
