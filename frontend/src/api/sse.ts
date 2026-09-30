// A small Server-Sent Events client over fetch.
//
// Why not EventSource: it hides comment lines, so the UI could not see the
// backend's `: keepalive` and could not tell a quiet stream from a dead one. It
// also offers no control over reconnect timing. The wire format is the backend's
// SSE contract (docs/api.md).

export interface SseFrame {
  id: string | null;
  event: string;
  data: string;
}

/** Incremental parser: feed text chunks, get complete frames. Tolerates any chunking. */
export class SseParser {
  private buffer = "";
  private id: string | null = null;
  private event = "message";
  private data: string[] = [];

  /** Returns frames completed by this chunk, and whether any line (incl. comments) arrived. */
  push(chunk: string): { frames: SseFrame[]; sawLine: boolean } {
    this.buffer += chunk.replace(/\r\n?/g, "\n");
    const frames: SseFrame[] = [];
    let sawLine = false;
    let newline = this.buffer.indexOf("\n");
    while (newline !== -1) {
      const line = this.buffer.slice(0, newline);
      this.buffer = this.buffer.slice(newline + 1);
      sawLine = true;
      if (line === "") {
        if (this.data.length > 0) {
          frames.push({ id: this.id, event: this.event, data: this.data.join("\n") });
        }
        this.event = "message";
        this.data = [];
      } else if (!line.startsWith(":")) {
        const colon = line.indexOf(":");
        const field = colon === -1 ? line : line.slice(0, colon);
        const value = colon === -1 ? "" : line.slice(colon + 1).replace(/^ /, "");
        if (field === "data") this.data.push(value);
        else if (field === "event") this.event = value;
        else if (field === "id") this.id = value;
      }
      newline = this.buffer.indexOf("\n");
    }
    return { frames, sawLine };
  }
}

export interface StreamHandlers {
  onOpen(): void;
  onFrame(frame: SseFrame): void;
  onActivity(): void; // any bytes, including keepalive comments
  onClose(reason: "ended" | "error" | "aborted"): void;
}

export interface StreamHandle {
  close(): void;
}

export type OpenStream = (lastEventId: string | null, handlers: StreamHandlers) => StreamHandle;

export function createStreamOpener(
  url = "/api/events",
  fetchImpl: typeof fetch = fetch.bind(globalThis),
): OpenStream {
  return (lastEventId, handlers) => {
    const controller = new AbortController();
    let closed = false;
    const finish = (reason: "ended" | "error" | "aborted") => {
      if (!closed) {
        closed = true;
        handlers.onClose(reason);
      }
    };
    void (async () => {
      try {
        const headers: Record<string, string> = { accept: "text/event-stream" };
        if (lastEventId) headers["last-event-id"] = lastEventId;
        const response = await fetchImpl(url, {
          headers,
          cache: "no-store",
          signal: controller.signal,
        });
        if (!response.ok || !response.body) {
          finish("error");
          return;
        }
        handlers.onOpen();
        const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
        const parser = new SseParser();
        for (;;) {
          const { value, done } = await reader.read();
          if (done) break;
          const { frames, sawLine } = parser.push(value);
          if (sawLine || value.length > 0) handlers.onActivity();
          for (const frame of frames) handlers.onFrame(frame);
        }
        finish("ended");
      } catch {
        finish(controller.signal.aborted ? "aborted" : "error");
      }
    })();
    return {
      close() {
        controller.abort();
        finish("aborted");
      },
    };
  };
}
