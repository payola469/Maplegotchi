// Static guards over the frontend source. The backend is the only place Maple's
// rules live; these tests fail if the UI starts re-implementing them.

import { describe, expect, it } from "vitest";
import { FURNITURE } from "./room/layout/anchors";
import { FURNITURE_ASSETS } from "./room/assets/manifest";

const SOURCES = import.meta.glob<string>(["./**/*.{ts,tsx}", "!./**/*.test.{ts,tsx}", "!./test/**"], {
  query: "?raw",
  import: "default",
  eager: true,
});
const STYLES = import.meta.glob<string>("./**/*.css", { query: "?raw", import: "default", eager: true });

describe("no frontend rule duplicating backend behaviour", () => {
  const code = Object.entries(SOURCES);

  it("finds the sources", () => {
    expect(code.length).toBeGreaterThan(15);
  });

  it.each([
    // Backend cooldowns / limits / reaction length (core/interaction.py) must not appear as numbers.
    ["greet cooldown", /\b60(?:_?000)?\b.*cooldown|cooldown.*\b60(?:_?000)?\b/i],
    ["pet cooldown", /\b30(?:_?000)?\b.*cooldown|cooldown.*\b30(?:_?000)?\b/i],
    ["reaction duration", /\b8(?:_?000)?\b.*reaction|reaction.*\b8(?:_?000)?\b/i],
    ["need decay / thresholds", /\b(decay|threshold)\b/i],
    ["expression rules", /expression\s*=\s*["'](happy|sleepy|curious|focused)/],
    ["activity choice", /activity\s*=\s*["'](sleep|read|write|observe_server|rest|walk)/],
    ["local availability", /available\s*[:=]\s*true/],
  ])("no %s in UI code", (_label, pattern) => {
    const offenders = code.filter(([, text]) => pattern.test(text)).map(([file]) => file);
    expect(offenders).toEqual([]);
  });

  it("uses no raw HTML sinks or inline style attributes (CSP)", () => {
    for (const [file, text] of code) {
      expect(text, file).not.toMatch(/innerHTML|dangerouslySetInnerHTML|\bstyle=\{/);
    }
  });

  it("honours prefers-reduced-motion in CSS", () => {
    expect(Object.values(STYLES).join("\n")).toMatch(/@media \(prefers-reduced-motion: reduce\)/);
  });

  it("collapses to one column on narrow screens (no horizontal scroll)", () => {
    const css = Object.values(STYLES).join("\n");
    expect(css).toMatch(/overflow-x:\s*hidden/);
    expect(css).toMatch(/@media \(max-width: 600px\)[\s\S]*grid-template-columns:\s*minmax\(0, 1fr\)/);
  });
});

describe("asset manifest", () => {
  it("describes every furniture piece in the layout", () => {
    expect(Object.keys(FURNITURE_ASSETS).sort()).toEqual(Object.keys(FURNITURE).sort());
    for (const [key, asset] of Object.entries(FURNITURE_ASSETS)) expect(asset.key).toBe(key);
  });
});
