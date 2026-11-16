/**
 * ConversationLearningReview correction contract.
 *
 * Goal 6 requires correcting teaching in place. These tests pin the visible
 * edit/save/cancel path to the existing candidate: only changed fields are
 * sent, the server's returned revision/status are displayed, confirmation is
 * cleared, and a stale tab surfaces the endpoint's conflict instead of
 * overwriting a newer revision.
 */
import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ConversationLearningReview } from "@/components/learning/ConversationLearningReview";
import * as learningApi from "@/lib/conversation-learning-api";

jest.mock("@/lib/conversation-learning-api", () => ({
  listLearningEmployees: jest.fn(),
  listLearningCandidates: jest.fn(),
  getLearningCandidate: jest.fn(),
  createLearningCandidate: jest.fn(),
  reviseLearningCandidate: jest.fn(),
  resolveLearningDependency: jest.fn(),
  confirmLearningCandidate: jest.fn(),
  promoteLearningCandidate: jest.fn(),
  applyLearningCandidate: jest.fn(),
  rejectLearningCandidate: jest.fn(),
}));

const listEmployees = learningApi.listLearningEmployees as jest.Mock;
const listCandidates = learningApi.listLearningCandidates as jest.Mock;
const reviseCandidate = learningApi.reviseLearningCandidate as jest.Mock;

function review(overrides: Record<string, any> = {}) {
  return {
    candidate_id: "cand/1",
    status: "review_ready",
    revision: 1,
    digest: "digest-1",
    review_ready: true,
    proposed_lesson: "Use the approved rates workbook.",
    where_it_applies: {
      applies_to: ["pricing"],
      context: { customer: "Acme" },
    },
    artifact_and_protocol: {
      format_spec: { greeting: "Dear colleague," },
      conditions: { region: "north" },
      decision_options: ["send", "hold"],
    },
    referenced_data_and_versions: [],
    method_and_assumptions: {
      method_status: "explicit",
      method: {
        intended_outcome: "Price the order",
        operation: "multiply_sum",
        inputs: [
          { concept: "quantity", column: "Qty", unit: "units" },
          { concept: "unit_price", column: "Price", unit: "USD" },
        ],
        output_unit: "USD",
        transformation: "quantity * unit_price",
        rounding: { places: 2, stage: "final" },
        assumptions: ["Prices exclude tax"],
      },
    },
    exceptions: [],
    unresolved_questions: [],
    supporting_messages: [{ message_id: "m1", is_authority: true }],
    authority: { message_id: "m1", excerpt: "Use the approved workbook" },
    confirmed_by: null,
    confirmed_revision: null,
    rejected_by: null,
    rejected_reason: "",
    invalidated_reason: "",
    promoted_entry_id: null,
    ...overrides,
  };
}

function payload(overrides: Record<string, any> = {}) {
  return {
    candidate: {},
    review: review(overrides),
    review_ready: true,
    blocking: [],
  };
}

async function openEditor() {
  render(
    <ConversationLearningReview
      threadId="thread-1"
      sourceKind="email"
      reviewer="owner"
    />,
  );
  fireEvent.click(await screen.findByTestId("learning-revise"));
  return screen.getByTestId("learning-edit-form");
}

describe("ConversationLearningReview correction", () => {
  beforeEach(() => {
    listEmployees.mockResolvedValue([{
      id: "agent-1",
      name: "Learning Agent",
      status: "supervised",
      category: "sales",
      role: "sales_assistant",
    }]);
    listCandidates.mockResolvedValue([payload({
      status: "confirmed",
      confirmed_by: "owner",
      confirmed_revision: 1,
    })]);
  });

  test("saves only edited fields against the visible revision and shows the server result", async () => {
    reviseCandidate.mockResolvedValue(payload({
      status: "review_ready",
      revision: 2,
      digest: "digest-2",
      proposed_lesson: "Use the corrected rates workbook.",
    }));

    await openEditor();
    fireEvent.change(screen.getByTestId("learning-edit-lesson"), {
      target: { value: "Use the corrected rates workbook." },
    });
    fireEvent.click(screen.getByTestId("learning-revise-save"));

    await waitFor(() => expect(reviseCandidate).toHaveBeenCalledTimes(1));
    const [threadId, candidateId, body, sourceKind] =
      reviseCandidate.mock.calls[0];
    expect(threadId).toBe("thread-1");
    expect(candidateId).toBe("cand/1");
    expect(sourceKind).toBe("email");
    // Unedited method/scope/format fields are omitted, so the server keeps
    // them rather than receiving a reconstructed copy.
    expect(body).toEqual({
      proposed_lesson: "Use the corrected rates workbook.",
      expected_revision: 1,
      expected_status: "confirmed",
    });

    expect(screen.getByTestId("learning-proposed-lesson")).toHaveTextContent(
      "Use the corrected rates workbook.");
    expect(screen.getByText("revision 2")).toBeInTheDocument();
    expect(screen.getByTestId("learning-notice")).toHaveTextContent(
      "Revision 2 saved");
    expect(screen.getByTestId("learning-notice")).toHaveTextContent(
      "confirmation was cleared");
    // Fresh confirmation is required before promotion.
    expect(screen.getByTestId("learning-promote")).toBeDisabled();
    expect(screen.getByTestId("learning-confirm")).toBeEnabled();
    expect(screen.queryByTestId("learning-edit-form")).not.toBeInTheDocument();
  });

  test("cancel leaves the review untouched and sends no request", async () => {
    await openEditor();
    fireEvent.change(screen.getByTestId("learning-edit-lesson"), {
      target: { value: "Abandoned correction." },
    });
    fireEvent.click(screen.getByTestId("learning-revise-cancel"));

    expect(reviseCandidate).not.toHaveBeenCalled();
    expect(screen.queryByTestId("learning-edit-form")).not.toBeInTheDocument();
    expect(screen.getByTestId("learning-proposed-lesson")).toHaveTextContent(
      "Use the approved rates workbook.");
    expect(screen.getByText("revision 1")).toBeInTheDocument();
    expect(screen.getByTestId("learning-notice")).toHaveTextContent(
      "Nothing was saved");
  });

  test("a stale save surfaces the endpoint conflict and keeps the edit open", async () => {
    reviseCandidate.mockRejectedValue({
      response: { data: { detail: "candidate_revision_changed" } },
    });

    await openEditor();
    fireEvent.change(screen.getByTestId("learning-edit-lesson"), {
      target: { value: "Stale tab overwrite." },
    });
    fireEvent.click(screen.getByTestId("learning-revise-save"));

    await waitFor(() => expect(screen.getByTestId("learning-error"))
      .toHaveTextContent("candidate_revision_changed"));
    expect(screen.getByTestId("learning-edit-form")).toBeInTheDocument();
    expect(screen.getByText("revision 1")).toBeInTheDocument();
    expect(screen.getByTestId("learning-proposed-lesson")).toHaveTextContent(
      "Use the approved rates workbook.");
  });

  test("a method edit merges into the existing method without dropping assumptions", async () => {
    reviseCandidate.mockResolvedValue(payload({
      revision: 2,
      proposed_lesson: "Use the approved rates workbook.",
    }));

    await openEditor();
    fireEvent.change(screen.getByTestId("learning-edit-column-2"), {
      target: { value: "NetPrice" },
    });
    fireEvent.click(screen.getByTestId("learning-revise-save"));

    await waitFor(() => expect(reviseCandidate).toHaveBeenCalledTimes(1));
    const body = reviseCandidate.mock.calls[0][2];
    expect(body.expected_revision).toBe(1);
    expect(body.expected_status).toBe("confirmed");
    expect(body.method.inputs[1]).toEqual({
      concept: "unit_price",
      column: "NetPrice",
      unit: "USD",
      unit_required: true,
    });
    expect(body.method.assumptions).toEqual(["Prices exclude tax"]);
    expect(body.method.rounding).toEqual({ places: 2, stage: "final" });
    expect(body.method.transformation).toBe("quantity * unit_price");
    expect(body).not.toHaveProperty("context");
    expect(body).not.toHaveProperty("applies_to");
    expect(body).not.toHaveProperty("format_spec");
    expect(body).not.toHaveProperty("conditions");
    expect(body).not.toHaveProperty("decision_options");
  });

  test("correcting a promoted lesson removes the apply block until re-promotion", async () => {
    listCandidates.mockResolvedValue([payload({
      status: "promoted",
      promoted_entry_id: "entry-1",
      confirmed_by: "owner",
      confirmed_revision: 1,
    })]);
    reviseCandidate.mockResolvedValue(payload({
      status: "review_ready",
      revision: 2,
      proposed_lesson: "Use the corrected rates workbook.",
    }));

    render(
      <ConversationLearningReview threadId="thread-1" sourceKind="email" />,
    );
    expect(await screen.findByTestId("learning-apply")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("learning-revise"));
    fireEvent.change(screen.getByTestId("learning-edit-lesson"), {
      target: { value: "Use the corrected rates workbook." },
    });
    fireEvent.click(screen.getByTestId("learning-revise-save"));

    await waitFor(() => expect(screen.getByText("revision 2"))
      .toBeInTheDocument());
    expect(screen.queryByTestId("learning-apply")).not.toBeInTheDocument();
    expect(screen.getByTestId("learning-promote")).toBeDisabled();
    expect(screen.getByTestId("learning-notice")).toHaveTextContent(
      "confirmation was cleared");
  });

  test("rejected candidates expose no correction control", async () => {
    listCandidates.mockResolvedValue([payload({
      status: "rejected",
      review_ready: false,
      rejected_by: "owner",
    })]);

    render(
      <ConversationLearningReview threadId="thread-1" sourceKind="email" />,
    );
    expect(await screen.findByTestId("learning-revise")).toBeDisabled();
  });
});
