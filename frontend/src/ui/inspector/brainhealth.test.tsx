// @vitest-environment happy-dom
// Brain Health in the owner Inspector (ADR-0034): healthy, degraded, offline and
// unknown come only from the backend; anything unavailable reads "Unknown".
import { act, cleanup, render, screen } from "@testing-library/preact";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ReadApi } from "../../api/read";
import type { BrainHealthOut } from "../../api/types";
import { makeBrainHealth, makeSnapshot } from "../../test/fixtures";
import { BrainHealthCard, Inspector, latencyLabel, modelLabel } from "./Inspector";

afterEach(cleanup);

function text(id: string): string {
  return screen.getByTestId(id).textContent ?? "";
}

describe("Brain Health card", () => {
  it("shows a healthy brain with provider, model, latencies and today's counts", () => {
    render(<BrainHealthCard health={makeBrainHealth()} error={null} />);
    const card = text("brain-health");
    expect(text("brain-health-status")).toBe("Healthy");
    expect(card).toContain("command");
    expect(card).toContain("Gemini 3.8 Flash Medium");
    const director = text("brain-health-director");
    expect(director).toContain("External");
    expect(director).toContain("20.2s");
    expect(director).toContain("Fallbacks today2");
    expect(director).toContain("Timeouts today2");
    const replier = text("brain-health-replier");
    expect(replier).toContain("14.7s");
    expect(replier).toContain("Fallbacks today1");
    expect(card).toContain("2026-09-30");
  });

  it("shows degraded with the fallback code of the latest call", () => {
    const health = makeBrainHealth(
      { status: "degraded", status_reason: "latest_call_failed" },
      {},
      { last_call: { at: makeBrainHealth().as_of, ok: false, code: "timeout", latency_ms: 12000 } },
    );
    render(<BrainHealthCard health={health} error={null} />);
    expect(text("brain-health-status")).toBe("Degraded");
    expect(screen.getByTestId("brain-health-status").className).toContain("badge--degraded");
    expect(text("brain-health-replier")).toContain("fell back (timeout)");
  });

  it("shows offline without inventing provider or model", () => {
    const health = makeBrainHealth({
      status: "offline",
      status_reason: "companion_unreachable",
      provider: null,
      model: null,
      companion: { probed: true, reachable: false, error: "timeout" },
    });
    render(<BrainHealthCard health={health} error={null} />);
    expect(text("brain-health-status")).toBe("Offline");
    const card = text("brain-health");
    expect(card).toContain("ProviderUnknown");
    expect(card).toContain("ModelUnknown");
    expect(card).not.toContain("Gemini");
    expect(card).toContain("did not answer");
  });

  it("shows unknown when nothing has been called yet", () => {
    const empty = { last_call: null, last_success_at: null, fallbacks_today: 0, timeouts_today: 0 };
    const health = makeBrainHealth(
      { status: "unknown", status_reason: "no_calls_yet", last_success_at: null },
      empty,
      empty,
    );
    render(<BrainHealthCard health={health} error={null} />);
    expect(text("brain-health-status")).toBe("Unknown");
    expect(text("brain-health-director")).toContain("none yet");
    expect(text("brain-health")).toContain("Last successnone yet");
  });

  it("shows Unknown everywhere when the endpoint fails, and unrecognised statuses as Unknown", () => {
    render(<BrainHealthCard health={null} error="network error" />);
    expect(text("brain-health-status")).toBe("Unknown");
    expect(text("brain-health")).toContain("could not be loaded");
    expect(text("brain-health")).toContain("ProviderUnknown");
    cleanup();
    render(<BrainHealthCard health={makeBrainHealth({ status: "exploded" })} error={null} />);
    expect(text("brain-health-status")).toBe("Unknown");
  });

  it("formats only what the backend sent", () => {
    expect(modelLabel(null)).toBe("Unknown");
    expect(modelLabel("gemini-3.8-flash-medium")).toBe("Gemini 3.8 Flash Medium");
    expect(latencyLabel(null)).toBe("Unknown");
    expect(latencyLabel(850)).toBe("850 ms");
    expect(latencyLabel(20200)).toBe("20.2s");
  });

  it("is part of the Inspector, fetched with GET only", async () => {
    const brainHealth = vi.fn(async (): Promise<BrainHealthOut> => makeBrainHealth());
    const api: ReadApi = {
      room: vi.fn(),
      lifeEvents: vi.fn(async () => ({ events: [], last_revision: 0 })),
      decisions: vi.fn(async () => []),
      memory: vi.fn(async () => []),
      reflections: vi.fn(async () => []),
      brainHealth,
    };
    render(<Inspector snapshot={makeSnapshot()} lifeEvents={[]} api={api} onClose={() => undefined} />);
    for (let i = 0; i < 3; i++) await act(async () => {});
    expect(brainHealth).toHaveBeenCalled();
    expect(text("brain-health-status")).toBe("Healthy");
  });
});
