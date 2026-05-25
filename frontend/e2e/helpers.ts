import { Page } from "@playwright/test";

const API = "http://localhost:8000/api/v1";

const ALICE_HEADERS = { "X-User-Email": "alice@changebook.dev", "X-User-Name": "Alice Engineer" };

/** Create a customer with a service via API, return their IDs. Idempotent. */
export async function ensureCustomer(): Promise<{ customerId: string; serviceId: string }> {
  const res = await fetch(`${API}/customers`, {
    headers: { ...ALICE_HEADERS, "Content-Type": "application/json" },
  });
  const customers = await res.json();
  if (customers.length > 0 && customers[0].services.length > 0) {
    return { customerId: customers[0].id, serviceId: customers[0].services[0].id };
  }
  const createRes = await fetch(`${API}/customers`, {
    method: "POST",
    headers: { ...ALICE_HEADERS, "Content-Type": "application/json" },
    body: JSON.stringify({ name: "Acme Corp", services: [{ name: "Platform" }] }),
  });
  const cust = await createRes.json();
  return { customerId: cust.id, serviceId: cust.services[0].id };
}

/** Create an environment via API, return its ID. Idempotent. */
export async function ensureEnvironment(): Promise<string> {
  const res = await fetch(`${API}/environments`, {
    headers: { ...ALICE_HEADERS, "Content-Type": "application/json" },
  });
  const envs = await res.json();
  if (envs.length > 0) return envs[0].id;
  const createRes = await fetch(`${API}/environments`, {
    method: "POST",
    headers: { ...ALICE_HEADERS, "Content-Type": "application/json" },
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
  // Ensure we're on the app origin so localStorage is accessible
  if (page.url() === "about:blank") {
    await page.goto("/");
    await page.waitForLoadState("networkidle");
  }
  await page.evaluate((u) => {
    localStorage.setItem("changebook_current_user", JSON.stringify(u));
  }, user);
}

export const USERS = {
  alice: { email: "alice@changebook.dev", name: "Alice Engineer", role: "Author" },
  bob: { email: "bob@changebook.dev", name: "Bob Reviewer", role: "Reviewer" },
  carol: { email: "carol@changebook.dev", name: "Carol Operator", role: "Operator" },
};
