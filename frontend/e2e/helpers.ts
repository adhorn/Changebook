import { Page } from "@playwright/test";
import { E2E_API_URL } from "./config";

const API = E2E_API_URL;

const ALICE = { email: "alice@changebook.dev", name: "Alice Engineer" };

function headersFor(user: { email: string; name: string }): Record<string, string> {
  return {
    "X-User-Email": user.email,
    "X-User-Name": user.name,
    "Content-Type": "application/json",
  };
}

/** API fetch as a specific user. Throws on non-2xx responses. */
export async function apiFetchAs(
  user: { email: string; name: string },
  path: string,
  options?: RequestInit,
): Promise<Response> {
  const res = await fetch(`${API}${path}`, {
    headers: headersFor(user),
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${options?.method || "GET"} ${path} returned ${res.status}: ${text}`);
  }
  return res;
}

/** API fetch as Alice (default user). Throws on non-2xx responses. */
export async function apiFetch(path: string, options?: RequestInit): Promise<Response> {
  return apiFetchAs(ALICE, path, options);
}

/** Create a customer with a service via API, return their IDs. Idempotent. */
export async function ensureCustomer(): Promise<{ customerId: string; serviceId: string }> {
  const res = await apiFetch("/customers");
  const customers = await res.json();
  if (customers.length > 0 && customers[0].services.length > 0) {
    return { customerId: customers[0].id, serviceId: customers[0].services[0].id };
  }
  const createRes = await apiFetch("/customers", {
    method: "POST",
    body: JSON.stringify({ name: "Acme Corp", services: [{ name: "Platform" }] }),
  });
  const cust = await createRes.json();
  return { customerId: cust.id, serviceId: cust.services[0].id };
}

/** Create an environment via API, return its ID. Idempotent. */
export async function ensureEnvironment(): Promise<string> {
  const res = await apiFetch("/environments");
  const envs = await res.json();
  if (envs.length > 0) return envs[0].id;
  const createRes = await apiFetch("/environments", {
    method: "POST",
    body: JSON.stringify({ name: "PROD-EU", platform: "AWS" }),
  });
  const env = await createRes.json();
  return env.id;
}

/**
 * Switch the active mock user by setting localStorage directly.
 * Navigates to the base URL first if needed (localStorage requires same-origin).
 */
export async function switchUser(page: Page, user: { email: string; name: string; role: string }) {
  if (page.url() === "about:blank") {
    await page.goto("/");
    await page.waitForLoadState("networkidle");
  }
  await page.evaluate((u) => {
    localStorage.setItem("changebook_current_user", JSON.stringify(u));
  }, user);
}

/** Pick the first option from a SearchableSelect combobox by its label text. */
export async function pickFirstOption(page: Page, labelText: string) {
  // Find the label, then its parent container, then the trigger button
  const label = page.locator(`label`, { hasText: labelText }).first();
  const container = label.locator("..");
  // Click the trigger button to open the dropdown
  await container.locator("button").first().click();
  // Click the first option in the dropdown list
  await container.locator("[class*='absolute'] [class*='overflow-y'] button").first().click();
}

/** Create a template via API, return its ID. */
export async function createTemplate(data: {
  title: string;
  description?: string;
  items?: { phase: string; description: string; command?: string; expected_outcome?: string; is_hold_point?: boolean }[];
}): Promise<string> {
  const res = await apiFetch("/templates", {
    method: "POST",
    body: JSON.stringify(data),
  });
  const template = await res.json();
  return template.id;
}

/** Create a change via API through to a target status, return its ID. */
export async function createChangeViaAPI(opts?: {
  title?: string;
  checklist?: boolean;
  preflight?: boolean;
}): Promise<string> {
  const { customerId, serviceId } = await ensureCustomer();
  const envId = await ensureEnvironment();

  const res = await apiFetch("/changes", {
    method: "POST",
    body: JSON.stringify({
      title: opts?.title || "E2E API-created change",
      customer_id: customerId,
      service_id: serviceId,
      environment_id: envId,
    }),
  });
  const change = await res.json();
  const changeId = change.id;

  if (opts?.checklist) {
    // Add one item per phase
    for (const phase of ["pre_flight", "execution", "verification"]) {
      await apiFetch(`/changes/${changeId}/checklist`, {
        method: "POST",
        body: JSON.stringify({ phase, description: `${phase} step` }),
      });
    }
  }

  if (opts?.preflight) {
    // Minimal preflight answers for the required keys
    const schemaRes = await apiFetch("/preflight-questions");
    const schema = await schemaRes.json();
    const answers: Record<string, string> = {};
    for (const section of schema.sections) {
      for (const q of section.questions) {
        if (q.required) answers[q.key] = "E2E test answer.";
      }
    }
    await apiFetch(`/changes/${changeId}`, {
      method: "PATCH",
      body: JSON.stringify({ preflight_answers: answers }),
    });
  }

  return changeId;
}

/** Drive a change through the lifecycle to a target status via API.
 *  Handles all intermediate transitions (reviewer assignment, approval, etc.). */
export async function driveChangeToStatus(
  changeId: string,
  targetStatus: "in_review" | "approved" | "executing" | "done" | "aborted",
): Promise<void> {
  const bob = { email: "bob@changebook.dev", name: "Bob Reviewer" };

  if (targetStatus === "aborted") {
    await apiFetch(
      `/changes/${changeId}/transition?target_status=aborted&reason=E2E+test`,
      { method: "POST" },
    );
    return;
  }

  // draft → in_review
  await apiFetch(`/changes/${changeId}/transition?target_status=in_review`, {
    method: "POST",
  });
  if (targetStatus === "in_review") return;

  // Assign Bob as reviewer and have him approve
  await apiFetch(`/changes/${changeId}/reviewers`, {
    method: "POST",
    body: JSON.stringify({ reviewer_name: "Bob Reviewer" }),
  });
  const reviewsRes = await apiFetchAs(bob, `/changes/${changeId}/reviewers`);
  const reviews = await reviewsRes.json();
  await apiFetchAs(
    bob,
    `/changes/${changeId}/reviewers/${reviews[0].id}/decision`,
    { method: "POST", body: JSON.stringify({ decision: "approved" }) },
  );

  // in_review → approved
  await apiFetch(`/changes/${changeId}/transition?target_status=approved`, {
    method: "POST",
  });
  if (targetStatus === "approved") return;

  // approved → executing
  await apiFetch(`/changes/${changeId}/transition?target_status=executing`, {
    method: "POST",
  });
  if (targetStatus === "executing") return;

  // executing → done: complete all checklist items first
  const itemsRes = await apiFetch(`/changes/${changeId}/checklist`);
  const items = await itemsRes.json();
  for (const item of items) {
    await apiFetch(`/changes/${changeId}/checklist/${item.id}/complete`, {
      method: "POST",
      body: JSON.stringify({ observed_result: "OK", status: "completed" }),
    });
  }
  await apiFetch(`/changes/${changeId}/transition?target_status=done`, {
    method: "POST",
  });
}

export const USERS = {
  alice: { email: "alice@changebook.dev", name: "Alice Engineer", role: "Author" },
  bob: { email: "bob@changebook.dev", name: "Bob Reviewer", role: "Reviewer" },
  carol: { email: "carol@changebook.dev", name: "Carol Operator", role: "Operator" },
};
