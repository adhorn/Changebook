"use client";

import { useState, useRef, useEffect } from "react";

interface Option {
  id: string;
  label: string;
  sublabel?: string;
}

interface SimilarMatch {
  name: string;
  id: string;
}

interface SearchableSelectProps {
  label: string;
  required?: boolean;
  options: Option[];
  value: string;
  onChange: (id: string) => void;
  placeholder?: string;
  /** Called when user wants to create a new item. Returns the new item's id, or null if cancelled. */
  onCreateNew?: (name: string) => Promise<string | null>;
  /** Noun for the "add new" button, e.g. "customer" or "environment" */
  itemNoun?: string;
}

/**
 * Find existing items whose names are similar to the input (case-insensitive).
 * Returns matches that aren't exact (case-sensitive) but are close.
 */
function findSimilar(input: string, options: Option[]): SimilarMatch[] {
  const trimmed = input.trim();
  if (!trimmed) return [];
  const lower = trimmed.toLowerCase();

  return options
    .filter((o) => {
      // Skip exact matches — those aren't "similar", they're the same
      if (o.label === trimmed) return false;
      // Case-insensitive match
      if (o.label.toLowerCase() === lower) return true;
      // Levenshtein-ish: one char difference for short names, two for longer
      const threshold = trimmed.length <= 5 ? 1 : 2;
      if (editDistance(o.label.toLowerCase(), lower) <= threshold) return true;
      // One is a prefix of the other (at least 3 chars)
      if (lower.length >= 3 && o.label.toLowerCase().startsWith(lower)) return true;
      if (lower.length >= 3 && lower.startsWith(o.label.toLowerCase())) return true;
      return false;
    })
    .map((o) => ({ name: o.label, id: o.id }));
}

/** Simple Levenshtein distance */
function editDistance(a: string, b: string): number {
  const m = a.length, n = b.length;
  const dp: number[][] = Array.from({ length: m + 1 }, () => Array(n + 1).fill(0));
  for (let i = 0; i <= m; i++) dp[i][0] = i;
  for (let j = 0; j <= n; j++) dp[0][j] = j;
  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      dp[i][j] = Math.min(
        dp[i - 1][j] + 1,
        dp[i][j - 1] + 1,
        dp[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1)
      );
    }
  }
  return dp[m][n];
}

export default function SearchableSelect({
  label,
  required,
  options,
  value,
  onChange,
  placeholder,
  onCreateNew,
  itemNoun = "item",
}: SearchableSelectProps) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [similarWarning, setSimilarWarning] = useState<SimilarMatch[]>([]);
  const [saving, setSaving] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const selectedOption = options.find((o) => o.id === value);

  // Filter options by search text
  const filtered = search
    ? options.filter(
        (o) =>
          o.label.toLowerCase().includes(search.toLowerCase()) ||
          (o.sublabel && o.sublabel.toLowerCase().includes(search.toLowerCase()))
      )
    : options;

  // Close on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
        setSearch("");
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  function handleSelect(id: string) {
    onChange(id);
    setOpen(false);
    setSearch("");
  }

  function startCreating() {
    setCreating(true);
    setNewName(search); // pre-fill with whatever they typed
    setOpen(false);
    setSearch("");
    setSimilarWarning([]);
  }

  function cancelCreating() {
    setCreating(false);
    setNewName("");
    setSimilarWarning([]);
  }

  function handleNewNameChange(name: string) {
    setNewName(name);
    const similar = findSimilar(name, options);
    setSimilarWarning(similar);
  }

  async function confirmCreate() {
    if (!onCreateNew || !newName.trim()) return;
    setSaving(true);
    try {
      const newId = await onCreateNew(newName.trim());
      if (newId) {
        onChange(newId);
      }
      setCreating(false);
      setNewName("");
      setSimilarWarning([]);
    } catch (err) {
      console.error("Failed to create:", err);
    } finally {
      setSaving(false);
    }
  }

  function handleUseSimilar(id: string) {
    onChange(id);
    setCreating(false);
    setNewName("");
    setSimilarWarning([]);
  }

  return (
    <div ref={containerRef} className="relative">
      <label className="block text-sm font-medium text-gray-700 mb-1">
        {label} {required && <span className="text-red-500">*</span>}
      </label>

      {!creating ? (
        <>
          {/* Trigger button — looks like a select */}
          <button
            type="button"
            onClick={() => {
              setOpen(!open);
              if (!open) setTimeout(() => inputRef.current?.focus(), 0);
            }}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm text-left focus:outline-none focus:ring-2 focus:ring-gray-900 focus:border-transparent bg-white flex items-center justify-between"
          >
            <span className={selectedOption ? "text-gray-900" : "text-gray-400"}>
              {selectedOption
                ? `${selectedOption.label}${selectedOption.sublabel ? ` (${selectedOption.sublabel})` : ""}`
                : placeholder || `Select ${itemNoun}...`}
            </span>
            <svg className="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>

          {/* Dropdown */}
          {open && (
            <div className="absolute z-10 mt-1 w-full bg-white border border-gray-200 rounded-lg shadow-lg max-h-64 overflow-hidden">
              {/* Search input */}
              <div className="p-2 border-b border-gray-100">
                <input
                  ref={inputRef}
                  type="text"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder={`Search ${itemNoun}s...`}
                  className="w-full px-2 py-1.5 text-sm border border-gray-200 rounded focus:outline-none focus:ring-1 focus:ring-gray-400"
                />
              </div>

              {/* Options list */}
              <div className="max-h-48 overflow-y-auto">
                {filtered.length === 0 && (
                  <div className="px-3 py-2 text-sm text-gray-400">No matches</div>
                )}
                {filtered.map((o) => (
                  <button
                    key={o.id}
                    type="button"
                    onClick={() => handleSelect(o.id)}
                    className={`w-full px-3 py-2 text-sm text-left hover:bg-gray-50 flex items-center justify-between ${
                      o.id === value ? "bg-gray-50 font-medium" : ""
                    }`}
                  >
                    <span>{o.label}</span>
                    {o.sublabel && <span className="text-gray-400 text-xs">{o.sublabel}</span>}
                  </button>
                ))}
              </div>

              {/* Add new */}
              {onCreateNew && (
                <div className="border-t border-gray-100">
                  <button
                    type="button"
                    onClick={startCreating}
                    className="w-full px-3 py-2 text-sm text-left text-gray-600 hover:bg-gray-50 flex items-center gap-1.5"
                  >
                    <span className="text-gray-400">+</span> Add new {itemNoun}
                  </button>
                </div>
              )}
            </div>
          )}
        </>
      ) : (
        /* Inline creation form */
        <div className="border border-gray-300 rounded-lg p-3 space-y-3 bg-gray-50">
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">
              New {itemNoun} name
            </label>
            <input
              type="text"
              value={newName}
              onChange={(e) => handleNewNameChange(e.target.value)}
              autoFocus
              placeholder={`e.g., Acme Corp`}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-gray-900 focus:border-transparent bg-white"
            />
          </div>

          {/* Similar name warning */}
          {similarWarning.length > 0 && (
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-3">
              <p className="text-sm font-medium text-amber-800 mb-1">
                Similar {itemNoun}s already exist:
              </p>
              <ul className="space-y-1">
                {similarWarning.map((s) => (
                  <li key={s.id} className="flex items-center justify-between text-sm">
                    <span className="text-amber-700 font-mono">{s.name}</span>
                    <button
                      type="button"
                      onClick={() => handleUseSimilar(s.id)}
                      className="text-xs text-amber-700 underline hover:text-amber-900"
                    >
                      Use this instead
                    </button>
                  </li>
                ))}
              </ul>
              <p className="text-xs text-amber-600 mt-2">
                If &ldquo;{newName.trim()}&rdquo; is genuinely different, go ahead and create it.
              </p>
            </div>
          )}

          <div className="flex gap-2">
            <button
              type="button"
              onClick={cancelCreating}
              className="px-3 py-1.5 text-xs font-medium text-gray-600 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={confirmCreate}
              disabled={!newName.trim() || saving}
              className="px-3 py-1.5 text-xs font-medium text-white bg-gray-900 rounded-lg hover:bg-gray-800 disabled:opacity-50"
            >
              {saving ? "Creating..." : `Create ${itemNoun}`}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
