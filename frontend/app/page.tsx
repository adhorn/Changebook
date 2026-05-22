"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, Change, ChangeStatus } from "@/lib/api";

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

function StatusBadge({ status }: { status: ChangeStatus }) {
  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${STATUS_COLORS[status]}`}
    >
      {STATUS_LABELS[status]}
    </span>
  );
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function Home() {
  const [changes, setChanges] = useState<Change[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listChanges()
      .then((res) => {
        setChanges(res.data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-semibold text-gray-900">Changebook</h1>
              <p className="text-sm text-gray-500">
                Production changes — from plan to verification
              </p>
            </div>
            <Link
              href="/changes/new"
              className="inline-flex items-center px-4 py-2 bg-gray-900 text-white text-sm font-medium rounded-lg hover:bg-gray-800 transition-colors"
            >
              New Change
            </Link>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
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
                  >
                    <td className="px-6 py-4">
                      <Link href={`/changes/${change.id}`} className="block">
                        <div className="text-sm font-medium text-gray-900">
                          {change.title}
                        </div>
                        {change.description && (
                          <div className="text-sm text-gray-500 truncate max-w-md">
                            {change.description}
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
                      <StatusBadge status={change.status} />
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
