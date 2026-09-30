import { describe, expect, it } from "vitest";
import { T0, T0_MS, makeSnapshot, observation } from "../test/fixtures";
import { availability, formatAge, formatClock, hostReadings, remainingSeconds } from "./presentation";

describe("presentation helpers", () => {
  it("reads availability from the backend list", () => {
    expect(availability(makeSnapshot(), "greet")?.available).toBe(true);
    expect(availability(null, "pet")).toBeNull();
  });

  it("counts a backend wait down from the snapshot's own time", () => {
    expect(remainingSeconds(42, T0, T0_MS)).toBe(42);
    expect(remainingSeconds(42, T0, T0_MS + 10_500)).toBe(32);
    expect(remainingSeconds(42, T0, T0_MS + 60_000)).toBe(0);
    expect(remainingSeconds(null, T0, T0_MS)).toBeNull();
  });

  it("formats ages and times, with honest fallbacks", () => {
    expect(formatAge(59)).toBe("0 min");
    expect(formatAge(3 * 3600 + 120)).toBe("3 h 2 min");
    expect(formatAge(86400)).toBe("1 day, 0 h");
    expect(formatAge(Number.NaN)).toBe("unknown");
    expect(formatClock(null)).toBe("never");
    expect(formatClock("garbage")).toBe("unknown");
  });

  it("host readings never invent values", () => {
    const snap = makeSnapshot();
    snap.server = {
      ...snap.server,
      host: [
        observation({ metric: "cpu_usage", value: 18.4 }),
        observation({ metric: "memory_usage", status: "unknown", value: null }),
        observation({ metric: "disk_usage", subject: "/data", value: 90 }), // not the root disk
        observation({ metric: "temperature", status: "unavailable", value: null, reason: "no sensor" }),
      ],
    };
    expect(hostReadings(snap)).toEqual([
      { label: "CPU", text: "18%", known: true },
      { label: "RAM", text: "unknown", known: false },
      { label: "Disk", text: "no data", known: false },
      { label: "Temperature", text: "unavailable (no sensor)", known: false },
    ]);
  });
});
