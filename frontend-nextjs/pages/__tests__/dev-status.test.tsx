import React from "react";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import DevStatus from "@/pages/dev-status";

jest.mock("@tauri-apps/api", (): any => ({ invoke: null }));

describe("DevStatus (web mode)", () => {
  const mockFetch = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    global.fetch = mockFetch;
    mockFetch.mockImplementation((url: string) => {
      if (url.includes(":3000")) return Promise.resolve({ ok: true, status: 200 });
      if (url.includes(":8000")) return Promise.resolve({ ok: true, status: 200 });
      return Promise.resolve({ ok: false, status: 500 });
    });
  });

  it("renders the header immediately", () => {
    mockFetch.mockReturnValue(new Promise(() => {}));
    render(<DevStatus />);
    expect(
      screen.getByRole("heading", { name: /development status/i })
    ).toBeInTheDocument();
  });

  it("shows system overview, service cards and health summary after checks", async () => {
    render(<DevStatus />);

    // Platform shows Web when no Tauri system info is available
    await waitFor(() => {
      expect(screen.getByText("Web")).toBeInTheDocument();
    });

    // 4 services, all healthy
    await waitFor(() => {
      expect(screen.getByText("4/4")).toBeInTheDocument();
    });
    expect(screen.getAllByText("Frontend").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Backend").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Database").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Desktop App").length).toBeGreaterThan(0);

    // Build status from the simulated build info
    expect(screen.getByText("87%")).toBeInTheDocument();
    expect(screen.getByText(/152\/156 tests passed/i)).toBeInTheDocument();

    // Service health summary table
    expect(screen.getByText("Service Health Summary")).toBeInTheDocument();
    expect(screen.getAllByText("healthy").length).toBeGreaterThanOrEqual(4);

    // Refresh button exists
    expect(screen.getByRole("button", { name: /refresh/i })).toBeInTheDocument();
  });

  it("marks services as unhealthy when the health check fails", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes(":3000")) return Promise.resolve({ ok: false, status: 503 });
      if (url.includes(":8000")) return Promise.resolve({ ok: true, status: 200 });
      return Promise.resolve({ ok: false, status: 500 });
    });

    render(<DevStatus />);

    await waitFor(() => {
      expect(screen.getByText("3/4")).toBeInTheDocument();
    });
    expect(screen.getAllByText("unhealthy").length).toBeGreaterThanOrEqual(1);
  });

  it("marks services as unhealthy when the health check throws", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes(":3000")) return Promise.reject(new Error("ECONNREFUSED"));
      if (url.includes(":8000")) return Promise.resolve({ ok: true, status: 200 });
      return Promise.resolve({ ok: false, status: 500 });
    });

    render(<DevStatus />);

    await waitFor(() => {
      expect(screen.getByText("3/4")).toBeInTheDocument();
    });
  });

  it("renders the build status tab with test results", async () => {
    render(<DevStatus />);

    await waitFor(() => {
      expect(screen.getByText("4/4")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /build status/i }));

    await waitFor(() => {
      expect(screen.getByText("Last Build")).toBeInTheDocument();
    });
    expect(screen.getByText("success")).toBeInTheDocument();
    expect(screen.getByText("2m 15s")).toBeInTheDocument();
    expect(screen.getByText("156")).toBeInTheDocument();
    expect(screen.getByText("152")).toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /start build/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /run tests/i })
    ).toBeInTheDocument();
  });

  it("renders the system info tab with a web-environment alert", async () => {
    render(<DevStatus />);

    await waitFor(() => {
      expect(screen.getByText("4/4")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /system info/i }));

    await waitFor(() => {
      expect(screen.getByText("Web Environment")).toBeInTheDocument();
    });
    expect(
      screen.getByText(/only available in the desktop application/i)
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /git status/i })
    ).toBeInTheDocument();
  });

  it("re-runs the health checks when Refresh is clicked", async () => {
    render(<DevStatus />);

    await waitFor(() => {
      expect(screen.getByText("4/4")).toBeInTheDocument();
    });
    const callsAfterMount = mockFetch.mock.calls.length;

    fireEvent.click(screen.getByRole("button", { name: /refresh/i }));

    await waitFor(() => {
      expect(mockFetch.mock.calls.length).toBeGreaterThan(callsAfterMount);
    });
  });

  it("renders service cards with response times", async () => {
    render(<DevStatus />);

    await waitFor(() => {
      expect(screen.getByText("4/4")).toBeInTheDocument();
    });

    const times = document.body.querySelectorAll("span");
    const hasMs = Array.from(times).some((el) => /ms$/.test(el.textContent || ""));
    expect(hasMs).toBe(true);
  });
});
