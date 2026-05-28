import { defineConfig, devices } from "@playwright/test";

// E2E tests run outside Docker on separate ports (8001, 3001) against
// the test database, so they never conflict with the dev server running
// via docker-compose on 8000/3000.
const E2E_BACKEND_PORT = 8001;
const E2E_FRONTEND_PORT = 3001;
const E2E_BACKEND_URL = `http://localhost:${E2E_BACKEND_PORT}`;
const E2E_DB_URL =
  "postgresql://changebook:changebook@localhost:5432/changebook_test";

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
