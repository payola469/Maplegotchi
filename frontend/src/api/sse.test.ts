import { describe, expect, it, vi } from "vitest";
import { SseParser, createStreamOpener, type StreamHandlers } from "./sse";

const WIRE =
  "retry: 3000\n\n" +
  ": keepalive\n\n" +
  "id: b1-7\nevent: heartbeat\ndata: {\"revision\":7}\n\n" +
  "id: b1-8\r\nevent: interaction\r\ndata: {\"revision\":8}\r\n\r\n";

describe("SseParser", () => {
  it("parses frames, ids, events and CRLF; comments produce activity but no frames", () => {
    const { frames, sawLine } = new SseParser().push(WIRE);
    expect(sawLine).toBe(true);
    expect(frames).toEqual([
      { id: "b1-7", event: "heartbeat", data: '{"revision":7}' },
      { id: "b1-8", event: "interaction", data: '{"revision":8}' },
    ]);
  });

  it("tolerates arbitrary chunking, one character at a time", () => {
    const parser = new SseParser();
    const frames = [...WIRE].flatMap((ch) => parser.push(ch).frames);
    expect(frames.map((f) => f.id)).toEqual(["b1-7", "b1-8"]);
  });

  it("reports a keepalive comment as activity", () => {
    const result = new SseParser().push(": keepalive\n\n");
    expect(result.frames).toEqual([]);
    expect(result.sawLine).toBe(true);
  });

  it("joins multi-line data and defaults the event name", () => {
    const { frames } = new SseParser().push("data: a\ndata: b\n\n");
    expect(frames).toEqual([{ id: null, event: "message", data: "a\nb" }]);
  });
});

function streamResponse(chunks: string[]): Response {
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      const enc = new TextEncoder();
      for (const c of chunks) controller.enqueue(enc.encode(c));
      controller.close();
    },
  });
  return new Response(body, { status: 200, headers: { "content-type": "text/event-stream" } });
}

describe("createStreamOpener", () => {
  it("sends Last-Event-ID and delivers frames, then reports the end", async () => {
    const fetchImpl = vi.fn(async () => streamResponse(["id: b1-9\nevent: journal\n", "data: {}\n\n"]));
    const h: StreamHandlers = { onOpen: vi.fn(), onFrame: vi.fn(), onActivity: vi.fn(), onClose: vi.fn() };
    const done = new Promise<string>((resolve) => {
      h.onClose = resolve;
    });
    createStreamOpener("/api/events", fetchImpl as unknown as typeof fetch)("b1-8", h);
    expect(await done).toBe("ended");
    const init = (fetchImpl.mock.calls[0] as unknown as [string, RequestInit])[1];
    expect((init.headers as Record<string, string>)["last-event-id"]).toBe("b1-8");
    expect(h.onOpen).toHaveBeenCalledOnce();
    expect(h.onFrame).toHaveBeenCalledWith({ id: "b1-9", event: "journal", data: "{}" });
  });

  it("reports an HTTP error without opening", async () => {
    const fetchImpl = vi.fn(async () => new Response("nope", { status: 503 }));
    const h: StreamHandlers = { onOpen: vi.fn(), onFrame: vi.fn(), onActivity: vi.fn(), onClose: vi.fn() };
    const done = new Promise<string>((resolve) => {
      h.onClose = resolve;
    });
    createStreamOpener("/api/events", fetchImpl as unknown as typeof fetch)(null, h);
    expect(await done).toBe("error");
    expect(h.onOpen).not.toHaveBeenCalled();
  });

  it("close() reports once, as aborted", async () => {
    const fetchImpl = vi.fn((_url: string, init: RequestInit) => new Promise<Response>((_resolve, reject) => {
      init.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
    }));
    const h: StreamHandlers = { onOpen: vi.fn(), onFrame: vi.fn(), onActivity: vi.fn(), onClose: vi.fn() };
    const handle = createStreamOpener("/api/events", fetchImpl as unknown as typeof fetch)(null, h);
    handle.close();
    await new Promise((r) => setTimeout(r, 0));
    expect(h.onClose).toHaveBeenCalledOnce();
    expect(h.onClose).toHaveBeenCalledWith("aborted");
  });
});
