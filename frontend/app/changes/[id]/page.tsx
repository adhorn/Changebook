"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api, ChangeDetail, ChangeStatus } from "@/lib/api";

const STATUS_COLORS: Record<ChangeStatus, string> = {
  draft: "bg-gray-100 text-gray-700",
  in_review: "bg-yellow-100 text-yellow-800",
  approved: "bg-blue-100 text-blue-800",
  executing: "bg-orange-100 text-orange-800",
  awaiting_verification: "bg-purple-100 text-purple-800",
  verified: "bg-green-100 text-green-800",
  closed: "bg-green-50 text-green-600",
  aborted: "bg-red-100 text-red-700",
};

const STATUS_LABELS: Record<ChangeStatus, string> = {
  draft: "Draft",
  in_review: "In Review",
  approved: "Approved",
  executing: "Executing",
  awaiting_verification: "Awaiting Verification",
  verified: "Verified",
  closed: "Closed",
  aborted: "Aborted",
};

const NEXT_TRANSITIONS: Partial<Record<ChangeStatus, { label: string; target: ChangeStatus }>> = {
  draft: { label: "Submit for Review", target: "in_review" },
  in_review: { label: "Approve", target: "approved" },
  approved: { label: "Start Execution", target: "executing" },
  executing: { label: "Move to Verification", target: "awaiting_verification" },
  awaiting_verification: { label: "Mark Verified", target: "verified" },
  verified: { label: "Close", target: "closed" },
};

const PREFLIGHT_LABELS: Record<string, string> = {
  what_is_this_change: "What is this change?",
  systems_affected: "What systems/services are affected?",
  expected_outcome: "What is the expected outcome?",
  who_is_using: "Who is using this system right now?",
  customer_notice: "Will the customer notice this change?",
  customer_mid_failure: "If this change fails, what is the customer doing?",
  what_if_fails: "What happens if this change fails?",
  rollback_plan: "How do you roll back?",
  rollback_duration: "How long does rollback take?",
  blast_radius: "What is the blast radius?",
  maintenance_window: "Maintenance window",
  why_this_time: "Why this time?",
  dependencies: "Dependencies",
  customer_informed: "Has the customer been informed?",
};

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function ChangeDetailPage() {
  const params = useParams();
  const id = params.id as string;

  const [change, setChange] = useState<ChangeDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [transitioning, setTransitioning] = useState(false);

  useEffect(() => {
    api
      .getChange(id)
      .then((c) => {
        setChange(c);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, [id]);

  async function handleTransition(target: ChangeStatus) {
    if (!change) return;
    setTransitioning(true);
    try {
      const updated = await api.transitionChange(change.id, target, change.author_name);
      setChange(updated);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Transition failed");
    }
    setTransitioning(false);
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center text-gray-500">
        Loading...
      </div>
    );
  }

  if (error || !change) {
    return (
      <div className="min-h-screen bg-gray-50 p-8">
        <div className="max-w-3xl mx-auto bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
          {error || "Change not found"}
        </div>
      </div>
    );
  }

  const nextAction = NEXT_TRANSITIONS[change.status];

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center gap-4">
            <Link href="/" className="text-gray-400 hover:text-gray-600">
              &larr;
            </Link>
            <div className="flex-1">
              <h1 className="text-xl font-semibold text-gray-900">{change.title}</h1>
              <div className="flex items-center gap-3 mt-1">
                <span
                  className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${STATUS_COLORS[change.status]}`}
                >
                  {STATUS_LABELS[change.status]}
                </span>
                <span className="text-sm text-gray-500">by {change.author_name}</span>
                <span className="text-sm text-gray-400">{formatDate(change.created_at)}</span>
              </div>
            </div>
            <div className="flex gap-2">
              {change.status !== "closed" && change.status !== "aborted" && (
                <button
                  onClick={() => handleTransition("aborted")}
                  disabled={transitioning}
                  className="px-3 py-1.5 text-xs font-medium text-red-600 bg-white border border-red-200 rounded-lg hover:bg-red-50 disabled:opacity-50"
                >
                  Abort
                </button>
              )}
              {nextAction && (
                <button
                  onClick={() => handleTransition(nextAction.target)}
                  disabled={transitioning}
                  className="px-4 py-1.5 text-sm font-medium text-white bg-gray-900 rounded-lg hover:bg-gray-800 disabled:opacity-50"
                >
                  {nextAction.label}
                </button>
              )}
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
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

        {/* Pre-flight answers */}
        {change.preflight_answers && Object.keys(change.preflight_answers).length > 0 && (
          <div className="bg-white rounded-lg border border-gray-200 p-6 space-y-4">
            <h2 className="text-lg font-medium text-gray-900">Pre-flight</h2>
            <dl className="space-y-3">
              {Object.entries(change.preflight_answers).map(([key, value]) => (
                <div key={key}>
                  <dt className="text-xs font-medium text-gray-500 uppercase tracking-wider">
                    {PREFLIGHT_LABELS[key] || key}
                  </dt>
                  <dd className="mt-0.5 text-sm text-gray-900 whitespace-pre-wrap">
                    {value}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        )}

        {/* Execution steps */}
        {change.steps.length > 0 && (
          <div className="bg-white rounded-lg border border-gray-200 p-6 space-y-4">
            <h2 className="text-lg font-medium text-gray-900">Execution Steps</h2>
            <ol className="space-y-3">
              {change.steps.map((step) => (
                <li
                  key={step.id}
                  className="border border-gray-200 rounded-lg p-4"
                >
                  <div className="flex items-start gap-3">
                    <span className="flex-shrink-0 w-6 h-6 bg-gray-100 rounded-full flex items-center justify-center text-xs font-medium text-gray-600">
                      {step.order}
                    </span>
                    <div className="flex-1 space-y-2">
                      <p className="text-sm text-gray-900">{step.description}</p>
                      {step.expected_outcome && (
                        <p className="text-xs text-gray-500">
                          Expected: {step.expected_outcome}
                        </p>
                      )}
                      {step.rollback_action && (
                        <p className="text-xs text-gray-500">
                          Rollback: {step.rollback_action}
                        </p>
                      )}
                      {step.script && (
                        <pre className="bg-gray-50 rounded p-2 text-xs font-mono text-gray-700 overflow-x-auto">
                          {step.script}
                        </pre>
                      )}
                      {step.is_hold_point && (
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-50 text-red-700">
                          Hold Point
                        </span>
                      )}
                    </div>
                  </div>
                </li>
              ))}
            </ol>
          </div>
        )}
      </main>
    </div>
  );
}
