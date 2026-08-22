import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import SchedulePage from "@/pages/workflows/schedule";
import { useToast } from "@/components/ui/use-toast";

jest.mock("@/components/ui/use-toast", () => ({
  useToast: jest.fn(() => ({ toast: jest.fn() })),
}));

const mockToast = jest.fn();

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

const JOBS = {
  jobs: [
    {
      id: "job-1",
      workflow_id: "wf_welcome_email",
      name: "Daily report",
      trigger: "cron",
      next_run_time: "2026-08-09T09:00:00Z",
    },
    {
      id: "job-2",
      workflow_id: "wf_inventory",
      trigger: "interval",
      next_run_time: null,
    },
  ],
};

const okResponse = (body: any) => ({ ok: true, status: 200, json: async () => body });
const errResponse = (status: number, body: any) => ({ ok: false, status, json: async () => body });

describe("SchedulePage", () => {
  const mockFetch = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(Storage.prototype, "getItem").mockReturnValue("test-token");
    (useToast as jest.Mock).mockReturnValue({ toast: mockToast });
    global.fetch = mockFetch;
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/scheduler/jobs")) return Promise.resolve(okResponse(JOBS));
      if (url.includes("/schedule")) return Promise.resolve(okResponse({ message: "Scheduled", job_id: "job-new" }));
      return Promise.resolve(okResponse({}));
    });
  });

  it("loads scheduled jobs with the auth header and renders them", async () => {
    render(<SchedulePage />);

    await waitFor(() => {
      expect(screen.getByText("Daily report")).toBeInTheDocument();
    });

    expect(mockFetch).toHaveBeenCalledWith(
      `${API_BASE}/scheduler/jobs`,
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: "Bearer test-token" }),
      })
    );
    expect(screen.getByText(/wf_welcome_email/)).toBeInTheDocument();
    expect(screen.getByText(/Trigger: cron/)).toBeInTheDocument();
    // Second job falls back to id for the name and omits next run
    expect(screen.getByText(/job-2/)).toBeInTheDocument();
    expect(screen.queryByText(/Next:/)).not.toBeNull();
  });

  it("shows the empty state when no jobs are scheduled", async () => {
    mockFetch.mockImplementation((url: string) =>
      Promise.resolve(okResponse({ jobs: [] }))
    );

    render(<SchedulePage />);

    await waitFor(() => {
      expect(screen.getByText("No scheduled jobs yet. Schedule one above.")).toBeInTheDocument();
    });
  });

  it("handles both a bare list and a {jobs} envelope from the endpoint", async () => {
    mockFetch.mockImplementation((url: string) =>
      Promise.resolve(okResponse([JOBS.jobs[0]]))
    );

    render(<SchedulePage />);

    await waitFor(() => {
      expect(screen.getByText("Daily report")).toBeInTheDocument();
    });
  });

  it("refreshes the job list from the refresh button", async () => {
    render(<SchedulePage />);
    await waitFor(() => expect(screen.getByText("Daily report")).toBeInTheDocument());

    const callsAfterMount = mockFetch.mock.calls.length;
    fireEvent.click(screen.getByRole("button", { name: /refresh/i }));

    await waitFor(() => {
      expect(mockFetch.mock.calls.length).toBeGreaterThan(callsAfterMount);
    });
  });

  it("requires a workflow ID before scheduling", async () => {
    render(<SchedulePage />);
    await waitFor(() => expect(screen.getByText("Daily report")).toBeInTheDocument());

    // Browser constraint validation blocks submission of the empty required field
    fireEvent.click(screen.getByRole("button", { name: /schedule workflow/i }));
    expect(mockToast).not.toHaveBeenCalled();
    expect(mockFetch).not.toHaveBeenCalledWith(
      expect.stringMatching(/\/schedule(\/|$)/),
      expect.anything()
    );

    // The page-level guard also rejects a direct submit event
    fireEvent.submit(document.querySelector("form")!);

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Workflow ID required", variant: "error" })
      );
    });
    expect(mockFetch).not.toHaveBeenCalledWith(
      expect.stringMatching(/\/schedule(\/|$)/),
      expect.anything()
    );
  });

  it("schedules an interval workflow and reloads the job list", async () => {
    render(<SchedulePage />);
    await waitFor(() => expect(screen.getByText("Daily report")).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText(/workflow id/i), {
      target: { value: "wf_welcome_email" },
    });
    fireEvent.click(screen.getByRole("button", { name: /schedule workflow/i }));

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        `${API_BASE}/workflows/wf_welcome_email/schedule`,
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            trigger_type: "interval",
            trigger_config: { minutes: 30 },
          }),
        })
      );
    });
    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: "Workflow scheduled", variant: "success" })
    );
  });

  it("clamps the interval minutes to at least 1", async () => {
    render(<SchedulePage />);
    await waitFor(() => expect(screen.getByText("Daily report")).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText(/workflow id/i), {
      target: { value: "wf_x" },
    });
    fireEvent.change(screen.getByLabelText(/interval \(minutes\)/i), {
      target: { value: "0" },
    });

    // A real browser blocks the click-submit for a number input below min=1,
    // so the clamp is exercised via a direct submit event
    fireEvent.submit(document.querySelector("form")!);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringMatching(/\/schedule(\/|$)/),
        expect.objectContaining({
          body: JSON.stringify({
            trigger_type: "interval",
            trigger_config: { minutes: 1 },
          }),
        })
      );
    });
  });

  it("schedules a cron workflow when the cron trigger is selected", async () => {
    render(<SchedulePage />);
    await waitFor(() => expect(screen.getByText("Daily report")).toBeInTheDocument());

    // Open the trigger Select and choose the cron option (radix also renders a
    // hidden native select, so target the visible trigger button / option)
    const triggerText = screen
      .getAllByText("Every N minutes (interval)")
      .find((el) => el.closest("button"));
    fireEvent.click(triggerText!.closest("button")!);
    fireEvent.click(await screen.findByRole("option", { name: "Cron expression" }));

    expect(screen.getByLabelText(/cron expression/i)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/workflow id/i), {
      target: { value: "wf_cron_job" },
    });
    fireEvent.click(screen.getByRole("button", { name: /schedule workflow/i }));

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        `${API_BASE}/workflows/wf_cron_job/schedule`,
        expect.objectContaining({
          body: JSON.stringify({
            trigger_type: "cron",
            trigger_config: { cron_expr: "*/5 * * * *" },
          }),
        })
      );
    });
  });

  it("shows the backend error detail when scheduling fails", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.endsWith("/schedule")) {
        return Promise.resolve(errResponse(400, { detail: "Unknown workflow" }));
      }
      return Promise.resolve(okResponse(JOBS));
    });

    render(<SchedulePage />);
    await waitFor(() => expect(screen.getByText("Daily report")).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText(/workflow id/i), {
      target: { value: "wf_missing" },
    });
    fireEvent.click(screen.getByRole("button", { name: /schedule workflow/i }));

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Scheduling failed", description: "Unknown workflow", variant: "error" })
      );
    });
  });

  it("removes a scheduled job", async () => {
    mockFetch.mockImplementation((url: string, opts?: any) => {
      if (url.includes("/scheduler/jobs")) return Promise.resolve(okResponse(JOBS));
      if (url.includes("/schedule/") && opts?.method === "DELETE") {
        return Promise.resolve(okResponse({}));
      }
      return Promise.resolve(okResponse({}));
    });

    render(<SchedulePage />);
    await waitFor(() => expect(screen.getByText("Daily report")).toBeInTheDocument());

    fireEvent.click(screen.getAllByRole("button", { name: /remove/i })[0]);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        `${API_BASE}/workflows/wf_welcome_email/schedule/job-1`,
        expect.objectContaining({ method: "DELETE" })
      );
    });
    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: "Removed", description: "Scheduled job deleted.", variant: "success" })
    );
  });

  it("cannot remove a job that is missing its workflow id", async () => {
    mockFetch.mockImplementation((url: string) =>
      Promise.resolve(
        okResponse({
          jobs: [{ id: "job-orphan", trigger: "interval", next_run_time: null }],
        })
      )
    );

    render(<SchedulePage />);
    await waitFor(() => {
      expect(screen.getByText("job-orphan")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /remove/i }));

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Cannot remove", description: "Workflow ID missing on this job.", variant: "error" })
      );
    });
    // No DELETE request was attempted
    expect(mockFetch).not.toHaveBeenCalledWith(
      expect.stringContaining("/schedule/"),
      expect.objectContaining({ method: "DELETE" })
    );
  });

  it("shows a failure toast when removing a job fails", async () => {
    mockFetch.mockImplementation((url: string, opts?: any) => {
      if (url.includes("/scheduler/jobs")) return Promise.resolve(okResponse(JOBS));
      if (opts?.method === "DELETE") return Promise.resolve(errResponse(500, {}));
      return Promise.resolve(okResponse({}));
    });

    render(<SchedulePage />);
    await waitFor(() => expect(screen.getByText("Daily report")).toBeInTheDocument());

    fireEvent.click(screen.getAllByRole("button", { name: /remove/i })[0]);

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Failed", variant: "error" })
      );
    });
  });
});
