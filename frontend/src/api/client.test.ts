import { describe, expect, it, vi } from "vitest";
import { makeInteraction, makeSnapshot } from "../test/fixtures";
import { ApiError, createApiClient } from "./client";

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

describe("api client", () => {
  it("fetches the snapshot uncached", async () => {
    const fetchImpl = vi.fn(async () => json(makeSnapshot()));
    const snap = await createApiClient(fetchImpl as unknown as typeof fetch).snapshot();
    expect(snap.revision).toBe(10);
    const [url, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/snapshot");
    expect(init.cache).toBe("no-store");
  });

  it("returns both accepted (200) and rejected (429) interaction results", async () => {
    const rejected = makeInteraction({ accepted: false, reason: "cooldown", retry_after_seconds: 42 });
    const fetchImpl = vi
      .fn()
      .mockResolvedValueOnce(json(makeInteraction()))
      .mockResolvedValueOnce(json(rejected, 429));
    const api = createApiClient(fetchImpl as unknown as typeof fetch);
    expect((await api.interact("greet")).accepted).toBe(true);
    const second = await api.interact("pet");
    expect(second.accepted).toBe(false);
    expect(second.retry_after_seconds).toBe(42);
    expect(fetchImpl.mock.calls[1]?.[0]).toBe("/api/interactions/pet");
    expect((fetchImpl.mock.calls[1]?.[1] as RequestInit).method).toBe("POST");
  });

  it("raises ApiError with the status for other responses and network failures", async () => {
    const api = createApiClient(vi.fn(async () => new Response("", { status: 403 })) as unknown as typeof fetch);
    await expect(api.interact("greet")).rejects.toMatchObject({ status: 403 });
    const down = createApiClient(vi.fn(async () => Promise.reject(new TypeError("down"))) as unknown as typeof fetch);
    await expect(down.snapshot()).rejects.toBeInstanceOf(ApiError);
  });
});
