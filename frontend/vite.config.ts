import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const runtime = globalThis as {
  process?: { env?: Record<string, string | undefined> };
};
const backendTarget =
  runtime.process?.env?.VITE_BACKEND_PROXY_TARGET ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: backendTarget,
        changeOrigin: false,
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
    css: true,
  },
});
