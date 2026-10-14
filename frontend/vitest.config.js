import { mergeConfig } from "vite";
import { defineConfig } from "vitest/config";
import viteConfig from "./vite.config.js";

export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      environment: "jsdom",
      setupFiles: ["./tests/setup.js"],
      include: ["tests/**/*.{test,spec}.{js,jsx}"],
      clearMocks: true,
      mockReset: true,
      restoreMocks: true,
      coverage: {
        provider: "v8",
        all: true,
        include: ["src/**/*.{js,jsx,ts,tsx}"],
        exclude: ["src/**/*.test.*", "src/**/__tests__/**"],
        reporter: ["text", "lcov", "json", "html"],
        reportsDirectory: "./coverage",
      },
    },
  }),
);
