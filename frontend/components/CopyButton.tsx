"use client";

import { useState } from "react";

export default function CopyButton({
  text,
  disabled,
  disabledTitle,
}: {
  text: string;
  disabled?: boolean;
  disabledTitle?: string;
}) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    if (disabled) return;
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback for non-HTTPS contexts
      const textarea = document.createElement("textarea");
      textarea.value = text;
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }

  // When disabled: visible (not hover-hidden) so the operator can see the
  // lock exists, and the verifier can see the operator can't run yet.
  const enabledClasses =
    "text-gray-400 hover:text-gray-700 hover:bg-gray-200 opacity-0 group-hover/cmd:opacity-100";
  const disabledClasses = "text-amber-500 cursor-not-allowed opacity-90";

  return (
    <button
      onClick={handleCopy}
      disabled={!!disabled}
      title={disabled ? (disabledTitle ?? "Copy disabled") : "Copy to clipboard"}
      className={`absolute top-1.5 right-1.5 p-1 rounded transition-opacity ${
        disabled ? disabledClasses : enabledClasses
      }`}
    >
      {disabled ? (
        // Lock icon when copy is gated
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 11c0-2.21 1.79-4 4-4s4 1.79 4 4v3M5 11h14a2 2 0 012 2v7a2 2 0 01-2 2H5a2 2 0 01-2-2v-7a2 2 0 012-2z" />
        </svg>
      ) : copied ? (
        <svg className="w-4 h-4 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
        </svg>
      ) : (
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
        </svg>
      )}
    </button>
  );
}
