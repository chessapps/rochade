import { defineConfig } from "vitest/config";

// Kept apart from vite.config.ts: vitest brings its own vite, and letting the
// two type-check against each other buys nothing but version friction.
export default defineConfig({
  test: {
    environment: "node",
    globals: true,
    include: ["src/**/*.test.ts"],
  },
});
