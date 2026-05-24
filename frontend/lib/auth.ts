/**
 * Mock auth: user identity for development.
 *
 * In dev mode, the user switcher lets you switch between preset users.
 * The selected user's identity is sent as X-User-Email / X-User-Name headers.
 */

export interface MockUser {
  email: string;
  name: string;
  role: string; // Display label (not enforced)
}

export const MOCK_USERS: MockUser[] = [
  { email: "alice@changebook.dev", name: "Alice Engineer", role: "Author" },
  { email: "bob@changebook.dev", name: "Bob Reviewer", role: "Reviewer" },
  { email: "carol@changebook.dev", name: "Carol Operator", role: "Operator" },
  { email: "dave@changebook.dev", name: "Dave Manager", role: "Manager" },
];

const STORAGE_KEY = "changebook_current_user";

export function getCurrentUser(): MockUser {
  if (typeof window === "undefined") return MOCK_USERS[0];

  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored) {
    try {
      return JSON.parse(stored);
    } catch {
      // Fall through to default
    }
  }
  return MOCK_USERS[0];
}

export function setCurrentUser(user: MockUser): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(user));
  // Dispatch event so components can react
  window.dispatchEvent(new CustomEvent("user-changed", { detail: user }));
}

export function getAuthHeaders(): Record<string, string> {
  const user = getCurrentUser();
  return {
    "X-User-Email": user.email,
    "X-User-Name": user.name,
  };
}
