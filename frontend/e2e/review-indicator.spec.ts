import { test, expect } from "@playwright/test";
import { ensureCustomer, ensureEnvironment, switchUser, USERS } from "./helpers";

/**
 * Review indicator E2E test.
 *
 * Verifies: "Needs your review" badge shows for the assigned reviewer,
 * and the "Needs my review" filter works on the change list.
 */

let changeId: string;

test.describe.serial("Review indicator", () => {
  test.beforeAll(async () => {
    await ensureCustomer();
    await ensureEnvironment();
  });

  test("setup: create a change and submit for review", async ({ page }) => {
    await switchUser(page, USERS.alice);
    await page.goto("/changes/new");
    await page.waitForLoadState("networkidle");

    await page.getByPlaceholder("e.g., Update connection pool").fill("E2E: Review indicator test");
    await page.locator("select").nth(0).selectOption({ index: 1 });
    await page.waitForTimeout(500);
    await page.locator("select").nth(1).selectOption({ index: 1 });
    await page.locator("select").nth(2).selectOption({ index: 1 });
    await page.getByRole("button", { name: "Create Change" }).click();
    await page.waitForURL(/\/changes\/[0-9a-f-]+/);
    changeId = page.url().split("/changes/")[1];

    // Add minimal checklist (one item per phase)
    const addButtons = page.getByRole("button", { name: "+ Add item" });
    for (let i = 0; i < 3; i++) {
      await addButtons.nth(i).click();
      const phases = ["PRE-FLIGHT", "EXECUTION", "VERIFICATION"];
      await page.getByPlaceholder("Description — what to do...").fill(`${phases[i]} step`);
      await page.getByRole("button", { name: "Add", exact: true }).click();
      await page.getByRole("button", { name: "Done" }).click();
    }

    // Fill preflight
    await page.locator("button", { hasText: "Change Profile" }).click();
    await page.waitForTimeout(300);
    await page.getByRole("main").getByRole("button", { name: "Edit", exact: true }).click();
    await page.waitForTimeout(300);

    const textareas = page.locator("textarea[placeholder]");
    const count = await textareas.count();
    for (let i = 0; i < count; i++) {
      const ta = textareas.nth(i);
      if (!(await ta.inputValue())) {
        await ta.fill("E2E test answer.");
      }
    }
    await page.getByRole("button", { name: "Save Answers" }).click();
    await page.waitForTimeout(1000);

    // Submit for review
    await page.getByRole("button", { name: "Submit for Review" }).click();
    await page.waitForTimeout(500);
    await expect(page.getByText("In Review")).toBeVisible();

    // Assign Bob as reviewer
    await page.getByRole("button", { name: "+ Assign reviewer" }).click();
    await page.getByPlaceholder("Reviewer name...").fill("Bob Reviewer");
    await page.getByRole("button", { name: "Assign" }).click();
    await page.waitForTimeout(500);
    await expect(page.getByText("pending")).toBeVisible();
  });

  test("Bob sees 'Needs your review' badge on the change list", async ({ page }) => {
    await switchUser(page, USERS.bob);
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    const row = page.getByRole("row", { name: /E2E: Review indicator test/ });
    await expect(row.first().getByText("Needs your review")).toBeVisible();
  });

  test("'Needs my review' filter works for Bob", async ({ page }) => {
    await switchUser(page, USERS.bob);
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    await page.getByRole("button", { name: "Needs my review" }).click();
    await page.waitForTimeout(500);

    await expect(page.getByText("E2E: Review indicator test").first()).toBeVisible();
  });

  test("Carol does NOT see 'Needs your review'", async ({ page }) => {
    await switchUser(page, USERS.carol);
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Filter to in_review to find our change
    await page.locator("select").selectOption("in_review");
    await page.waitForTimeout(500);

    const row = page.getByRole("row", { name: /E2E: Review indicator test/ });
    if (await row.first().isVisible()) {
      await expect(row.first().getByText("Needs your review")).not.toBeVisible();
    }
  });

  test("after Bob approves, badge disappears", async ({ page }) => {
    await switchUser(page, USERS.bob);
    await page.goto(`/changes/${changeId}`);
    await page.waitForLoadState("networkidle");

    await page.locator("button:has-text('Approve')").first().click();
    await page.waitForTimeout(500);

    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Filter to in_review
    await page.locator("select").selectOption("in_review");
    await page.waitForTimeout(500);

    const row = page.getByRole("row", { name: /E2E: Review indicator test/ });
    if (await row.first().isVisible()) {
      await expect(row.first().getByText("Needs your review")).not.toBeVisible();
    }
  });
});
