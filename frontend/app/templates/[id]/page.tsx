"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import SearchableSelect from "@/components/SearchableSelect";
import UserSwitcher from "@/components/UserSwitcher";
import { api, TemplateDetail, Customer, Environment } from "@/lib/api";
import { PHASE_LABELS, PHASE_ORDER, formatDate } from "@/lib/constants";

export default function TemplateDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;

  const [template, setTemplate] = useState<TemplateDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // "Use template" form state
  const [showUse, setShowUse] = useState(false);
  const [useTitle, setUseTitle] = useState("");
  const [useCustomerId, setUseCustomerId] = useState("");
  const [useServiceId, setUseServiceId] = useState("");
  const [useEnvironmentId, setUseEnvironmentId] = useState("");
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [environments, setEnvironments] = useState<Environment[]>([]);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    api
      .getTemplate(id)
      .then((t) => {
        setTemplate(t);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, [id]);

  async function openUseForm() {
    setShowUse(true);
    setUseTitle(template?.title || "");
    try {
      const [c, e] = await Promise.all([
        api.listCustomers(),
        api.listEnvironments(),
      ]);
      setCustomers(c);
      setEnvironments(e);
    } catch {
      // non-critical
    }
  }

  async function handleUse() {
    const missing: string[] = [];
    if (!useTitle.trim()) missing.push("Title");
    if (!useCustomerId) missing.push("Customer");
    if (!useServiceId) missing.push("Service");
    if (!useEnvironmentId) missing.push("Environment");
    if (missing.length > 0) {
      setError(`Required: ${missing.join(", ")}`);
      return;
    }
    setCreating(true);
    setError(null);
    try {
      const result = await api.useTemplate(id, {
        title: useTitle,
        customer_id: useCustomerId,
        service_id: useServiceId,
        environment_id: useEnvironmentId,
      });
      router.push(`/changes/${result.change_id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create change");
      setCreating(false);
    }
  }

  async function handleCreateCustomer(name: string): Promise<string | null> {
    const c = await api.createCustomer({ name, services: [{ name: "Default" }] });
    setCustomers((prev) => [...prev, c]);
    setUseServiceId(c.services[0]?.id || "");
    return c.id;
  }

  async function handleCreateService(name: string): Promise<string | null> {
    if (!useCustomerId) return null;
    const s = await api.addService(useCustomerId, { name });
    setCustomers((prev) =>
      prev.map((c) =>
        c.id === useCustomerId ? { ...c, services: [...c.services, s] } : c
      )
    );
    return s.id;
  }

  async function handleCreateEnvironment(name: string): Promise<string | null> {
    const e = await api.createEnvironment({ name });
    setEnvironments((prev) => [...prev, e]);
    return e.id;
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center text-gray-500">
        Loading...
      </div>
    );
  }

  if (!template) {
    return (
      <div className="min-h-screen bg-gray-50 p-8">
        <div className="max-w-3xl mx-auto bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
          {error || "Template not found"}
        </div>
      </div>
    );
  }

  // Group items by phase
  const itemsByPhase: Record<string, typeof template.items> = {};
  for (const item of template.items) {
    if (!itemsByPhase[item.phase]) itemsByPhase[item.phase] = [];
    itemsByPhase[item.phase].push(item);
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center gap-4">
            <Link
              href="/templates"
              className="text-gray-400 hover:text-gray-600"
            >
              &larr;
            </Link>
            <div className="flex-1">
              <h1 className="text-xl font-semibold text-gray-900">
                {template.title}
              </h1>
              <div className="flex items-center gap-3 mt-1">
                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-indigo-100 text-indigo-700">
                  Template
                </span>
                <span className="text-sm text-gray-500">
                  by {template.author_name}
                </span>
                <span className="text-sm text-gray-400">
                  {formatDate(template.created_at)}
                </span>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <UserSwitcher />
              <button
                onClick={openUseForm}
                className="px-4 py-2 text-sm font-medium text-white bg-gray-900 rounded-lg hover:bg-gray-800"
              >
                Use this template
              </button>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 text-sm">
            {error}
            <button onClick={() => setError(null)} className="ml-2 underline">
              dismiss
            </button>
          </div>
        )}

        {/* Use template form */}
        {showUse && (
          <div className="bg-white rounded-lg border border-blue-200 p-6 space-y-4">
            <h2 className="text-sm font-medium text-gray-900">
              Create a change from this template
            </h2>
            <p className="text-xs text-gray-500">
              The checklist, defence tags, and general change profile answers
              will be pre-filled. You provide the context: title, customer,
              service, and environment.
            </p>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">
                Title *
              </label>
              <input
                type="text"
                value={useTitle}
                onChange={(e) => setUseTitle(e.target.value)}
                placeholder="e.g., Resize connection pool on PROD-EU"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-gray-900 focus:border-transparent"
                autoFocus
              />
            </div>
            <div className="grid grid-cols-1 gap-4">
              <SearchableSelect
                label="Customer"
                required
                options={customers.map((c) => ({ id: c.id, label: c.name }))}
                value={useCustomerId}
                onChange={(id) => {
                  setUseCustomerId(id);
                  setUseServiceId("");
                }}
                placeholder="Select customer..."
                onCreateNew={handleCreateCustomer}
                itemNoun="customer"
              />
              {useCustomerId && (
                <SearchableSelect
                  label="Service"
                  required
                  options={(
                    customers.find((c) => c.id === useCustomerId)?.services || []
                  ).map((s) => ({ id: s.id, label: s.name }))}
                  value={useServiceId}
                  onChange={setUseServiceId}
                  placeholder="Select service..."
                  onCreateNew={handleCreateService}
                  itemNoun="service"
                />
              )}
              <SearchableSelect
                label="Environment"
                required
                options={environments.map((e) => ({
                  id: e.id,
                  label: e.name,
                  sublabel: e.platform || undefined,
                }))}
                value={useEnvironmentId}
                onChange={setUseEnvironmentId}
                placeholder="Select environment..."
                onCreateNew={handleCreateEnvironment}
                itemNoun="environment"
              />
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleUse}
                disabled={creating}
                className="px-4 py-1.5 text-sm font-medium text-white bg-gray-900 rounded-lg hover:bg-gray-800 disabled:opacity-50"
              >
                {creating ? "Creating..." : "Create Change"}
              </button>
              <button
                onClick={() => setShowUse(false)}
                className="px-4 py-1.5 text-sm font-medium text-gray-600 hover:text-gray-800"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {template.description && (
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <p className="text-sm text-gray-700">{template.description}</p>
          </div>
        )}

        {/* Defence tags */}
        {template.defence_tags && template.defence_tags.length > 0 && (
          <div className="flex gap-2">
            {template.defence_tags.map((tag) => (
              <span
                key={tag}
                className="inline-flex items-center px-2.5 py-1 rounded-md text-xs font-medium bg-amber-50 text-amber-800 border border-amber-200"
              >
                {tag}
              </span>
            ))}
          </div>
        )}

        {/* Preflight answers preview */}
        {template.preflight_answers &&
          Object.keys(template.preflight_answers).length > 0 && (
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <h2 className="text-lg font-medium text-gray-900 mb-4">
                Change Profile (pre-filled)
              </h2>
              <dl className="space-y-2">
                {Object.entries(template.preflight_answers).map(
                  ([key, value]) =>
                    value ? (
                      <div
                        key={key}
                        className="pl-3 border-l-2 border-gray-100"
                      >
                        <dt className="text-xs font-medium text-gray-500">
                          {key.replace(/_/g, " ")}
                        </dt>
                        <dd className="mt-0.5 text-sm text-gray-900 whitespace-pre-wrap">
                          {value}
                        </dd>
                      </div>
                    ) : null
                )}
              </dl>
            </div>
          )}

        {/* Checklist preview */}
        <div className="bg-white rounded-lg border border-gray-200 p-6 space-y-6">
          <h2 className="text-lg font-medium text-gray-900">Checklist</h2>

          {PHASE_ORDER.map((phase) => {
            const items = itemsByPhase[phase] || [];
            if (items.length === 0) return null;
            return (
              <div key={phase}>
                <h3 className="text-sm font-medium text-gray-700 mb-2 uppercase tracking-wider">
                  {PHASE_LABELS[phase]}
                </h3>
                <div className="space-y-2">
                  {items.map((item) => (
                    <div
                      key={item.id}
                      className="border border-gray-200 rounded-lg p-4"
                    >
                      <div className="flex items-start gap-3">
                        <span className="flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-xs font-medium bg-gray-100 text-gray-600">
                          {item.order}
                        </span>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm text-gray-900">
                            {item.description}
                          </p>
                          {item.command && (
                            <pre
                              className="mt-1 bg-gray-50 rounded p-2 text-xs font-mono text-gray-700 overflow-x-auto"
                              style={{
                                whiteSpace: "pre-wrap",
                                fontVariantLigatures: "none",
                                fontFeatureSettings:
                                  '"liga" 0, "clig" 0',
                              }}
                            >
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
                              Hold Point
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </main>
    </div>
  );
}
