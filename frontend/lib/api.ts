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
    let message: string;
    if (typeof error.detail === "string") {
      message = error.detail;
    } else if (Array.isArray(error.detail)) {
      // FastAPI validation errors: [{loc: [...], msg: "..."}, ...]
      message = error.detail
        .map((e: { loc?: string[]; msg?: string }) => {
          const field = e.loc?.slice(-1)[0] || "unknown";
          return `${field}: ${e.msg}`;
        })
        .join("; ");
    } else {
      message = `API error: ${res.status}`;
    }
    throw new Error(message);
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
  abort_reason: string | null;
  window_override_reason: string | null;
  maintenance_window_start: string | null;
  maintenance_window_end: string | null;
  maintenance_window_tz: string | null;
  created_at: string;
  updated_at: string;
  audit_event_count?: number;
  customer_name: string | null;
  service_name: string | null;
  environment_name: string | null;
  environment_platform: string | null;
  pending_reviewers: string[];
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
  added_during_execution: boolean;
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

export interface Template {
  id: string;
  title: string;
  description: string | null;
  defence_tags: string[] | null;
  preflight_answers: Record<string, string> | null;
  source_change_id: string | null;
  author_name: string;
  item_count: number;
  created_at: string;
  updated_at: string;
}

export interface TemplateChecklistItemCreate {
  phase: string;
  description: string;
  command?: string;
  expected_outcome?: string;
  rollback_action?: string;
  is_hold_point?: boolean;
}

export interface TemplateChecklistItem {
  id: string;
  phase: string;
  order: number;
  description: string;
  command: string | null;
  expected_outcome: string | null;
  rollback_action: string | null;
  is_hold_point: boolean;
}

export interface TemplateDetail extends Template {
  items: TemplateChecklistItem[];
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
    maintenance_window_start?: string;
    maintenance_window_end?: string;
    maintenance_window_tz?: string;
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

  verifyHoldPoint: (changeId: string, itemId: string, verifiedBy: string) =>
    request<ChecklistCompletion>(`/changes/${changeId}/checklist/${itemId}/hold-point-verify`, {
      method: "POST",
      body: JSON.stringify({ verified_by: verifiedBy }),
    }),

  addExecutionStep: (changeId: string, data: {
    insert_after_item_id: string;
    description: string;
    command?: string;
    expected_outcome?: string;
    rollback_action?: string;
    is_hold_point?: boolean;
  }) =>
    request<ChecklistItem>(`/changes/${changeId}/checklist/execution-step`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  getExecutionStatus: (changeId: string) =>
    request<ExecutionStatus>(`/changes/${changeId}/execution-status`),

  // Reviews
  listReviews: (changeId: string) =>
    request<Review[]>(`/changes/${changeId}/reviewers`),

  assignReviewer: (changeId: string, reviewerName?: string) =>
    request<Review>(`/changes/${changeId}/reviewers`, {
      method: "POST",
      body: JSON.stringify(reviewerName ? { reviewer_name: reviewerName } : {}),
    }),

  submitDecision: (changeId: string, reviewId: string, decision: string, comment?: string) =>
    request<Review>(`/changes/${changeId}/reviewers/${reviewId}/decision`, {
      method: "POST",
      body: JSON.stringify({ decision, comment }),
    }),

  // Customers
  listCustomers: () => request<Customer[]>("/customers"),
  getCustomer: (id: string) => request<Customer>(`/customers/${id}`),
  createCustomer: (data: { name: string; description?: string; services?: { name: string; description?: string }[] }) =>
    request<Customer>("/customers", { method: "POST", body: JSON.stringify(data) }),
  addService: (customerId: string, data: { name: string; description?: string }) =>
    request<Service>(`/customers/${customerId}/services`, { method: "POST", body: JSON.stringify(data) }),

  // Environments
  listEnvironments: () => request<Environment[]>("/environments"),
  createEnvironment: (data: { name: string; platform?: string; description?: string }) =>
    request<Environment>("/environments", { method: "POST", body: JSON.stringify(data) }),

  // People (known names from activity)
  listPeople: () => request<string[]>("/people"),

  // Templates
  listTemplates: (params?: Record<string, string>) => {
    const query = new URLSearchParams(params);
    const qs = query.toString();
    return request<Template[]>(`/templates${qs ? `?${qs}` : ""}`);
  },

  getTemplate: (id: string) => request<TemplateDetail>(`/templates/${id}`),

  createTemplate: (data: {
    title: string;
    description?: string;
    defence_tags?: string[];
    preflight_answers?: Record<string, string>;
    items?: TemplateChecklistItemCreate[];
  }) => request<TemplateDetail>("/templates", { method: "POST", body: JSON.stringify(data) }),

  saveAsTemplate: (changeId: string, data: { title?: string; description?: string }) =>
    request<TemplateDetail>(`/changes/${changeId}/save-as-template`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  useTemplate: (templateId: string, data: {
    title: string;
    customer_id: string;
    service_id: string;
    environment_id: string;
  }) => request<{ change_id: string }>(`/templates/${templateId}/use`, {
    method: "POST",
    body: JSON.stringify(data),
  }),
};
