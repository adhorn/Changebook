/**
 * E2E test configuration — single source of truth.
 *
 * E2E tests run outside Docker on separate ports against the test database,
 * so they never conflict with the dev server running via docker-compose
 * on 8000/3000.
 *
 * Consumed by: playwright.config.ts, helpers.ts
 */

export const E2E_BACKEND_PORT = 8001;
export const E2E_FRONTEND_PORT = 3001;
export const E2E_BACKEND_URL = `http://localhost:${E2E_BACKEND_PORT}`;
export const E2E_API_URL = `${E2E_BACKEND_URL}/api/v1`;
export const E2E_DB_URL =
  "postgresql://changebook:changebook@localhost:5432/changebook_test";
