import { test, expect } from "@playwright/test";
import { ensureCustomer, ensureEnvironment, switchUser, pickFirstOption, USERS } from "./helpers";

/**
 * Full change lifecycle E2E test.
 *
 * Walks through: create → add checklist → fill preflight → submit for review →
 * assign reviewer → switch user & approve → start execution → complete items →
 * verify hold point → mark done.
 *
 * Uses test.describe.serial so tests run in order and share state.
 */

let changeId: string;

test.describe.serial("Change lifecycle", () => {
  test.beforeAll(async () => {
    await ensureCustomer();
    await ensureEnvironment();
  });

  test("create a new change", async ({ page }) => {
    await switchUser(page, USERS.alice);
    await page.goto("/changes/new");
    await page.waitForLoadState("networkidle");

    // Fill basic details
    await page.getByPlaceholder("e.g., Update connection pool").fill("E2E: Upgrade Redis to 7.4");
    await page.getByPlaceholder("Brief summary").fill("Rolling upgrade of Redis cluster.");

    // Select customer, service, environment from searchable dropdowns
    await pickFirstOption(page, "Customer *");
    await page.waitForTimeout(500);
    await pickFirstOption(page, "Service *");
    await pickFirstOption(page, "Environment *");

    // Submit
    await page.getByRole("button", { name: "Create Change" }).click();

    // Should redirect to the detail page
    await page.waitForURL(/\/changes\/[0-9a-f-]+/);
    changeId = page.url().split("/changes/")[1];

    await expect(page.getByText("E2E: Upgrade Redis to 7.4")).toBeVisible();
    await expect(page.getByText("Draft")).toBeVisible();
    await expect(page.getByText("by Alice Engineer")).toBeVisible();
  });

  test("add checklist items with a hold point", async ({ page }) => {
    await switchUser(page, USERS.alice);
    await page.goto(`/changes/${changeId}`);
    await page.waitForLoadState("networkidle");

    // Add pre-flight item
    const addButtons = page.getByRole("button", { name: "+ Add item" });
    await addButtons.nth(0).click();
    await page.getByPlaceholder("Description — what to do...").fill("Confirm backup completed");
    await page.getByRole("button", { name: "Add", exact: true }).click();
    await expect(page.getByText("Confirm backup completed")).toBeVisible();
    await page.getByRole("button", { name: "Done" }).click();

    // Add execution items
    await addButtons.nth(1).click();

    // First execution item
    await page.getByPlaceholder("Description — what to do...").fill("Run Redis upgrade script");
    await page.getByPlaceholder(/Command/).first().fill("redis-cli INFO server | grep redis_version");
    await page.getByRole("button", { name: "Add", exact: true }).click();
    await expect(page.getByText("Run Redis upgrade script")).toBeVisible();

    // Second execution item — hold point with a command
    // (so the verify-before UX hides the command until verification)
    await page.getByPlaceholder("Description — what to do...").fill("Verify cluster health");
    await page.getByPlaceholder(/Command/).first().fill("redis-cli CLUSTER NODES | grep -c master");
    // Check the hold point checkbox
    await page.locator('label:has-text("Hold point") input[type="checkbox"]').check();
    await page.getByRole("button", { name: "Add", exact: true }).click();
    await expect(page.getByText("Verify cluster health")).toBeVisible();
    await expect(page.getByText("Hold Point", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Done" }).click();

    // Add verification item
    await addButtons.nth(2).click();
    await page.getByPlaceholder("Description — what to do...").fill("Check client reconnection");
    await page.getByRole("button", { name: "Add", exact: true }).click();
    await expect(page.getByText("Check client reconnection")).toBeVisible();
    await page.getByRole("button", { name: "Done" }).click();
  });

  test("fill preflight answers and submit for review", async ({ page }) => {
    await switchUser(page, USERS.alice);
    await page.goto(`/changes/${changeId}`);
    await page.waitForLoadState("networkidle");

    // The Change Profile section has a clickable header to expand, and an Edit button.
    // Expand the section first.
    const profileHeader = page.locator("button", { hasText: "Change Profile" });
    await profileHeader.click();
    await page.waitForTimeout(500);

    // The preflight edit button is in <main>, distinct from the header Edit button
    await page.getByRole("main").getByRole("button", { name: "Edit", exact: true }).click();
    await page.waitForTimeout(500);

    // Fill all empty preflight textareas (the edit form renders all questions)
    const textareas = page.locator("textarea[placeholder]");
    const count = await textareas.count();
    for (let i = 0; i < count; i++) {
      const ta = textareas.nth(i);
      const currentValue = await ta.inputValue();
      if (!currentValue) {
        await ta.fill("E2E test answer for this question.");
      }
    }

    await page.getByRole("button", { name: "Save Answers" }).click();
    await page.waitForTimeout(1000);

    // Submit for review
    await page.getByRole("button", { name: "Submit for Review" }).click();
    await page.waitForTimeout(500);
    await expect(page.getByText("In Review")).toBeVisible();
  });

  test("assign reviewer and approve", async ({ page }) => {
    // Alice assigns Bob as reviewer
    await switchUser(page, USERS.alice);
    await page.goto(`/changes/${changeId}`);
    await page.waitForLoadState("networkidle");

    await page.getByRole("button", { name: "+ Assign reviewer" }).click();
    await page.locator("select").last().selectOption("Bob Reviewer");
    await page.waitForTimeout(500);
    await expect(page.getByText("Bob Reviewer")).toBeVisible();
    await expect(page.getByText("pending")).toBeVisible();

    // Switch to Bob and approve
    await switchUser(page, USERS.bob);
    await page.goto(`/changes/${changeId}`);
    await page.waitForLoadState("networkidle");

    // The "Approve" button on the review card (not the transition button)
    await page.locator("button:has-text('Approve')").first().click();
    await page.waitForTimeout(500);
    await expect(page.locator("text=approved")).toBeVisible();
  });

  test("approve transition and start execution", async ({ page }) => {
    // Alice (author) performs the status transitions
    await switchUser(page, USERS.alice);
    await page.goto(`/changes/${changeId}`);
    await page.waitForLoadState("networkidle");

    // Transition from in_review to approved — all reviews are approved,
    // so this button must be visible. Assert it, don't conditionally handle it.
    const approveBtn = page.getByRole("button", { name: "Approve" });
    await expect(approveBtn).toBeVisible();
    await approveBtn.click();
    await page.waitForTimeout(500);

    // Start execution
    await page.getByRole("button", { name: "Start Execution" }).click();
    await page.waitForTimeout(500);
    await expect(page.getByText("Executing")).toBeVisible();
    await expect(page.getByText("Execution Progress")).toBeVisible();
  });

  test("complete checklist items sequentially", async ({ page }) => {
    await switchUser(page, USERS.alice);
    await page.goto(`/changes/${changeId}`);
    await page.waitForLoadState("networkidle");

    // Helper: complete the next item with a given result
    async function completeNextItem(result: string) {
      await page.getByRole("button", { name: "Complete this item" }).click();
      // The completion form has a textarea for observed result
      const resultTextarea = page.locator("textarea").last();
      await resultTextarea.fill(result);
      await page.getByRole("button", { name: "Record" }).click();
      await page.waitForTimeout(1000);
    }

    // Complete pre-flight item
    await completeNextItem("Backup verified at 14:00 UTC");

    // Complete first execution item
    await completeNextItem("redis_version:7.4.0");

    // The next item is a hold point — it should be blocked from completion
    // and show the verify-before message. The command must be hidden.
    await expect(page.getByText("A second person must verify")).toBeVisible();
    await expect(page.getByText("Command hidden — hold point.")).toBeVisible();
    // No "Complete this item" button should be present yet
    await expect(page.getByRole("button", { name: "Complete this item" })).not.toBeVisible();
  });

  test("verify hold point with two-person rule", async ({ page }) => {
    await switchUser(page, USERS.alice);
    await page.goto(`/changes/${changeId}`);
    await page.waitForLoadState("networkidle");

    // Click "Verify Hold Point" — verification happens BEFORE completion
    await page.getByRole("button", { name: "Verify Hold Point" }).click();

    // Try same person (the operator) — should show client-side error
    await page.getByPlaceholder("Name of the person who checked this").fill("Alice Engineer");
    await page.getByRole("button", { name: "Confirm" }).click();
    await expect(page.getByText("Must be a different person")).toBeVisible();

    // Use a different person
    await page.getByPlaceholder("Name of the person who checked this").clear();
    await page.getByPlaceholder("Name of the person who checked this").fill("Bob Reviewer");
    await page.getByRole("button", { name: "Confirm" }).click();
    await page.waitForTimeout(1000);

    // Command is now revealed and the hold-point item can be completed
    await expect(page.getByText("Command hidden — hold point.")).not.toBeVisible();
    await expect(page.getByRole("button", { name: "Complete this item" })).toBeVisible();
  });

  test("complete remaining items and mark done", async ({ page }) => {
    await switchUser(page, USERS.alice);
    await page.goto(`/changes/${changeId}`);
    await page.waitForLoadState("networkidle");

    // Complete the verified hold-point item
    await page.getByRole("button", { name: "Complete this item" }).click();
    await page.locator("textarea").last().fill("Cluster nodes all healthy, 0 failed");
    await page.getByRole("button", { name: "Record" }).click();
    await page.waitForTimeout(1000);

    // Confirm the verified-by line is shown on the completed item
    await expect(page.getByText("Hold point verified by Bob Reviewer")).toBeVisible();

    // Complete the verification phase item
    await page.getByRole("button", { name: "Complete this item" }).click();
    await page.locator("textarea").last().fill("All clients reconnected within 30s");
    await page.getByRole("button", { name: "Record" }).click();
    await page.waitForTimeout(1000);

    // Mark done
    await page.getByRole("button", { name: "Mark Done" }).click();
    await page.waitForTimeout(500);
    await expect(page.getByText("Done")).toBeVisible();
  });

  test("done change appears in the list", async ({ page }) => {
    await switchUser(page, USERS.alice);
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Filter by done status to find our specific change
    await page.locator("select").selectOption("done");
    await page.waitForTimeout(500);

    // Should have at least one row with our change title and Done status
    const row = page.getByRole("row", { name: /E2E: Upgrade Redis to 7.4.*Done/ });
    await expect(row.first()).toBeVisible();
  });
});
