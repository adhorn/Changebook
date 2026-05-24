"use client";

import { useState, useEffect, useRef } from "react";
import { MOCK_USERS, getCurrentUser, setCurrentUser, type MockUser } from "@/lib/auth";

export default function UserSwitcher() {
  const [user, setUser] = useState<MockUser>(MOCK_USERS[0]);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setUser(getCurrentUser());

    function handleUserChanged(e: Event) {
      setUser((e as CustomEvent).detail);
    }
    window.addEventListener("user-changed", handleUserChanged);
    return () => window.removeEventListener("user-changed", handleUserChanged);
  }, []);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  function handleSelect(u: MockUser) {
    setCurrentUser(u);
    setUser(u);
    setOpen(false);
    // Reload to re-fetch data with new identity
    window.location.reload();
  }

  // Initials for avatar
  const initials = user.name
    .split(" ")
    .map((w) => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 px-2 py-1 rounded-lg hover:bg-gray-100 transition-colors"
      >
        <span className="w-7 h-7 rounded-full bg-gray-900 text-white text-xs font-medium flex items-center justify-center">
          {initials}
        </span>
        <span className="text-sm text-gray-700">{user.name}</span>
        <svg className="w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && (
        <div className="absolute right-0 mt-1 w-56 bg-white border border-gray-200 rounded-lg shadow-lg z-50">
          <div className="px-3 py-2 border-b border-gray-100">
            <p className="text-xs text-gray-500 font-medium">Switch user (dev mode)</p>
          </div>
          {MOCK_USERS.map((u) => (
            <button
              key={u.email}
              onClick={() => handleSelect(u)}
              className={`w-full text-left px-3 py-2 text-sm hover:bg-gray-50 flex items-center gap-3 ${
                u.email === user.email ? "bg-gray-50" : ""
              }`}
            >
              <span className="w-7 h-7 rounded-full bg-gray-200 text-gray-700 text-xs font-medium flex items-center justify-center shrink-0">
                {u.name.split(" ").map((w) => w[0]).join("").slice(0, 2).toUpperCase()}
              </span>
              <div className="min-w-0">
                <p className="font-medium text-gray-900 truncate">
                  {u.name}
                  {u.email === user.email && (
                    <span className="ml-1 text-xs text-green-600">active</span>
                  )}
                </p>
                <p className="text-xs text-gray-500">{u.role}</p>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
