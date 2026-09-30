import preact from "@preact/preset-vite";
import { defineConfig } from "vitest/config";

// The built assets in dist/ are served by FastAPI (same origin as /api), per CLAUDE.md D13.
// In development, Vite proxies /api to the local backend. Both bind to localhost only.
// Dev backend port 8470 is documented in CLAUDE.md §5 ("Dev ports") and README.md.
export default defineConfig({
  plugins: [preact()],
  server: {
    host: "127.0.0.1",
    proxy: {
      "/api": "http://127.0.0.1:8470",
    },
  },
  build: {
    outDir: "dist",
    sourcemap: true,
  },
  test: {
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
