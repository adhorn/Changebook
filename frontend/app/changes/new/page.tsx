"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, Team, CustomerDetail } from "@/lib/api";

// The pre-flight checklist is structured around cognitive forcing functions.
// Each section makes the operator think about a different dimension of the change
// BEFORE they start planning execution. This is the "think" phase, not the "do" phase.
const PREFLIGHT_SECTIONS = [
  {
    title: "The Change",
    description: "What are you doing and what should happen?",
    fields: [
      { key: "what_is_this_change", label: "What is this change?" },
      { key: "expected_outcome", label: "What is the expected outcome?" },
    ],
  },
  {
    title: "What the Customer Experiences",
    description:
      "Think from the customer's perspective, not yours.",
    fields: [
      {
        key: "customer_notice",
        label: "Will the customer notice this change? How?",
      },
      {
        key: "customer_mid_failure",
        label:
          "If this change fails mid-way, what is the customer in the middle of doing? What happens to their work?",
      },
    ],
  },
  {
    title: "Failure and Recovery",
    description: "Assume this will go wrong. What then?",
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
        label: "What is the blast radius? (customers/environments)",
      },
    ],
  },
  {
    title: "Timing and Coordination",
    description: "Is this the right moment — for the customer, not just for you?",
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

export default function NewChange() {
  const router = useRouter();
  const [teams, setTeams] = useState<Team[]>([]);
  const [customers, setCustomers] = useState<CustomerDetail[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Form state
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [teamId, setTeamId] = useState("");
  const [authorName, setAuthorName] = useState("");
  const [selectedCustomerIds, setSelectedCustomerIds] = useState<string[]>([]);
  const [preflightAnswers, setPreflightAnswers] = useState<Record<string, string>>({});

  useEffect(() => {
    api.listTeams().then(setTeams).catch(console.error);
    api.listCustomers().then(setCustomers).catch(console.error);
  }, []);

  function updatePreflight(key: string, value: string) {
    setPreflightAnswers((prev) => ({ ...prev, [key]: value }));
  }

  function toggleCustomer(customerId: string) {
    setSelectedCustomerIds((prev) =>
      prev.includes(customerId)
        ? prev.filter((id) => id !== customerId)
        : [...prev, customerId]
    );
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
        customer_ids: selectedCustomerIds.length > 0 ? selectedCustomerIds : undefined,
        preflight_answers: preflightAnswers,
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
              <p className="text-sm text-gray-500">
                Think before you act — what, who, what-if, when
              </p>
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

          {/* Customer selection */}
          {customers.length > 0 && (
            <div className="bg-white rounded-lg border border-gray-200 p-6 space-y-4">
              <h2 className="text-lg font-medium text-gray-900">
                Affected Customers
              </h2>
              <p className="text-sm text-gray-500">
                Which customers are affected by this change?
              </p>
              <div className="space-y-2">
                {customers.map((customer) => (
                  <label
                    key={customer.id}
                    className={`flex items-start gap-3 p-3 border rounded-lg cursor-pointer transition-colors ${
                      selectedCustomerIds.includes(customer.id)
                        ? "border-gray-900 bg-gray-50"
                        : "border-gray-200 hover:border-gray-300"
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={selectedCustomerIds.includes(customer.id)}
                      onChange={() => toggleCustomer(customer.id)}
                      className="mt-0.5 rounded border-gray-300"
                    />
                    <div>
                      <span className="text-sm font-medium text-gray-900">
                        {customer.name}
                      </span>
                      {customer.description && (
                        <p className="text-xs text-gray-500 mt-0.5">
                          {customer.description}
                        </p>
                      )}
                      {customer.services.length > 0 && (
                        <div className="flex gap-1.5 mt-1.5">
                          {customer.services.map((svc) => (
                            <span
                              key={svc.id}
                              className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-gray-100 text-gray-600"
                            >
                              {svc.name}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </label>
                ))}
              </div>
            </div>
          )}

          {/* Pre-flight questions */}
          {PREFLIGHT_SECTIONS.map((section) => (
            <div
              key={section.title}
              className="bg-white rounded-lg border border-gray-200 p-6 space-y-4"
            >
              <h2 className="text-lg font-medium text-gray-900">{section.title}</h2>
              {section.description && (
                <p className="text-sm text-gray-500 -mt-2">{section.description}</p>
              )}
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
