import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { apiClient } from "@/lib/api-client";
import {
  InvoiceCommitmentReview,
  invoiceCommitmentReplyId,
  isAppliedInvoiceReplyStep,
} from "../InvoiceCommitmentReview";
import type {
  InvoiceCommitmentRead,
  InvoiceCommitmentRevision,
} from "@/lib/invoice-commitment-api";

jest.mock("@/lib/api-client", () => ({
  apiClient: {
    get: jest.fn(),
    put: jest.fn(),
  },
}));

const get = jest.mocked(apiClient.get);
const put = jest.mocked(apiClient.put);

function revision(
  value: number,
  overrides: Partial<InvoiceCommitmentRevision> = {},
): InvoiceCommitmentRevision {
  return {
    revision: value,
    verdict: "confirmed",
    commitment_date: "2026-11-01",
    reviewed_at: "2026-11-02T10:00:00+00:00",
    reviewed_by: "reviewer-1",
    ...overrides,
  };
}

function readResult(
  value: number,
  current: InvoiceCommitmentRevision | null = null,
  history: InvoiceCommitmentRevision[] = current ? [current] : [],
): InvoiceCommitmentRead {
  return {
    run_id: "run-1",
    step_id: "step-1",
    revision: value,
    current,
    history,
  };
}

function respondRead(value: InvoiceCommitmentRead) {
  return { data: value } as any;
}

const path = "/api/assignments/run-1/invoice-commitment/step-1";

beforeEach(() => {
  get.mockReset();
  put.mockReset();
});

describe("InvoiceCommitmentReview", () => {
  it("does not fetch until the reviewer opens the panel", async () => {
    get.mockResolvedValue(respondRead(readResult(0)));
    render(<InvoiceCommitmentReview runId="run-1" stepId="step-1" />);

    expect(get).not.toHaveBeenCalled();
    fireEvent.click(screen.getByTestId("invoice-commitment-toggle"));

    await waitFor(() => expect(get).toHaveBeenCalledWith(path));
    expect(put).not.toHaveBeenCalled();
  });

  it("shows the current verdict, date and revision history", async () => {
    const older = revision(1, { commitment_date: "2026-10-10" });
    const current = revision(2, {
      verdict: "unclear",
      commitment_date: null,
      reason: "Reply did not settle the date",
    });
    get.mockResolvedValue(
      respondRead(readResult(2, current, [older, current])),
    );
    render(<InvoiceCommitmentReview runId="run-1" stepId="step-1" />);

    fireEvent.click(screen.getByTestId("invoice-commitment-toggle"));

    expect(await screen.findByText(/Current: Unclear/)).toBeTruthy();
    expect(screen.getByTestId("invoice-commitment-current-date").textContent)
      .toBe("—");
    expect(screen.getByText(/Revision 1 · Confirmed/)).toBeTruthy();
    expect(screen.getByText(/Revision 2 · Unclear/)).toBeTruthy();
    expect(
      screen.getAllByText(/Reply did not settle the date/).length,
    ).toBeGreaterThan(0);
  });

  it("offers exactly the confirmed, no-commitment and unclear verdicts", async () => {
    get.mockResolvedValue(respondRead(readResult(0)));
    render(<InvoiceCommitmentReview runId="run-1" stepId="step-1" />);

    fireEvent.click(screen.getByTestId("invoice-commitment-toggle"));
    await screen.findByText(/Based on revision 0/);

    expect(screen.getByTestId("invoice-commitment-verdict-confirmed"))
      .toBeTruthy();
    expect(screen.getByTestId("invoice-commitment-verdict-no-commitment"))
      .toBeTruthy();
    expect(screen.getByTestId("invoice-commitment-verdict-unclear"))
      .toBeTruthy();
    expect(screen.queryByTestId("invoice-commitment-verdict-corrected"))
      .toBeNull();
  });

  it("requires a date for confirmed and records the first revision", async () => {
    get.mockResolvedValue(respondRead(readResult(0)));
    put.mockResolvedValue(
      respondRead(readResult(1, revision(1, { commitment_date: "2026-11-19" }))),
    );
    render(<InvoiceCommitmentReview runId="run-1" stepId="step-1" />);

    fireEvent.click(screen.getByTestId("invoice-commitment-toggle"));
    await screen.findByText(/Based on revision 0/);

    fireEvent.click(screen.getByTestId("invoice-commitment-submit"));
    expect(screen.getByTestId("invoice-commitment-error").textContent)
      .toMatch(/commitment date/);
    expect(put).not.toHaveBeenCalled();

    fireEvent.change(screen.getByTestId("invoice-commitment-date"), {
      target: { value: "2026-11-19" },
    });
    fireEvent.click(screen.getByTestId("invoice-commitment-submit"));

    await waitFor(() => expect(put).toHaveBeenCalledTimes(1));
    expect(put).toHaveBeenCalledWith(
      path,
      {
        expected_revision: 0,
        verdict: "confirmed",
        commitment_date: "2026-11-19",
        reason: null,
      },
      { retry: false },
    );
  });

  it("writes no date for a non-confirmed first revision", async () => {
    get.mockResolvedValue(respondRead(readResult(0)));
    put.mockResolvedValue(
      respondRead(readResult(1, revision(1, { verdict: "no_commitment" }))),
    );
    render(<InvoiceCommitmentReview runId="run-1" stepId="step-1" />);

    fireEvent.click(screen.getByTestId("invoice-commitment-toggle"));
    await screen.findByText(/Based on revision 0/);

    fireEvent.click(
      screen.getByTestId("invoice-commitment-verdict-no-commitment"),
    );
    expect(screen.queryByTestId("invoice-commitment-date")).toBeNull();
    fireEvent.click(screen.getByTestId("invoice-commitment-submit"));

    await waitFor(() => expect(put).toHaveBeenCalledTimes(1));
    expect(put).toHaveBeenCalledWith(
      path,
      {
        expected_revision: 0,
        verdict: "no_commitment",
        commitment_date: null,
        reason: null,
      },
      { retry: false },
    );
  });

  it("requires a reason for any revision after the first", async () => {
    const current = revision(2, { commitment_date: "2026-11-01" });
    get.mockResolvedValue(respondRead(readResult(2, current, [current])));
    put.mockResolvedValue(
      respondRead(readResult(3, revision(3, { commitment_date: "2026-11-19" }))),
    );
    render(
      <InvoiceCommitmentReview
        runId="run-1"
        stepId="step-1"
        expectedReplyId="reply-9"
      />,
    );

    fireEvent.click(screen.getByTestId("invoice-commitment-toggle"));
    await screen.findByText(/Based on revision 2/);

    // A later confirmed revision is still a correction and keeps the date.
    fireEvent.change(screen.getByTestId("invoice-commitment-date"), {
      target: { value: "2026-11-19" },
    });
    fireEvent.click(screen.getByTestId("invoice-commitment-submit"));
    expect(screen.getByTestId("invoice-commitment-error").textContent)
      .toMatch(/Explain the correction/);
    expect(put).not.toHaveBeenCalled();

    fireEvent.change(screen.getByTestId("invoice-commitment-reason"), {
      target: { value: "Corrected after the reply review" },
    });
    fireEvent.click(screen.getByTestId("invoice-commitment-submit"));

    await waitFor(() => expect(put).toHaveBeenCalledTimes(1));
    expect(put).toHaveBeenCalledWith(
      path,
      {
        expected_revision: 2,
        verdict: "confirmed",
        commitment_date: "2026-11-19",
        reason: "Corrected after the reply review",
        expected_reply_id: "reply-9",
      },
      { retry: false },
    );
  });

  it("refreshes after a 409 without retrying the write", async () => {
    get
      .mockResolvedValueOnce(respondRead(readResult(1)))
      .mockResolvedValueOnce(
        respondRead(
          readResult(2, revision(2, { commitment_date: "2026-11-20" })),
        ),
      );
    put.mockRejectedValue({ response: { status: 409 } });
    render(<InvoiceCommitmentReview runId="run-1" stepId="step-1" />);

    fireEvent.click(screen.getByTestId("invoice-commitment-toggle"));
    await screen.findByText(/Based on revision 1/);
    fireEvent.change(screen.getByTestId("invoice-commitment-date"), {
      target: { value: "2026-11-19" },
    });
    fireEvent.change(screen.getByTestId("invoice-commitment-reason"), {
      target: { value: "Confirmed after refresh" },
    });
    fireEvent.click(screen.getByTestId("invoice-commitment-submit"));

    await waitFor(() =>
      expect(screen.getByTestId("invoice-commitment-notice").textContent)
        .toMatch(/changed elsewhere/),
    );
    expect(put).toHaveBeenCalledTimes(1);
    expect(get).toHaveBeenCalledTimes(2);
    await screen.findByText(/Based on revision 2/);
  });
});

describe("invoice commitment step helpers", () => {
  it("recognises only applied invoice reply wait steps", () => {
    expect(
      isAppliedInvoiceReplyStep({
        adapter: "invoice.wait_for_reply",
        status: "applied",
        title: "Wait for exact Outlook reply",
      }),
    ).toBe(true);
    expect(
      isAppliedInvoiceReplyStep({
        adapter: "invoice.wait_for_reply",
        status: "waiting",
        title: "Wait for exact Outlook reply",
      }),
    ).toBe(false);
    expect(
      isAppliedInvoiceReplyStep({
        adapter: "outlook.wait_for_reply",
        status: "applied",
        title: "Invoice wait for reply",
      }),
    ).toBe(false);
  });

  it("finds the reply identity exposed by the applied step", () => {
    expect(
      invoiceCommitmentReplyId({
        status: "applied",
        operation: "invoice.wait_for_reply",
        waiting: { reply_message_id: "reply-42" },
      }),
    ).toBe("reply-42");
  });
});
