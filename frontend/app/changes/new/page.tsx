"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, Customer, Environment, PreflightSection } from "@/lib/api";
import UserSwitcher from "@/components/UserSwitcher";
import SearchableSelect from "@/components/SearchableSelect";

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
  const [windowStart, setWindowStart] = useState("");
  const [windowEnd, setWindowEnd] = useState("");
  const [windowTz, setWindowTz] = useState("UTC");
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

  async function handleCreateCustomer(name: string): Promise<string | null> {
    const newCustomer = await api.createCustomer({ name, services: [{ name: "Default" }] });
    setCustomers((prev) => [...prev, newCustomer]);
    setServiceId(newCustomer.services[0]?.id || "");
    return newCustomer.id;
  }

  async function handleCreateService(name: string): Promise<string | null> {
    if (!customerId) return null;
    const newService = await api.addService(customerId, { name });
    setCustomers((prev) =>
      prev.map((c) =>
        c.id === customerId ? { ...c, services: [...c.services, newService] } : c
      )
    );
    return newService.id;
  }

  async function handleCreateEnvironment(name: string): Promise<string | null> {
    const newEnv = await api.createEnvironment({ name });
    setEnvironments((prev) => [...prev, newEnv]);
    return newEnv.id;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    const missing: string[] = [];
    if (!title.trim()) missing.push("Title");
    if (!customerId) missing.push("Customer");
    if (!serviceId) missing.push("Service");
    if (!environmentId) missing.push("Environment");
    if (missing.length > 0) {
      setError(`Required: ${missing.join(", ")}`);
      return;
    }

    setSubmitting(true);
    try {
      const change = await api.createChange({
        title,
        description: description || undefined,
        customer_id: customerId,
        service_id: serviceId,
        environment_id: environmentId,
        preflight_answers: Object.keys(preflightAnswers).length > 0 ? preflightAnswers : undefined,
        maintenance_window_start: windowStart ? new Date(windowStart).toISOString() : undefined,
        maintenance_window_end: windowEnd ? new Date(windowEnd).toISOString() : undefined,
        maintenance_window_tz: windowStart ? windowTz : undefined,
      });
      router.push(`/changes/${change.id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create change");
      setSubmitting(false);
    }
  }

  const customerOptions = customers.map((c) => ({ id: c.id, label: c.name }));
  const serviceOptions = selectedCustomer
    ? selectedCustomer.services.map((s) => ({ id: s.id, label: s.name }))
    : [];
  const environmentOptions = environments.map((e) => ({
    id: e.id,
    label: e.name,
    sublabel: e.platform || undefined,
  }));

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
          </div>

          {/* Customer / Service / Environment */}
          <div className="bg-white rounded-lg border border-gray-200 p-6 space-y-4">
            <h2 className="text-lg font-medium text-gray-900">Where</h2>
            <p className="text-sm text-gray-500 -mt-2">
              One change, one customer, one service, one environment.
            </p>
            <div className="grid grid-cols-1 gap-4">
              <SearchableSelect
                label="Customer"
                required
                options={customerOptions}
                value={customerId}
                onChange={(id) => {
                  setCustomerId(id);
                  setServiceId("");
                }}
                placeholder="Select customer..."
                onCreateNew={handleCreateCustomer}
                itemNoun="customer"
              />

              {selectedCustomer && (
                <SearchableSelect
                  label="Service"
                  required
                  options={serviceOptions}
                  value={serviceId}
                  onChange={setServiceId}
                  placeholder="Select service..."
                  onCreateNew={handleCreateService}
                  itemNoun="service"
                />
              )}

              <SearchableSelect
                label="Environment"
                required
                options={environmentOptions}
                value={environmentId}
                onChange={setEnvironmentId}
                placeholder="Select environment..."
                onCreateNew={handleCreateEnvironment}
                itemNoun="environment"
              />
            </div>
          </div>

          {/* Maintenance window */}
          <div className="bg-white rounded-lg border border-gray-200 p-6 space-y-4">
            <h2 className="text-lg font-medium text-gray-900">When</h2>
            <p className="text-sm text-gray-500 -mt-2">
              The maintenance window for this change. Optional — set it when you know the schedule.
            </p>
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Start</label>
                <input
                  type="datetime-local"
                  value={windowStart}
                  onChange={(e) => setWindowStart(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-gray-900 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">End</label>
                <input
                  type="datetime-local"
                  value={windowEnd}
                  onChange={(e) => setWindowEnd(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-gray-900 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Timezone</label>
                <select
                  value={windowTz}
                  onChange={(e) => setWindowTz(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-gray-900 focus:border-transparent"
                >
                  {["UTC", "Europe/London", "Europe/Paris", "Europe/Berlin", "Europe/Copenhagen", "US/Eastern", "US/Central", "US/Mountain", "US/Pacific", "Asia/Tokyo", "Asia/Singapore", "Australia/Sydney"].map((tz) => (
                    <option key={tz} value={tz}>{tz}</option>
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
