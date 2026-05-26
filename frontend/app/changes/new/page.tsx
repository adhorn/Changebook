"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, Customer, Environment, PreflightSection } from "@/lib/api";
import UserSwitcher from "@/components/UserSwitcher";

export default function NewChange() {
  const router = useRouter();
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [environments, setEnvironments] = useState<Environment[]>([]);
  const [preflightSections, setPreflightSections] = useState<PreflightSection[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Form state
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [customerId, setCustomerId] = useState("");
  const [serviceId, setServiceId] = useState("");
  const [environmentId, setEnvironmentId] = useState("");
  const [preflightAnswers, setPreflightAnswers] = useState<Record<string, string>>({});

  const selectedCustomer = customers.find((c) => c.id === customerId);

  useEffect(() => {
    api.listCustomers().then(setCustomers).catch(console.error);
    api.listEnvironments().then(setEnvironments).catch(console.error);
    api.getPreflightQuestions().then((schema) => {
      setPreflightSections(schema.sections);
    }).catch(console.error);
  }, []);

  function updatePreflight(key: string, value: string) {
    setPreflightAnswers((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      const change = await api.createChange({
        title,
        description: description || undefined,
        customer_id: customerId,
        service_id: serviceId,
        environment_id: environmentId,
        preflight_answers: Object.keys(preflightAnswers).length > 0 ? preflightAnswers : undefined,
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
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
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
            <UserSwitcher />
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
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
            {/* Author comes from auth — shown in the user switcher */}
          </div>

          {/* Customer / Service / Environment */}
          <div className="bg-white rounded-lg border border-gray-200 p-6 space-y-4">
            <h2 className="text-lg font-medium text-gray-900">Where</h2>
            <p className="text-sm text-gray-500 -mt-2">
              One change, one customer, one service, one environment.
            </p>
            <div className="grid grid-cols-1 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Customer *
                </label>
                <select
                  required
                  value={customerId}
                  onChange={(e) => {
                    setCustomerId(e.target.value);
                    setServiceId(""); // reset service when customer changes
                  }}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-gray-900 focus:border-transparent"
                >
                  <option value="">Select customer...</option>
                  {customers.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </div>
              {selectedCustomer && selectedCustomer.services.length > 0 && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Service *
                  </label>
                  <select
                    required
                    value={serviceId}
                    onChange={(e) => setServiceId(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-gray-900 focus:border-transparent"
                  >
                    <option value="">Select service...</option>
                    {selectedCustomer.services.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.name}
                      </option>
                    ))}
                  </select>
                </div>
              )}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Environment *
                </label>
                <select
                  required
                  value={environmentId}
                  onChange={(e) => setEnvironmentId(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-gray-900 focus:border-transparent"
                >
                  <option value="">Select environment...</option>
                  {environments.map((env) => (
                    <option key={env.id} value={env.id}>
                      {env.name} {env.platform ? `(${env.platform})` : ""}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          {/* Pre-flight questions — from API */}
          {preflightSections.map((section) => (
            <div
              key={section.title}
              className="bg-white rounded-lg border border-gray-200 p-6 space-y-4"
            >
              <h2 className="text-lg font-medium text-gray-900">{section.title}</h2>
              <p className="text-sm text-gray-500 -mt-2 italic">{section.framing}</p>
              {section.questions.map((q) => (
                <div key={q.key}>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {q.label}
                    {q.required && <span className="text-red-500 ml-0.5">*</span>}
                  </label>
                  <p className="text-xs text-gray-400 mb-1">{q.description}</p>
                  <textarea
                    value={preflightAnswers[q.key] || ""}
                    onChange={(e) => updatePreflight(q.key, e.target.value)}
                    rows={2}
                    placeholder={q.example}
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
