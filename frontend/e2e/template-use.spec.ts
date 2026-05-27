import { test, expect } from "@playwright/test";
import {
  ensureCustomer,
  ensureEnvironment,
  switchUser,
  pickFirstOption,
  createTemplate,
  USERS,
} from "./helpers";

/**
 * Template use E2E test.
 *
 * Creates a template with checklist items via API, then uses it from the UI
 * to create a new change. Verifies checklist items are populated.
 */

let templateId: string;

test.describe.serial("Template use", () => {
  test.beforeAll(async () => {
    await ensureCustomer();
    await ensureEnvironment();

    // Create a template with items across all phases
    templateId = await createTemplate({
      title: "E2E: Redis upgrade procedure",
      description: "Standard Redis rolling upgrade",
      items: [
        { phase: "pre_flight", description: "Verify backup exists" },
        { phase: "execution", description: "Stop replica node", command: "redis-cli -p 6380 SHUTDOWN" },
        { phase: "execution", description: "Upgrade Redis binary", is_hold_point: true },
        { phase: "verification", description: "Check cluster health", command: "redis-cli CLUSTER INFO" },
      ],
    });
  });

  test("template appears in the library", async ({ page }) => {
    await switchUser(page, USERS.alice);
    await page.goto("/templates");
    await page.waitForLoadState("networkidle");

    await expect(page.getByText("E2E: Redis upgrade procedure").first()).toBeVisible();
    await expect(page.getByText("4 checklist items").first()).toBeVisible();
  });

  test("create a change from the template", async ({ page }) => {
    await switchUser(page, USERS.alice);
    await page.goto(`/templates/${templateId}`);
    await page.waitForLoadState("networkidle");

    // Verify template detail shows the items
    await expect(page.getByText("Verify backup exists")).toBeVisible();
    await expect(page.getByText("Stop replica node")).toBeVisible();
    await expect(page.getByText("Upgrade Redis binary")).toBeVisible();
    await expect(page.getByText("Check cluster health")).toBeVisible();

    // Click "Use this template"
    await page.getByRole("button", { name: "Use this template" }).click();
    await page.waitForTimeout(500);

    // Fill in the use-template form
    await page.getByPlaceholder("e.g., Resize connection pool").fill("E2E: Redis 7.4 upgrade PROD");
    await pickFirstOption(page, "Customer");
    await page.waitForTimeout(500);
    await pickFirstOption(page, "Service");
    await pickFirstOption(page, "Environment");

    // Submit
    await page.getByRole("button", { name: "Create Change" }).click();

    // Should redirect to the new change
    await page.waitForURL(/\/changes\/[0-9a-f-]+/);
    await expect(page.getByText("E2E: Redis 7.4 upgrade PROD")).toBeVisible();
    await expect(page.getByText("Draft")).toBeVisible();
  });

  test("new change has all checklist items from the template", async ({ page }) => {
    await switchUser(page, USERS.alice);
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Find the change we just created
    await page.getByText("E2E: Redis 7.4 upgrade PROD").first().click();
    await page.waitForLoadState("networkidle");

    // All template items should be present
    await expect(page.getByText("Verify backup exists")).toBeVisible();
    await expect(page.getByText("Stop replica node")).toBeVisible();
    await expect(page.getByText("Upgrade Redis binary")).toBeVisible();
    await expect(page.getByText("Check cluster health")).toBeVisible();

    // Hold point should carry over
    await expect(page.getByText("Hold Point", { exact: true })).toBeVisible();

    // Command should carry over
    await expect(page.getByText("redis-cli -p 6380 SHUTDOWN")).toBeVisible();
  });
});
