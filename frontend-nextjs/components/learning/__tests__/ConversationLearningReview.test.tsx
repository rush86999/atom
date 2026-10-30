import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";

jest.mock("@/lib/conversation-learning-api", () => ({
  __esModule: true,
  listLearningCandidates: jest.fn(),
  getLearningCandidate: jest.fn(),
  createLearningCandidate: jest.fn(),
  resolveLearningDependency: jest.fn(),
  confirmLearningCandidate: jest.fn(),
  promoteLearningCandidate: jest.fn(),
  rejectLearningCandidate: jest.fn(),
}));

import {
  confirmLearningCandidate,
  createLearningCandidate,
  listLearningCandidates,
  promoteLearningCandidate,
  rejectLearningCandidate,
  resolveLearningDependency,
} from "@/lib/conversation-learning-api";
import { ConversationLearningReview } from "../ConversationLearningReview";

function payload(overrides: Record<string, any> = {}) {
  const review = {
    candidate_id: "lc-1",
    status: "needs_clarification",
    revision: 1,
    digest: "digest-1",
    review_ready: false,
    proposed_lesson: "Use the approved rates workbook for pricing.",
    where_it_applies: { applies_to: ["pricing"], context: {} },
    referenced_data_and_versions: [{
      reference: "the attached workbook",
      relation: "attachment",
      status: "ambiguous",
      basis: "multiple_attachments",
      resource_id: null,
      file_name: null,
      sheet: null,
      source_version: null,
      candidates: [{
        resource_id: "ds-1",
        dataset_name: "rates",
        original_file_name: "rates.xlsx",
        sheet: "Rates",
        source_version: "v1",
        status: "active",
      }],
    }],
    method_and_assumptions: {
      method_status: "explicit",
      method: {
        intended_outcome: "Price the order",
        operation: "multiply_sum",
        inputs: [
          { concept: "quantity", column: "Qty", unit: "units" },
          { concept: "unit_price", column: "Price", unit: "USD" },
        ],
        transformation: "quantity * unit_price",
        assumptions: ["Prices exclude tax"],
        exceptions: [],
      },
    },
    exceptions: [{ field: "Region", equals: "north" }],
    unresolved_questions: [{
      dependency_id: "dep-1",
      kind: "attachment",
      status: "ambiguous",
      question: "Which resource did 'the attached workbook' mean?",
      resource_id: null,
    }],
    supporting_messages: [{
      message_id: "m1",
      is_authority: true,
    }],
    authority: {
      message_id: "m1",
      excerpt: "Use the attached workbook",
    },
    confirmed_by: null,
    confirmed_revision: null,
    rejected_by: null,
    rejected_reason: "",
    invalidated_reason: "",
    promoted_entry_id: null,
    ...overrides,
  };
  return {
    candidate: { candidate_id: "lc-1", revision: review.revision },
    review,
    review_ready: review.review_ready,
    blocking: [],
  };
}

describe("ConversationLearningReview", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("shows the evidence chain and resolves a dependency before confirmation", async () => {
    (listLearningCandidates as jest.Mock).mockResolvedValue([payload()]);
    (resolveLearningDependency as jest.Mock).mockResolvedValue(payload({
      status: "review_ready",
      review_ready: true,
      unresolved_questions: [],
    }));
    (confirmLearningCandidate as jest.Mock).mockResolvedValue(payload({
      status: "confirmed",
      review_ready: true,
      unresolved_questions: [],
      confirmed_by: "owner",
      confirmed_revision: 1,
    }));
    (promoteLearningCandidate as jest.Mock).mockResolvedValue({
      lesson_id: "lesson-1",
      candidate: { candidate_id: "lc-1", status: "promoted" },
    });

    render(<ConversationLearningReview threadId="thread-1" reviewer="owner" />);

    expect(await screen.findByTestId("learning-proposed-lesson")).toHaveTextContent(
      "Use the approved rates workbook for pricing."
    );
    expect(screen.getByTestId("learning-applies-to")).toHaveTextContent("pricing");
    expect(screen.getByTestId("learning-references")).toHaveTextContent("rates.xlsx");
    expect(screen.getByTestId("learning-method")).toHaveTextContent("multiply_sum");
    expect(screen.getByTestId("learning-exceptions")).toHaveTextContent("north");
    expect(screen.getByTestId("learning-unresolved")).toHaveTextContent(
      "Which resource did 'the attached workbook' mean?"
    );
    expect(screen.getByTestId("learning-confirm")).toBeDisabled();

    fireEvent.change(screen.getByTestId("learning-resource-dep-1"), {
      target: { value: "ds-1" },
    });
    fireEvent.click(screen.getByTestId("learning-resolve-dep-1"));

    await waitFor(() => {
      expect(resolveLearningDependency).toHaveBeenCalledWith(
        "thread-1", "lc-1",
        expect.objectContaining({
          dependency_id: "dep-1",
          resource_id: "ds-1",
          confirmed_by: "owner",
        })
      );
    });
    expect(await screen.findByText("No unresolved questions.")).toBeInTheDocument();
    expect(screen.getByTestId("learning-confirm")).toBeEnabled();

    fireEvent.click(screen.getByTestId("learning-confirm"));
    await waitFor(() => {
      expect(confirmLearningCandidate).toHaveBeenCalledWith(
        "thread-1", "lc-1", "owner", 1);
    });
    expect(screen.getByTestId("learning-promote")).toBeEnabled();

    fireEvent.click(screen.getByTestId("learning-promote"));
    await waitFor(() => {
      expect(promoteLearningCandidate).toHaveBeenCalledWith(
        "thread-1", "lc-1", "owner", 1, "digest-1");
    });
  });

  it("rejects a proposal without promoting it", async () => {
    (listLearningCandidates as jest.Mock).mockResolvedValue([payload()]);
    (rejectLearningCandidate as jest.Mock).mockResolvedValue(payload({
      status: "rejected",
      rejected_by: "owner",
      rejected_reason: "Rejected in review",
    }));

    render(<ConversationLearningReview threadId="thread-1" reviewer="owner" />);
    fireEvent.click(await screen.findByTestId("learning-reject"));

    await waitFor(() => {
      expect(rejectLearningCandidate).toHaveBeenCalledWith(
        "thread-1", "lc-1", "owner", "Rejected in review");
    });
    expect(await screen.findByTestId("learning-notice")).toHaveTextContent(
      "No lesson was written."
    );
  });

  it("drafts a candidate with an explicit method", async () => {
    (listLearningCandidates as jest.Mock).mockResolvedValue([]);
    (createLearningCandidate as jest.Mock).mockResolvedValue(payload());

    render(<ConversationLearningReview threadId="thread-1" reviewer="owner" />);
    fireEvent.change(await screen.findByTestId("learning-agent-input"), {
      target: { value: "agent-1" },
    });
    fireEvent.change(screen.getByTestId("learning-lesson-input"), {
      target: { value: "Use net price." },
    });
    fireEvent.change(screen.getByTestId("learning-column-1"), {
      target: { value: "Price" },
    });
    fireEvent.click(screen.getByTestId("learning-draft-button"));

    await waitFor(() => {
      expect(createLearningCandidate).toHaveBeenCalledWith(
        expect.objectContaining({
          thread_id: "thread-1",
          agent_id: "agent-1",
          proposed_lesson: "Use net price.",
          method_status: "explicit",
          method: expect.objectContaining({
            operation: "sum",
            inputs: expect.arrayContaining([
              expect.objectContaining({ column: "Price", unit: "USD" }),
            ]),
          }),
        })
      );
    });
  });
});
