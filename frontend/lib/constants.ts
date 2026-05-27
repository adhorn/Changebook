import type { ChangeStatus } from "./api";

export const STATUS_COLORS: Record<ChangeStatus, string> = {
  draft: "bg-gray-100 text-gray-700",
  in_review: "bg-yellow-100 text-yellow-800",
  approved: "bg-blue-100 text-blue-800",
  executing: "bg-orange-100 text-orange-800",
  done: "bg-green-100 text-green-800",
  aborted: "bg-red-100 text-red-700",
};

export const STATUS_LABELS: Record<ChangeStatus, string> = {
  draft: "Draft",
  in_review: "In Review",
  approved: "Approved",
  executing: "Executing",
  done: "Done",
  aborted: "Aborted",
};

export const PHASE_LABELS: Record<string, string> = {
  pre_flight: "Pre-flight",
  execution: "Execution",
  verification: "Verification",
};

export const PHASE_ORDER = ["pre_flight", "execution", "verification"];

export const TIMEZONES = [
  "UTC",
  "Europe/London",
  "Europe/Paris",
  "Europe/Berlin",
  "Europe/Copenhagen",
  "US/Eastern",
  "US/Central",
  "US/Mountain",
  "US/Pacific",
  "Asia/Tokyo",
  "Asia/Singapore",
  "Australia/Sydney",
];

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatDateShort(iso: string): string {
  return new Date(iso).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}
