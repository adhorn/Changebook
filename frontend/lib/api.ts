const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}/api/v1${path}`, {
    headers: {
      "Content-Type": "application/json",
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

// --- Types ---

export type ChangeStatus =
  | "draft"
  | "in_review"
  | "approved"
  | "executing"
  | "awaiting_verification"
  | "verified"
  | "closed"
  | "aborted";

export interface Change {
  id: string;
  title: string;
  description: string | null;
  status: ChangeStatus;
  team_id: string;
  author_name: string;
  environment_ids: string[] | null;
  preflight_answers: Record<string, string> | null;
  defence_tags: string[] | null;
  created_at: string;
  updated_at: string;
}

export interface Step {
  id: string;
  order: number;
  description: string;
  expected_outcome: string | null;
  rollback_action: string | null;
  script: string | null;
  is_hold_point: boolean;
  created_at: string;
}

export interface ChangeDetail extends Change {
  steps: Step[];
}

export interface ChangeListResponse {
  data: Change[];
  meta: { total: number; limit: number; offset: number };
}

export interface Organisation {
  id: string;
  name: string;
  created_at: string;
}

export interface Team {
  id: string;
  name: string;
  organisation_id: string;
  created_at: string;
}

export interface Environment {
  id: string;
  name: string;
  platform: string | null;
  description: string | null;
  organisation_id: string;
  created_at: string;
}

// --- API calls ---

export const api = {
  // Changes
  listChanges: (params?: { team_id?: string; status?: ChangeStatus }) => {
    const query = new URLSearchParams();
    if (params?.team_id) query.set("team_id", params.team_id);
    if (params?.status) query.set("status", params.status);
    const qs = query.toString();
    return request<ChangeListResponse>(`/changes${qs ? `?${qs}` : ""}`);
  },

  getChange: (id: string) => request<ChangeDetail>(`/changes/${id}`),

  createChange: (data: {
    title: string;
    description?: string;
    team_id: string;
    author_name: string;
    environment_ids?: string[];
    preflight_answers?: Record<string, string>;
    defence_tags?: string[];
    steps?: {
      description: string;
      expected_outcome?: string;
      rollback_action?: string;
      script?: string;
      is_hold_point?: boolean;
    }[];
  }) => request<ChangeDetail>("/changes", { method: "POST", body: JSON.stringify(data) }),

  transitionChange: (id: string, targetStatus: ChangeStatus, actorName: string) =>
    request<ChangeDetail>(
      `/changes/${id}/transition?target_status=${targetStatus}&actor_name=${encodeURIComponent(actorName)}`,
      { method: "POST" }
    ),

  // Organisations
  listOrganisations: () => request<Organisation[]>("/organisations"),
  createOrganisation: (name: string) =>
    request<Organisation>("/organisations", {
      method: "POST",
      body: JSON.stringify({ name }),
    }),

  // Teams
  listTeams: (organisationId?: string) => {
    const qs = organisationId ? `?organisation_id=${organisationId}` : "";
    return request<Team[]>(`/teams${qs}`);
  },
  createTeam: (name: string, organisationId: string) =>
    request<Team>("/teams", {
      method: "POST",
      body: JSON.stringify({ name, organisation_id: organisationId }),
    }),

  // Environments
  listEnvironments: (organisationId?: string) => {
    const qs = organisationId ? `?organisation_id=${organisationId}` : "";
    return request<Environment[]>(`/environments${qs}`);
  },
  createEnvironment: (data: {
    name: string;
    platform?: string;
    description?: string;
    organisation_id: string;
  }) =>
    request<Environment>("/environments", {
      method: "POST",
      body: JSON.stringify(data),
    }),
};
