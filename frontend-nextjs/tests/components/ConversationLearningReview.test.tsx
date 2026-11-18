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
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ConversationLearningReview } from "@/components/learning/ConversationLearningReview";
import * as learningApi from "@/lib/conversation-learning-api";

jest.mock("@/lib/conversation-learning-api", () => ({
  listLearningEmployees: jest.fn(),
  listLearningCandidates: jest.fn(),
  getLearningCandidate: jest.fn(),
  getLearningCandidateHistory: jest.fn(),
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
const historyFor = learningApi.getLearningCandidateHistory as jest.Mock;

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

function snapshot(revision: number, lesson: string) {
  return {
    revision,
    status: "review_ready",
    recorded_digest: `digest-${revision}`,
    proposed_lesson: lesson,
    method_status: "explicit",
    applies_to: ["pricing"],
    decision_options: [],
    context: {},
    format_spec: {},
    conditions: {},
    method: {},
  };
}

function historyPage(overrides: Record<string, any> = {}) {
  return {
    thread_id: "thread-1",
    source_kind: "email",
    candidate_id: "cand/1",
    events: [
      {
        event_id: "ev-2",
        kind: "learning_candidate_revised",
        recorded_at: "2026-11-17T10:00:00+00:00",
        revision: 2,
        status: "review_ready",
        recorded_digest: "digest-2",
        actor: "owner@example.com",
        actor_role: "author",
        reason: "Wrong workbook was cited.",
        reason_recorded: true,
        changed_fields: ["proposed_lesson"],
        before: snapshot(1, "Use the approved rates workbook."),
        after: snapshot(2, "Use the corrected rates workbook."),
      },
      {
        event_id: "ev-1",
        kind: "learning_candidate_created",
        recorded_at: "2026-11-17T09:00:00+00:00",
        revision: 1,
        status: "confirmed",
        recorded_digest: "digest-1",
        actor: null,
        actor_role: "author",
        reason: null,
        reason_recorded: false,
        changed_fields: [],
        before: null,
        after: null,
      },
    ],
    coverage: {
      history_complete: true,
      scan_limit: 2000,
      scan_truncated: false,
      out_of_scope_events_excluded: 0,
      total_events: 2,
      returned: 2,
      limit: 10,
      offset: 0,
      has_more: false,
    },
    signatures: { present: false, detail: "no signature mechanism" },
    read_only: true,
    ...overrides,
  };
}

function historyPageWithReason(reason: string, candidateId = "cand/1") {
  const page = historyPage();
  return {
    ...page,
    candidate_id: candidateId,
    events: [{
      ...page.events[0],
      event_id: `ev-${reason}`,
      reason,
      reason_recorded: true,
    }],
    coverage: {
      ...page.coverage,
      total_events: 1,
      returned: 1,
    },
  };
}

function emptyHistoryPage(candidateId = "cand/2") {
  const page = historyPage();
  return {
    ...page,
    candidate_id: candidateId,
    events: [],
    coverage: {
      ...page.coverage,
      total_events: 0,
      returned: 0,
    },
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
    jest.clearAllMocks();
    historyFor.mockResolvedValue(historyPage());
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

  test("shows every proposal with its status instead of hiding all but the first", async () => {
    listCandidates.mockResolvedValue([
      payload({ candidate_id: "cand/1", status: "review_ready" }),
      payload({
        candidate_id: "cand/2",
        status: "rejected",
        review_ready: false,
        proposed_lesson: "Use the superseded vendor rate.",
        rejected_by: "dana@example.com",
        rejected_reason: "Rates expired in March.",
      }),
    ]);

    render(
      <ConversationLearningReview threadId="thread-1" sourceKind="email" />,
    );

    const select = await screen.findByTestId("learning-candidate-select");
    expect((select as HTMLSelectElement).value).toBe("cand/1");
    const options = Array.from(
      (select as HTMLSelectElement).options).map((option) => option.value);
    expect(options).toEqual(["cand/1", "cand/2"]);
    expect(screen.getByText(/rejected · revision 1/)).toBeInTheDocument();

    fireEvent.change(select, { target: { value: "cand/2" } });

    expect(await screen.findByTestId("learning-proposed-lesson"))
      .toHaveTextContent("Use the superseded vendor rate.");
    expect(screen.getByTestId("learning-rejected-reason"))
      .toHaveTextContent("Rates expired in March.");
    expect(screen.getByTestId("learning-revise")).toBeDisabled();
  });

  test("opens the stored revision history only on request and reports it truthfully", async () => {
    render(
      <ConversationLearningReview
        threadId="thread-1"
        sourceKind="email"
        reviewer="owner"
      />,
    );
    expect(await screen.findByTestId("learning-proposed-lesson"))
      .toBeInTheDocument();
    // The primary review makes no history request.
    expect(historyFor).not.toHaveBeenCalled();

    fireEvent.click(screen.getByTestId("learning-history-toggle"));

    await waitFor(() => expect(historyFor).toHaveBeenCalledTimes(1));
    expect(historyFor.mock.calls[0]).toEqual([
      "thread-1", "cand/1", { limit: 10, offset: 0 }, "email"]);

    const events = await screen.findAllByTestId("learning-history-event");
    expect(events).toHaveLength(2);
    expect(events[0]).toHaveTextContent("Revision saved");
    expect(events[0]).toHaveTextContent("Author: owner@example.com");
    expect(events[0]).toHaveTextContent("Reason: Wrong workbook was cited.");
    expect(screen.getAllByTestId("learning-history-diff")[0])
      .toHaveTextContent("Before: Use the approved rates workbook.");
    // No reason was stored on the creation event; none is invented.
    expect(events[1]).toHaveTextContent("Reason: not recorded");
    expect(events[1]).toHaveTextContent("Actor not recorded");
    expect(screen.getByTestId("learning-history-coverage"))
      .toHaveTextContent("Showing 2 of 2 recorded entries.");
    expect(screen.getByTestId("learning-history-panel"))
      .toHaveTextContent("they are not signed");
    expect(screen.queryByTestId("learning-history-more"))
      .not.toBeInTheDocument();
  });

  test("loads older stored entries on request and appends them once", async () => {
    historyFor.mockResolvedValueOnce(historyPage({
      coverage: {
        ...historyPage().coverage,
        history_complete: false,
        total_events: 3,
        returned: 2,
        has_more: true,
      },
    }));
    historyFor.mockResolvedValueOnce(historyPage({
      events: [{
        event_id: "ev-0",
        kind: "learning_candidate_rejected",
        recorded_at: "2026-11-16T09:00:00+00:00",
        revision: 1,
        status: "rejected",
        recorded_digest: "digest-0",
        actor: "dana@example.com",
        actor_role: "reviewer",
        reason: "Not applicable.",
        reason_recorded: true,
        changed_fields: [],
        before: null,
        after: null,
      }],
      coverage: {
        ...historyPage().coverage,
        history_complete: false,
        total_events: 3,
        returned: 1,
        offset: 2,
        has_more: false,
      },
    }));

    render(
      <ConversationLearningReview threadId="thread-1" sourceKind="email" />,
    );
    fireEvent.click(await screen.findByTestId("learning-history-toggle"));
    await waitFor(() => expect(historyFor).toHaveBeenCalledTimes(1));

    fireEvent.click(await screen.findByTestId("learning-history-more"));

    await waitFor(() => expect(historyFor).toHaveBeenCalledTimes(2));
    expect(historyFor.mock.calls[1]).toEqual([
      "thread-1", "cand/1", { limit: 10, offset: 2 }, "email"]);
    expect(await screen.findAllByTestId("learning-history-event"))
      .toHaveLength(3);
    expect(screen.getByTestId("learning-history-coverage"))
      .toHaveTextContent("Showing 3 of 3 recorded entries.");
    expect(screen.queryByTestId("learning-history-more"))
      .not.toBeInTheDocument();
  });

  test("sends the optional reason only when the reviewer typed one", async () => {
    reviseCandidate.mockResolvedValue(payload({
      revision: 2,
      proposed_lesson: "Use the corrected rates workbook.",
    }));

    await openEditor();
    fireEvent.change(screen.getByTestId("learning-edit-lesson"), {
      target: { value: "Use the corrected rates workbook." },
    });
    fireEvent.change(screen.getByTestId("learning-edit-reason"), {
      target: { value: "  Superseded by the April workbook.  " },
    });
    fireEvent.click(screen.getByTestId("learning-revise-save"));

    await waitFor(() => expect(reviseCandidate).toHaveBeenCalledTimes(1));
    expect(reviseCandidate.mock.calls[0][2].reason).toBe(
      "Superseded by the April workbook.");
    expect(screen.getByTestId("learning-notice"))
      .toHaveTextContent("The reason was recorded with this revision.");
  });

  test("a reason without a content change is not saved as a revision", async () => {
    await openEditor();
    fireEvent.change(screen.getByTestId("learning-edit-reason"), {
      target: { value: "No content change." },
    });
    fireEvent.click(screen.getByTestId("learning-revise-save"));

    expect(reviseCandidate).not.toHaveBeenCalled();
    expect(screen.getByTestId("learning-notice"))
      .toHaveTextContent("The reason is optional");
    expect(screen.getByTestId("learning-edit-form")).toBeInTheDocument();
  });

  test("shows invalidated and outdated-evidence state plainly", async () => {
    listCandidates.mockResolvedValue([payload({
      status: "invalidated",
      review_ready: false,
      invalidated_reason: "source_changed",
      referenced_data_and_versions: [{
        reference: "rates.xlsx",
        relation: "attachment",
        status: "stale",
        basis: "resource_stale",
        resource_id: "ds-1",
        file_name: "rates.xlsx",
        sheet: null,
        source_version: "v1",
        candidates: [],
      }],
    })]);

    render(
      <ConversationLearningReview threadId="thread-1" sourceKind="email" />,
    );

    expect(await screen.findByTestId("learning-invalidated-reason"))
      .toHaveTextContent("the source conversation changed");
    expect(screen.getByTestId("learning-evidence-stale"))
      .toHaveTextContent("rates.xlsx (stale)");
  });

  test("ROOT deferred history cannot appear under another candidate", async () => {
    let resolveA: (value: any) => void = () => {};
    historyFor.mockImplementationOnce(() => new Promise((resolve) => {
      resolveA = resolve;
    }));
    historyFor.mockResolvedValue(historyPage({ candidate_id: "cand/2", events: [] }));
    listCandidates.mockResolvedValue([
      payload(),
      payload({ candidate_id: "cand/2", proposed_lesson: "SECOND CANDIDATE" }),
    ]);
    render(<ConversationLearningReview threadId="thread-1" sourceKind="email" />);
    fireEvent.click(await screen.findByTestId("learning-history-toggle"));
    await waitFor(() => expect(historyFor).toHaveBeenCalledTimes(1));
    fireEvent.change(screen.getByTestId("learning-candidate-select"), {
      target: { value: "cand/2" },
    });
    await waitFor(() => expect(screen.getByTestId("learning-proposed-lesson"))
      .toHaveTextContent("SECOND CANDIDATE"));
    fireEvent.click(screen.getByTestId("learning-history-toggle"));
    await act(async () => {
      resolveA(historyPage());
    });
    await waitFor(() => expect(screen.queryByText(/Wrong workbook was cited/))
      .not.toBeInTheDocument());
    expect(historyFor.mock.calls.some((call: any[]) => call[1] === "cand/2"))
      .toBe(true);
  });

  test("the newly selected candidate shows its own history while the first is pending", async () => {
    let resolveA: (value: any) => void = () => {};
    historyFor.mockImplementationOnce(() => new Promise((resolve) => {
      resolveA = resolve;
    }));
    historyFor.mockResolvedValueOnce(
      historyPageWithReason("B recorded history.", "cand/2"));
    listCandidates.mockResolvedValue([
      payload(),
      payload({ candidate_id: "cand/2", proposed_lesson: "SECOND CANDIDATE" }),
    ]);
    render(<ConversationLearningReview threadId="thread-1" sourceKind="email" />);
    fireEvent.click(await screen.findByTestId("learning-history-toggle"));
    await waitFor(() => expect(historyFor).toHaveBeenCalledTimes(1));

    fireEvent.change(screen.getByTestId("learning-candidate-select"), {
      target: { value: "cand/2" },
    });
    await waitFor(() => expect(screen.getByTestId("learning-proposed-lesson"))
      .toHaveTextContent("SECOND CANDIDATE"));
    fireEvent.click(screen.getByTestId("learning-history-toggle"));

    expect(await screen.findByText(/B recorded history/)).toBeInTheDocument();
    expect(historyFor.mock.calls[1][1]).toBe("cand/2");
    await act(async () => {
      resolveA(historyPage());
    });
    expect(screen.getByText(/B recorded history/)).toBeInTheDocument();
    expect(screen.queryByText(/Wrong workbook was cited/))
      .not.toBeInTheDocument();
    expect(historyFor).toHaveBeenCalledTimes(2);
  });

  test("a late error from the previous candidate does not surface under the new one", async () => {
    let rejectA: (reason?: any) => void = () => {};
    historyFor.mockImplementationOnce(() => new Promise((_resolve, reject) => {
      rejectA = reject;
    }));
    historyFor.mockResolvedValueOnce(
      historyPageWithReason("B recorded history.", "cand/2"));
    listCandidates.mockResolvedValue([
      payload(),
      payload({ candidate_id: "cand/2", proposed_lesson: "SECOND CANDIDATE" }),
    ]);
    render(<ConversationLearningReview threadId="thread-1" sourceKind="email" />);
    fireEvent.click(await screen.findByTestId("learning-history-toggle"));
    await waitFor(() => expect(historyFor).toHaveBeenCalledTimes(1));

    fireEvent.change(screen.getByTestId("learning-candidate-select"), {
      target: { value: "cand/2" },
    });
    await waitFor(() => expect(screen.getByTestId("learning-proposed-lesson"))
      .toHaveTextContent("SECOND CANDIDATE"));
    fireEvent.click(screen.getByTestId("learning-history-toggle"));
    expect(await screen.findByText(/B recorded history/)).toBeInTheDocument();

    await act(async () => {
      rejectA(new Error("deferred A failure"));
    });
    expect(screen.queryByTestId("learning-history-error"))
      .not.toBeInTheDocument();
    expect(screen.getByText(/B recorded history/)).toBeInTheDocument();
  });

  test("returning to the first candidate ignores its earlier deferred page", async () => {
    let resolveFirstA: (value: any) => void = () => {};
    historyFor.mockImplementationOnce(() => new Promise((resolve) => {
      resolveFirstA = resolve;
    }));
    historyFor.mockResolvedValueOnce(
      historyPageWithReason("Fresh A history."));
    listCandidates.mockResolvedValue([
      payload(),
      payload({ candidate_id: "cand/2", proposed_lesson: "SECOND CANDIDATE" }),
    ]);
    render(<ConversationLearningReview threadId="thread-1" sourceKind="email" />);
    fireEvent.click(await screen.findByTestId("learning-history-toggle"));
    await waitFor(() => expect(historyFor).toHaveBeenCalledTimes(1));

    fireEvent.change(screen.getByTestId("learning-candidate-select"), {
      target: { value: "cand/2" },
    });
    await waitFor(() => expect(screen.getByTestId("learning-proposed-lesson"))
      .toHaveTextContent("SECOND CANDIDATE"));
    fireEvent.change(screen.getByTestId("learning-candidate-select"), {
      target: { value: "cand/1" },
    });
    await waitFor(() => expect(screen.getByTestId("learning-proposed-lesson"))
      .toHaveTextContent("Use the approved rates workbook."));
    fireEvent.click(screen.getByTestId("learning-history-toggle"));

    await waitFor(() => expect(historyFor).toHaveBeenCalledTimes(2));
    expect(await screen.findByText(/Fresh A history/)).toBeInTheDocument();

    await act(async () => {
      resolveFirstA(historyPageWithReason("STALE first A page."));
    });
    expect(screen.queryByText(/STALE first A page/)).not.toBeInTheDocument();
    expect(screen.getByText(/Fresh A history/)).toBeInTheDocument();
    expect(historyFor).toHaveBeenCalledTimes(2);
  });

  test("a page for the pre-revision candidate is dropped after a revision is saved", async () => {
    let resolveOldRevision: (value: any) => void = () => {};
    historyFor.mockImplementationOnce(() => new Promise((resolve) => {
      resolveOldRevision = resolve;
    }));
    historyFor.mockResolvedValueOnce(
      historyPageWithReason("Fresh revision history."));
    listCandidates.mockResolvedValue([payload({
      status: "confirmed",
      confirmed_by: "owner",
      confirmed_revision: 1,
    })]);
    reviseCandidate.mockResolvedValue(payload({
      status: "review_ready",
      revision: 2,
      proposed_lesson: "Use the corrected rates workbook.",
    }));
    render(<ConversationLearningReview threadId="thread-1" sourceKind="email" />);
    fireEvent.click(await screen.findByTestId("learning-history-toggle"));
    await waitFor(() => expect(historyFor).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByTestId("learning-revise"));
    fireEvent.change(screen.getByTestId("learning-edit-lesson"), {
      target: { value: "Use the corrected rates workbook." },
    });
    fireEvent.click(screen.getByTestId("learning-revise-save"));

    await waitFor(() => expect(screen.getByText("revision 2"))
      .toBeInTheDocument());
    // The cached page was dropped for the new revision, so the open drawer
    // reloads exactly once.
    await waitFor(() => expect(historyFor).toHaveBeenCalledTimes(2));
    expect(historyFor.mock.calls[1][1]).toBe("cand/1");
    expect(await screen.findByText(/Fresh revision history/))
      .toBeInTheDocument();

    await act(async () => {
      resolveOldRevision(historyPageWithReason("STALE pre-revision page."));
    });
    expect(screen.queryByText(/STALE pre-revision page/))
      .not.toBeInTheDocument();
    expect(screen.getByText(/Fresh revision history/)).toBeInTheDocument();
    expect(historyFor).toHaveBeenCalledTimes(2);
  });
});
