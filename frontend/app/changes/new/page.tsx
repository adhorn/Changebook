"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, Team } from "@/lib/api";

const PREFLIGHT_SECTIONS = [
  {
    title: "The Change",
    fields: [
      { key: "what_is_this_change", label: "What is this change?" },
      { key: "systems_affected", label: "What systems/services are affected?" },
      { key: "expected_outcome", label: "What is the expected outcome?" },
    ],
  },
  {
    title: "What the Customer Experiences",
    fields: [
      {
        key: "who_is_using",
        label: "Who is using this system right now? What are they trying to do?",
      },
      {
        key: "customer_notice",
        label: "Will the customer notice this change? How?",
      },
      {
        key: "customer_mid_failure",
        label:
          "If this change fails mid-execution, what is the customer in the middle of doing? What happens to their work?",
      },
    ],
  },
  {
    title: "Failure and Recovery",
    fields: [
      { key: "what_if_fails", label: "What happens if this change fails?" },
      { key: "rollback_plan", label: "How do you roll back?" },
      {
        key: "rollback_duration",
        label:
          "How long does rollback take? What is the customer's experience during rollback?",
      },
      {
        key: "blast_radius",
        label: "What is the blast radius? (customers/systems/environments)",
      },
    ],
  },
  {
    title: "Timing and Coordination",
    fields: [
      { key: "maintenance_window", label: "Is there a maintenance window? When?" },
      {
        key: "why_this_time",
        label:
          "Why this time? Is this the lowest-impact window for the customer, or the most convenient for the operator?",
      },
      {
        key: "dependencies",
        label: "Are there dependencies on other changes or teams?",
      },
      {
        key: "customer_informed",
        label: "Has the customer been informed? Do they need to be?",
      },
    ],
  },
];

interface StepInput {
  description: string;
  expected_outcome: string;
  rollback_action: string;
  script: string;
  is_hold_point: boolean;
}

const EMPTY_STEP: StepInput = {
  description: "",
  expected_outcome: "",
  rollback_action: "",
  script: "",
  is_hold_point: false,
};

export default function NewChange() {
  const router = useRouter();
  const [teams, setTeams] = useState<Team[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Form state
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [teamId, setTeamId] = useState("");
  const [authorName, setAuthorName] = useState("");
  const [preflightAnswers, setPreflightAnswers] = useState<Record<string, string>>({});
  const [steps, setSteps] = useState<StepInput[]>([{ ...EMPTY_STEP }]);

  useEffect(() => {
    api.listTeams().then(setTeams).catch(console.error);
  }, []);

  function updatePreflight(key: string, value: string) {
    setPreflightAnswers((prev) => ({ ...prev, [key]: value }));
  }

  function updateStep(index: number, field: keyof StepInput, value: string | boolean) {
    setSteps((prev) =>
      prev.map((s, i) => (i === index ? { ...s, [field]: value } : s))
    );
  }

  function addStep() {
    setSteps((prev) => [...prev, { ...EMPTY_STEP }]);
  }

  function removeStep(index: number) {
    setSteps((prev) => prev.filter((_, i) => i !== index));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      const change = await api.createChange({
        title,
        description: description || undefined,
        team_id: teamId,
        author_name: authorName,
        preflight_answers: preflightAnswers,
        steps: steps
          .filter((s) => s.description.trim())
          .map((s) => ({
            description: s.description,
            expected_outcome: s.expected_outcome || undefined,
            rollback_action: s.rollback_action || undefined,
            script: s.script || undefined,
            is_hold_point: s.is_hold_point,
          })),
      });
      router.push(`/changes/${change.id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create change");
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center gap-4">
            <Link href="/" className="text-gray-400 hover:text-gray-600">
              &larr;
            </Link>
            <div>
              <h1 className="text-xl font-semibold text-gray-900">New Change</h1>
              <p className="text-sm text-gray-500">Pre-flight checklist</p>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <form onSubmit={handleSubmit} className="space-y-8">
          {/* Basic info */}
          <div className="bg-white rounded-lg border border-gray-200 p-6 space-y-4">
            <h2 className="text-lg font-medium text-gray-900">Change Details</h2>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Title *
              </label>
              <input
                type="text"
                required
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g., Update connection pool size on PROD-EU"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-gray-900 focus:border-transparent"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Description
              </label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={2}
                placeholder="Brief summary of the change"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-gray-900 focus:border-transparent"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Team *
                </label>
                <select
                  required
                  value={teamId}
                  onChange={(e) => setTeamId(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-gray-900 focus:border-transparent"
                >
                  <option value="">Select team...</option>
                  {teams.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Author *
                </label>
                <input
                  type="text"
                  required
                  value={authorName}
                  onChange={(e) => setAuthorName(e.target.value)}
                  placeholder="Your name"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-gray-900 focus:border-transparent"
                />
              </div>
            </div>
          </div>

          {/* Pre-flight questions */}
          {PREFLIGHT_SECTIONS.map((section) => (
            <div
              key={section.title}
              className="bg-white rounded-lg border border-gray-200 p-6 space-y-4"
            >
              <h2 className="text-lg font-medium text-gray-900">{section.title}</h2>
              {section.fields.map((field) => (
                <div key={field.key}>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {field.label}
                  </label>
                  <textarea
                    value={preflightAnswers[field.key] || ""}
                    onChange={(e) => updatePreflight(field.key, e.target.value)}
                    rows={2}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-gray-900 focus:border-transparent"
                  />
                </div>
              ))}
            </div>
          ))}

          {/* Execution steps */}
          <div className="bg-white rounded-lg border border-gray-200 p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-medium text-gray-900">Execution Steps</h2>
              <button
                type="button"
                onClick={addStep}
                className="text-sm text-gray-600 hover:text-gray-900"
              >
                + Add Step
              </button>
            </div>
            {steps.map((step, index) => (
              <div
                key={index}
                className="border border-gray-200 rounded-lg p-4 space-y-3"
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-gray-500">
                    Step {index + 1}
                  </span>
                  {steps.length > 1 && (
                    <button
                      type="button"
                      onClick={() => removeStep(index)}
                      className="text-xs text-red-500 hover:text-red-700"
                    >
                      Remove
                    </button>
                  )}
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">
                    What to do
                  </label>
                  <textarea
                    value={step.description}
                    onChange={(e) => updateStep(index, "description", e.target.value)}
                    rows={2}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-gray-900 focus:border-transparent"
                  />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-gray-500 mb-1">
                      Expected outcome
                    </label>
                    <input
                      type="text"
                      value={step.expected_outcome}
                      onChange={(e) =>
                        updateStep(index, "expected_outcome", e.target.value)
                      }
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-gray-900 focus:border-transparent"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-500 mb-1">
                      Rollback action
                    </label>
                    <input
                      type="text"
                      value={step.rollback_action}
                      onChange={(e) =>
                        updateStep(index, "rollback_action", e.target.value)
                      }
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-gray-900 focus:border-transparent"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">
                    Script / command (optional)
                  </label>
                  <textarea
                    value={step.script}
                    onChange={(e) => updateStep(index, "script", e.target.value)}
                    rows={2}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-gray-900 focus:border-transparent"
                  />
                </div>
                <label className="flex items-center gap-2 text-sm text-gray-600">
                  <input
                    type="checkbox"
                    checked={step.is_hold_point}
                    onChange={(e) =>
                      updateStep(index, "is_hold_point", e.target.checked)
                    }
                    className="rounded border-gray-300"
                  />
                  Hold point — requires independent verification before proceeding
                </label>
              </div>
            ))}
          </div>

          {/* Submit */}
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 text-sm">
              {error}
            </div>
          )}

          <div className="flex justify-end gap-3">
            <Link
              href="/"
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
            >
              Cancel
            </Link>
            <button
              type="submit"
              disabled={submitting}
              className="px-4 py-2 text-sm font-medium text-white bg-gray-900 rounded-lg hover:bg-gray-800 disabled:opacity-50 transition-colors"
            >
              {submitting ? "Creating..." : "Create Change"}
            </button>
          </div>
        </form>
      </main>
    </div>
  );
}
