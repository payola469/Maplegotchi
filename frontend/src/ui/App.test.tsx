import { describe, expect, it } from "vitest";
import { App, SCAFFOLD_NOTICE } from "./App";

describe("App (Phase 0 scaffold)", () => {
  it("shows only the scaffold notice, no invented Maple state", () => {
    const vnode = App();
    expect(vnode.type).toBe("main");
    expect(vnode.props.children).toBe(SCAFFOLD_NOTICE);
  });
});
