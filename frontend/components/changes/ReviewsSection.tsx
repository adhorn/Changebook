"use client";

import { Change, Review } from "@/lib/api";
import ReviewCard from "@/components/ReviewCard";

export default function ReviewsSection({
  change,
  reviews,
  currentUserName,
  isAuthor,
  addingReviewer,
  knownPeople,
  onOpenReviewerInput,
  onAddReviewer,
  onCancelAddReviewer,
  onReviewDecision,
}: {
  change: Change;
  reviews: Review[];
  currentUserName: string;
  isAuthor: boolean;
  addingReviewer: boolean;
  knownPeople: string[];
  onOpenReviewerInput: () => void;
  onAddReviewer: (name: string) => void;
  onCancelAddReviewer: () => void;
  onReviewDecision: (reviewId: string, decision: string, comment?: string) => void;
}) {
  const isDraft = change.status === "draft";

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-6 space-y-4">
      <h2 className="text-lg font-medium text-gray-900">Reviews</h2>

      {reviews.length === 0 ? (
        <p className="text-sm text-gray-500">
          No reviewers assigned yet.
        </p>
      ) : (
        <div className="space-y-2">
          {reviews.map((review) => (
            <ReviewCard
              key={review.id}
              review={review}
              canDecide={
                review.decision === "pending" &&
                change.status === "in_review" &&
                currentUserName === review.reviewer_name
              }
              onDecision={(decision, comment) =>
                onReviewDecision(review.id, decision, comment)
              }
            />
          ))}
        </div>
      )}

      {/* Assign reviewer — only in draft or in_review */}
      {(isDraft || change.status === "in_review") && isAuthor && (
        <>
          {!addingReviewer ? (
            <button
              onClick={onOpenReviewerInput}
              className="px-3 py-1.5 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
            >
              + Assign reviewer
            </button>
          ) : (
            <div className="flex items-center gap-2">
              <select
                defaultValue=""
                onChange={(e) => {
                  if (e.target.value) onAddReviewer(e.target.value);
                }}
                className="flex-1 px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-1 focus:ring-gray-900"
                autoFocus
              >
                <option value="" disabled>Select reviewer...</option>
                {knownPeople
                  .filter((p) => {
                    if (reviews.some((r) => r.reviewer_name === p)) return false;
                    if (p === change.author_name) return false;
                    return true;
                  })
                  .map((person) => (
                    <option key={person} value={person}>{person}</option>
                  ))}
              </select>
              <button
                onClick={onCancelAddReviewer}
                className="px-2 py-1.5 text-sm text-gray-500 hover:text-gray-700"
              >
                Cancel
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
