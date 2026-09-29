import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// Same-origin in development: the SPA on :5173 proxies /api to the backend on :8000, so session
// cookies and the Zoho OAuth callback (http://localhost:5173/api/v1/oauth/zoho-books/callback)
// work exactly as they will behind Caddy in production (plan §33.2).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      // CLARIO_API_URL lets a developer point the SPA at a backend on another port.
      "/api": {
        target: process.env.CLARIO_API_URL ?? "http://127.0.0.1:8000",
        changeOrigin: false,
        xfwd: true,
      },
    },
  },
  build: {
    sourcemap: true,
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
});
