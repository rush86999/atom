/**
 * DevStatus page tests (pages/dev-status.tsx, was 0% coverage) — web mode
 *
 * Covers initial load, service health checks (healthy/unhealthy/error),
 * build status rendering, tab navigation, and the no-system-info fallback.
 *
 * NOTE: fetch is routed by URL rather than mockResolvedValueOnce chains —
 * loadSystemStatus can run concurrently (double effect invocation), so
 * sequential Once mocks are consumed out of order.
 */

import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import DevStatus from "@/pages/dev-status";

const mockToast = jest.fn();

jest.mock("@/components/ui/use-toast", () => ({
  useToast: () => ({ toast: mockToast }),
}));

jest.mock("@tauri-apps/api", () => ({ invoke: null }));

const okResponse = (ok: boolean) => ({ ok, status: ok ? 200 : 503 });

const routeFetch = (mockFetch: jest.Mock, backendDown = true) => {
  mockFetch.mockImplementation(async (url: string) => {
    if (backendDown && url.includes(":8000")) throw new Error("backend down");
    return okResponse(true);
  });
};

describe("DevStatus (web mode)", () => {
  let mockFetch: jest.Mock;

  beforeEach(() => {
    jest.clearAllMocks();
    mockFetch = jest.fn();
    global.fetch = mockFetch;
  });

  test("renders header and loads service checks on mount", async () => {
    routeFetch(mockFetch);
    render(<DevStatus />);

    expect(screen.getByText("Development Status")).toBeInTheDocument();

    await waitFor(() => expect(screen.getAllByText("healthy").length).toBeGreaterThanOrEqual(2));
    expect(screen.getAllByText("unhealthy").length).toBeGreaterThan(0);

    expect(mockFetch).toHaveBeenCalledWith("http://localhost:3000", { method: "HEAD" });
    expect(mockFetch).toHaveBeenCalledWith("http://localhost:8000", { method: "GET" });
  });

  test("renders healthy-services count and platform card", async () => {
    routeFetch(mockFetch);
    render(<DevStatus />);
    await waitFor(() => expect(screen.getAllByText("unhealthy").length).toBeGreaterThan(0));

    expect(screen.getByText("3/4")).toBeInTheDocument();
    expect(screen.getByText("Web")).toBeInTheDocument();
    expect(screen.getByText("Unknown")).toBeInTheDocument();
  });

  test("refresh button reloads services", async () => {
    routeFetch(mockFetch, false);
    render(<DevStatus />);
    await waitFor(() => expect(screen.getAllByText("healthy").length).toBeGreaterThan(0));
    const before = mockFetch.mock.calls.length;

    fireEvent.click(screen.getByRole("button", { name: /Refresh/ }));
    await waitFor(() => expect(mockFetch.mock.calls.length).toBeGreaterThan(before));
  });

  test("backend outage shows one unhealthy and correct count", async () => {
    routeFetch(mockFetch, true);
    render(<DevStatus />);
    await waitFor(() => expect(screen.getByText("3/4")).toBeInTheDocument());
    expect(screen.getAllByText("unhealthy").length).toBeGreaterThan(0);
  });

  test("build status panel renders build + test results", async () => {
    routeFetch(mockFetch);
    render(<DevStatus />);
    await waitFor(() => expect(screen.getAllByText("unhealthy").length).toBeGreaterThan(0));

    fireEvent.click(screen.getByRole("button", { name: /Build Status/ }));
    expect(screen.getByText("Last Build")).toBeInTheDocument();
    expect(screen.getByText("2m 15s")).toBeInTheDocument();
    expect(screen.getByText("152")).toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();
    expect(screen.getByText("87%")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Start Build/ })).toBeInTheDocument();
  });

  test("system info tab shows web environment alert without invoke", async () => {
    routeFetch(mockFetch);
    render(<DevStatus />);
    await waitFor(() => expect(screen.getAllByText("unhealthy").length).toBeGreaterThan(0));

    fireEvent.click(screen.getByRole("button", { name: /System Info/ }));
    expect(screen.getByText("Web Environment")).toBeInTheDocument();
    expect(screen.getByText("Quick Actions")).toBeInTheDocument();
  });
});
