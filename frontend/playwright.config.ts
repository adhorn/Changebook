import { defineConfig, devices } from "@playwright/test";
import {
  E2E_BACKEND_PORT,
  E2E_BACKEND_URL,
  E2E_DB_URL,
  E2E_FRONTEND_PORT,
} from "./e2e/config";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false, // tests depend on shared state (created changes)
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: process.env.CI ? "github" : "html",

  use: {
    baseURL: `http://localhost:${E2E_FRONTEND_PORT}`,
    trace: "on-first-retry",
  },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],

  webServer: [
    {
      command: `cd ../backend && CHANGEBOOK_DATABASE_URL=${E2E_DB_URL} CHANGEBOOK_CORS_ORIGINS='["http://localhost:${E2E_FRONTEND_PORT}"]' uvicorn app.main:app --host 0.0.0.0 --port ${E2E_BACKEND_PORT}`,
      url: `${E2E_BACKEND_URL}/health`,
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
    },
    {
      command: `NEXT_PUBLIC_API_URL=${E2E_BACKEND_URL} npx next dev --port ${E2E_FRONTEND_PORT}`,
      url: `http://localhost:${E2E_FRONTEND_PORT}`,
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
    },
  ],
});
