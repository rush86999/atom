/**
 * Match-confidence reviewer UI helpers (Phase 5 of MATCH_CONFIDENCE.md).
 *
 * Pure functions extracted from MatchConfidenceReviewer.tsx for testability.
 * The component itself lives at components/canvas/MatchConfidenceReviewer.tsx
 * and consumes these helpers.
 */
import type {
  MatchConfidence,
  MatchLevel,
  SelectorCandidate,
} from "@/components/canvas/types";

export type BadgeColor = "green" | "yellow" | "red";

/**
 * Map a MatchLevel to a badge color for the reviewer UI.
 * - high → green (proceeds automatically)
 * - partial → yellow (LLM tiebreaker or human review)
 * - ambiguous → red (human review required)
 */
export function levelToBadgeColor(level: MatchLevel): BadgeColor {
  switch (level) {
    case "high":
      return "green";
    case "partial":
      return "yellow";
    case "ambiguous":
      return "red";
  }
}

/**
 * Order candidates for reviewer display: chosen candidate first,
 * then the rest in original order. When chosen_index is -1 (no LLM
 * decision), preserves original order.
 */
export function orderCandidatesForReview(
  mc: MatchConfidence,
): SelectorCandidate[] {
  if (!mc.candidates || mc.candidates.length === 0) {
    return [];
  }
  if (mc.chosen_index < 0 || mc.chosen_index >= mc.candidates.length) {
    return [...mc.candidates];
  }
  const chosen = mc.candidates[mc.chosen_index];
  const rest = mc.candidates.filter((_, i) => i !== mc.chosen_index);
  return [chosen, ...rest];
}

/**
 * Build the modifications payload sent to /api/v1/proposals/{id}/approve
 * when a reviewer overrides the selector. Returns null for empty input
 * (component should disable the submit button in that case).
 */
export function buildModificationPayload(
  newSelector: string,
): { selector: string } | null {
  const trimmed = newSelector.trim();
  if (!trimmed) {
    return null;
  }
  return { selector: trimmed };
}
