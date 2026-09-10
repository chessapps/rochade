import tailwind from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

import pkg from "./package.json" with { type: "json" };

export default defineConfig({
  plugins: [react(), tailwind()],
  define: { __APP_VERSION__: JSON.stringify(pkg.version) },
  // Caddy serves the built app under /admin and strips the prefix before
  // looking on disk, so asset URLs must carry it or they land on the hall app.
  base: "/admin/",
  server: {
    port: 5174,
    // Dev only: the built app is served same-origin behind Caddy.
    proxy: { "/api": process.env.ROCHADE_API_URL ?? "http://localhost:8000" },
  },
});
