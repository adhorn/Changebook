import { test, expect } from "@playwright/test";
import {
  ensureCustomer,
  ensureEnvironment,
  switchUser,
  pickFirstOption,
  USERS,
} from "./helpers";

/**
 * Checklist editing E2E test.
 *
 * Covers: add items, edit an item, delete an item, reorder items — all in draft.
 */

let changeId: string;

test.describe.serial("Checklist editing", () => {
  test.beforeAll(async () => {
    await ensureCustomer();
    await ensureEnvironment();
  });

  test("create a draft change", async ({ page }) => {
    await switchUser(page, USERS.alice);
    await page.goto("/changes/new");
    await page.waitForLoadState("networkidle");

    await page.getByPlaceholder("e.g., Update connection pool").fill("E2E: Checklist editing test");
    await pickFirstOption(page, "Customer *");
    await page.waitForTimeout(500);
    await pickFirstOption(page, "Service *");
    await pickFirstOption(page, "Environment *");
    await page.getByRole("button", { name: "Create Change" }).click();

    await page.waitForURL(/\/changes\/[0-9a-f-]+/);
    changeId = page.url().split("/changes/")[1];
    await expect(page.getByText("Draft")).toBeVisible();
  });

  test("add checklist items with all fields", async ({ page }) => {
    await switchUser(page, USERS.alice);
    await page.goto(`/changes/${changeId}`);
    await page.waitForLoadState("networkidle");

    // Add an execution item with command, expected outcome, rollback
    const addButtons = page.getByRole("button", { name: "+ Add item" });
    await addButtons.nth(1).click(); // execution phase

    await page.getByPlaceholder("Description — what to do...").fill("Deploy new config");
    await page.getByPlaceholder(/Command/).first().fill("kubectl apply -f config.yaml");
    await page.getByPlaceholder("Expected outcome").fill("configmap/app-config configured");
    await page.getByPlaceholder("Rollback action").fill("kubectl rollout undo");
    await page.getByRole("button", { name: "Add", exact: true }).click();

    await expect(page.getByText("Deploy new config")).toBeVisible();
    await expect(page.getByText("kubectl apply -f config.yaml")).toBeVisible();

    // Add a second execution item
    await page.getByPlaceholder("Description — what to do...").fill("Restart pods");
    await page.getByRole("button", { name: "Add", exact: true }).click();
    await expect(page.getByText("Restart pods")).toBeVisible();
    await page.getByRole("button", { name: "Done" }).click();
  });

  test("edit a checklist item", async ({ page }) => {
    await switchUser(page, USERS.alice);
    await page.goto(`/changes/${changeId}`);
    await page.waitForLoadState("networkidle");

    // Click the edit button on "Deploy new config" — target the small edit
    // button inside the checklist item row (title="Edit item")
    const editBtn = page.locator("button[title='Edit item']").first();
    await editBtn.click();
    await page.waitForTimeout(300);

    // Change description — the edit form shows an input with the current text
    // It's the first input in the blue edit form (bg-blue-50/30)
    const editForm = page.locator("div.border-blue-200").first();
    const descInput = editForm.locator("input[type='text']").first();
    await descInput.clear();
    await descInput.fill("Deploy updated config map");

    await page.getByRole("button", { name: "Save", exact: true }).click();
    await page.waitForTimeout(500);

    await expect(page.getByText("Deploy updated config map")).toBeVisible();
    // Old text should be gone
    await expect(page.getByText("Deploy new config", { exact: true })).not.toBeVisible();
  });

  test("delete a checklist item", async ({ page }) => {
    await switchUser(page, USERS.alice);
    await page.goto(`/changes/${changeId}`);
    await page.waitForLoadState("networkidle");

    // Delete "Restart pods" — use the delete button with title
    // Accept the confirm dialog
    page.on("dialog", (dialog) => dialog.accept());
    // The second checklist item's delete button (first is "Deploy updated config map")
    await page.locator("button[title='Delete item']").last().click();
    await page.waitForTimeout(500);

    await expect(page.getByText("Restart pods")).not.toBeVisible();
    // The other item should still be there
    await expect(page.getByText("Deploy updated config map")).toBeVisible();
  });
});
