"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import SearchableSelect from "@/components/SearchableSelect";
import ChangeHeader from "@/components/changes/ChangeHeader";
import PreflightProfile from "@/components/changes/PreflightProfile";
import ChecklistSection from "@/components/changes/ChecklistSection";
import ReviewsSection from "@/components/changes/ReviewsSection";
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
import {
  PHASE_LABELS,
  TIMEZONES,
} from "@/lib/constants";

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
  const [preflightExpanded, setPreflightExpanded] = useState(false);
  const [preflightEditing, setPreflightEditing] = useState(false);
  const [editedAnswers, setEditedAnswers] = useState<Record<string, string>>({});
  const [savingPreflight, setSavingPreflight] = useState(false);
  const [showDuplicate, setShowDuplicate] = useState(false);
  const [dupTitle, setDupTitle] = useState("");
  const [duplicating, setDuplicating] = useState(false);
  const [showWindowWarning, setShowWindowWarning] = useState(false);
  const [windowWarningMessage, setWindowWarningMessage] = useState("");
  const [windowOverrideReason, setWindowOverrideReason] = useState("");

  // Inline editing for draft details
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

  // Reviewer state
  const [addingReviewer, setAddingReviewer] = useState(false);
  const [knownPeople, setKnownPeople] = useState<string[]>([]);

  // Template state
  const [showSaveTemplate, setShowSaveTemplate] = useState(false);
  const [templateTitle, setTemplateTitle] = useState("");
  const [savingTemplate, setSavingTemplate] = useState(false);

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

  // --- Handlers ---

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
      await loadAll();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed");
    }
  }

  function toLocalInput(isoStr: string | null): string {
    if (!isoStr) return "";
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

  async function handleSaveAsTemplate() {
    setSavingTemplate(true);
    setError(null);
    try {
      await api.saveAsTemplate(id, {
        title: templateTitle.trim() || undefined,
      });
      setShowSaveTemplate(false);
      setTemplateTitle("");
      setError(null);
      alert("Template saved to the library.");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to save template");
    }
    setSavingTemplate(false);
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

  // --- Loading and error states ---

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

  // --- Derived state ---

  const isExecuting = change.status === "executing";
  const isDraft = change.status === "draft";
  const isTerminal = change.status === "done" || change.status === "aborted";
  const isAuthor = currentUserName === change.author_name;
  const canEdit = isDraft && isAuthor;

  // Determine available transitions
  const transitions: { label: string; target: ChangeStatus; style: string; disabled?: boolean; hint?: string }[] = [];
  if (change.status === "draft") {
    transitions.push({ label: "Submit for Review", target: "in_review", style: "bg-gray-900 text-white hover:bg-gray-800" });
  } else if (change.status === "in_review") {
    transitions.push({ label: "Approve", target: "approved", style: "bg-blue-600 text-white hover:bg-blue-700" });
    transitions.push({ label: "Back to Draft", target: "draft", style: "bg-white text-gray-700 border border-gray-300 hover:bg-gray-50" });
  } else if (change.status === "approved") {
    transitions.push({ label: "Start Execution", target: "executing", style: "bg-orange-600 text-white hover:bg-orange-700" });
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

  // --- Render ---

  return (
    <div className="min-h-screen bg-gray-50">
      <ChangeHeader
        change={change}
        canEdit={canEdit}
        isTerminal={isTerminal}
        isAuthor={isAuthor}
        editingDetails={editingDetails}
        transitions={transitions}
        transitioning={transitioning}
        onStartEditingDetails={startEditingDetails}
        onExport={handleExport}
        onDuplicate={() => { setDupTitle(`${change.title} (copy)`); setShowDuplicate(true); }}
        onSaveAsTemplate={() => { setTemplateTitle(change.title); setShowSaveTemplate(true); }}
        onAbortToggle={() => setShowAbort(!showAbort)}
        showAbort={showAbort}
        onTransitionClick={handleTransitionClick}
      />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        {/* Abort confirmation */}
        {showAbort && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 space-y-3">
            <h2 className="text-sm font-medium text-red-900">Abort this change</h2>
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
                onClick={() => { setShowAbort(false); setAbortReason(""); }}
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
                <h2 className="text-sm font-medium text-amber-900">Executing outside maintenance window</h2>
                <p className="mt-1 text-sm text-amber-800">{windowWarningMessage}</p>
              </div>
            </div>
            <div>
              <label className="block text-xs font-medium text-amber-900 mb-1">Why are you proceeding outside the window? *</label>
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
                onClick={() => { setShowWindowWarning(false); handleTransition("executing", windowOverrideReason.trim()); setWindowOverrideReason(""); }}
                disabled={transitioning || !windowOverrideReason.trim()}
                className="px-4 py-1.5 text-sm font-medium text-white bg-orange-600 rounded-lg hover:bg-orange-700 disabled:opacity-50"
              >
                {transitioning ? "Starting..." : "Proceed Anyway"}
              </button>
              <button
                onClick={() => { setShowWindowWarning(false); setWindowOverrideReason(""); }}
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
            <button onClick={() => setError(null)} className="ml-2 underline">dismiss</button>
          </div>
        )}

        {/* Status banners */}
        {change.status === "aborted" && change.abort_reason && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4">
            <h3 className="text-sm font-medium text-red-900">Abort reason</h3>
            <p className="mt-1 text-sm text-red-700 whitespace-pre-wrap">{change.abort_reason}</p>
          </div>
        )}
        {change.window_override_reason && (
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
            <h3 className="text-sm font-medium text-amber-900">⚠️ Executed outside maintenance window</h3>
            <p className="mt-1 text-sm text-amber-800 whitespace-pre-wrap">{change.window_override_reason}</p>
          </div>
        )}

        {/* Duplicate form */}
        {showDuplicate && (
          <div className="bg-white rounded-lg border border-gray-200 p-6 space-y-3">
            <h2 className="text-sm font-medium text-gray-900">Duplicate this change</h2>
            <p className="text-xs text-gray-500">Creates a copy with the same change profile, checklist, and defence tags. Status resets to Draft.</p>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Title</label>
                <input type="text" value={dupTitle} onChange={(e) => setDupTitle(e.target.value)} className="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-1 focus:ring-gray-900" />
              </div>
            </div>
            <div className="flex gap-2">
              <button onClick={handleDuplicate} disabled={duplicating} className="px-4 py-1.5 text-sm font-medium text-white bg-gray-900 rounded-lg hover:bg-gray-800 disabled:opacity-50">
                {duplicating ? "Duplicating..." : "Create Duplicate"}
              </button>
              <button onClick={() => setShowDuplicate(false)} className="px-4 py-1.5 text-sm font-medium text-gray-600 hover:text-gray-800">Cancel</button>
            </div>
          </div>
        )}

        {/* Save as template form */}
        {showSaveTemplate && (
          <div className="bg-white rounded-lg border border-indigo-200 p-6 space-y-3">
            <h2 className="text-sm font-medium text-gray-900">Save as Template</h2>
            <p className="text-xs text-gray-500">Saves the checklist, defence tags, and change profile answers to the template library. Customer, service, environment, and maintenance window are not included.</p>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Template name</label>
              <input type="text" value={templateTitle} onChange={(e) => setTemplateTitle(e.target.value)} placeholder={`${change.title} (template)`} className="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-1 focus:ring-indigo-500" autoFocus />
            </div>
            <div className="flex gap-2">
              <button onClick={handleSaveAsTemplate} disabled={savingTemplate} className="px-4 py-1.5 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 disabled:opacity-50">
                {savingTemplate ? "Saving..." : "Save Template"}
              </button>
              <button onClick={() => setShowSaveTemplate(false)} className="px-4 py-1.5 text-sm font-medium text-gray-600 hover:text-gray-800">Cancel</button>
            </div>
          </div>
        )}

        {/* Edit change details form */}
        {editingDetails && (
          <div className="bg-white rounded-lg border border-blue-200 p-6 space-y-4">
            <h2 className="text-sm font-medium text-gray-900">Edit Change Details</h2>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Title</label>
              <input type="text" value={editTitle} onChange={(e) => setEditTitle(e.target.value)} className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-gray-900 focus:border-transparent" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Description</label>
              <textarea value={editDescription} onChange={(e) => setEditDescription(e.target.value)} rows={2} className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-gray-900 focus:border-transparent" />
            </div>
            <div className="grid grid-cols-1 gap-4">
              <SearchableSelect label="Customer" required options={customers.map((c) => ({ id: c.id, label: c.name }))} value={editCustomerId} onChange={(id) => { setEditCustomerId(id); setEditServiceId(""); }} placeholder="Select customer..." onCreateNew={handleCreateCustomer} itemNoun="customer" />
              {editCustomerId && (
                <SearchableSelect label="Service" required options={(customers.find((c) => c.id === editCustomerId)?.services || []).map((s) => ({ id: s.id, label: s.name }))} value={editServiceId} onChange={setEditServiceId} placeholder="Select service..." onCreateNew={handleCreateService} itemNoun="service" />
              )}
              <SearchableSelect label="Environment" required options={environments.map((e) => ({ id: e.id, label: e.name, sublabel: e.platform || undefined }))} value={editEnvironmentId} onChange={setEditEnvironmentId} placeholder="Select environment..." onCreateNew={handleCreateEnvironment} itemNoun="environment" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-2">Maintenance Window</label>
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Start</label>
                  <input type="datetime-local" value={editWindowStart} onChange={(e) => setEditWindowStart(e.target.value)} className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-gray-900 focus:border-transparent" />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">End</label>
                  <input type="datetime-local" value={editWindowEnd} onChange={(e) => setEditWindowEnd(e.target.value)} className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-gray-900 focus:border-transparent" />
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">Timezone</label>
                  <select value={editWindowTz} onChange={(e) => setEditWindowTz(e.target.value)} className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-gray-900 focus:border-transparent">
                    {TIMEZONES.map((tz) => (<option key={tz} value={tz}>{tz}</option>))}
                  </select>
                </div>
              </div>
            </div>
            <div className="flex gap-2">
              <button onClick={handleSaveDetails} disabled={savingDetails || !editTitle.trim()} className="px-4 py-1.5 text-sm font-medium text-white bg-gray-900 rounded-lg hover:bg-gray-800 disabled:opacity-50">
                {savingDetails ? "Saving..." : "Save"}
              </button>
              <button onClick={() => setEditingDetails(false)} className="px-4 py-1.5 text-sm font-medium text-gray-600 hover:text-gray-800">Cancel</button>
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
              <span key={tag} className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium bg-amber-50 text-amber-800 border border-amber-200">{tag}</span>
            ))}
          </div>
        )}

        {/* Maintenance window banner — visible during execution */}
        {isExecuting && change.maintenance_window_start && change.maintenance_window_end && (
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 flex items-center gap-3">
            <span className="text-blue-600 text-lg">🕐</span>
            <span className="text-sm font-medium text-blue-900">
              Window:{" "}
              {new Date(change.maintenance_window_start).toLocaleString("en-GB", { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: change.maintenance_window_tz || "UTC" })}
              {" – "}
              {new Date(change.maintenance_window_end).toLocaleString("en-GB", { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: change.maintenance_window_tz || "UTC" })}
              {" "}{change.maintenance_window_tz || "UTC"}
            </span>
          </div>
        )}

        {/* Execution progress bar */}
        {isExecuting && execStatus && (
          <div className="bg-white rounded-lg border border-orange-200 p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-gray-900">Execution Progress</span>
              <span className="text-sm text-gray-500">{execStatus.completed_items} / {execStatus.total_items} items</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div className="bg-orange-500 h-2 rounded-full transition-all" style={{ width: `${execStatus.total_items > 0 ? (execStatus.completed_items / execStatus.total_items) * 100 : 0}%` }} />
            </div>
            {execStatus.current_phase && (
              <p className="text-xs text-gray-500 mt-1">Current phase: {PHASE_LABELS[execStatus.current_phase] || execStatus.current_phase}</p>
            )}
          </div>
        )}

        {/* Change Profile */}
        <PreflightProfile
          change={change}
          preflightSections={preflightSections}
          preflightLabelMap={preflightLabelMap}
          canEdit={canEdit}
          preflightExpanded={preflightExpanded}
          preflightEditing={preflightEditing}
          editedAnswers={editedAnswers}
          savingPreflight={savingPreflight}
          onToggleExpanded={() => setPreflightExpanded(!preflightExpanded)}
          onStartEditing={startEditingPreflight}
          onCancelEditing={() => setPreflightEditing(false)}
          onUpdateAnswer={updateEditedAnswer}
          onSave={handleSavePreflight}
        />

        {/* Checklist */}
        <ChecklistSection
          checklist={checklist}
          execStatus={execStatus}
          isExecuting={isExecuting}
          canEdit={canEdit}
          changeId={id}
          currentUserName={currentUserName}
          addingToPhase={addingToPhase}
          newItemDesc={newItemDesc}
          newItemCommand={newItemCommand}
          newItemExpectedOutcome={newItemExpectedOutcome}
          newItemRollbackAction={newItemRollbackAction}
          newItemHoldPoint={newItemHoldPoint}
          onSetAddingToPhase={setAddingToPhase}
          onSetNewItemDesc={setNewItemDesc}
          onSetNewItemCommand={setNewItemCommand}
          onSetNewItemExpectedOutcome={setNewItemExpectedOutcome}
          onSetNewItemRollbackAction={setNewItemRollbackAction}
          onSetNewItemHoldPoint={setNewItemHoldPoint}
          onAddItem={handleAddChecklistItem}
          onReload={loadAll}
        />

        {/* Reviews */}
        <ReviewsSection
          change={change}
          reviews={reviews}
          currentUserName={currentUserName}
          isAuthor={isAuthor}
          addingReviewer={addingReviewer}
          knownPeople={knownPeople}
          onOpenReviewerInput={openReviewerInput}
          onAddReviewer={handleAddReviewer}
          onCancelAddReviewer={() => setAddingReviewer(false)}
          onReviewDecision={handleReviewDecision}
        />
      </main>
    </div>
  );
}
