"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, Change, ChangeStatus } from "@/lib/api";
import { getCurrentUser } from "@/lib/auth";
import { STATUS_COLORS, STATUS_LABELS, formatDate } from "@/lib/constants";
import UserSwitcher from "@/components/UserSwitcher";

function StatusBadge({ status }: { status: ChangeStatus }) {
  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${STATUS_COLORS[status] || "bg-gray-100 text-gray-700"}`}
    >
      {STATUS_LABELS[status] || status}
    </span>
  );
}

export default function Home() {
  const router = useRouter();
  const [changes, setChanges] = useState<Change[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState("");
  const [needsMyReview, setNeedsMyReview] = useState(false);
  const [currentUserName, setCurrentUserName] = useState("");

  function loadChanges(params?: Record<string, string>) {
    setLoading(true);
    api
      .listChanges(params)
      .then((res) => {
        setChanges(res.data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }

  // Track current user (updates when user switcher changes)
  useEffect(() => {
    setCurrentUserName(getCurrentUser().name);
    const onUserChanged = () => setCurrentUserName(getCurrentUser().name);
    window.addEventListener("user-changed", onUserChanged);
    return () => window.removeEventListener("user-changed", onUserChanged);
  }, []);

  useEffect(() => {
    const params: Record<string, string> = {};
    if (statusFilter) params.status = statusFilter;
    if (searchQuery) params.title_search = searchQuery;
    if (needsMyReview && currentUserName) params.needs_review_by = currentUserName;
    loadChanges(params);
  }, [statusFilter, searchQuery, needsMyReview, currentUserName]);

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-semibold text-gray-900">Changebook</h1>
              <p className="text-sm text-gray-500">
                Production changes — think, plan, execute, verify
              </p>
            </div>
            <div className="flex items-center gap-3">
              <UserSwitcher />
              <Link
                href="/templates"
                className="inline-flex items-center px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
              >
                Templates
              </Link>
              <Link
                href="/changes/new"
                className="inline-flex items-center px-4 py-2 bg-gray-900 text-white text-sm font-medium rounded-lg hover:bg-gray-800 transition-colors"
              >
                New Change
              </Link>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Filters */}
        <div className="flex gap-3 mb-6">
          <input
            type="text"
            placeholder="Search by title..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-gray-900 focus:border-transparent w-64"
          />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-gray-900 focus:border-transparent"
          >
            <option value="">All statuses</option>
            {Object.entries(STATUS_LABELS).map(([val, label]) => (
              <option key={val} value={val}>
                {label}
              </option>
            ))}
          </select>
          <button
            onClick={() => setNeedsMyReview(!needsMyReview)}
            className={`inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
              needsMyReview
                ? "bg-purple-100 text-purple-800 border border-purple-300"
                : "bg-white text-gray-600 border border-gray-300 hover:bg-gray-50"
            }`}
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
            </svg>
            Needs my review
          </button>
        </div>

        {loading && (
          <div className="text-center py-12 text-gray-500">Loading changes...</div>
        )}

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
            {error}
          </div>
        )}

        {!loading && !error && changes.length === 0 && (
          <div className="text-center py-16">
            <h2 className="text-lg font-medium text-gray-900 mb-2">No changes yet</h2>
            <p className="text-gray-500 mb-6">
              Create your first change to start tracking production work.
            </p>
            <Link
              href="/changes/new"
              className="inline-flex items-center px-4 py-2 bg-gray-900 text-white text-sm font-medium rounded-lg hover:bg-gray-800 transition-colors"
            >
              Create a Change
            </Link>
          </div>
        )}

        {!loading && changes.length > 0 && (
          <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Change
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Author
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Created
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {changes.map((change) => (
                  <tr
                    key={change.id}
                    className="hover:bg-gray-50 cursor-pointer"
                    onClick={() => router.push(`/changes/${change.id}`)}
                  >
                    <td className="px-6 py-4">
                      <Link href={`/changes/${change.id}`} className="block">
                        <div className="text-sm font-medium text-gray-900">
                          {change.title}
                        </div>
                        {(change.customer_name || change.environment_name) && (
                          <div className="text-xs text-gray-400 mt-0.5">
                            {[change.customer_name, change.service_name].filter(Boolean).join(" / ")}
                            {change.environment_name && (
                              <> → <span className="text-gray-500 font-medium">{change.environment_name}</span></>
                            )}
                          </div>
                        )}
                        {change.defence_tags && change.defence_tags.length > 0 && (
                          <div className="flex gap-1 mt-1">
                            {change.defence_tags.map((tag) => (
                              <span
                                key={tag}
                                className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-gray-100 text-gray-600"
                              >
                                {tag}
                              </span>
                            ))}
                          </div>
                        )}
                      </Link>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center gap-2">
                        <StatusBadge status={change.status} />
                        {change.pending_reviewers?.includes(currentUserName) && (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-800">
                            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                              <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                              <path strokeLinecap="round" strokeLinejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                            </svg>
                            Needs your review
                          </span>
                        )}
                        {change.window_override_reason && (
                          <span
                            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-800"
                            title={change.window_override_reason}
                          >
                            ⚠️ Outside window
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {change.author_name}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {formatDate(change.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  );
}
