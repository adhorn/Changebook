import { getAuthHeaders } from "./auth";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}/api/v1${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders(),
      ...options?.headers,
    },
    ...options,
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || `API error: ${res.status}`);
  }

  return res.json();
}

async function requestText(path: string): Promise<string> {
  const res = await fetch(`${API_BASE}/api/v1${path}`, {
    headers: {
      ...getAuthHeaders(),
    },
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.status}`);
  }
  return res.text();
}

// --- Types ---

export type ChangeStatus =
  | "draft"
  | "in_review"
  | "approved"
  | "executing"
  | "done"
  | "aborted";

export interface Change {
  id: string;
  title: string;
  description: string | null;
  status: ChangeStatus;
  customer_id: string;
  service_id: string;
  environment_id: string;
  author_name: string;
  preflight_answers: Record<string, string> | null;
  preflight_schema_version: string | null;
  defence_tags: string[] | null;
  cloned_from: string | null;
  created_at: string;
  updated_at: string;
  audit_event_count?: number;
  customer_name: string | null;
  service_name: string | null;
  environment_name: string | null;
  environment_platform: string | null;
}

export interface ChangeListResponse {
  data: Change[];
  meta: { total: number; limit: number; offset: number };
}

export interface ChecklistItem {
  id: string;
  change_id: string;
  phase: "pre_flight" | "execution" | "verification";
  order: number;
  description: string;
  command: string | null;
  expected_outcome: string | null;
  rollback_action: string | null;
  is_hold_point: boolean;
  created_at: string;
  completion: ChecklistCompletion | null;
}

export interface ChecklistCompletion {
  id: string;
  item_id: string;
  observed_result: string;
  status: "completed" | "flagged" | "skipped_with_justification";
  completed_by: string;
  completed_at: string;
  hold_point_verified_by: string | null;
  hold_point_verified_at: string | null;
}

export interface Review {
  id: string;
  change_id: string;
  reviewer_name: string;
  decision: "pending" | "approved" | "changes_requested" | "blocked";
  comment: string | null;
  created_at: string;
}

export interface PreflightQuestion {
  key: string;
  label: string;
  type: string;
  required: boolean;
  description: string;
  example: string;
}

export interface PreflightSection {
  title: string;
  framing: string;
  questions: PreflightQuestion[];
}

export interface PreflightSchema {
  schema_version: string;
  sections: PreflightSection[];
}

export interface ExecutionStatus {
  current_phase: string | null;
  total_items: number;
  completed_items: number;
  next_item_id: string | null;
  all_complete: boolean;
  phases: Record<string, { total: number; completed: number; complete: boolean }>;
}

export interface Customer {
  id: string;
  name: string;
  description: string | null;
  organisation_id: string;
  services: Service[];
}

export interface Service {
  id: string;
  name: string;
  description: string | null;
  customer_id: string;
}

export interface Environment {
  id: string;
  name: string;
  platform: string | null;
  description: string | null;
  organisation_id: string;
  customer_id: string | null;
}

// --- API calls ---

export const api = {
  // Changes
  listChanges: (params?: Record<string, string>) => {
    const query = new URLSearchParams(params);
    const qs = query.toString();
    return request<ChangeListResponse>(`/changes${qs ? `?${qs}` : ""}`);
  },

  getChange: (id: string) => request<Change>(`/changes/${id}`),

  createChange: (data: {
    title: string;
    description?: string;
    customer_id: string;
    service_id: string;
    environment_id: string;
    preflight_answers?: Record<string, string>;
    defence_tags?: string[];
  }) => request<Change>("/changes", { method: "POST", body: JSON.stringify(data) }),

  updateChange: (id: string, data: Record<string, unknown>) =>
    request<Change>(`/changes/${id}`, { method: "PATCH", body: JSON.stringify(data) }),

  transitionChange: (id: string, targetStatus: ChangeStatus, reason?: string) => {
    const params = new URLSearchParams({
      target_status: targetStatus,
    });
    if (reason) params.set("reason", reason);
    return request<Change>(
      `/changes/${id}/transition?${params}`,
      { method: "POST" }
    );
  },

  duplicateChange: (id: string, data: { title?: string; environment_id?: string }) =>
    request<Change>(`/changes/${id}/duplicate`, { method: "POST", body: JSON.stringify(data) }),

  exportMarkdown: (id: string) => requestText(`/changes/${id}/export/markdown`),

  // Preflight
  getPreflightQuestions: () => request<PreflightSchema>("/preflight-questions"),

  // Checklist
  listChecklist: (changeId: string) =>
    request<ChecklistItem[]>(`/changes/${changeId}/checklist`),

  addChecklistItem: (changeId: string, data: {
    phase: string;
    description: string;
    command?: string;
    expected_outcome?: string;
    rollback_action?: string;
    is_hold_point?: boolean;
  }) =>
    request<ChecklistItem>(`/changes/${changeId}/checklist`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  updateChecklistItem: (changeId: string, itemId: string, data: {
    description?: string;
    command?: string | null;
    expected_outcome?: string | null;
    rollback_action?: string | null;
    is_hold_point?: boolean;
  }) =>
    request<ChecklistItem>(`/changes/${changeId}/checklist/${itemId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  deleteChecklistItem: (changeId: string, itemId: string) =>
    fetch(`${API_BASE}/api/v1/changes/${changeId}/checklist/${itemId}`, {
      method: "DELETE",
      headers: { ...getAuthHeaders() },
    }),

  // Execution
  completeItem: (changeId: string, itemId: string, data: {
    observed_result: string;
    status: string;
  }) =>
    request<ChecklistCompletion>(`/changes/${changeId}/checklist/${itemId}/complete`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  verifyHoldPoint: (changeId: string, itemId: string) =>
    request<ChecklistCompletion>(`/changes/${changeId}/checklist/${itemId}/hold-point-verify`, {
      method: "POST",
      body: JSON.stringify({}),
    }),

  getExecutionStatus: (changeId: string) =>
    request<ExecutionStatus>(`/changes/${changeId}/execution-status`),

  // Reviews
  listReviews: (changeId: string) =>
    request<Review[]>(`/changes/${changeId}/reviewers`),

  assignReviewer: (changeId: string) =>
    request<Review>(`/changes/${changeId}/reviewers`, {
      method: "POST",
      body: JSON.stringify({}),
    }),

  submitDecision: (changeId: string, reviewId: string, decision: string, comment?: string) =>
    request<Review>(`/changes/${changeId}/reviewers/${reviewId}/decision`, {
      method: "POST",
      body: JSON.stringify({ decision, comment }),
    }),

  // Customers
  listCustomers: () => request<Customer[]>("/customers"),
  getCustomer: (id: string) => request<Customer>(`/customers/${id}`),

  // Environments
  listEnvironments: () => request<Environment[]>("/environments"),
};
