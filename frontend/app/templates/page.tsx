"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, Template } from "@/lib/api";
import UserSwitcher from "@/components/UserSwitcher";

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export default function TemplatesPage() {
  const router = useRouter();
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => {
    setLoading(true);
    const params: Record<string, string> = {};
    if (searchQuery) params.title_search = searchQuery;
    api
      .listTemplates(params)
      .then((data) => {
        setTemplates(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, [searchQuery]);

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-semibold text-gray-900">
                Template Library
              </h1>
              <p className="text-sm text-gray-500">
                Reusable procedures — saved from past changes or created from
                scratch
              </p>
            </div>
            <div className="flex items-center gap-3">
              <UserSwitcher />
              <Link
                href="/"
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
              >
                Changes
              </Link>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex gap-3 mb-6">
          <input
            type="text"
            placeholder="Search templates..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-gray-900 focus:border-transparent w-64"
          />
        </div>

        {loading && (
          <div className="text-center py-12 text-gray-500">
            Loading templates...
          </div>
        )}

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
            {error}
          </div>
        )}

        {!loading && !error && templates.length === 0 && (
          <div className="text-center py-16">
            <h2 className="text-lg font-medium text-gray-900 mb-2">
              No templates yet
            </h2>
            <p className="text-gray-500 mb-2">
              Templates are reusable procedures saved from past changes.
            </p>
            <p className="text-sm text-gray-400">
              Complete a change, then click &quot;Save as Template&quot; to add
              it to the library.
            </p>
          </div>
        )}

        {!loading && templates.length > 0 && (
          <div className="grid gap-4">
            {templates.map((tmpl) => (
              <div
                key={tmpl.id}
                className="bg-white rounded-lg border border-gray-200 p-5 hover:border-gray-300 transition-colors cursor-pointer"
                onClick={() => router.push(`/templates/${tmpl.id}`)}
              >
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="text-sm font-medium text-gray-900">
                      {tmpl.title}
                    </h3>
                    {tmpl.description && (
                      <p className="mt-1 text-sm text-gray-500">
                        {tmpl.description}
                      </p>
                    )}
                    <div className="flex items-center gap-3 mt-2 text-xs text-gray-400">
                      <span>
                        {tmpl.item_count} checklist item
                        {tmpl.item_count !== 1 ? "s" : ""}
                      </span>
                      <span>by {tmpl.author_name}</span>
                      <span>{formatDate(tmpl.created_at)}</span>
                    </div>
                  </div>
                  {tmpl.defence_tags && tmpl.defence_tags.length > 0 && (
                    <div className="flex gap-1">
                      {tmpl.defence_tags.map((tag) => (
                        <span
                          key={tag}
                          className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-gray-100 text-gray-600"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
