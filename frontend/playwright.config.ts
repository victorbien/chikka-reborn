import { defineConfig, devices } from "@playwright/test";
import path from "node:path";
import { JWT_SECRET, MOCK_WEBHOOK_SECRET } from "./e2e/support/stack";

/**
 * Browser end-to-end suite. It starts a complete throwaway stack on 127.0.0.1/localhost:
 *   PGlite (every migration, RLS on) -> fake Supabase Auth/Storage -> uvicorn API -> Vite SPA.
 * SMS, AI and email run in simulation (mock) mode. Nothing leaves this machine, and every
 * secret below is a throwaway test value. The settings are pinned explicitly because the
 * backend reads backend/.env: a developer's real project values must never reach this stack.
 *
 * The SPA must be served from `localhost` (not 127.0.0.1): the refresh cookie is SameSite=Lax,
 * so it only travels between localhost:5173 and localhost:8010.
 */
const root = path.resolve(import.meta.dirname, "..");
const python = path.join(
  root,
  "backend",
  ".venv",
  process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
);

const DB_PORT = 54329;
const FAKE_PORT = 54400;
const API_PORT = 8010;
const WEB_PORT = 5173;
const dbUrl = `postgresql+asyncpg://postgres:postgres@127.0.0.1:${DB_PORT}/postgres`;

const backendEnv: Record<string, string> = {
  APP_ENV: "development",
  DATABASE_URL: dbUrl,
  DB_POOL_SIZE: "4",
  DB_MAX_OVERFLOW: "0",
  SUPABASE_URL: `http://127.0.0.1:${FAKE_PORT}`,
  SUPABASE_JWT_SECRET: JWT_SECRET,
  SUPABASE_JWKS_URL: "",
  SUPABASE_ANON_KEY: "e2e-anon-key",
  SUPABASE_SERVICE_ROLE_KEY: "e2e-service-role-key",
  APP_SECRET_KEY: "e2e-only-app-secret-key-0123456789",
  CORS_ORIGINS: `http://localhost:${WEB_PORT}`,
  FRONTEND_BASE_URL: `http://localhost:${WEB_PORT}`,
  COOKIE_SECURE: "false",
  SMS_PROVIDER_MODE: "mock",
  SMS_LIVE_CONFIRMED: "false",
  SMS_PUBLIC_BASE_URL: "",
  SMS_MOCK_WEBHOOK_SECRET: MOCK_WEBHOOK_SECRET,
  SMS_WORKER_ENABLED: "true",
  SMS_WORKER_POLL_SECONDS: "1",
  TWILIO_ACCOUNT_SID: "",
  TWILIO_AUTH_TOKEN: "",
  EMAIL_PROVIDER_MODE: "mock",
  AI_PROVIDER_MODE: "mock",
  BEDROCK_API_KEY: "",
  NOTIFICATIONS_WORKER_ENABLED: "true",
  NOTIFICATIONS_WORKER_POLL_SECONDS: "1",
};

const inherited = Object.fromEntries(
  Object.entries(process.env).filter((entry): entry is [string, string] => entry[1] !== undefined),
);

export default defineConfig({
  testDir: "./e2e",
  testMatch: "**/*.e2e.ts",
  // One shared backend, database and IP: specs run in order so quotas and state stay predictable.
  fullyParallel: false,
  workers: 1,
  retries: 0,
  forbidOnly: !!process.env.CI,
  timeout: 90_000,
  expect: { timeout: 10_000 },
  reporter: [
    ["list"],
    ["json", { outputFile: "e2e-results/results.json" }],
    ["html", { outputFolder: "e2e-results/html", open: "never" }],
  ],
  outputDir: "e2e-results/artifacts",
  use: {
    baseURL: `http://localhost:${WEB_PORT}`,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
    actionTimeout: 10_000,
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  // Started in order; each waits for the one before it.
  webServer: [
    {
      command: "node serve-db.mjs --port=" + DB_PORT,
      cwd: path.join(root, "supabase", "tools"),
      port: DB_PORT,
      timeout: 120_000,
      reuseExistingServer: false,
    },
    {
      command: `"${python}" -m tests.support.run_fake_supabase --port ${FAKE_PORT} --database-url ${dbUrl}`,
      cwd: path.join(root, "backend"),
      env: { ...inherited, ...backendEnv },
      url: `http://127.0.0.1:${FAKE_PORT}/__outbox?to=nobody@example.com`,
      timeout: 120_000,
      reuseExistingServer: false,
    },
    {
      command: `"${python}" -m uvicorn app.main:app --port ${API_PORT}`,
      cwd: path.join(root, "backend"),
      env: { ...inherited, ...backendEnv },
      url: `http://127.0.0.1:${API_PORT}/api/v1/health`,
      timeout: 120_000,
      reuseExistingServer: false,
    },
    {
      command: `npx vite --port ${WEB_PORT} --strictPort --host localhost`,
      cwd: import.meta.dirname,
      env: { ...inherited, VITE_API_BASE_URL: `http://localhost:${API_PORT}` },
      url: `http://localhost:${WEB_PORT}`,
      timeout: 120_000,
      reuseExistingServer: false,
    },
  ],
});
