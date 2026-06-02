import { test, expect } from "@playwright/test";
import {
  apiFetch,
  apiFetchAs,
  createChangeViaAPI,
  driveChangeToStatus,
  ensureCustomer,
  ensureEnvironment,
  switchUser,
  USERS,
} from "./helpers";

/**
 * Safety gate E2E tests.
 *
 * These test that the system STOPS you when something is wrong.
 * Each test exercises a gate — a rule that blocks an unsafe action.
 *
 * The happy path is tested elsewhere (change-lifecycle.spec.ts).
 * These tests prove the gates actually fire.
 */

test.describe.serial("Safety gates", () => {
  test.beforeAll(async () => {
    await ensureCustomer();
    await ensureEnvironment();
  });

  test("cannot submit for review without checklist items", async ({ page }) => {
    const changeId = await createChangeViaAPI({
      title: "E2E: Gate — empty checklist",
      preflight: true,
    });

    await switchUser(page, USERS.alice);
    await page.goto(`/changes/${changeId}`);
    await page.waitForLoadState("networkidle");

    await page.getByRole("button", { name: "Submit for Review" }).click();
    await page.waitForTimeout(500);

    await expect(page.getByText("Cannot submit for review")).toBeVisible();
    await expect(page.getByText("Draft")).toBeVisible();
  });

  test("cannot submit for review with only one phase", async ({ page }) => {
    const changeId = await createChangeViaAPI({
      title: "E2E: Gate — missing phases",
      preflight: true,
    });

    // Add only an execution item — missing pre_flight and verification
    await apiFetch(`/changes/${changeId}/checklist`, {
      method: "POST",
      body: JSON.stringify({ phase: "execution", description: "Only execution step" }),
    });

    await switchUser(page, USERS.alice);
    await page.goto(`/changes/${changeId}`);
    await page.waitForLoadState("networkidle");

    await page.getByRole("button", { name: "Submit for Review" }).click();
    await page.waitForTimeout(500);

    await expect(page.getByText("Cannot submit for review")).toBeVisible();
    await expect(page.getByText("Draft")).toBeVisible();
  });

  test("cannot submit for review without preflight answers", async ({ page }) => {
    const changeId = await createChangeViaAPI({
      title: "E2E: Gate — no preflight",
      checklist: true,
      // no preflight: true
    });

    await switchUser(page, USERS.alice);
    await page.goto(`/changes/${changeId}`);
    await page.waitForLoadState("networkidle");

    await page.getByRole("button", { name: "Submit for Review" }).click();
    await page.waitForTimeout(500);

    await expect(page.getByText(/Cannot submit for review|incomplete/i)).toBeVisible();
    await expect(page.getByText("Draft")).toBeVisible();
  });

  test("cannot mark done with incomplete checklist items", async ({ page }) => {
    const changeId = await createChangeViaAPI({
      title: "E2E: Gate — incomplete execution",
      checklist: true,
      preflight: true,
    });

    await driveChangeToStatus(changeId, "executing");

    await switchUser(page, USERS.alice);
    await page.goto(`/changes/${changeId}`);
    await page.waitForLoadState("networkidle");

    await expect(page.getByText("Executing")).toBeVisible();

    // The button should exist but be disabled — frontend gate prevents the click
    const markDoneBtn = page.getByRole("button", { name: "Mark Done" });
    await expect(markDoneBtn).toBeVisible();
    await expect(markDoneBtn).toBeDisabled();
  });

  test("Bob cannot edit Alice's change", async ({ page }) => {
    const changeId = await createChangeViaAPI({
      title: "E2E: Gate — author enforcement",
    });

    await switchUser(page, USERS.bob);
    await page.goto(`/changes/${changeId}`);
    await page.waitForLoadState("networkidle");

    await expect(page.getByText("E2E: Gate — author enforcement")).toBeVisible();
    await expect(page.getByRole("button", { name: "Edit Change Details" })).not.toBeVisible();
    await expect(page.getByRole("button", { name: "+ Add item" })).not.toBeVisible();
    await expect(page.getByRole("button", { name: "Submit for Review" })).not.toBeVisible();
  });

  test("Bob cannot complete or insert steps on Alice's executing change", async () => {
    // Author is Alice (the default for createChangeViaAPI). Drive the change
    // all the way to executing.
    const changeId = await createChangeViaAPI({
      title: "E2E: Gate — execution author enforcement",
      checklist: true,
      preflight: true,
    });
    await driveChangeToStatus(changeId, "executing");

    // Find the next item Bob would try to complete.
    const itemsRes = await apiFetch(`/changes/${changeId}/checklist`);
    const items = await itemsRes.json();
    const firstItemId = items[0].id;

    // Bob attempts to complete the item as himself — expect 403.
    let rejected = false;
    try {
      await apiFetchAs(USERS.bob, `/changes/${changeId}/checklist/${firstItemId}/complete`, {
        method: "POST",
        body: JSON.stringify({ observed_result: "Bob did this", status: "completed" }),
      });
    } catch (err) {
      rejected = err instanceof Error && err.message.includes("403");
    }
    expect(rejected, "Bob should get 403 when completing an item on Alice's change").toBe(true);

    // Bob attempts to insert an execution step — expect 403.
    rejected = false;
    try {
      await apiFetchAs(USERS.bob, `/changes/${changeId}/checklist/execution-step`, {
        method: "POST",
        body: JSON.stringify({
          insert_after_item_id: firstItemId,
          description: "Bob's inserted step",
        }),
      });
    } catch (err) {
      rejected = err instanceof Error && err.message.includes("403");
    }
    expect(rejected, "Bob should get 403 when adding an execution step on Alice's change").toBe(
      true,
    );
  });

  test("done changes have no transition buttons", async ({ page }) => {
    const changeId = await createChangeViaAPI({
      title: "E2E: Gate — terminal done",
      checklist: true,
      preflight: true,
    });

    await driveChangeToStatus(changeId, "done");

    await switchUser(page, USERS.alice);
    await page.goto(`/changes/${changeId}`);
    await page.waitForLoadState("networkidle");

    await expect(page.getByText("Done", { exact: true })).toBeVisible();

    await expect(page.getByRole("button", { name: "Submit for Review" })).not.toBeVisible();
    await expect(page.getByRole("button", { name: "Start Execution" })).not.toBeVisible();
    await expect(page.getByRole("button", { name: "Mark Done" })).not.toBeVisible();
    await expect(page.getByRole("button", { name: "Back to Draft" })).not.toBeVisible();
  });

  test("aborted changes have no transition buttons", async ({ page }) => {
    const changeId = await createChangeViaAPI({
      title: "E2E: Gate — terminal aborted",
    });

    await driveChangeToStatus(changeId, "aborted");

    await switchUser(page, USERS.alice);
    await page.goto(`/changes/${changeId}`);
    await page.waitForLoadState("networkidle");

    await expect(page.getByText("Aborted", { exact: true })).toBeVisible();

    await expect(page.getByRole("button", { name: "Submit for Review" })).not.toBeVisible();
    await expect(page.getByRole("button", { name: "Start Execution" })).not.toBeVisible();
    await expect(page.getByRole("button", { name: "Back to Draft" })).not.toBeVisible();
  });
});
