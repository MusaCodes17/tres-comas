import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

// The backend dev server listens on 127.0.0.1:8001. Use the IP literal rather
// than "localhost": Node 17+ resolves localhost to ::1 first, and the backend
// is not bound to IPv6, so the proxy would fail intermittently.
const BACKEND = "http://127.0.0.1:8001";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      manifest: {
        name: "Tres Comas",
        short_name: "Tres Comas",
        start_url: "/",
        display: "standalone",
        background_color: "#0f172a",
        theme_color: "#0f172a",
        icons: [
          {
            src: "/icon.svg",
            sizes: "any",
            type: "image/svg+xml",
            purpose: "any maskable",
          },
        ],
      },
      workbox: {
        // API, MCP and health routes are served by the backend, never the SPA shell.
        navigateFallbackDenylist: [/^\/api/, /^\/mcp/, /^\/health/],
      },
    }),
  ],
  server: {
    port: 5174, // Anton uses 5173
    proxy: {
      "/api": BACKEND,
      "/health": BACKEND,
    },
  },
});
