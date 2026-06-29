/**
 * MatchConfidenceReviewer — Phase 5 reviewer UI component.
 *
 * Renders when a proposal with selector_candidates is pending review.
 * Shows the match rationale, candidate list with score badges, and an
 * optional "Modify selector" input that posts to the proposal approve
 * endpoint with modifications={selector: <new>}.
 *
 * Props mirror the proposal_data shape stored by
 * ProposalService.create_action_proposal when gated by
 * _maybe_gate_with_proposal in tools/browser_tool.py.
 */
import React, { useState } from "react";
import type { MatchConfidence, SelectorCandidate } from "./types";
import {
  levelToBadgeColor,
  orderCandidatesForReview,
  buildModificationPayload,
} from "@/lib/matchConfidence";

export interface MatchConfidenceReviewerProps {
  proposalId: string;
  matchConfidence: MatchConfidence;
  onApprove: (proposalId: string, modifications?: { selector: string }) => void;
  onReject: (proposalId: string, reason: string) => void;
}

const BADGE_COLOR_CLASS: Record<string, string> = {
  green: "bg-green-100 text-green-800 border-green-300",
  yellow: "bg-yellow-100 text-yellow-800 border-yellow-300",
  red: "bg-red-100 text-red-800 border-red-300",
};

export function MatchConfidenceReviewer({
  proposalId,
  matchConfidence,
  onApprove,
  onReject,
}: MatchConfidenceReviewerProps) {
  const [modifyValue, setModifyValue] = useState<string>(
    matchConfidence.candidates[matchConfidence.chosen_index]?.selector ?? "",
  );
  const [rejectReason, setRejectReason] = useState<string>("");
  const [showModify, setShowModify] = useState<boolean>(
    matchConfidence.level !== "high",
  );

  const badgeColor = levelToBadgeColor(matchConfidence.level);
  const orderedCandidates = orderCandidatesForReview(matchConfidence);

  const handleApprove = () => {
    const payload = showModify ? buildModificationPayload(modifyValue) : null;
    if (showModify && !payload) {
      return; // invalid input — button disabled
    }
    onApprove(proposalId, payload ?? undefined);
  };

  return (
    <div
      className="border rounded-lg p-4 space-y-4"
      data-testid={`match-confidence-reviewer-${proposalId}`}
    >
      <div className="flex items-center gap-2">
        <span
          className={`inline-flex items-center px-2 py-1 rounded text-xs font-semibold border ${BADGE_COLOR_CLASS[badgeColor]}`}
          aria-label={`match-level-${matchConfidence.level}`}
        >
          {matchConfidence.level.toUpperCase()} · {matchConfidence.score.toFixed(2)}
        </span>
        <span className="text-sm text-gray-700">{matchConfidence.rationale}</span>
      </div>

      {orderedCandidates.length > 0 && (
        <ul className="text-sm space-y-1" aria-label="candidate-list">
          {orderedCandidates.map((c: SelectorCandidate, i: number) => (
            <li
              key={`${c.selector}-${i}`}
              className="flex items-center gap-2 font-mono"
            >
              <span className="text-xs text-gray-500">
                {i === 0 && matchConfidence.chosen_index >= 0 ? "★" : `${i + 1}.`}
              </span>
              <code className="bg-gray-100 px-1 rounded">{c.selector}</code>
              <span className="text-xs text-gray-500">
                ({c.match_count} match{c.match_count !== 1 ? "es" : ""})
              </span>
            </li>
          ))}
        </ul>
      )}

      {showModify && (
        <label className="block text-sm space-y-1">
          <span className="font-medium">Modify selector:</span>
          <input
            type="text"
            value={modifyValue}
            onChange={(e) => setModifyValue(e.target.value)}
            className="w-full border rounded px-2 py-1 font-mono text-sm"
            placeholder="Enter a more specific selector"
            aria-label="modify-selector-input"
          />
        </label>
      )}

      <div className="flex gap-2">
        <button
          type="button"
          onClick={handleApprove}
          className="px-3 py-1 rounded bg-blue-600 text-white text-sm disabled:opacity-50"
          disabled={showModify && !buildModificationPayload(modifyValue)}
        >
          {showModify ? "Approve with modification" : "Approve"}
        </button>
        <button
          type="button"
          onClick={() => onReject(proposalId, rejectReason || "Reviewer rejected selector")}
          className="px-3 py-1 rounded bg-gray-200 text-gray-800 text-sm"
        >
          Reject
        </button>
        <button
          type="button"
          onClick={() => setShowModify((s) => !s)}
          className="px-3 py-1 rounded bg-gray-100 text-gray-700 text-sm"
        >
          {showModify ? "Cancel modification" : "Modify selector"}
        </button>
      </div>

      {!showModify && (
        <input
          type="text"
          value={rejectReason}
          onChange={(e) => setRejectReason(e.target.value)}
          className="w-full border rounded px-2 py-1 text-sm"
          placeholder="Optional rejection reason"
          aria-label="reject-reason-input"
        />
      )}
    </div>
  );
}

export default MatchConfidenceReviewer;
