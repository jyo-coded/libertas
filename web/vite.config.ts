import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The built console is served by the Libertas API itself (same origin, strict CSP, no CDNs).
export default defineConfig({
  plugins: [react()],
  base: "/",
  build: { outDir: "../libertas/api/forum", emptyOutDir: true, sourcemap: false, chunkSizeWarningLimit: 1600 },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8700",
      "/ws": { target: "ws://127.0.0.1:8700", ws: true },
    },
  },
});
