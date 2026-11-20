import { fileURLToPath } from "node:url";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { loadEnv } from "vite";
import { configDefaults, defineConfig } from "vitest/config";
import { hostedEnvProblem } from "./src/lib/env-rules";
export default defineConfig(({ command, mode }) => {
  if (command === "build") {
    // A hosted build with a missing or non-https API URL fails here, not in the browser.
    const problem = hostedEnvProblem(loadEnv(mode, process.cwd(), "VITE_"));
    if (problem) throw new Error(`Invalid frontend environment configuration: ${problem}`);
  }
  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
    },
    test: {
      globals: true,
      environment: "jsdom",
      setupFiles: ["./src/test/setup.ts"],
      css: false,
      // Playwright specs (*.e2e.ts) run in a real browser through `npm run test:e2e`.
      exclude: [...configDefaults.exclude, "e2e/**"],
      // Page-level tests drive several requests and renders each.
      testTimeout: 15_000,
      coverage: {
        provider: "v8",
        include: ["src/**/*.{ts,tsx}"],
        exclude: ["src/**/*.test.{ts,tsx}", "src/test/**", "src/main.tsx", "src/vite-env.d.ts"],
        reporter: ["text-summary", "text"],
      },
    },
  };
});
