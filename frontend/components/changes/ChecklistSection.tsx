"use client";

import { useState } from "react";
import { api, ChecklistItem, ExecutionStatus } from "@/lib/api";
import { PHASE_LABELS, PHASE_ORDER } from "@/lib/constants";
import ChecklistItemRow from "@/components/ChecklistItemRow";

export default function ChecklistSection({
  checklist,
  execStatus,
  isExecuting,
  canEdit,
  changeId,
  currentUserName,
  addingToPhase,
  newItemDesc,
  newItemCommand,
  newItemExpectedOutcome,
  newItemRollbackAction,
  newItemHoldPoint,
  onSetAddingToPhase,
  onSetNewItemDesc,
  onSetNewItemCommand,
  onSetNewItemExpectedOutcome,
  onSetNewItemRollbackAction,
  onSetNewItemHoldPoint,
  onAddItem,
  onReload,
}: {
  checklist: ChecklistItem[];
  execStatus: ExecutionStatus | null;
  isExecuting: boolean;
  canEdit: boolean;
  changeId: string;
  currentUserName: string;
  addingToPhase: string | null;
  newItemDesc: string;
  newItemCommand: string;
  newItemExpectedOutcome: string;
  newItemRollbackAction: string;
  newItemHoldPoint: boolean;
  onSetAddingToPhase: (phase: string | null) => void;
  onSetNewItemDesc: (v: string) => void;
  onSetNewItemCommand: (v: string) => void;
  onSetNewItemExpectedOutcome: (v: string) => void;
  onSetNewItemRollbackAction: (v: string) => void;
  onSetNewItemHoldPoint: (v: boolean) => void;
  onAddItem: (phase: string) => void;
  onReload: () => void;
}) {
  // Execution step insertion state
  const [insertAfterItemId, setInsertAfterItemId] = useState<string | null>(null);
  const [execStepDesc, setExecStepDesc] = useState("");
  const [execStepCommand, setExecStepCommand] = useState("");
  const [execStepExpected, setExecStepExpected] = useState("");
  const [execStepRollback, setExecStepRollback] = useState("");
  const [execStepHold, setExecStepHold] = useState(false);
  const [execStepError, setExecStepError] = useState<string | null>(null);
  const [execStepSubmitting, setExecStepSubmitting] = useState(false);

  function resetExecStepForm() {
    setInsertAfterItemId(null);
    setExecStepDesc("");
    setExecStepCommand("");
    setExecStepExpected("");
    setExecStepRollback("");
    setExecStepHold(false);
    setExecStepError(null);
  }

  async function handleAddExecutionStep() {
    if (!insertAfterItemId || !execStepDesc.trim()) return;
    setExecStepSubmitting(true);
    setExecStepError(null);
    try {
      await api.addExecutionStep(changeId, {
        insert_after_item_id: insertAfterItemId,
        description: execStepDesc.trim(),
        command: execStepCommand.trim() || undefined,
        expected_outcome: execStepExpected.trim() || undefined,
        rollback_action: execStepRollback.trim() || undefined,
        is_hold_point: execStepHold,
      });
      resetExecStepForm();
      onReload();
    } catch (err: unknown) {
      setExecStepError(err instanceof Error ? err.message : "Failed to add step");
    }
    setExecStepSubmitting(false);
  }

  // Group checklist by phase
  const checklistByPhase: Record<string, ChecklistItem[]> = {};
  for (const item of checklist) {
    if (!checklistByPhase[item.phase]) checklistByPhase[item.phase] = [];
    checklistByPhase[item.phase].push(item);
  }

  function resetForm() {
    onSetAddingToPhase(null);
    onSetNewItemDesc("");
    onSetNewItemCommand("");
    onSetNewItemExpectedOutcome("");
    onSetNewItemRollbackAction("");
    onSetNewItemHoldPoint(false);
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-6 space-y-6">
      <h2 className="text-lg font-medium text-gray-900">Checklist</h2>

      {PHASE_ORDER.map((phase) => {
        const items = checklistByPhase[phase] || [];
        const isDraft = canEdit;
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
                  <div key={item.id}>
                    <ChecklistItemRow
                      item={item}
                      isNext={execStatus?.next_item_id === item.id}
                      isExecuting={isExecuting}
                      isDraft={canEdit}
                      changeId={changeId}
                      currentUserName={currentUserName}
                      onCompleted={onReload}
                      onAddStepAfter={isExecuting ? (id) => {
                        resetExecStepForm();
                        setInsertAfterItemId(id);
                      } : undefined}
                    />

                    {/* Inline form to add step after this completed item */}
                    {insertAfterItemId === item.id && (
                      <div
                        className="mt-2 ml-9 p-3 bg-purple-50/50 rounded-lg border border-purple-200 space-y-2"
                        ref={(el) => {
                          if (el) el.scrollIntoView({ behavior: "smooth", block: "nearest" });
                        }}
                      >
                        <p className="text-xs font-medium text-purple-700">Add step after &ldquo;{item.description}&rdquo;</p>
                        <input
                          type="text"
                          value={execStepDesc}
                          onChange={(e) => setExecStepDesc(e.target.value)}
                          placeholder="What needs to happen next?"
                          className="w-full px-2 py-1.5 border border-purple-300 rounded text-xs focus:outline-none focus:ring-1 focus:ring-purple-500"
                          onKeyDown={(e) => {
                            if (e.key === "Enter" && !e.shiftKey) handleAddExecutionStep();
                            if (e.key === "Escape") resetExecStepForm();
                          }}
                          autoFocus
                        />
                        <input
                          type="text"
                          value={execStepCommand}
                          onChange={(e) => setExecStepCommand(e.target.value)}
                          placeholder="Command (optional)"
                          className="w-full px-2 py-1.5 border border-purple-300 rounded text-xs font-mono focus:outline-none focus:ring-1 focus:ring-purple-500"
                          style={{
                            fontVariantLigatures: "none",
                            fontFeatureSettings: '"liga" 0, "clig" 0',
                            textRendering: "optimizeSpeed",
                          }}
                        />
                        <input
                          type="text"
                          value={execStepExpected}
                          onChange={(e) => setExecStepExpected(e.target.value)}
                          placeholder="Expected outcome (optional)"
                          className="w-full px-2 py-1.5 border border-purple-300 rounded text-xs focus:outline-none focus:ring-1 focus:ring-purple-500"
                        />
                        <input
                          type="text"
                          value={execStepRollback}
                          onChange={(e) => setExecStepRollback(e.target.value)}
                          placeholder="Rollback action (optional)"
                          className="w-full px-2 py-1.5 border border-purple-300 rounded text-xs focus:outline-none focus:ring-1 focus:ring-purple-500"
                        />
                        <div className="flex items-center gap-3">
                          <button
                            onClick={handleAddExecutionStep}
                            disabled={execStepSubmitting || !execStepDesc.trim()}
                            className="px-3 py-1.5 text-xs font-medium text-white bg-purple-600 rounded hover:bg-purple-700 disabled:opacity-50"
                          >
                            {execStepSubmitting ? "Adding..." : "Add step"}
                          </button>
                          <label className="flex items-center gap-1.5 text-xs text-gray-600 cursor-pointer select-none">
                            <input
                              type="checkbox"
                              checked={execStepHold}
                              onChange={(e) => setExecStepHold(e.target.checked)}
                              className="rounded border-gray-300 text-amber-600 focus:ring-amber-500"
                            />
                            🔒 Hold point
                          </label>
                          <button
                            onClick={resetExecStepForm}
                            className="ml-auto px-2 py-1.5 text-xs text-gray-500 hover:text-gray-700"
                          >
                            Cancel
                          </button>
                        </div>
                        {execStepError && <p className="text-xs text-red-600">{execStepError}</p>}
                      </div>
                    )}
                  </div>
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
                  onChange={(e) => onSetNewItemDesc(e.target.value)}
                  placeholder="Description — what to do..."
                  className="w-full px-2 py-1.5 border border-gray-300 rounded text-xs focus:outline-none focus:ring-1 focus:ring-gray-900"
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) onAddItem(phase);
                    if (e.key === "Escape") resetForm();
                  }}
                  autoFocus
                />
                <input
                  type="text"
                  value={newItemCommand}
                  onChange={(e) => onSetNewItemCommand(e.target.value)}
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
                  onChange={(e) => onSetNewItemExpectedOutcome(e.target.value)}
                  placeholder="Expected outcome (optional) — what should you see?"
                  className="w-full px-2 py-1.5 border border-gray-300 rounded text-xs focus:outline-none focus:ring-1 focus:ring-gray-900"
                />
                <input
                  type="text"
                  value={newItemRollbackAction}
                  onChange={(e) => onSetNewItemRollbackAction(e.target.value)}
                  placeholder="Rollback action (optional) — what if this step fails?"
                  className="w-full px-2 py-1.5 border border-gray-300 rounded text-xs focus:outline-none focus:ring-1 focus:ring-gray-900"
                />
                <div className="flex items-center gap-3">
                  <button
                    onClick={() => onAddItem(phase)}
                    disabled={!newItemDesc.trim()}
                    className="px-3 py-1.5 text-xs font-medium text-white bg-gray-900 rounded hover:bg-gray-800 disabled:opacity-50"
                  >
                    Add
                  </button>
                  <label className="flex items-center gap-1.5 text-xs text-gray-600 cursor-pointer select-none">
                    <input
                      type="checkbox"
                      checked={newItemHoldPoint}
                      onChange={(e) => onSetNewItemHoldPoint(e.target.checked)}
                      className="rounded border-gray-300 text-amber-600 focus:ring-amber-500"
                    />
                    🔒 Hold point
                  </label>
                  <button
                    onClick={resetForm}
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
                  resetForm();
                  onSetAddingToPhase(phase);
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
  );
}
