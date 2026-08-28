/**
 * Tests for match-confidence reviewer UI helpers (Phase 5).
 *
 * Verifies the level → badge-color mapping, the chosen-candidate-first
 * rendering for LLM-tiebroken partials, and the modify-input path.
 */
import type { SelectorCandidate, MatchConfidence } from "@/components/canvas/types";
import {
  levelToBadgeColor,
  orderCandidatesForReview,
  buildModificationPayload,
} from "../matchConfidence";

describe("levelToBadgeColor", () => {
  it("renders green for high", () => {
    expect(levelToBadgeColor("high")).toBe("green");
  });

  it("renders yellow for partial", () => {
    expect(levelToBadgeColor("partial")).toBe("yellow");
  });

  it("renders red for ambiguous", () => {
    expect(levelToBadgeColor("ambiguous")).toBe("red");
  });
});

describe("orderCandidatesForReview", () => {
  const c1: SelectorCandidate = {
    selector: "button.a", match_count: 1, is_text_only: false,
    appeared_after_ms: 0, tag_hint: "BUTTON", attributes: {},
  };
  const c2: SelectorCandidate = {
    selector: "button.b", match_count: 1, is_text_only: false,
    appeared_after_ms: 0, tag_hint: "BUTTON", attributes: {},
  };

  it("partial with LLM tiebreaker renders chosen candidate first", () => {
    const mc: MatchConfidence = {
      level: "partial", score: 0.70,
      rationale: "LLM tiebreak: second is submit",
      candidates: [c1, c2], chosen_index: 1,
    };
    const ordered = orderCandidatesForReview(mc);
    expect(ordered[0].selector).toBe("button.b");
    expect(ordered[1].selector).toBe("button.a");
  });

  it("ambiguous with chosen_index=-1 preserves original order", () => {
    const mc: MatchConfidence = {
      level: "ambiguous", score: 0.0,
      rationale: "3 matches",
      candidates: [c1, c2], chosen_index: -1,
    };
    const ordered = orderCandidatesForReview(mc);
    expect(ordered[0].selector).toBe("button.a");
  });

  it("out-of-range chosen_index preserves original order", () => {
    const mc: MatchConfidence = {
      level: "partial", score: 0.70,
      rationale: "stale index",
      candidates: [c1, c2], chosen_index: 5,
    };
    const ordered = orderCandidatesForReview(mc);
    expect(ordered[0].selector).toBe("button.a");
    expect(ordered[1].selector).toBe("button.b");
  });

  it("returns an empty array when no candidates exist", () => {
    const mc = {
      level: "high", score: 0.95,
      rationale: "single match",
      candidates: [],
    } as unknown as MatchConfidence;
    expect(orderCandidatesForReview(mc)).toEqual([]);
  });
});

describe("buildModificationPayload", () => {
  it("modify button submits overridden selector", () => {
    const payload = buildModificationPayload("button.better");
    expect(payload).toEqual({ selector: "button.better" });
  });

  it("empty modification rejected", () => {
    const payload = buildModificationPayload("");
    expect(payload).toBeNull();
  });
});
