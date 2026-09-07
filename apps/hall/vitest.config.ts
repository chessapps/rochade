import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// Kept apart from vite.config.ts: vitest brings its own vite, and letting the
// two type-check against each other buys nothing but version friction.
export default defineConfig({
  plugins: [react()],
  test: {
    // jsdom throughout: the queue tests never needed a DOM, and the screens do.
    environment: "jsdom",
    globals: true,
    include: ["src/**/*.test.{ts,tsx}"],
    setupFiles: ["./src/test-setup.ts"],
  },
});
