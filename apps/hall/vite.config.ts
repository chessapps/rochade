import tailwind from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwind()],
  server: {
    port: 5173,
    // Dev only: the built app is served same-origin behind Caddy.
    proxy: { "/api": process.env.SEEBACH_API_URL ?? "http://localhost:8000" },
  },
});
