"use client";

import { useState } from "react";
import { Review } from "@/lib/api";

const DECISION_COLORS: Record<string, string> = {
  approved: "bg-green-100 text-green-700",
  blocked: "bg-red-100 text-red-700",
  changes_requested: "bg-yellow-100 text-yellow-700",
  pending: "bg-gray-100 text-gray-600",
};

export default function ReviewCard({
  review,
  canDecide,
  onDecision,
}: {
  review: Review;
  canDecide: boolean;
  onDecision: (decision: string, comment?: string) => void;
}) {
  const [comment, setComment] = useState("");
  const [showComment, setShowComment] = useState(false);

  return (
    <div className="p-3 border border-gray-200 rounded-lg">
      <div className="flex items-center justify-between">
        <div>
          <span className="text-sm font-medium text-gray-900">
            {review.reviewer_name}
          </span>
          <span
            className={`ml-2 inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${DECISION_COLORS[review.decision] || DECISION_COLORS.pending}`}
          >
            {review.decision}
          </span>
        </div>
        {canDecide && !showComment && (
          <div className="flex gap-1">
            <button
              onClick={() => onDecision("approved", undefined)}
              className="px-2 py-1 text-xs text-green-700 bg-green-50 rounded hover:bg-green-100"
            >
              Approve
            </button>
            <button
              onClick={() => setShowComment(true)}
              className="px-2 py-1 text-xs text-yellow-700 bg-yellow-50 rounded hover:bg-yellow-100"
            >
              Request Changes
            </button>
            <button
              onClick={() => setShowComment(true)}
              className="px-2 py-1 text-xs text-red-700 bg-red-50 rounded hover:bg-red-100"
            >
              Block
            </button>
          </div>
        )}
      </div>
      {review.comment && (
        <p className="text-xs text-gray-500 mt-1">{review.comment}</p>
      )}
      {showComment && canDecide && (
        <div className="mt-2 space-y-2">
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Comment (optional)..."
            rows={2}
            className="w-full px-2 py-1.5 border border-gray-300 rounded text-xs focus:outline-none focus:ring-1 focus:ring-gray-500"
            autoFocus
          />
          <div className="flex gap-1">
            <button
              onClick={() => {
                onDecision("changes_requested", comment || undefined);
              }}
              className="px-2 py-1 text-xs text-yellow-700 bg-yellow-50 rounded hover:bg-yellow-100"
            >
              Request Changes
            </button>
            <button
              onClick={() => {
                onDecision("blocked", comment || undefined);
              }}
              className="px-2 py-1 text-xs text-red-700 bg-red-50 rounded hover:bg-red-100"
            >
              Block
            </button>
            <button
              onClick={() => setShowComment(false)}
              className="px-2 py-1 text-xs text-gray-500 hover:text-gray-700"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
