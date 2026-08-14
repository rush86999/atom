/**
 * JITVerificationDashboard tests (pages/admin/jit-verification.tsx, was 0% coverage)
 *
 * Covers: loading state, data-driven render (overview metrics, worker
 * metrics, cache panels, health issues), backend-unavailable fallbacks,
 * manual refresh, auto-refresh toggle, keyboard shortcut actions, and
 * the shortcuts help dialog.
 */

import React from "react";
import { render, screen, fireEvent, act, waitFor } from "@testing-library/react";
import JITVerificationDashboard from "@/pages/admin/jit-verification";

const mockGetWorkerMetrics = jest.fn();
const mockGetCacheStats = jest.fn();
const mockGetHealth = jest.fn();
const mockPollerStart = jest.fn();
const mockPollerStop = jest.fn();
const mockToast = jest.fn();

jest.mock("@/lib/api-admin", () => ({
  jitVerificationAPI: {
    getWorkerMetrics: (...args: any[]) => mockGetWorkerMetrics(...args),
    getCacheStats: (...args: any[]) => mockGetCacheStats(...args),
    getHealth: (...args: any[]) => mockGetHealth(...args),
  },
  AdminPoller: class {
    // Mimic the real poller's initial fetch → onUpdate behavior so the
    // callbacks registered by the page are actually invoked in tests.
    start(fetchFn: any, onUpdate: any) {
      mockPollerStart(fetchFn, onUpdate);
      Promise.resolve()
        .then(() => fetchFn())
        .then((data: any) => onUpdate(data))
        .catch(() => undefined);
    }
    stop() {
      mockPollerStop();
    }
  },
}));

jest.mock("@/components/ui/use-toast", () => ({
  useToast: () => ({ toast: (...args: any[]) => mockToast(...args) }),
}));

jest.mock("@/components/admin/jit-verification/WorkerStatusMonitor", () => ({
  WorkerStatusMonitor: () => <div data-testid="worker-status-monitor">Monitor</div>,
}));
jest.mock("@/components/admin/jit-verification/SystemStatusCards", () => ({
  SystemStatusCards: () => <div data-testid="system-status-cards">Status</div>,
}));
jest.mock("@/components/admin/jit-verification/QuickActions", () => ({
  QuickActions: () => <div data-testid="quick-actions">Actions</div>,
}));
jest.mock("@/components/admin/jit-verification/CacheMetricsPanel", () => ({
  CacheMetricsPanel: () => <div data-testid="cache-metrics-panel">CacheMetrics</div>,
}));
jest.mock("@/components/admin/jit-verification/LatencyDisplay", () => ({
  LatencyDisplay: () => <div data-testid="latency-display">Latency</div>,
}));
jest.mock("@/components/admin/jit-verification/CacheActions", () => ({
  CacheActions: () => <div data-testid="cache-actions">CacheActions</div>,
}));
jest.mock("@/components/admin/jit-verification/CitationVerificationPanel", () => ({
  CitationVerificationPanel: () => <div data-testid="citation-panel">Citations</div>,
}));
jest.mock("@/components/admin/jit-verification/VerificationLogs", () => ({
  VerificationLogs: () => <div data-testid="verification-logs">Logs</div>,
}));
jest.mock("@/components/admin/jit-verification/TopCitations", () => ({
  TopCitations: () => <div data-testid="top-citations">TopCitations</div>,
}));

let shortcutsConfig: any = null;
jest.mock("@/components/admin/shared", () => ({
  ErrorBoundary: ({ children }: any) => <div data-testid="error-boundary">{children}</div>,
  OfflineIndicator: () => <div data-testid="offline-indicator" />,
  useKeyboardShortcuts: (config: any) => {
    shortcutsConfig = config;
  },
  KeyboardShortcutsHelp: ({ open, onClose }: any) => (
    <div data-testid="keyboard-help">
      <span>{open ? "help-open" : "help-closed"}</span>
      <button onClick={onClose}>close-help</button>
    </div>
  ),
}));

const WORKER_DATA = {
  status: "running",
  running: true,
  processed_count: 124,
  average_verification_time: 0.123,
  last_run_duration: 4.5,
  verified_count: 10,
  failed_count: 2,
  stale_facts: 3,
  total_citations: 15,
  top_citations: [{ citation: "citation-1", access_count: 9 }],
};

const CACHE_DATA = {
  l1_verification_hit_rate: 0.96,
  l1_verification_cache_size: 450,
};

const HEALTH_DATA = {
  status: "healthy",
  issues: ["Disk usage high"],
};

describe("JITVerificationDashboard", () => {
  let consoleErrorSpy: jest.SpyInstance;
  let consoleLogSpy: jest.SpyInstance;

  const mockApiSuccess = () => {
    mockGetWorkerMetrics.mockResolvedValue({ data: WORKER_DATA });
    mockGetCacheStats.mockResolvedValue({ data: CACHE_DATA });
    mockGetHealth.mockResolvedValue({ data: HEALTH_DATA });
  };

  const renderDashboard = async () => {
    const utils = render(<JITVerificationDashboard />);
    await waitFor(() =>
      expect(screen.getByText("JIT Verification")).toBeInTheDocument()
    );
    return utils;
  };

  beforeEach(() => {
    jest.clearAllMocks();
    mockApiSuccess();
    consoleErrorSpy = jest.spyOn(console, "error").mockImplementation(() => {});
    consoleLogSpy = jest.spyOn(console, "log").mockImplementation(() => {});
    shortcutsConfig = null;
  });

  afterEach(() => {
    consoleErrorSpy.mockRestore();
    consoleLogSpy.mockRestore();
  });

  test("shows a loading spinner while data is in flight", () => {
    mockGetWorkerMetrics.mockReturnValue(new Promise(() => {}));
    mockGetCacheStats.mockReturnValue(new Promise(() => {}));
    mockGetHealth.mockReturnValue(new Promise(() => {}));
    const { container } = render(<JITVerificationDashboard />);
    expect(container.querySelector(".animate-spin")).not.toBeNull();
    expect(screen.queryByText("JIT Verification")).not.toBeInTheDocument();
  });

  test("renders the dashboard with data-driven panels and overview metrics", async () => {
    await renderDashboard();

    expect(screen.getByText("Monitor and manage business fact citation verification")).toBeInTheDocument();
    expect(screen.getByTestId("system-status-cards")).toBeInTheDocument();
    expect(screen.getByTestId("quick-actions")).toBeInTheDocument();
    expect(screen.getByTestId("worker-status-monitor")).toBeInTheDocument();
    expect(screen.getByTestId("offline-indicator")).toBeInTheDocument();

    // Overview tab metrics.
    expect(screen.getByText("96.0%")).toBeInTheDocument();
    expect(screen.getByText("0.123s")).toBeInTheDocument();
    expect(screen.getByText("4.50s")).toBeInTheDocument();
    expect(screen.getByText("Last Run Duration")).toBeInTheDocument();

    // Health issues card.
    expect(screen.getByText("Health Issues Detected")).toBeInTheDocument();
    expect(screen.getByText("• Disk usage high")).toBeInTheDocument();

    // Auto-refresh started via the poller on mount.
    expect(mockPollerStart).toHaveBeenCalledTimes(1);
  });

  test("worker tab shows metric counts and top citations", async () => {
    await renderDashboard();
    fireEvent.click(screen.getByRole("button", { name: "Worker" }));

    expect(screen.getByText("Verified")).toBeInTheDocument();
    expect(screen.getByText("10")).toBeInTheDocument();
    expect(screen.getByText("Failed")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("Stale Facts")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("Total Citations")).toBeInTheDocument();
    expect(screen.getByText("15")).toBeInTheDocument();
    expect(screen.getByText("citation-1")).toBeInTheDocument();
    expect(screen.getByText("9x")).toBeInTheDocument();
  });

  test("cache, citations, logs, and top-citations tabs render their panels", async () => {
    await renderDashboard();

    fireEvent.click(screen.getByRole("button", { name: "Cache" }));
    expect(screen.getByTestId("cache-metrics-panel")).toBeInTheDocument();
    expect(screen.getByTestId("latency-display")).toBeInTheDocument();
    expect(screen.getByTestId("cache-actions")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Citations" }));
    expect(screen.getByTestId("citation-panel")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Logs" }));
    expect(screen.getByTestId("verification-logs")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Top Citations" }));
    expect(screen.getByTestId("top-citations")).toBeInTheDocument();
  });

  test("falls back to baseline metrics when the backend is unavailable", async () => {
    mockGetWorkerMetrics.mockRejectedValue(new Error("down"));
    mockGetCacheStats.mockRejectedValue(new Error("down"));
    mockGetHealth.mockRejectedValue(new Error("down"));

    await renderDashboard();
    expect(screen.getByText("96.0%")).toBeInTheDocument(); // fallback hit rate 0.96
    expect(screen.getByText("0s")).toBeInTheDocument(); // no average_verification_time in fallback
    expect(consoleErrorSpy).not.toHaveBeenCalled(); // per-endpoint .catch swallows errors
  });

  test("manual refresh re-fetches all three endpoints", async () => {
    await renderDashboard();
    // Initial fetch + the poller's own initial fetch.
    await waitFor(() => expect(mockGetWorkerMetrics).toHaveBeenCalledTimes(2));

    fireEvent.click(screen.getByRole("button", { name: /^Refresh/ }));
    await waitFor(() => {
      expect(mockGetWorkerMetrics).toHaveBeenCalledTimes(3);
      expect(mockGetCacheStats).toHaveBeenCalledTimes(3);
      expect(mockGetHealth).toHaveBeenCalledTimes(3);
    });
  });

  test("toggling auto-refresh stops and restarts the poller with toasts", async () => {
    await renderDashboard();

    fireEvent.click(screen.getByRole("button", { name: /Auto-refreshing/ }));
    expect(mockPollerStop).toHaveBeenCalled();
    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: "Auto-refresh disabled" })
    );
    expect(screen.getByRole("button", { name: /^Auto-refresh$/ })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /^Auto-refresh$/ }));
    expect(mockPollerStart).toHaveBeenCalledTimes(3); // mount + toggle-on + effect re-run
    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: "Auto-refresh enabled" })
    );
    expect(screen.getByRole("button", { name: /Auto-refreshing/ })).toBeInTheDocument();
  });

  test("keyboard shortcut actions work (help, refresh, toggle, tab navigation)", async () => {
    await renderDashboard();
    expect(shortcutsConfig).not.toBeNull();

    const [navigation, tabs] = shortcutsConfig;

    act(() => {
      navigation.shortcuts[0].action(); // "?" opens help
    });
    expect(screen.getByText("help-open")).toBeInTheDocument();

    act(() => {
      tabs.shortcuts.forEach((s: any) => s.action()); // "1".."6" log navigation
    });
    expect(consoleLogSpy).toHaveBeenCalledWith("Navigate to Overview tab");
    expect(consoleLogSpy).toHaveBeenCalledWith("Navigate to Top Citations tab");

    act(() => {
      navigation.shortcuts[1].action(); // "r" refreshes
    });
    await waitFor(() => expect(mockGetWorkerMetrics).toHaveBeenCalledTimes(3));

    act(() => {
      navigation.shortcuts[2].action(); // "a" toggles auto-refresh off
    });
    expect(screen.getByRole("button", { name: /^Auto-refresh$/ })).toBeInTheDocument();
  });

  test("shortcuts button opens the help dialog and closing it dismisses", async () => {
    await renderDashboard();
    expect(screen.getByText("help-closed")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Shortcuts/ }));
    expect(screen.getByText("help-open")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "close-help" }));
    expect(screen.getByText("help-closed")).toBeInTheDocument();
  });

  test("stops the poller on unmount", async () => {
    const { unmount } = await renderDashboard();
    unmount();
    expect(mockPollerStop).toHaveBeenCalled();
  });
});
