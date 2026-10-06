import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Same-origin in development: the app on :5173 forwards every /api request to the production
// backend on :8000, so the browser never needs CORS. Production paths already start with /api,
// so no rewrite is needed.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: false,
      },
    },
  },
});
