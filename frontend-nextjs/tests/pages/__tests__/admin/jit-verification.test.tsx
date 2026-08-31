import React from "react";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import JITVerificationDashboard from "@/pages/admin/jit-verification";
import { jitVerificationAPI, AdminPoller } from "@/lib/api-admin";
import { useToast } from "@/components/ui/use-toast";

jest.mock("@/lib/api-admin", () => ({
  jitVerificationAPI: {
    getWorkerMetrics: jest.fn(),
    getCacheStats: jest.fn(),
    getHealth: jest.fn(),
    getTopCitations: jest.fn(),
    verifyCitations: jest.fn(),
    verifyFactCitations: jest.fn(),
    startWorker: jest.fn(),
    stopWorker: jest.fn(),
    clearCache: jest.fn(),
    warmCache: jest.fn(),
    getConfig: jest.fn(),
  },
  AdminPoller: jest.fn(),
}));

jest.mock("@/components/ui/use-toast", () => ({
  useToast: jest.fn(() => ({ toast: jest.fn() })),
}));

describe("JITVerificationDashboard", () => {
  const mockToast = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    (AdminPoller as jest.Mock).mockImplementation(() => ({
      start: jest.fn(),
      stop: jest.fn(),
    }));
    (useToast as jest.Mock).mockReturnValue({ toast: mockToast });
    (jitVerificationAPI.getWorkerMetrics as jest.Mock).mockResolvedValue({
      data: {
        status: "idle",
        processed_count: 124,
        error_count: 0,
        avg_latency_ms: 12,
        verified_count: 10,
        failed_count: 2,
        stale_facts: 3,
        total_citations: 15,
        average_verification_time: 0.042,
        last_run_duration: 3.5,
        running: false,
        top_citations: [],
      },
    });
    (jitVerificationAPI.getCacheStats as jest.Mock).mockResolvedValue({
      data: {
        l1_verification_hit_rate: 0.96,
        l1_verification_cache_size: 100,
        l1_query_cache_size: 50,
        l1_verification_hits: 450,
        l1_verification_misses: 20,
        l1_query_hits: 180,
        l1_query_misses: 5,
        l1_query_hit_rate: 0.97,
        l1_evictions: 2,
        l2_enabled: true,
      },
    });
    (jitVerificationAPI.getHealth as jest.Mock).mockResolvedValue({
      data: { status: "healthy", components: {}, issues: [] },
    });
    (jitVerificationAPI.getTopCitations as jest.Mock).mockResolvedValue({
      data: { top_citations: [] },
    });
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ logs: [] }),
    }) as any;
  });

  describe("Component Import/Export", () => {
    it("should import and render the page", () => {
      render(<JITVerificationDashboard />);
      expect(document.querySelector(".animate-spin")).toBeInTheDocument();
    });
  });

  describe("Dashboard data loading", () => {
    it("should fetch all dashboard data and render header", async () => {
      render(<JITVerificationDashboard />);

      await waitFor(() => {
        expect(
          screen.getByRole("heading", { name: /jit verification/i })
        ).toBeInTheDocument();
      });

      expect(jitVerificationAPI.getWorkerMetrics).toHaveBeenCalled();
      expect(jitVerificationAPI.getCacheStats).toHaveBeenCalled();
      expect(jitVerificationAPI.getHealth).toHaveBeenCalled();
    });

    it("should start polling on mount", async () => {
            render(<JITVerificationDashboard />);

      await waitFor(() => {
        expect(AdminPoller).toHaveBeenCalled();
      });
      const pollerInstance = (AdminPoller as jest.Mock).mock.results[0].value;
      expect(pollerInstance.start).toHaveBeenCalled();
    });

    it("should stop polling on unmount", async () => {
            const { unmount } = render(<JITVerificationDashboard />);

      await waitFor(() => {
        expect(screen.getByRole("heading", { name: /jit verification/i })).toBeInTheDocument();
      });

      unmount();
      const pollerInstance = (AdminPoller as jest.Mock).mock.results[0].value;
      expect(pollerInstance.stop).toHaveBeenCalled();
    });
  });

  describe("Overview content", () => {
    it("should render performance metrics with cache hit rate and avg verification time", async () => {
      render(<JITVerificationDashboard />);

      await waitFor(() => {
        expect(screen.getByText("Performance Metrics")).toBeInTheDocument();
      });

      expect(screen.getByText("Cache Hit Rate")).toBeInTheDocument();
      expect(screen.getByText("Avg Verification Time")).toBeInTheDocument();
      expect(screen.getByText("0.042s")).toBeInTheDocument();
      expect(screen.getByText("3.50s")).toBeInTheDocument();
    });

    it("should render fallback values when API data is missing", async () => {
      (jitVerificationAPI.getWorkerMetrics as jest.Mock).mockResolvedValue(null);
      (jitVerificationAPI.getCacheStats as jest.Mock).mockResolvedValue(null);
      (jitVerificationAPI.getHealth as jest.Mock).mockResolvedValue(null);

      render(<JITVerificationDashboard />);

      await waitFor(() => {
        expect(screen.getByText("Performance Metrics")).toBeInTheDocument();
      });

      // Fallback cache hit rate 96% -> 96.0%
      expect(screen.getByText("96.0%")).toBeInTheDocument();
    });

    it("should display health issues when reported", async () => {
      (jitVerificationAPI.getHealth as jest.Mock).mockResolvedValue({
        data: {
          status: "degraded",
          components: {},
          issues: ["Cache is stale", "Worker behind schedule"],
        },
      });

      render(<JITVerificationDashboard />);

      await waitFor(() => {
        expect(screen.getByText("Health Issues Detected")).toBeInTheDocument();
      });
      expect(screen.getByText(/Cache is stale/)).toBeInTheDocument();
      expect(screen.getByText(/Worker behind schedule/)).toBeInTheDocument();
    });
  });

  describe("Worker tab", () => {
    it("should show worker metrics when worker tab is selected", async () => {
      render(<JITVerificationDashboard />);

      await waitFor(() => {
        expect(screen.getByText("Performance Metrics")).toBeInTheDocument();
      });

      fireEvent.click(screen.getByRole("button", { name: "Worker" }));

      const workerCard = screen.getByText("Worker Metrics").closest(
        "div.rounded-lg"
      ) as HTMLElement;
      expect(workerCard).toBeTruthy();
      expect(within(workerCard).getByText("Verified")).toBeInTheDocument();
      expect(within(workerCard).getByText("10")).toBeInTheDocument();
      expect(within(workerCard).getByText("Failed")).toBeInTheDocument();
      expect(within(workerCard).getByText("2")).toBeInTheDocument();
      expect(within(workerCard).getByText("Stale Facts")).toBeInTheDocument();
      expect(within(workerCard).getByText("3")).toBeInTheDocument();
      expect(within(workerCard).getByText("Total Citations")).toBeInTheDocument();
      expect(within(workerCard).getByText("15")).toBeInTheDocument();
    });
  });

  describe("Refresh", () => {
    it("should refetch all data when refresh is clicked", async () => {
      render(<JITVerificationDashboard />);

      await waitFor(() => {
        expect(screen.getByText("Performance Metrics")).toBeInTheDocument();
      });

      const callsBefore = (jitVerificationAPI.getWorkerMetrics as jest.Mock).mock.calls.length;
      fireEvent.click(screen.getByRole("button", { name: /^refresh$/i }));

      await waitFor(() => {
        expect((jitVerificationAPI.getWorkerMetrics as jest.Mock).mock.calls.length).toBeGreaterThan(callsBefore);
      });
    });
  });

  describe("Auto-refresh toggle", () => {
    it("should disable auto-refresh with toast", async () => {
            render(<JITVerificationDashboard />);

      await waitFor(() => {
        expect(screen.getByText("Performance Metrics")).toBeInTheDocument();
      });

      const pollerInstance = (AdminPoller as jest.Mock).mock.results[0].value;
      fireEvent.click(screen.getByRole("button", { name: /auto-refreshing/i }));

      expect(pollerInstance.stop).toHaveBeenCalled();
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Auto-refresh disabled" })
      );
    });

    it("should re-enable auto-refresh when toggled back on", async () => {
            render(<JITVerificationDashboard />);

      await waitFor(() => {
        expect(screen.getByText("Performance Metrics")).toBeInTheDocument();
      });

      const pollerInstance = (AdminPoller as jest.Mock).mock.results[0].value;
      fireEvent.click(screen.getByRole("button", { name: /auto-refreshing/i }));
      fireEvent.click(screen.getByRole("button", { name: /auto-refresh/i }));

      expect(pollerInstance.start).toHaveBeenCalled();
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Auto-refresh enabled" })
      );
    });
  });

  describe("Keyboard shortcuts", () => {
    it("should refresh dashboard when 'r' is pressed", async () => {
      render(<JITVerificationDashboard />);

      await waitFor(() => {
        expect(screen.getByText("Performance Metrics")).toBeInTheDocument();
      });

      const callsBefore = (jitVerificationAPI.getHealth as jest.Mock).mock.calls.length;
      fireEvent.keyDown(window, { key: "r" });

      await waitFor(() => {
        expect((jitVerificationAPI.getHealth as jest.Mock).mock.calls.length).toBeGreaterThan(callsBefore);
      });
    });

    it("should open shortcuts help when '?' is pressed", async () => {
      render(<JITVerificationDashboard />);

      await waitFor(() => {
        expect(screen.getByText("Performance Metrics")).toBeInTheDocument();
      });

      fireEvent.keyDown(window, { key: "?" });

      await waitFor(() => {
        expect(screen.getByText("Keyboard Shortcuts")).toBeInTheDocument();
      });
    });
  });
});
