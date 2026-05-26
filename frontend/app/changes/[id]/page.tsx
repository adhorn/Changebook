"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import UserSwitcher from "@/components/UserSwitcher";
import SearchableSelect from "@/components/SearchableSelect";
import { getCurrentUser } from "@/lib/auth";
import {
  api,
  Change,
  ChangeStatus,
  ChecklistItem,
  Review,
  ExecutionStatus,
  PreflightSection,
  Customer,
  Environment,
} from "@/lib/api";

const STATUS_COLORS: Record<ChangeStatus, string> = {
  draft: "bg-gray-100 text-gray-700",
  in_review: "bg-yellow-100 text-yellow-800",
  approved: "bg-blue-100 text-blue-800",
  executing: "bg-orange-100 text-orange-800",
  done: "bg-green-100 text-green-800",
  aborted: "bg-red-100 text-red-700",
};

const STATUS_LABELS: Record<ChangeStatus, string> = {
  draft: "Draft",
  in_review: "In Review",
  approved: "Approved",
  executing: "Executing",
  done: "Done",
  aborted: "Aborted",
};

const PHASE_LABELS: Record<string, string> = {
  pre_flight: "Pre-flight",
  execution: "Execution",
  verification: "Verification",
};

const PHASE_ORDER = ["pre_flight", "execution", "verification"];

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

// --- Copy to clipboard button ---

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback for non-HTTPS contexts
      const textarea = document.createElement("textarea");
      textarea.value = text;
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }

  return (
    <button
      onClick={handleCopy}
      className="absolute top-1.5 right-1.5 p-1 rounded text-gray-400 hover:text-gray-700 hover:bg-gray-200 opacity-0 group-hover/cmd:opacity-100 transition-opacity"
      title="Copy to clipboard"
    >
      {copied ? (
        <svg className="w-4 h-4 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
        </svg>
      ) : (
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
        </svg>
      )}
    </button>
  );
}

// --- Checklist Item Component ---

function ChecklistItemRow({
  item,
  isNext,
  isExecuting,
  isDraft,
  changeId,
  currentUserName,
  onCompleted,
}: {
  item: ChecklistItem;
  isNext: boolean;
  isExecuting: boolean;
  isDraft: boolean;
  changeId: string;
  currentUserName: string;
  onCompleted: () => void;
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
          {item.expected_outcome && (
            <p className="mt-1 text-xs text-gray-500">
              Expected: {item.expected_outcome}
            </p>
          )}
          {item.rollback_action && (
            <p className="mt-1 text-xs text-gray-500">
              Rollback: {item.rollback_action}
            </p>
          )}
          {item.is_hold_point && (
            <span className="inline-flex items-center mt-1 px-2 py-0.5 rounded text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200">
              Hold Point
            </span>
          )}

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
                  <div>
                    <label className="block text-xs font-medium text-gray-700 mb-1">
                      Result — paste output or describe what you observed *
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

// --- Review Card Component ---

function ReviewCard({
  review,
  canDecide,
  onDecision,
}: {
  review: Review;
  canDecide: boolean;
  onDecision: (decision: string, comment?: string) => void;
}) {
  const [comment, setComment] = useState("");
  const [showComment, setShowComment] = useState(false);

  const decisionColors: Record<string, string> = {
    approved: "bg-green-100 text-green-700",
    blocked: "bg-red-100 text-red-700",
    changes_requested: "bg-yellow-100 text-yellow-700",
    pending: "bg-gray-100 text-gray-600",
  };

  return (
    <div className="p-3 border border-gray-200 rounded-lg">
      <div className="flex items-center justify-between">
        <div>
          <span className="text-sm font-medium text-gray-900">
            {review.reviewer_name}
          </span>
          <span
            className={`ml-2 inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${decisionColors[review.decision] || decisionColors.pending}`}
          >
            {review.decision}
          </span>
        </div>
        {canDecide && !showComment && (
          <div className="flex gap-1">
            <button
              onClick={() => onDecision("approved", undefined)}
              className="px-2 py-1 text-xs text-green-700 bg-green-50 rounded hover:bg-green-100"
            >
              Approve
            </button>
            <button
              onClick={() => setShowComment(true)}
              className="px-2 py-1 text-xs text-yellow-700 bg-yellow-50 rounded hover:bg-yellow-100"
            >
              Request Changes
            </button>
            <button
              onClick={() => setShowComment(true)}
              className="px-2 py-1 text-xs text-red-700 bg-red-50 rounded hover:bg-red-100"
            >
              Block
            </button>
          </div>
        )}
      </div>
      {review.comment && (
        <p className="text-xs text-gray-500 mt-1">{review.comment}</p>
      )}
      {showComment && canDecide && (
        <div className="mt-2 space-y-2">
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Comment (optional)..."
            rows={2}
            className="w-full px-2 py-1.5 border border-gray-300 rounded text-xs focus:outline-none focus:ring-1 focus:ring-gray-500"
            autoFocus
          />
          <div className="flex gap-1">
            <button
              onClick={() => {
                onDecision("changes_requested", comment || undefined);
              }}
              className="px-2 py-1 text-xs text-yellow-700 bg-yellow-50 rounded hover:bg-yellow-100"
            >
              Request Changes
            </button>
            <button
              onClick={() => {
                onDecision("blocked", comment || undefined);
              }}
              className="px-2 py-1 text-xs text-red-700 bg-red-50 rounded hover:bg-red-100"
            >
              Block
            </button>
            <button
              onClick={() => setShowComment(false)}
              className="px-2 py-1 text-xs text-gray-500 hover:text-gray-700"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// --- Main Page ---

export default function ChangeDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;

  const [currentUserName, setCurrentUserName] = useState(getCurrentUser().name);

  // Listen for user switches
  useEffect(() => {
    function handleUserChanged(e: Event) {
      const detail = (e as CustomEvent).detail;
      if (detail?.name) setCurrentUserName(detail.name);
    }
    window.addEventListener("user-changed", handleUserChanged);
    return () => window.removeEventListener("user-changed", handleUserChanged);
  }, []);

  const [change, setChange] = useState<Change | null>(null);
  const [checklist, setChecklist] = useState<ChecklistItem[]>([]);
  const [reviews, setReviews] = useState<Review[]>([]);
  const [execStatus, setExecStatus] = useState<ExecutionStatus | null>(null);
  const [preflightSections, setPreflightSections] = useState<
    PreflightSection[]
  >([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [transitioning, setTransitioning] = useState(false);
  const [showAbort, setShowAbort] = useState(false);
  const [abortReason, setAbortReason] = useState("");
  // Reviewer identity comes from auth headers
  const [preflightExpanded, setPreflightExpanded] = useState(false);
  const [preflightEditing, setPreflightEditing] = useState(false);
  const [editedAnswers, setEditedAnswers] = useState<Record<string, string>>({});
  const [savingPreflight, setSavingPreflight] = useState(false);
  const [showDuplicate, setShowDuplicate] = useState(false);
  // Duplicate author comes from auth headers
  const [dupTitle, setDupTitle] = useState("");
  const [duplicating, setDuplicating] = useState(false);
  const [showWindowWarning, setShowWindowWarning] = useState(false);
  const [windowWarningMessage, setWindowWarningMessage] = useState("");
  const [windowOverrideReason, setWindowOverrideReason] = useState("");

  // Inline editing for draft details (title, description, customer/service/environment)
  const [editingDetails, setEditingDetails] = useState(false);
  const [editTitle, setEditTitle] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editCustomerId, setEditCustomerId] = useState("");
  const [editServiceId, setEditServiceId] = useState("");
  const [editEnvironmentId, setEditEnvironmentId] = useState("");
  const [editWindowStart, setEditWindowStart] = useState("");
  const [editWindowEnd, setEditWindowEnd] = useState("");
  const [editWindowTz, setEditWindowTz] = useState("UTC");
  const [savingDetails, setSavingDetails] = useState(false);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [environments, setEnvironments] = useState<Environment[]>([]);

  // New checklist item form — per-phase
  const [addingToPhase, setAddingToPhase] = useState<string | null>(null);
  const [newItemDesc, setNewItemDesc] = useState("");
  const [newItemCommand, setNewItemCommand] = useState("");
  const [newItemExpectedOutcome, setNewItemExpectedOutcome] = useState("");
  const [newItemRollbackAction, setNewItemRollbackAction] = useState("");
  const [newItemHoldPoint, setNewItemHoldPoint] = useState(false);

  const loadAll = useCallback(async () => {
    try {
      const [c, items, revs, schema] = await Promise.all([
        api.getChange(id),
        api.listChecklist(id),
        api.listReviews(id),
        api.getPreflightQuestions(),
      ]);
      setChange(c);
      setChecklist(items);
      setReviews(revs);
      setPreflightSections(schema.sections);

      if (c.status === "executing") {
        const es = await api.getExecutionStatus(id);
        setExecStatus(es);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load");
    }
    setLoading(false);
  }, [id]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  // Build key→label map from preflight schema
  const preflightLabelMap: Record<string, string> = {};
  for (const section of preflightSections) {
    for (const q of section.questions) {
      preflightLabelMap[q.key] = q.label;
    }
  }

  async function handleTransition(target: ChangeStatus, reason?: string) {
    if (!change) return;
    setTransitioning(true);
    setError(null);
    try {
      await api.transitionChange(change.id, target, reason);
      setShowAbort(false);
      setAbortReason("");
      await loadAll();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Transition failed");
    }
    setTransitioning(false);
  }

  function handleTransitionClick(target: ChangeStatus) {
    if (!change) return;
    if (target === "executing" && change.maintenance_window_start && change.maintenance_window_end) {
      const now = new Date();
      const start = new Date(change.maintenance_window_start);
      const end = new Date(change.maintenance_window_end);
      const tz = change.maintenance_window_tz || "UTC";
      const fmt = (d: Date) =>
        d.toLocaleString("en-GB", {
          weekday: "short",
          day: "numeric",
          month: "short",
          hour: "2-digit",
          minute: "2-digit",
          timeZone: tz,
        });
      if (now < start) {
        setWindowWarningMessage(
          `The maintenance window has not opened yet. It starts ${fmt(start)} ${tz}. You are about to execute before the agreed window.`
        );
        setShowWindowWarning(true);
        return;
      }
      if (now > end) {
        setWindowWarningMessage(
          `The maintenance window closed at ${fmt(end)} ${tz}. You are about to execute after the agreed window.`
        );
        setShowWindowWarning(true);
        return;
      }
    }
    handleTransition(target);
  }

  const [addingReviewer, setAddingReviewer] = useState(false);
  const [knownPeople, setKnownPeople] = useState<string[]>([]);

  async function openReviewerInput() {
    setAddingReviewer(true);
    try {
      const people = await api.listPeople();
      setKnownPeople(people);
    } catch {
      // non-critical
    }
  }

  async function handleAddReviewer(name: string) {
    try {
      await api.assignReviewer(id, name);
      setAddingReviewer(false);
      await loadAll();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to add reviewer");
    }
  }

  async function handleReviewDecision(reviewId: string, decision: string, comment?: string) {
    try {
      await api.submitDecision(id, reviewId, decision, comment || undefined);
      await loadAll();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed");
    }
  }

  async function handleAddChecklistItem(phase: string) {
    if (!newItemDesc.trim()) return;
    try {
      await api.addChecklistItem(id, {
        phase,
        description: newItemDesc.trim(),
        command: newItemCommand.trim() || undefined,
        expected_outcome: newItemExpectedOutcome.trim() || undefined,
        rollback_action: newItemRollbackAction.trim() || undefined,
        is_hold_point: newItemHoldPoint || undefined,
      });
      setNewItemDesc("");
      setNewItemCommand("");
      setNewItemExpectedOutcome("");
      setNewItemRollbackAction("");
      setNewItemHoldPoint(false);
      // Keep the form open in the same phase so you can add multiple items
      await loadAll();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed");
    }
  }

  function toLocalInput(isoStr: string | null): string {
    if (!isoStr) return "";
    // datetime-local inputs need "YYYY-MM-DDTHH:MM" format
    return isoStr.slice(0, 16);
  }

  function startEditingDetails() {
    if (!change) return;
    setEditTitle(change.title);
    setEditDescription(change.description || "");
    setEditCustomerId(change.customer_id);
    setEditServiceId(change.service_id);
    setEditEnvironmentId(change.environment_id);
    setEditWindowStart(toLocalInput(change.maintenance_window_start));
    setEditWindowEnd(toLocalInput(change.maintenance_window_end));
    setEditWindowTz(change.maintenance_window_tz || "UTC");
    setEditingDetails(true);
    // Load customers/environments for dropdowns
    api.listCustomers().then(setCustomers).catch(console.error);
    api.listEnvironments().then(setEnvironments).catch(console.error);
  }

  async function handleSaveDetails() {
    setError(null);
    const missing: string[] = [];
    if (!editTitle.trim()) missing.push("Title");
    if (!editCustomerId) missing.push("Customer");
    if (!editServiceId) missing.push("Service");
    if (!editEnvironmentId) missing.push("Environment");
    if (missing.length > 0) {
      setError(`Required: ${missing.join(", ")}`);
      return;
    }
    setSavingDetails(true);
    try {
      await api.updateChange(id, {
        title: editTitle,
        description: editDescription || undefined,
        customer_id: editCustomerId,
        service_id: editServiceId,
        environment_id: editEnvironmentId,
        maintenance_window_start: editWindowStart ? new Date(editWindowStart).toISOString() : null,
        maintenance_window_end: editWindowEnd ? new Date(editWindowEnd).toISOString() : null,
        maintenance_window_tz: editWindowStart ? editWindowTz : null,
      });
      setEditingDetails(false);
      await loadAll();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to save changes");
    }
    setSavingDetails(false);
  }

  async function handleCreateCustomer(name: string): Promise<string | null> {
    const newCustomer = await api.createCustomer({ name, services: [{ name: "Default" }] });
    setCustomers((prev) => [...prev, newCustomer]);
    setEditServiceId(newCustomer.services[0]?.id || "");
    return newCustomer.id;
  }

  async function handleCreateService(name: string): Promise<string | null> {
    if (!editCustomerId) return null;
    const newService = await api.addService(editCustomerId, { name });
    setCustomers((prev) =>
      prev.map((c) =>
        c.id === editCustomerId ? { ...c, services: [...c.services, newService] } : c
      )
    );
    return newService.id;
  }

  async function handleCreateEnvironment(name: string): Promise<string | null> {
    const newEnv = await api.createEnvironment({ name });
    setEnvironments((prev) => [...prev, newEnv]);
    return newEnv.id;
  }

  function startEditingPreflight() {
    setEditedAnswers({ ...(change?.preflight_answers || {}) });
    setPreflightEditing(true);
    setPreflightExpanded(true);
  }

  function updateEditedAnswer(key: string, value: string) {
    setEditedAnswers((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSavePreflight() {
    setSavingPreflight(true);
    setError(null);
    try {
      await api.updateChange(id, {
        preflight_answers: editedAnswers,
      });
      setPreflightEditing(false);
      await loadAll();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to save change profile");
    }
    setSavingPreflight(false);
  }

  async function handleDuplicate() {
    setDuplicating(true);
    setError(null);
    try {
      const clone = await api.duplicateChange(id, {
        title: dupTitle.trim() || undefined,
      });
      router.push(`/changes/${clone.id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to duplicate");
      setDuplicating(false);
    }
  }

  async function handleExport() {
    setError(null);
    try {
      const md = await api.exportMarkdown(id);
      const blob = new Blob([md], { type: "text/markdown" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${change?.title || "change"}.md`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to export");
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center text-gray-500">
        Loading...
      </div>
    );
  }

  if (!change) {
    return (
      <div className="min-h-screen bg-gray-50 p-8">
        <div className="max-w-3xl mx-auto bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
          {error || "Change not found"}
        </div>
      </div>
    );
  }

  const isExecuting = change.status === "executing";
  const isDraft = change.status === "draft";
  const isTerminal = change.status === "done" || change.status === "aborted";
  const isAuthor = currentUserName === change.author_name;
  const canEdit = isDraft && isAuthor;

  // Group checklist by phase
  const checklistByPhase: Record<string, ChecklistItem[]> = {};
  for (const item of checklist) {
    if (!checklistByPhase[item.phase]) checklistByPhase[item.phase] = [];
    checklistByPhase[item.phase].push(item);
  }

  // Determine available transitions
  const transitions: { label: string; target: ChangeStatus; style: string; disabled?: boolean; hint?: string }[] =
    [];
  if (change.status === "draft") {
    transitions.push({
      label: "Submit for Review",
      target: "in_review",
      style: "bg-gray-900 text-white hover:bg-gray-800",
    });
  } else if (change.status === "in_review") {
    transitions.push({
      label: "Approve",
      target: "approved",
      style: "bg-blue-600 text-white hover:bg-blue-700",
    });
    transitions.push({
      label: "Back to Draft",
      target: "draft",
      style: "bg-white text-gray-700 border border-gray-300 hover:bg-gray-50",
    });
  } else if (change.status === "approved") {
    transitions.push({
      label: "Start Execution",
      target: "executing",
      style: "bg-orange-600 text-white hover:bg-orange-700",
    });
  } else if (change.status === "executing") {
    const allComplete = execStatus?.all_complete ?? false;
    transitions.push({
      label: "Mark Done",
      target: "done",
      style: "bg-green-600 text-white hover:bg-green-700",
      disabled: !allComplete,
      hint: !allComplete ? "Complete all checklist items first" : undefined,
    });
  }

  // Pre-flight: group answers by section
  const hasPreflightAnswers =
    change.preflight_answers &&
    Object.keys(change.preflight_answers).length > 0;

  const answeredCount = hasPreflightAnswers
    ? Object.values(change.preflight_answers!).filter((v) => v && v.trim())
        .length
    : 0;

  return (
    <div className="min-h-screen bg-gray-50">
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
                      <span className="text-gray-300">→</span>
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
                  onClick={startEditingDetails}
                  className="px-3 py-1.5 text-xs font-medium text-gray-600 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
                >
                  Edit
                </button>
              )}
              <button
                onClick={handleExport}
                className="px-3 py-1.5 text-xs font-medium text-gray-600 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
              >
                Export
              </button>
              <button
                onClick={() => {
                  setDupTitle(`${change.title} (copy)`);
                  setShowDuplicate(true);
                }}
                className="px-3 py-1.5 text-xs font-medium text-gray-600 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
              >
                Duplicate
              </button>
              {!isTerminal && isAuthor && (
                <button
                  onClick={() => setShowAbort(!showAbort)}
                  className="px-3 py-1.5 text-xs font-medium text-red-600 bg-white border border-red-200 rounded-lg hover:bg-red-50"
                >
                  {showAbort ? "Cancel" : "Abort"}
                </button>
              )}
              {isAuthor && transitions.map((t) => (
                <button
                  key={t.target}
                  onClick={() => handleTransitionClick(t.target)}
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

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        {/* Abort confirmation */}
        {showAbort && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 space-y-3">
            <h2 className="text-sm font-medium text-red-900">
              Abort this change
            </h2>
            <textarea
              value={abortReason}
              onChange={(e) => setAbortReason(e.target.value)}
              rows={2}
              placeholder="Why is this change being aborted?"
              className="w-full px-3 py-2 border border-red-300 rounded-lg text-sm focus:outline-none focus:ring-1 focus:ring-red-500"
              autoFocus
            />
            <div className="flex gap-2">
              <button
                onClick={() => handleTransition("aborted", abortReason.trim() || undefined)}
                disabled={transitioning || !abortReason.trim()}
                className="px-4 py-1.5 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 disabled:opacity-50"
              >
                {transitioning ? "Aborting..." : "Confirm Abort"}
              </button>
              <button
                onClick={() => {
                  setShowAbort(false);
                  setAbortReason("");
                }}
                className="px-4 py-1.5 text-sm font-medium text-gray-600 hover:text-gray-800"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {/* Out-of-window warning */}
        {showWindowWarning && (
          <div className="bg-amber-50 border border-amber-300 rounded-lg p-4 space-y-3">
            <div className="flex items-start gap-3">
              <span className="text-amber-600 text-lg flex-shrink-0">⚠️</span>
              <div>
                <h2 className="text-sm font-medium text-amber-900">
                  Executing outside maintenance window
                </h2>
                <p className="mt-1 text-sm text-amber-800">
                  {windowWarningMessage}
                </p>
              </div>
            </div>
            <div>
              <label className="block text-xs font-medium text-amber-900 mb-1">
                Why are you proceeding outside the window? *
              </label>
              <textarea
                value={windowOverrideReason}
                onChange={(e) => setWindowOverrideReason(e.target.value)}
                rows={2}
                placeholder="e.g., Customer approved early start due to severity of issue"
                className="w-full px-3 py-2 border border-amber-300 rounded-lg text-sm focus:outline-none focus:ring-1 focus:ring-amber-500"
                autoFocus
              />
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => {
                  setShowWindowWarning(false);
                  handleTransition("executing", windowOverrideReason.trim());
                  setWindowOverrideReason("");
                }}
                disabled={transitioning || !windowOverrideReason.trim()}
                className="px-4 py-1.5 text-sm font-medium text-white bg-orange-600 rounded-lg hover:bg-orange-700 disabled:opacity-50"
              >
                {transitioning ? "Starting..." : "Proceed Anyway"}
              </button>
              <button
                onClick={() => {
                  setShowWindowWarning(false);
                  setWindowOverrideReason("");
                }}
                className="px-4 py-1.5 text-sm font-medium text-gray-600 hover:text-gray-800"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 text-sm">
            {error}
            <button
              onClick={() => setError(null)}
              className="ml-2 underline"
            >
              dismiss
            </button>
          </div>
        )}

        {/* Abort reason banner */}
        {change.status === "aborted" && change.abort_reason && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4">
            <h3 className="text-sm font-medium text-red-900">Abort reason</h3>
            <p className="mt-1 text-sm text-red-700 whitespace-pre-wrap">{change.abort_reason}</p>
          </div>
        )}

        {/* Duplicate form */}
        {showDuplicate && (
          <div className="bg-white rounded-lg border border-gray-200 p-6 space-y-3">
            <h2 className="text-sm font-medium text-gray-900">
              Duplicate this change
            </h2>
            <p className="text-xs text-gray-500">
              Creates a copy with the same change profile, checklist, and
              defence tags. Status resets to Draft.
            </p>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  Title
                </label>
                <input
                  type="text"
                  value={dupTitle}
                  onChange={(e) => setDupTitle(e.target.value)}
                  className="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-1 focus:ring-gray-900"
                />
              </div>
              {/* Author comes from auth */}
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleDuplicate}
                disabled={duplicating}
                className="px-4 py-1.5 text-sm font-medium text-white bg-gray-900 rounded-lg hover:bg-gray-800 disabled:opacity-50"
              >
                {duplicating ? "Duplicating..." : "Create Duplicate"}
              </button>
              <button
                onClick={() => setShowDuplicate(false)}
                className="px-4 py-1.5 text-sm font-medium text-gray-600 hover:text-gray-800"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {/* Inline editing for draft details */}
        {editingDetails && (
          <div className="bg-white rounded-lg border border-blue-200 p-6 space-y-4">
            <h2 className="text-sm font-medium text-gray-900">Edit Change Details</h2>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Title</label>
              <input
                type="text"
                value={editTitle}
                onChange={(e) => setEditTitle(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-gray-900 focus:border-transparent"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Description</label>
              <textarea
                value={editDescription}
                onChange={(e) => setEditDescription(e.target.value)}
                rows={2}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-gray-900 focus:border-transparent"
              />
            </div>
            <div className="grid grid-cols-1 gap-4">
              <SearchableSelect
                label="Customer"
                required
                options={customers.map((c) => ({ id: c.id, label: c.name }))}
                value={editCustomerId}
                onChange={(id) => { setEditCustomerId(id); setEditServiceId(""); }}
                placeholder="Select customer..."
                onCreateNew={handleCreateCustomer}
                itemNoun="customer"
              />
              {editCustomerId && (
                <SearchableSelect
                  label="Service"
                  required
                  options={(customers.find((c) => c.id === editCustomerId)?.services || []).map((s) => ({ id: s.id, label: s.name }))}
                  value={editServiceId}
                  onChange={setEditServiceId}
                  placeholder="Select service..."
                  onCreateNew={handleCreateService}
                  itemNoun="service"
                />
              )}
              <SearchableSelect
                label="Environment"
                required
                options={environments.map((e) => ({ id: e.id, label: e.name, sublabel: e.platform || undefined }))}
                value={editEnvironmentId}
                onChange={setEditEnvironmentId}
                placeholder="Select environment..."
                onCreateNew={handleCreateEnvironment}
                itemNoun="environment"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-2">Maintenance Window</label>
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Start</label>
                  <input
                    type="datetime-local"
                    value={editWindowStart}
                    onChange={(e) => setEditWindowStart(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-gray-900 focus:border-transparent"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">End</label>
                  <input
                    type="datetime-local"
                    value={editWindowEnd}
                    onChange={(e) => setEditWindowEnd(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-gray-900 focus:border-transparent"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Timezone</label>
                  <select
                    value={editWindowTz}
                    onChange={(e) => setEditWindowTz(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-gray-900 focus:border-transparent"
                  >
                    {["UTC", "Europe/London", "Europe/Paris", "Europe/Berlin", "Europe/Copenhagen", "US/Eastern", "US/Central", "US/Mountain", "US/Pacific", "Asia/Tokyo", "Asia/Singapore", "Australia/Sydney"].map((tz) => (
                      <option key={tz} value={tz}>{tz}</option>
                    ))}
                  </select>
                </div>
              </div>
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleSaveDetails}
                disabled={savingDetails || !editTitle.trim()}
                className="px-4 py-1.5 text-sm font-medium text-white bg-gray-900 rounded-lg hover:bg-gray-800 disabled:opacity-50"
              >
                {savingDetails ? "Saving..." : "Save"}
              </button>
              <button
                onClick={() => setEditingDetails(false)}
                className="px-4 py-1.5 text-sm font-medium text-gray-600 hover:text-gray-800"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {!editingDetails && change.description && (
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <p className="text-sm text-gray-700">{change.description}</p>
          </div>
        )}

        {/* Defence tags */}
        {change.defence_tags && change.defence_tags.length > 0 && (
          <div className="flex gap-2">
            {change.defence_tags.map((tag) => (
              <span
                key={tag}
                className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium bg-amber-50 text-amber-800 border border-amber-200"
              >
                {tag}
              </span>
            ))}
          </div>
        )}

        {/* Maintenance window banner — visible during execution */}
        {isExecuting && change.maintenance_window_start && change.maintenance_window_end && (
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 flex items-center gap-3">
            <span className="text-blue-600 text-lg">🕐</span>
            <div>
              <span className="text-sm font-medium text-blue-900">
                Window:{" "}
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
          </div>
        )}

        {/* Execution progress bar */}
        {isExecuting && execStatus && (
          <div className="bg-white rounded-lg border border-orange-200 p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-gray-900">
                Execution Progress
              </span>
              <span className="text-sm text-gray-500">
                {execStatus.completed_items} / {execStatus.total_items} items
              </span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className="bg-orange-500 h-2 rounded-full transition-all"
                style={{
                  width: `${execStatus.total_items > 0 ? (execStatus.completed_items / execStatus.total_items) * 100 : 0}%`,
                }}
              />
            </div>
            {execStatus.current_phase && (
              <p className="text-xs text-gray-500 mt-1">
                Current phase:{" "}
                {PHASE_LABELS[execStatus.current_phase] ||
                  execStatus.current_phase}
              </p>
            )}
          </div>
        )}

        {/* Pre-flight answers — collapsible, grouped by section, editable in draft */}
        {(hasPreflightAnswers || (isDraft && preflightSections.length > 0)) && (
          <div className="bg-white rounded-lg border border-gray-200">
            <div className="flex items-center justify-between p-6">
              <button
                onClick={() => setPreflightExpanded(!preflightExpanded)}
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
                  onClick={startEditingPreflight}
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
                              updateEditedAnswer(q.key, e.target.value)
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
                    onClick={handleSavePreflight}
                    disabled={savingPreflight}
                    className="px-4 py-1.5 text-sm font-medium text-white bg-gray-900 rounded-lg hover:bg-gray-800 disabled:opacity-50"
                  >
                    {savingPreflight ? "Saving..." : "Save Answers"}
                  </button>
                  <button
                    onClick={() => setPreflightEditing(false)}
                    className="px-4 py-1.5 text-sm font-medium text-gray-600 hover:text-gray-800"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Three-phase Checklist */}
        <div className="bg-white rounded-lg border border-gray-200 p-6 space-y-6">
          <h2 className="text-lg font-medium text-gray-900">Checklist</h2>

          {PHASE_ORDER.map((phase) => {
            const items = checklistByPhase[phase] || [];
            if (items.length === 0 && !isDraft) return null;
            const isAddingHere = addingToPhase === phase;

            return (
              <div key={phase}>
                <h3 className="text-sm font-medium text-gray-700 mb-2 uppercase tracking-wider">
                  {PHASE_LABELS[phase]}
                  {execStatus?.phases?.[phase] && (
                    <span className="ml-2 text-xs font-normal normal-case text-gray-400">
                      ({execStatus.phases[phase].completed}/
                      {execStatus.phases[phase].total})
                    </span>
                  )}
                </h3>
                {items.length === 0 && !isAddingHere ? (
                  <p className="text-xs text-gray-400 italic">No items yet</p>
                ) : (
                  <div className="space-y-2">
                    {items.map((item) => (
                      <ChecklistItemRow
                        key={item.id}
                        item={item}
                        isNext={execStatus?.next_item_id === item.id}
                        isExecuting={isExecuting}
                        isDraft={canEdit}
                        changeId={id}
                        currentUserName={currentUserName}
                        onCompleted={loadAll}
                      />
                    ))}
                  </div>
                )}

                {/* Per-phase add form — appears below the last item */}
                {canEdit && isAddingHere && (
                  <div
                    className="mt-2 p-3 bg-gray-50 rounded-lg border border-gray-200 space-y-2"
                    ref={(el) => {
                      if (el) el.scrollIntoView({ behavior: "smooth", block: "nearest" });
                    }}
                  >
                    <input
                      type="text"
                      value={newItemDesc}
                      onChange={(e) => setNewItemDesc(e.target.value)}
                      placeholder="Description — what to do..."
                      className="w-full px-2 py-1.5 border border-gray-300 rounded text-xs focus:outline-none focus:ring-1 focus:ring-gray-900"
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && !e.shiftKey) handleAddChecklistItem(phase);
                        if (e.key === "Escape") {
                          setAddingToPhase(null);
                          setNewItemDesc("");
                          setNewItemCommand("");
                          setNewItemExpectedOutcome("");
                          setNewItemRollbackAction("");
                          setNewItemHoldPoint(false);
                        }
                      }}
                      autoFocus
                    />
                    <input
                      type="text"
                      value={newItemCommand}
                      onChange={(e) => setNewItemCommand(e.target.value)}
                      placeholder="Command (optional) — e.g. kubectl get pods -n prod"
                      className="w-full px-2 py-1.5 border border-gray-300 rounded text-xs font-mono focus:outline-none focus:ring-1 focus:ring-gray-900"
                      style={{
                        fontVariantLigatures: "none",
                        fontFeatureSettings: '"liga" 0, "clig" 0',
                        textRendering: "optimizeSpeed",
                      }}
                    />
                    <input
                      type="text"
                      value={newItemExpectedOutcome}
                      onChange={(e) => setNewItemExpectedOutcome(e.target.value)}
                      placeholder="Expected outcome (optional) — what should you see?"
                      className="w-full px-2 py-1.5 border border-gray-300 rounded text-xs focus:outline-none focus:ring-1 focus:ring-gray-900"
                    />
                    <input
                      type="text"
                      value={newItemRollbackAction}
                      onChange={(e) => setNewItemRollbackAction(e.target.value)}
                      placeholder="Rollback action (optional) — what if this step fails?"
                      className="w-full px-2 py-1.5 border border-gray-300 rounded text-xs focus:outline-none focus:ring-1 focus:ring-gray-900"
                    />
                    <div className="flex items-center gap-3">
                      <button
                        onClick={() => handleAddChecklistItem(phase)}
                        disabled={!newItemDesc.trim()}
                        className="px-3 py-1.5 text-xs font-medium text-white bg-gray-900 rounded hover:bg-gray-800 disabled:opacity-50"
                      >
                        Add
                      </button>
                      <label className="flex items-center gap-1.5 text-xs text-gray-600 cursor-pointer select-none">
                        <input
                          type="checkbox"
                          checked={newItemHoldPoint}
                          onChange={(e) => setNewItemHoldPoint(e.target.checked)}
                          className="rounded border-gray-300 text-amber-600 focus:ring-amber-500"
                        />
                        🔒 Hold point
                      </label>
                      <button
                        onClick={() => {
                          setAddingToPhase(null);
                          setNewItemDesc("");
                          setNewItemCommand("");
                          setNewItemExpectedOutcome("");
                          setNewItemRollbackAction("");
                          setNewItemHoldPoint(false);
                        }}
                        className="ml-auto px-2 py-1.5 text-xs text-gray-500 hover:text-gray-700"
                      >
                        Done
                      </button>
                    </div>
                  </div>
                )}

                {/* Add button at the bottom of each phase */}
                {canEdit && !isAddingHere && (
                  <button
                    onClick={() => {
                      setAddingToPhase(phase);
                      setNewItemDesc("");
                      setNewItemCommand("");
                      setNewItemExpectedOutcome("");
                      setNewItemRollbackAction("");
                      setNewItemHoldPoint(false);
                    }}
                    className="mt-2 px-3 py-1.5 text-xs font-medium text-gray-500 hover:text-gray-700 hover:bg-gray-50 rounded-lg transition-colors"
                  >
                    + Add item
                  </button>
                )}
              </div>
            );
          })}
        </div>

        {/* Reviews */}
        <div className="bg-white rounded-lg border border-gray-200 p-6 space-y-4">
          <h2 className="text-lg font-medium text-gray-900">Reviews</h2>

          {reviews.length === 0 ? (
            <p className="text-sm text-gray-500">
              No reviewers assigned yet.
            </p>
          ) : (
            <div className="space-y-2">
              {reviews.map((review) => (
                <ReviewCard
                  key={review.id}
                  review={review}
                  canDecide={
                    review.decision === "pending" &&
                    change.status === "in_review" &&
                    currentUserName === review.reviewer_name
                  }
                  onDecision={(decision, comment) =>
                    handleReviewDecision(review.id, decision, comment)
                  }
                />
              ))}
            </div>
          )}

          {/* Assign reviewer — only the author can assign */}
          {!isTerminal && isAuthor && (
            <>
              {!addingReviewer ? (
                <button
                  onClick={openReviewerInput}
                  className="px-3 py-1.5 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
                >
                  + Assign reviewer
                </button>
              ) : (
                <div className="flex items-center gap-2">
                  <select
                    defaultValue=""
                    onChange={(e) => {
                      if (e.target.value) handleAddReviewer(e.target.value);
                    }}
                    className="flex-1 px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-1 focus:ring-gray-900"
                    autoFocus
                  >
                    <option value="" disabled>Select reviewer...</option>
                    {knownPeople
                      .filter((p) => {
                        if (reviews.some((r) => r.reviewer_name === p)) return false;
                        if (p === change.author_name) return false;
                        return true;
                      })
                      .map((person) => (
                        <option key={person} value={person}>{person}</option>
                      ))}
                  </select>
                  <button
                    onClick={() => setAddingReviewer(false)}
                    className="px-2 py-1.5 text-sm text-gray-500 hover:text-gray-700"
                  >
                    Cancel
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </main>
    </div>
  );
}
