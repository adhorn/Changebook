"use client";

import Link from "next/link";
import UserSwitcher from "@/components/UserSwitcher";
import { Change, ChangeStatus } from "@/lib/api";
import { STATUS_COLORS, STATUS_LABELS, formatDate } from "@/lib/constants";

interface Transition {
  label: string;
  target: ChangeStatus;
  style: string;
  disabled?: boolean;
  hint?: string;
}

export default function ChangeHeader({
  change,
  canEdit,
  isTerminal,
  isAuthor,
  editingDetails,
  transitions,
  transitioning,
  onStartEditingDetails,
  onExport,
  onDuplicate,
  onSaveAsTemplate,
  onAbortToggle,
  showAbort,
  onTransitionClick,
}: {
  change: Change;
  canEdit: boolean;
  isTerminal: boolean;
  isAuthor: boolean;
  editingDetails: boolean;
  transitions: Transition[];
  transitioning: boolean;
  onStartEditingDetails: () => void;
  onExport: () => void;
  onDuplicate: () => void;
  onSaveAsTemplate: () => void;
  onAbortToggle: () => void;
  showAbort: boolean;
  onTransitionClick: (target: ChangeStatus) => void;
}) {
  return (
    <header className="bg-white border-b border-gray-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
        <div className="flex items-center gap-4">
          <Link href="/" className="text-gray-400 hover:text-gray-600">
            &larr;
          </Link>
          <div className="flex-1">
            <h1 className="text-xl font-semibold text-gray-900">
              {change.title}
            </h1>
            <div className="flex items-center gap-3 mt-1">
              <span
                className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${STATUS_COLORS[change.status]}`}
              >
                {STATUS_LABELS[change.status]}
              </span>
              <span className="text-sm text-gray-500">
                by {change.author_name}
              </span>
              <span className="text-sm text-gray-400">
                {formatDate(change.created_at)}
              </span>
            </div>
            {(change.customer_name || change.environment_name) && (
              <div className="flex items-center gap-1.5 mt-1 text-sm text-gray-500">
                {change.customer_name && (
                  <span>{change.customer_name}</span>
                )}
                {change.service_name && (
                  <>
                    <span className="text-gray-300">/</span>
                    <span>{change.service_name}</span>
                  </>
                )}
                {change.environment_name && (
                  <>
                    <span className="text-gray-300">&rarr;</span>
                    <span className="font-medium text-gray-700">
                      {change.environment_name}
                    </span>
                    {change.environment_platform && (
                      <span className="text-xs text-gray-400">
                        ({change.environment_platform})
                      </span>
                    )}
                  </>
                )}
              </div>
            )}
            {change.maintenance_window_start && change.maintenance_window_end && (
              <div className="flex items-center gap-1.5 text-xs text-gray-500 mt-0.5">
                <span>🕐</span>
                <span>
                  {new Date(change.maintenance_window_start).toLocaleString("en-GB", {
                    weekday: "short",
                    day: "numeric",
                    month: "short",
                    hour: "2-digit",
                    minute: "2-digit",
                    timeZone: change.maintenance_window_tz || "UTC",
                  })}
                  {" – "}
                  {new Date(change.maintenance_window_end).toLocaleString("en-GB", {
                    weekday: "short",
                    day: "numeric",
                    month: "short",
                    hour: "2-digit",
                    minute: "2-digit",
                    timeZone: change.maintenance_window_tz || "UTC",
                  })}
                  {" "}
                  {change.maintenance_window_tz || "UTC"}
                </span>
              </div>
            )}
          </div>
          <div className="flex items-center gap-3">
            <UserSwitcher />
            {canEdit && !editingDetails && (
              <button
                onClick={onStartEditingDetails}
                className="px-3 py-1.5 text-xs font-medium text-gray-600 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
              >
                Edit
              </button>
            )}
            <button
              onClick={onExport}
              className="px-3 py-1.5 text-xs font-medium text-gray-600 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
            >
              Export
            </button>
            <button
              onClick={onDuplicate}
              className="px-3 py-1.5 text-xs font-medium text-gray-600 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
            >
              Duplicate
            </button>
            <button
              onClick={onSaveAsTemplate}
              className="px-3 py-1.5 text-xs font-medium text-indigo-600 bg-white border border-indigo-200 rounded-lg hover:bg-indigo-50"
            >
              Save as Template
            </button>
            {!isTerminal && isAuthor && (
              <button
                onClick={onAbortToggle}
                className="px-3 py-1.5 text-xs font-medium text-red-600 bg-white border border-red-200 rounded-lg hover:bg-red-50"
              >
                {showAbort ? "Cancel" : "Abort"}
              </button>
            )}
            {isAuthor && transitions.map((t) => (
              <button
                key={t.target}
                onClick={() => onTransitionClick(t.target)}
                disabled={transitioning || t.disabled}
                title={t.hint}
                className={`px-4 py-1.5 text-sm font-medium rounded-lg disabled:opacity-50 disabled:cursor-not-allowed ${t.style}`}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>
      </div>
    </header>
  );
}
