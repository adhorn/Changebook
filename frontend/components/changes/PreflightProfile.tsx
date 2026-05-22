"use client";

import { Change, PreflightSection } from "@/lib/api";

export default function PreflightProfile({
  change,
  preflightSections,
  preflightLabelMap,
  canEdit,
  preflightExpanded,
  preflightEditing,
  editedAnswers,
  savingPreflight,
  onToggleExpanded,
  onStartEditing,
  onCancelEditing,
  onUpdateAnswer,
  onSave,
}: {
  change: Change;
  preflightSections: PreflightSection[];
  preflightLabelMap: Record<string, string>;
  canEdit: boolean;
  preflightExpanded: boolean;
  preflightEditing: boolean;
  editedAnswers: Record<string, string>;
  savingPreflight: boolean;
  onToggleExpanded: () => void;
  onStartEditing: () => void;
  onCancelEditing: () => void;
  onUpdateAnswer: (key: string, value: string) => void;
  onSave: () => void;
}) {
  const hasPreflightAnswers =
    change.preflight_answers &&
    Object.keys(change.preflight_answers).length > 0;

  const answeredCount = hasPreflightAnswers
    ? Object.values(change.preflight_answers!).filter((v) => v && v.trim())
        .length
    : 0;

  const isDraft = change.status === "draft";

  if (!hasPreflightAnswers && !(isDraft && preflightSections.length > 0)) {
    return null;
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200">
      <div className="flex items-center justify-between p-6">
        <button
          onClick={onToggleExpanded}
          className="flex-1 flex items-center justify-between text-left hover:opacity-80 transition-opacity"
        >
          <div>
            <h2 className="text-lg font-medium text-gray-900">
              Change Profile
            </h2>
            <p className="text-sm text-gray-500 mt-0.5">
              {answeredCount} questions answered
            </p>
          </div>
          <span className="text-gray-400 text-lg">
            {preflightExpanded ? "▾" : "▸"}
          </span>
        </button>
        {canEdit && !preflightEditing && (
          <button
            onClick={onStartEditing}
            className="ml-4 px-3 py-1.5 text-xs font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
          >
            Edit
          </button>
        )}
      </div>

      {preflightExpanded && !preflightEditing && (
        <div className="px-6 pb-6 space-y-6 border-t border-gray-100 pt-4">
          {preflightSections.map((section) => {
            const answeredQuestions = section.questions.filter(
              (q) => change.preflight_answers?.[q.key]
            );
            if (answeredQuestions.length === 0) return null;

            return (
              <div key={section.title}>
                <h3 className="text-sm font-medium text-gray-900 mb-2">
                  {section.title}
                </h3>
                <dl className="space-y-2">
                  {answeredQuestions.map((q) => (
                    <div
                      key={q.key}
                      className="pl-3 border-l-2 border-gray-100"
                    >
                      <dt className="text-xs font-medium text-gray-500">
                        {q.label}
                      </dt>
                      <dd className="mt-0.5 text-sm text-gray-900 whitespace-pre-wrap">
                        {change.preflight_answers![q.key]}
                      </dd>
                    </div>
                  ))}
                </dl>
              </div>
            );
          })}

          {/* Orphaned keys not in current schema */}
          {(() => {
            const schemaKeys = new Set(
              preflightSections.flatMap((s) =>
                s.questions.map((q) => q.key)
              )
            );
            const orphanedEntries = Object.entries(
              change.preflight_answers || {}
            ).filter(([key]) => !schemaKeys.has(key));
            if (orphanedEntries.length === 0) return null;
            return (
              <div>
                <h3 className="text-sm font-medium text-gray-900 mb-2">
                  Other
                </h3>
                <dl className="space-y-2">
                  {orphanedEntries.map(([key, value]) => (
                    <div
                      key={key}
                      className="pl-3 border-l-2 border-gray-100"
                    >
                      <dt className="text-xs font-medium text-gray-500">
                        {preflightLabelMap[key] ||
                          key.replace(/_/g, " ")}
                      </dt>
                      <dd className="mt-0.5 text-sm text-gray-900 whitespace-pre-wrap">
                        {value}
                      </dd>
                    </div>
                  ))}
                </dl>
              </div>
            );
          })()}
        </div>
      )}

      {/* Edit mode — show all questions as textareas */}
      {preflightExpanded && preflightEditing && (
        <div className="px-6 pb-6 space-y-6 border-t border-gray-100 pt-4">
          {preflightSections.map((section) => (
            <div key={section.title}>
              <h3 className="text-sm font-medium text-gray-900 mb-1">
                {section.title}
              </h3>
              <p className="text-xs text-gray-400 italic mb-3">
                {section.framing}
              </p>
              <div className="space-y-3">
                {section.questions.map((q) => (
                  <div key={q.key}>
                    <label className="block text-xs font-medium text-gray-700 mb-1">
                      {q.label}
                      {q.required && (
                        <span className="text-red-500 ml-0.5">*</span>
                      )}
                    </label>
                    <p className="text-xs text-gray-400 mb-1">
                      {q.description}
                    </p>
                    <textarea
                      value={editedAnswers[q.key] || ""}
                      onChange={(e) =>
                        onUpdateAnswer(q.key, e.target.value)
                      }
                      rows={2}
                      placeholder={q.example}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-gray-900 focus:border-transparent"
                    />
                  </div>
                ))}
              </div>
            </div>
          ))}

          <div className="flex gap-2 pt-2 border-t border-gray-100">
            <button
              onClick={onSave}
              disabled={savingPreflight}
              className="px-4 py-1.5 text-sm font-medium text-white bg-gray-900 rounded-lg hover:bg-gray-800 disabled:opacity-50"
            >
              {savingPreflight ? "Saving..." : "Save Answers"}
            </button>
            <button
              onClick={onCancelEditing}
              className="px-4 py-1.5 text-sm font-medium text-gray-600 hover:text-gray-800"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
