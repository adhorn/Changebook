"use client";

import { useState } from "react";
import { api, ChecklistItem } from "@/lib/api";
import { formatDate } from "@/lib/constants";
import CopyButton from "@/components/CopyButton";

export default function ChecklistItemRow({
  item,
  isNext,
  isExecuting,
  isDraft,
  changeId,
  currentUserName,
  onCompleted,
  onAddStepAfter,
}: {
  item: ChecklistItem;
  isNext: boolean;
  isExecuting: boolean;
  isDraft: boolean;
  changeId: string;
  currentUserName: string;
  onCompleted: () => void;
  onAddStepAfter?: (itemId: string) => void;
}) {
  const [showComplete, setShowComplete] = useState(false);
  const [showVerify, setShowVerify] = useState(false);
  const [verifierName, setVerifierName] = useState("");
  const [observedResult, setObservedResult] = useState("");
  const [completionStatus, setCompletionStatus] = useState("completed");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Edit mode state
  const [editing, setEditing] = useState(false);
  const [editDesc, setEditDesc] = useState("");
  const [editCommand, setEditCommand] = useState("");
  const [editExpectedOutcome, setEditExpectedOutcome] = useState("");
  const [editRollbackAction, setEditRollbackAction] = useState("");
  const [editIsHoldPoint, setEditIsHoldPoint] = useState(false);
  const [saving, setSaving] = useState(false);

  const completion = item.completion;
  const isCompleted = !!completion;

  function startEditing() {
    setEditDesc(item.description);
    setEditCommand(item.command || "");
    setEditExpectedOutcome(item.expected_outcome || "");
    setEditRollbackAction(item.rollback_action || "");
    setEditIsHoldPoint(item.is_hold_point);
    setEditing(true);
  }

  async function handleSaveEdit() {
    setSaving(true);
    setError(null);
    try {
      await api.updateChecklistItem(changeId, item.id, {
        description: editDesc.trim(),
        command: editCommand.trim() || null,
        expected_outcome: editExpectedOutcome.trim() || null,
        rollback_action: editRollbackAction.trim() || null,
        is_hold_point: editIsHoldPoint,
      });
      setEditing(false);
      onCompleted();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to save");
    }
    setSaving(false);
  }

  async function handleDelete() {
    if (!confirm("Delete this checklist item?")) return;
    try {
      await api.deleteChecklistItem(changeId, item.id);
      onCompleted();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to delete");
    }
  }

  async function handleComplete() {
    setSubmitting(true);
    setError(null);
    try {
      await api.completeItem(changeId, item.id, {
        observed_result: observedResult,
        status: completionStatus,
      });
      setShowComplete(false);
      onCompleted();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed");
    }
    setSubmitting(false);
  }

  async function handleVerifyHoldPoint() {
    if (!verifierName.trim()) {
      setError("Enter the name of the person who verified this step.");
      return;
    }
    if (verifierName.trim() === completion?.completed_by) {
      setError(`Must be a different person than ${completion.completed_by}.`);
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await api.verifyHoldPoint(changeId, item.id, verifierName.trim());
      setShowVerify(false);
      setVerifierName("");
      onCompleted();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to verify hold point");
    }
    setSubmitting(false);
  }

  const needsHoldVerification =
    isCompleted && item.is_hold_point && !completion?.hold_point_verified_by;

  // --- Edit mode rendering ---
  if (editing) {
    return (
      <div className="border border-blue-200 rounded-lg p-4 bg-blue-50/30 space-y-2">
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">Description *</label>
          <input
            type="text"
            value={editDesc}
            onChange={(e) => setEditDesc(e.target.value)}
            className="w-full px-2 py-1.5 border border-gray-300 rounded text-xs focus:outline-none focus:ring-1 focus:ring-gray-900"
            autoFocus
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">Command</label>
          <input
            type="text"
            value={editCommand}
            onChange={(e) => setEditCommand(e.target.value)}
            placeholder="e.g. kubectl get pods -n prod"
            className="w-full px-2 py-1.5 border border-gray-300 rounded text-xs font-mono focus:outline-none focus:ring-1 focus:ring-gray-900"
            style={{
              fontVariantLigatures: "none",
              fontFeatureSettings: '"liga" 0, "clig" 0',
              textRendering: "optimizeSpeed",
            }}
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">Expected outcome</label>
          <input
            type="text"
            value={editExpectedOutcome}
            onChange={(e) => setEditExpectedOutcome(e.target.value)}
            placeholder="What should you see if this succeeds?"
            className="w-full px-2 py-1.5 border border-gray-300 rounded text-xs focus:outline-none focus:ring-1 focus:ring-gray-900"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">Rollback action</label>
          <input
            type="text"
            value={editRollbackAction}
            onChange={(e) => setEditRollbackAction(e.target.value)}
            placeholder="What to do if this step fails"
            className="w-full px-2 py-1.5 border border-gray-300 rounded text-xs focus:outline-none focus:ring-1 focus:ring-gray-900"
          />
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleSaveEdit}
            disabled={saving || !editDesc.trim()}
            className="px-3 py-1.5 text-xs font-medium text-white bg-gray-900 rounded hover:bg-gray-800 disabled:opacity-50"
          >
            {saving ? "Saving..." : "Save"}
          </button>
          <label className="flex items-center gap-1.5 text-xs text-gray-600 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={editIsHoldPoint}
              onChange={(e) => setEditIsHoldPoint(e.target.checked)}
              className="rounded border-gray-300 text-amber-600 focus:ring-amber-500"
            />
            Hold point
          </label>
          <button
            onClick={() => setEditing(false)}
            className="ml-auto px-2 py-1.5 text-xs text-gray-500 hover:text-gray-700"
          >
            Cancel
          </button>
        </div>
        {error && <p className="text-xs text-red-600">{error}</p>}
      </div>
    );
  }

  // --- Read-only rendering ---
  return (
    <div
      className={`border rounded-lg p-4 ${
        isCompleted
          ? "border-green-200 bg-green-50/50"
          : isNext && isExecuting
            ? "border-blue-300 bg-blue-50/30"
            : "border-gray-200"
      }`}
    >
      <div className="flex items-start gap-3">
        <span
          className={`flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-xs font-medium ${
            isCompleted
              ? "bg-green-100 text-green-700"
              : isNext && isExecuting
                ? "bg-blue-100 text-blue-700"
                : "bg-gray-100 text-gray-600"
          }`}
        >
          {isCompleted ? "✓" : item.order}
        </span>
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <p className="text-sm text-gray-900">{item.description}</p>
            {isDraft && (
              <div className="flex items-center gap-1 flex-shrink-0">
                <button
                  onClick={startEditing}
                  className="px-1.5 py-0.5 text-xs text-gray-400 hover:text-gray-700 hover:bg-gray-100 rounded transition-colors"
                  title="Edit item"
                >
                  edit
                </button>
                <button
                  onClick={handleDelete}
                  className="px-1.5 py-0.5 text-xs text-gray-400 hover:text-red-600 hover:bg-red-50 rounded transition-colors"
                  title="Delete item"
                >
                  delete
                </button>
              </div>
            )}
          </div>
          {item.command && (
            <div className="relative mt-1 group/cmd">
              <pre
                className="bg-gray-50 rounded p-2 pr-10 text-xs font-mono text-gray-700 overflow-x-auto"
                style={{
                  whiteSpace: "pre-wrap",
                  fontVariantLigatures: "none",
                  fontFeatureSettings: '"liga" 0, "clig" 0',
                  textRendering: "optimizeSpeed",
                }}
              >
                {item.command}
              </pre>
              <CopyButton text={item.command} />
            </div>
          )}
          {item.expected_outcome && !showComplete && (
            <p className="mt-1 text-xs text-gray-500">
              Expected: {item.expected_outcome}
            </p>
          )}
          {item.rollback_action && !showComplete && (
            <p className="mt-1 text-xs text-gray-500">
              Rollback: {item.rollback_action}
            </p>
          )}
          <div className="flex flex-wrap items-center gap-1.5 mt-1">
            {item.is_hold_point && (
              <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200">
                Hold Point
              </span>
            )}
            {item.added_during_execution && (
              <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-purple-50 text-purple-700 border border-purple-200">
                Added during execution
              </span>
            )}
          </div>

          {/* Completion details */}
          {isCompleted && completion && (
            <div className="mt-2 p-2 bg-white rounded border border-green-100 text-xs space-y-1">
              <div className="flex items-center gap-2">
                <span
                  className={`font-medium ${
                    completion.status === "completed"
                      ? "text-green-700"
                      : completion.status === "flagged"
                        ? "text-amber-700"
                        : "text-orange-700"
                  }`}
                >
                  {completion.status === "completed"
                    ? "Completed"
                    : completion.status === "flagged"
                      ? "Flagged"
                      : "Skipped"}
                </span>
                <span className="text-gray-400">
                  by {completion.completed_by}
                </span>
                <span className="text-gray-400">
                  {formatDate(completion.completed_at)}
                </span>
              </div>
              <pre
                className="mt-1 bg-gray-50 rounded p-2 font-mono text-gray-700 whitespace-pre-wrap overflow-x-auto"
                style={{
                  fontVariantLigatures: "none",
                  fontFeatureSettings: '"liga" 0, "clig" 0',
                  textRendering: "optimizeSpeed",
                }}
              >
                {completion.observed_result}
              </pre>
              {completion.hold_point_verified_by && (
                <p className="text-green-700">
                  Hold point verified by {completion.hold_point_verified_by}
                </p>
              )}
            </div>
          )}

          {/* Hold point verification */}
          {needsHoldVerification && isExecuting && (
            <>
              {!showVerify ? (
                <div className="mt-2">
                  <p className="text-xs text-amber-700 mb-1">
                    A second person must verify this hold point before proceeding.
                  </p>
                  <button
                    onClick={() => { setShowVerify(true); setError(null); }}
                    className="px-3 py-1.5 text-xs font-medium text-amber-700 bg-amber-50 border border-amber-200 rounded-lg hover:bg-amber-100"
                  >
                    Verify Hold Point
                  </button>
                </div>
              ) : (
                <div className="mt-2 p-3 bg-amber-50/50 border border-amber-200 rounded-lg space-y-2">
                  <label className="block text-xs font-medium text-amber-900">
                    Who verified this step?
                  </label>
                  <input
                    type="text"
                    value={verifierName}
                    onChange={(e) => { setVerifierName(e.target.value); setError(null); }}
                    placeholder="Name of the person who checked this"
                    className="w-full px-2 py-1.5 border border-amber-300 rounded text-xs focus:outline-none focus:ring-1 focus:ring-amber-500"
                    autoFocus
                  />
                  {error && <p className="text-xs text-red-600">{error}</p>}
                  <div className="flex gap-2">
                    <button
                      onClick={handleVerifyHoldPoint}
                      disabled={submitting || !verifierName.trim()}
                      className="px-3 py-1.5 text-xs font-medium text-white bg-amber-600 rounded hover:bg-amber-700 disabled:opacity-50"
                    >
                      {submitting ? "..." : "Confirm"}
                    </button>
                    <button
                      onClick={() => { setShowVerify(false); setVerifierName(""); setError(null); }}
                      className="px-3 py-1.5 text-xs font-medium text-gray-600 hover:text-gray-800"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}
            </>
          )}

          {/* Add step after — only on completed items during execution */}
          {isCompleted && isExecuting && onAddStepAfter && (
            <button
              onClick={() => onAddStepAfter(item.id)}
              className="mt-2 px-2 py-1 text-xs text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded transition-colors"
            >
              + Add step after this
            </button>
          )}

          {/* Complete button */}
          {isNext && isExecuting && !isCompleted && (
            <>
              {!showComplete ? (
                <button
                  onClick={() => setShowComplete(true)}
                  className="mt-2 px-3 py-1.5 text-xs font-medium text-blue-700 bg-blue-50 border border-blue-200 rounded-lg hover:bg-blue-100"
                >
                  Complete this item
                </button>
              ) : (
                <div className="mt-3 space-y-2 p-3 bg-white border border-blue-200 rounded-lg">
                  {/* Surface expected outcome prominently when recording */}
                  {item.expected_outcome && (
                    <div className="p-2.5 bg-blue-50 border border-blue-100 rounded-md">
                      <p className="text-xs font-medium text-blue-800 mb-0.5">
                        What you should see
                      </p>
                      <p className="text-sm text-blue-900 whitespace-pre-wrap">
                        {item.expected_outcome}
                      </p>
                    </div>
                  )}
                  {item.rollback_action && (
                    <div className="p-2.5 bg-gray-50 border border-gray-200 rounded-md">
                      <p className="text-xs font-medium text-gray-500 mb-0.5">
                        If this doesn&apos;t look right
                      </p>
                      <p className="text-xs text-gray-700 whitespace-pre-wrap">
                        {item.rollback_action}
                      </p>
                    </div>
                  )}
                  <div>
                    <label className="block text-xs font-medium text-gray-700 mb-1">
                      What did you observe? *
                    </label>
                    <textarea
                      value={observedResult}
                      onChange={(e) => {
                        setObservedResult(e.target.value);
                        // Auto-resize to fit content
                        const ta = e.target;
                        ta.style.height = "auto";
                        ta.style.height = ta.scrollHeight + "px";
                      }}
                      rows={3}
                      placeholder="$ kubectl get pods -n prod&#10;NAME           READY   STATUS&#10;api-7d8f9c     1/1     Running"
                      className="w-full px-2 py-1.5 border border-gray-300 rounded text-xs font-mono focus:outline-none focus:ring-1 focus:ring-blue-500 resize-y"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="block text-xs font-medium text-gray-700 mb-1">
                        Status
                      </label>
                      <select
                        value={completionStatus}
                        onChange={(e) => setCompletionStatus(e.target.value)}
                        className="w-full px-2 py-1.5 border border-gray-300 rounded text-xs"
                      >
                        <option value="completed">Completed</option>
                        <option value="flagged">Flagged</option>
                        <option value="skipped_with_justification">
                          Skipped
                        </option>
                      </select>
                    </div>
                    {/* Identity comes from auth */}
                  </div>
                  {error && <p className="text-xs text-red-600">{error}</p>}
                  <div className="flex gap-2">
                    <button
                      onClick={handleComplete}
                      disabled={submitting || !observedResult}
                      className="px-3 py-1.5 text-xs font-medium text-white bg-blue-600 rounded hover:bg-blue-700 disabled:opacity-50"
                    >
                      {submitting ? "..." : "Record"}
                    </button>
                    <button
                      onClick={() => setShowComplete(false)}
                      className="px-3 py-1.5 text-xs font-medium text-gray-600 hover:text-gray-800"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
