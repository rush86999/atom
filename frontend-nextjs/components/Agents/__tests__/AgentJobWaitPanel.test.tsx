/**
 * Ordinary member journey through the Agents page job panel:
 * exact question -> answer -> second question -> final durable result,
 * reload readback, stale/cancelled and uncertain answers, and no completion
 * from a bare HTTP 200 or model text.
 *
 * The transport is a controlled fetch double; no live model/provider/browser.
 */
import React from "react";
import { render, screen, waitFor, cleanup, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import userEvent from "@testing-library/user-event";

import AgentJobWaitPanel, {
  AgentJobReadback,
} from "../AgentJobWaitPanel";

const waitingJob = (
  id: string,
  question: string,
  correlationId: string,
  overrides: Partial<AgentJobReadback> = {},
): AgentJobReadback => ({
  agent_id: "a1",
  job_id: "job-1",
  execution_id: "exec-1",
  job_status: "waiting",
  outcome: "waiting",
  reason: "execution_waiting",
  next_action: "await_information",
  requires_reconciliation: false,
  wait: {
    id,
    kind: "information_request",
    status: "pending",
    question,
    missing_fact: "title",
    subject: { label: "closing task" },
    correlation_id: correlationId,
    can_answer: true,
  },
  ...overrides,
});

const successJob = (): AgentJobReadback => ({
  agent_id: "a1",
  job_id: "job-1",
  execution_id: "exec-1",
  job_status: "success",
  outcome: "success",
  reason: "execution_succeeded",
  next_action: "none",
  requires_reconciliation: false,
  result: { status: "success", output: "Created the task." },
});

const jsonResponse = (data: any, status = 200) =>
  Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: async () => ({ success: status < 400, data }),
  } as any);

const errorResponse = (status: number, message: string) =>
  Promise.resolve({
    ok: false,
    status,
    json: async () => ({ success: false, error: { code: "X", message } }),
  } as any);

const postCalls = (fetchMock: jest.Mock) =>
  fetchMock.mock.calls.filter(([, init]) => init?.method === "POST");

describe("AgentJobWaitPanel", () => {
  let fetchMock: jest.Mock;

  beforeEach(() => {
    fetchMock = jest.fn();
    global.fetch = fetchMock as any;
    window.localStorage.clear();
    window.localStorage.setItem("auth_token", "test-token");
  });

  afterEach(() => {
    cleanup();
    jest.resetAllMocks();
  });

  test("answers the exact wait, shows the second question, then the durable result", async () => {
    const user = userEvent.setup();
    fetchMock
      .mockResolvedValueOnce(jsonResponse(waitingJob("wait-1", "What title?", "corr-1")))
      .mockResolvedValueOnce(
        jsonResponse(waitingJob("wait-2", "What priority?", "corr-2"), 202),
      )
      .mockResolvedValueOnce(jsonResponse(waitingJob("wait-2", "What priority?", "corr-2")))
      .mockResolvedValueOnce(jsonResponse(successJob()))
      .mockResolvedValueOnce(jsonResponse(successJob()));

    render(<AgentJobWaitPanel agentId="a1" jobId="job-1" />);

    expect(await screen.findByText("What title?")).toBeInTheDocument();
    expect(screen.getByTestId("agent-job-blocking")).toHaveTextContent(
      "Waiting for: title",
    );
    expect(screen.getByText(/not approval of an action/i)).toBeInTheDocument();
    expect(screen.queryByTestId("agent-job-completed")).not.toBeInTheDocument();

    const input = screen.getByTestId(
      "agent-job-answer-input",
    ) as HTMLTextAreaElement;
    await user.type(input, "Closing task");
    await user.click(screen.getByTestId("agent-job-answer-submit"));

    expect(await screen.findByText("What priority?")).toBeInTheDocument();
    // The first answer is not completion and the new wait clears the typed
    // answer instead of letting it settle the second question.
    expect(screen.queryByTestId("agent-job-completed")).not.toBeInTheDocument();
    await waitFor(() =>
      expect(
        (screen.getByTestId("agent-job-answer-input") as HTMLTextAreaElement)
          .value,
      ).toBe(""),
    );

    await user.type(
      screen.getByTestId("agent-job-answer-input"),
      "high",
    );
    await user.click(screen.getByTestId("agent-job-answer-submit"));

    expect(await screen.findByTestId("agent-job-completed")).toHaveTextContent(
      "Completed",
    );
    expect(screen.getByTestId("agent-job-result")).toHaveTextContent(
      "Created the task.",
    );
    // Both submits used the exact server-owned correlation for the current
    // wait, never "whichever wait is current".
    const posts = postCalls(fetchMock);
    expect(posts).toHaveLength(2);
    expect(JSON.parse(posts[0][1].body)).toEqual({
      answer: "Closing task",
      correlation_id: "corr-1",
    });
    expect(JSON.parse(posts[1][1].body)).toEqual({
      answer: "high",
      correlation_id: "corr-2",
    });
  });

  test("reload readback restores the question from the authorized server read", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(waitingJob("wait-1", "What title?", "corr-1")),
    );
    const first = render(<AgentJobWaitPanel agentId="a1" jobId="job-1" />);
    expect(await screen.findByText("What title?")).toBeInTheDocument();
    first.unmount();

    fetchMock.mockResolvedValueOnce(
      jsonResponse(waitingJob("wait-1", "What title?", "corr-1")),
    );
    render(<AgentJobWaitPanel agentId="a1" jobId="job-1" />);
    expect(await screen.findByText("What title?")).toBeInTheDocument();
    expect(screen.getByTestId("agent-job-status")).toHaveTextContent(
      "Waiting for your answer",
    );
  });

  test("a changed wait clears a typed answer on refresh", async () => {
    const user = userEvent.setup();
    fetchMock
      .mockResolvedValueOnce(jsonResponse(waitingJob("wait-1", "What title?", "corr-1")))
      .mockResolvedValueOnce(jsonResponse(waitingJob("wait-2", "What priority?", "corr-2")));

    render(<AgentJobWaitPanel agentId="a1" jobId="job-1" />);
    await screen.findByText("What title?");
    await user.type(
      screen.getByTestId("agent-job-answer-input"),
      "typed for the old question",
    );
    await user.click(screen.getByTestId("agent-job-refresh"));

    expect(await screen.findByText("What priority?")).toBeInTheDocument();
    await waitFor(() =>
      expect(
        (screen.getByTestId("agent-job-answer-input") as HTMLTextAreaElement)
          .value,
      ).toBe(""),
    );
  });

  test("double click cannot send the same answer twice", async () => {
    const user = userEvent.setup();
    let resolvePost: (value: any) => void = () => {};
    const pendingPost = new Promise((resolve) => {
      resolvePost = resolve;
    });
    fetchMock
      .mockResolvedValueOnce(jsonResponse(waitingJob("wait-1", "What title?", "corr-1")))
      .mockReturnValueOnce(pendingPost as any)
      .mockResolvedValueOnce(jsonResponse(successJob()));

    render(<AgentJobWaitPanel agentId="a1" jobId="job-1" />);
    await screen.findByText("What title?");
    await user.type(screen.getByTestId("agent-job-answer-input"), "once");
    const submit = screen.getByTestId("agent-job-answer-submit");
    fireEvent.click(submit);
    fireEvent.click(submit);

    expect(postCalls(fetchMock)).toHaveLength(1);
    resolvePost({
      ok: true,
      status: 200,
      json: async () => ({ success: true, data: successJob() }),
    });
    expect(await screen.findByTestId("agent-job-completed")).toBeInTheDocument();
    expect(postCalls(fetchMock)).toHaveLength(1);
  });

  test("a stale response for a previous job cannot replace the current job", async () => {
    let resolveOld: (value: any) => void = () => {};
    const oldResponse = new Promise((resolve) => {
      resolveOld = resolve;
    });
    fetchMock.mockImplementation((url: string) => {
      if (String(url).includes("/jobs/job-old")) return oldResponse as any;
      return jsonResponse(
        waitingJob("wait-new", "New question", "corr-new", {
          job_id: "job-new",
        }),
      );
    });

    const { rerender } = render(
      <AgentJobWaitPanel agentId="a1" jobId="job-old" />,
    );
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/jobs/job-old"),
        expect.anything(),
      ),
    );

    rerender(<AgentJobWaitPanel agentId="a1" jobId="job-new" />);
    expect(await screen.findByText("New question")).toBeInTheDocument();

    resolveOld({
      ok: true,
      status: 200,
      json: async () => ({
        success: true,
        data: waitingJob("wait-old", "Old question", "corr-old", {
          job_id: "job-old",
        }),
      }),
    });
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(screen.queryByText("Old question")).not.toBeInTheDocument();
    expect(screen.getByText("New question")).toBeInTheDocument();
  });

  test("409 stale answer refreshes the cancelled job and never auto-resends", async () => {
    const user = userEvent.setup();
    fetchMock
      .mockResolvedValueOnce(jsonResponse(waitingJob("wait-1", "What title?", "corr-1")))
      .mockResolvedValueOnce(
        errorResponse(409, "This information wait was already decided"),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          ...successJob(),
          job_status: "cancelled",
          outcome: "cancelled",
          reason: "execution_cancelled",
          next_action: "none",
          result: null,
        }),
      );

    render(<AgentJobWaitPanel agentId="a1" jobId="job-1" />);
    await screen.findByText("What title?");
    await user.type(screen.getByTestId("agent-job-answer-input"), "late");
    await user.click(screen.getByTestId("agent-job-answer-submit"));

    expect(await screen.findByTestId("agent-job-error")).toHaveTextContent(
      /no longer current/i,
    );
    expect(await screen.findByTestId("agent-job-failure")).toHaveTextContent(
      /cancelled/i,
    );
    expect(screen.queryByTestId("agent-job-answer-input")).not.toBeInTheDocument();
    expect(postCalls(fetchMock)).toHaveLength(1);
  });

  test("503 uncertain answer refreshes truthfully and does not resend", async () => {
    const user = userEvent.setup();
    fetchMock
      .mockResolvedValueOnce(jsonResponse(waitingJob("wait-1", "What title?", "corr-1")))
      .mockResolvedValueOnce(
        errorResponse(503, "The agent execution outcome is uncertain"),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          ...successJob(),
          job_status: "failed",
          outcome: "uncertain",
          reason: "execution_uncertain",
          next_action: "reconcile_operation",
          requires_reconciliation: true,
          result: null,
        }),
      );

    render(<AgentJobWaitPanel agentId="a1" jobId="job-1" />);
    await screen.findByText("What title?");
    await user.type(screen.getByTestId("agent-job-answer-input"), "maybe");
    await user.click(screen.getByTestId("agent-job-answer-submit"));

    expect(await screen.findByTestId("agent-job-error")).toHaveTextContent(
      /uncertain/i,
    );
    expect(await screen.findByTestId("agent-job-failure")).toHaveTextContent(
      /reconcile/i,
    );
    expect(postCalls(fetchMock)).toHaveLength(1);
  });

  test("a 200-envelope without a completion status is not shown as completed", async () => {
    const user = userEvent.setup();
    fetchMock
      .mockResolvedValueOnce(jsonResponse(waitingJob("wait-1", "What title?", "corr-1")))
      .mockResolvedValueOnce(
        jsonResponse({
          agent_id: "a1",
          job_id: "job-1",
          execution_id: "exec-1",
          job_status: "running",
          next_action: "await_completion",
          requires_reconciliation: false,
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          agent_id: "a1",
          job_id: "job-1",
          execution_id: "exec-1",
          job_status: "running",
          next_action: "await_completion",
          requires_reconciliation: false,
        }),
      );

    render(<AgentJobWaitPanel agentId="a1" jobId="job-1" />);
    await screen.findByText("What title?");
    await user.type(screen.getByTestId("agent-job-answer-input"), "some fact");
    await user.click(screen.getByTestId("agent-job-answer-submit"));

    await screen.findByTestId("agent-job-notice");
    expect(screen.queryByTestId("agent-job-completed")).not.toBeInTheDocument();
    expect(screen.getByTestId("agent-job-status")).toHaveTextContent("Working");
  });

  test("a waiting job without a verifiable question is not shown as failed or answerable", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        agent_id: "a1",
        job_id: "job-1",
        execution_id: "exec-1",
        job_status: "waiting",
        outcome: "waiting",
        reason: "execution_waiting",
        next_action: "review_execution",
        requires_reconciliation: false,
        wait_unavailable: true,
      }),
    );

    render(<AgentJobWaitPanel agentId="a1" jobId="job-1" />);

    expect(
      await screen.findByTestId("agent-job-wait-unavailable"),
    ).toHaveTextContent(/question could not be verified/i);
    expect(screen.getByTestId("agent-job-status")).toHaveTextContent(
      /question unavailable/i,
    );
    expect(screen.queryByTestId("agent-job-question")).not.toBeInTheDocument();
    expect(screen.queryByTestId("agent-job-answer-input")).not.toBeInTheDocument();
    expect(screen.queryByTestId("agent-job-failure")).not.toBeInTheDocument();
  });

  test("an unauthorized job exposes no question/result and is forgotten", async () => {
    const onForget = jest.fn();
    fetchMock.mockResolvedValueOnce(
      errorResponse(404, "Agent job not found"),
    ).mockResolvedValueOnce(errorResponse(404, "Agent job not found"));

    render(
      <AgentJobWaitPanel agentId="a1" jobId="job-1" onForget={onForget} />,
    );

    expect(await screen.findByTestId("agent-job-error")).toHaveTextContent(
      /not available/i,
    );
    expect(screen.queryByTestId("agent-job-question")).not.toBeInTheDocument();
    expect(screen.queryByTestId("agent-job-result")).not.toBeInTheDocument();
    expect(onForget).toHaveBeenCalled();
  });
});
