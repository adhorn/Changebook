import { test, expect } from "@playwright/test";
import {
  ensureCustomer,
  ensureEnvironment,
  switchUser,
  pickFirstOption,
  USERS,
} from "./helpers";

/**
 * Preflight edit after review E2E test.
 *
 * Verifies: when preflight answers are edited after a review,
 * all reviews reset to pending — the integrity guarantee.
 *
 * Flow: create → add checklist → fill preflight → submit for review →
 * assign reviewer → reviewer approves → send back to draft →
 * edit preflight answers → submit for review → verify reviews are pending.
 */

let changeId: string;

test.describe.serial("Preflight edit resets reviews", () => {
  test.beforeAll(async () => {
    await ensureCustomer();
    await ensureEnvironment();
  });

  test("create change with checklist and preflight", async ({ page }) => {
    await switchUser(page, USERS.alice);
    await page.goto("/changes/new");
    await page.waitForLoadState("networkidle");

    await page.getByPlaceholder("e.g., Update connection pool").fill("E2E: Preflight edit test");
    await pickFirstOption(page, "Customer *");
    await page.waitForTimeout(500);
    await pickFirstOption(page, "Service *");
    await pickFirstOption(page, "Environment *");
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
        await ta.fill("Original preflight answer.");
      }
    }
    await page.getByRole("button", { name: "Save Answers" }).click();
    await page.waitForTimeout(1000);
  });

  test("submit for review and get approved", async ({ page }) => {
    await switchUser(page, USERS.alice);
    await page.goto(`/changes/${changeId}`);
    await page.waitForLoadState("networkidle");

    // Submit for review
    await page.getByRole("button", { name: "Submit for Review" }).click();
    await page.waitForTimeout(500);
    await expect(page.getByText("In Review")).toBeVisible();

    // Assign Bob as reviewer
    await page.getByRole("button", { name: "+ Assign reviewer" }).click();
    await page.locator("select").last().selectOption("Bob Reviewer");
    await page.waitForTimeout(500);

    // Switch to Bob and approve
    await switchUser(page, USERS.bob);
    await page.goto(`/changes/${changeId}`);
    await page.waitForLoadState("networkidle");

    await page.locator("button:has-text('Approve')").first().click();
    await page.waitForTimeout(500);
    await expect(page.locator("text=approved")).toBeVisible();
  });

  test("send back to draft and edit preflight", async ({ page }) => {
    // Alice sends the in_review change back to draft
    await switchUser(page, USERS.alice);
    await page.goto(`/changes/${changeId}`);
    await page.waitForLoadState("networkidle");

    // Transition in_review → draft (the "Back to Draft" button)
    await page.getByRole("button", { name: "Back to Draft" }).click();
    await page.waitForTimeout(500);
    await expect(page.getByText("Draft")).toBeVisible();

    // Edit preflight answers
    await page.locator("button", { hasText: "Change Profile" }).click();
    await page.waitForTimeout(300);
    await page.getByRole("main").getByRole("button", { name: "Edit", exact: true }).click();
    await page.waitForTimeout(300);

    // Change the first answer
    const firstTextarea = page.locator("textarea[placeholder]").first();
    await firstTextarea.clear();
    await firstTextarea.fill("Updated preflight answer after review.");
    await page.getByRole("button", { name: "Save Answers" }).click();
    await page.waitForTimeout(1000);
  });

  test("reviews are reset to pending after edit", async ({ page }) => {
    await switchUser(page, USERS.alice);
    await page.goto(`/changes/${changeId}`);
    await page.waitForLoadState("networkidle");

    // Submit for review again
    await page.getByRole("button", { name: "Submit for Review" }).click();
    await page.waitForTimeout(500);
    await expect(page.getByText("In Review")).toBeVisible();

    // Bob's review should now show as pending (not approved)
    await expect(page.getByText("pending")).toBeVisible();
    // "approved" text from Bob's previous decision should not be present
    // (the review card should show pending, not approved)
    const bobReview = page.locator("div", { hasText: "Bob Reviewer" });
    await expect(bobReview.getByText("pending").first()).toBeVisible();
  });
});
