"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  api,
  Change,
  ChangeStatus,
  ChecklistItem,
  Review,
  ExecutionStatus,
  PreflightSection,
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

// --- Checklist Item Component ---

function ChecklistItemRow({
  item,
  isNext,
  isExecuting,
  changeId,
  onCompleted,
}: {
  item: ChecklistItem;
  isNext: boolean;
  isExecuting: boolean;
  changeId: string;
  onCompleted: () => void;
}) {
  const [showComplete, setShowComplete] = useState(false);
  const [showVerify, setShowVerify] = useState(false);
  const [observedResult, setObservedResult] = useState("");
  const [completionStatus, setCompletionStatus] = useState("completed");
  const [completedBy, setCompletedBy] = useState("");
  const [verifierName, setVerifierName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const completion = item.completion;
  const isCompleted = !!completion;

  async function handleComplete() {
    setSubmitting(true);
    setError(null);
    try {
      await api.completeItem(changeId, item.id, {
        observed_result: observedResult,
        status: completionStatus,
        completed_by: completedBy,
      });
      setShowComplete(false);
      onCompleted();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed");
    }
    setSubmitting(false);
  }

  async function handleVerifyHoldPoint() {
    if (!verifierName.trim()) return;
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
          <p className="text-sm text-gray-900">{item.description}</p>
          {item.command && (
            <pre className="mt-1 bg-gray-50 rounded p-2 text-xs font-mono text-gray-700 overflow-x-auto">
              {item.command}
            </pre>
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
              🔒 Hold Point
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
                    ? "✅ Completed"
                    : completion.status === "flagged"
                      ? "⚠️ Flagged"
                      : "⏭️ Skipped"}
                </span>
                <span className="text-gray-400">
                  by {completion.completed_by}
                </span>
                <span className="text-gray-400">
                  {formatDate(completion.completed_at)}
                </span>
              </div>
              <pre className="mt-1 bg-gray-50 rounded p-2 font-mono text-gray-700 whitespace-pre-wrap overflow-x-auto">
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
                <button
                  onClick={() => setShowVerify(true)}
                  className="mt-2 px-3 py-1.5 text-xs font-medium text-amber-700 bg-amber-50 border border-amber-200 rounded-lg hover:bg-amber-100"
                >
                  Verify Hold Point
                </button>
              ) : (
                <div className="mt-2 flex items-center gap-2">
                  <input
                    type="text"
                    value={verifierName}
                    onChange={(e) => setVerifierName(e.target.value)}
                    placeholder="Verifier name..."
                    className="px-2 py-1.5 border border-amber-300 rounded text-xs focus:outline-none focus:ring-1 focus:ring-amber-500"
                    onKeyDown={(e) => {
                      if (e.key === "Enter") handleVerifyHoldPoint();
                    }}
                    autoFocus
                  />
                  <button
                    onClick={handleVerifyHoldPoint}
                    disabled={!verifierName.trim() || submitting}
                    className="px-3 py-1.5 text-xs font-medium text-white bg-amber-600 rounded hover:bg-amber-700 disabled:opacity-50"
                  >
                    {submitting ? "..." : "Verify"}
                  </button>
                  <button
                    onClick={() => setShowVerify(false)}
                    className="px-2 py-1.5 text-xs text-gray-500 hover:text-gray-700"
                  >
                    Cancel
                  </button>
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
                    <div>
                      <label className="block text-xs font-medium text-gray-700 mb-1">
                        Your name *
                      </label>
                      <input
                        type="text"
                        value={completedBy}
                        onChange={(e) => setCompletedBy(e.target.value)}
                        placeholder="Name"
                        className="w-full px-2 py-1.5 border border-gray-300 rounded text-xs"
                      />
                    </div>
                  </div>
                  {error && <p className="text-xs text-red-600">{error}</p>}
                  <div className="flex gap-2">
                    <button
                      onClick={handleComplete}
                      disabled={submitting || !observedResult || !completedBy}
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
  const [newReviewer, setNewReviewer] = useState("");
  const [preflightExpanded, setPreflightExpanded] = useState(false);
  const [preflightEditing, setPreflightEditing] = useState(false);
  const [editedAnswers, setEditedAnswers] = useState<Record<string, string>>({});
  const [savingPreflight, setSavingPreflight] = useState(false);
  const [showDuplicate, setShowDuplicate] = useState(false);
  const [dupAuthor, setDupAuthor] = useState("");
  const [dupTitle, setDupTitle] = useState("");
  const [duplicating, setDuplicating] = useState(false);

  // New checklist item form — per-phase
  const [addingToPhase, setAddingToPhase] = useState<string | null>(null);
  const [newItemDesc, setNewItemDesc] = useState("");
  const [newItemCommand, setNewItemCommand] = useState("");

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

  async function handleTransition(target: ChangeStatus) {
    if (!change) return;
    setTransitioning(true);
    setError(null);
    try {
      await api.transitionChange(change.id, target, change.author_name);
      await loadAll();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Transition failed");
    }
    setTransitioning(false);
  }

  async function handleAddReviewer() {
    if (!newReviewer.trim()) return;
    try {
      await api.assignReviewer(id, newReviewer.trim());
      setNewReviewer("");
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
      });
      setNewItemDesc("");
      setNewItemCommand("");
      // Keep the form open in the same phase so you can add multiple items
      await loadAll();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed");
    }
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
      setError(err instanceof Error ? err.message : "Failed to save pre-flight answers");
    }
    setSavingPreflight(false);
  }

  async function handleDuplicate() {
    if (!dupAuthor.trim()) return;
    setDuplicating(true);
    setError(null);
    try {
      const clone = await api.duplicateChange(id, {
        author_name: dupAuthor.trim(),
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

  // Group checklist by phase
  const checklistByPhase: Record<string, ChecklistItem[]> = {};
  for (const item of checklist) {
    if (!checklistByPhase[item.phase]) checklistByPhase[item.phase] = [];
    checklistByPhase[item.phase].push(item);
  }

  // Determine available transitions
  const transitions: { label: string; target: ChangeStatus; style: string }[] =
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
    transitions.push({
      label: "Mark Done",
      target: "done",
      style: "bg-green-600 text-white hover:bg-green-700",
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
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
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
            </div>
            <div className="flex gap-2">
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
              {!isTerminal && (
                <button
                  onClick={() => handleTransition("aborted")}
                  disabled={transitioning}
                  className="px-3 py-1.5 text-xs font-medium text-red-600 bg-white border border-red-200 rounded-lg hover:bg-red-50 disabled:opacity-50"
                >
                  Abort
                </button>
              )}
              {transitions.map((t) => (
                <button
                  key={t.target}
                  onClick={() => handleTransition(t.target)}
                  disabled={transitioning}
                  className={`px-4 py-1.5 text-sm font-medium rounded-lg disabled:opacity-50 ${t.style}`}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
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

        {/* Duplicate form */}
        {showDuplicate && (
          <div className="bg-white rounded-lg border border-gray-200 p-6 space-y-3">
            <h2 className="text-sm font-medium text-gray-900">
              Duplicate this change
            </h2>
            <p className="text-xs text-gray-500">
              Creates a copy with the same pre-flight answers, checklist, and
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
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  Author name *
                </label>
                <input
                  type="text"
                  value={dupAuthor}
                  onChange={(e) => setDupAuthor(e.target.value)}
                  placeholder="Your name"
                  className="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-1 focus:ring-gray-900"
                  onKeyDown={(e) => {
                    if (e.key === "Enter") handleDuplicate();
                  }}
                  autoFocus
                />
              </div>
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleDuplicate}
                disabled={!dupAuthor.trim() || duplicating}
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

        {change.description && (
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
                    Pre-flight Answers
                  </h2>
                  <p className="text-sm text-gray-500 mt-0.5">
                    {answeredCount} questions answered
                  </p>
                </div>
                <span className="text-gray-400 text-lg">
                  {preflightExpanded ? "▾" : "▸"}
                </span>
              </button>
              {isDraft && !preflightEditing && (
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
                        changeId={id}
                        onCompleted={loadAll}
                      />
                    ))}
                  </div>
                )}

                {/* Per-phase add form — appears below the last item */}
                {isDraft && isAddingHere && (
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
                      onKeyDown={(e) => {
                        if (e.key === "Enter") handleAddChecklistItem(phase);
                        if (e.key === "Escape") {
                          setAddingToPhase(null);
                          setNewItemDesc("");
                          setNewItemCommand("");
                        }
                      }}
                    />
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleAddChecklistItem(phase)}
                        disabled={!newItemDesc.trim()}
                        className="px-3 py-1.5 text-xs font-medium text-white bg-gray-900 rounded hover:bg-gray-800 disabled:opacity-50"
                      >
                        Add
                      </button>
                      <button
                        onClick={() => {
                          setAddingToPhase(null);
                          setNewItemDesc("");
                          setNewItemCommand("");
                        }}
                        className="px-2 py-1.5 text-xs text-gray-500 hover:text-gray-700"
                      >
                        Done
                      </button>
                    </div>
                  </div>
                )}

                {/* Add button at the bottom of each phase */}
                {isDraft && !isAddingHere && (
                  <button
                    onClick={() => {
                      setAddingToPhase(phase);
                      setNewItemDesc("");
                      setNewItemCommand("");
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
                    change.status === "in_review"
                  }
                  onDecision={(decision, comment) =>
                    handleReviewDecision(review.id, decision, comment)
                  }
                />
              ))}
            </div>
          )}

          {/* Add reviewer */}
          {!isTerminal && (
            <div className="flex gap-2">
              <input
                type="text"
                value={newReviewer}
                onChange={(e) => setNewReviewer(e.target.value)}
                placeholder="Reviewer name..."
                className="flex-1 px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-1 focus:ring-gray-900"
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    handleAddReviewer();
                  }
                }}
              />
              <button
                onClick={handleAddReviewer}
                disabled={!newReviewer.trim()}
                className="px-3 py-1.5 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50"
              >
                Add Reviewer
              </button>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
