import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ChakraProvider, defaultSystem } from "@chakra-ui/react";
import RoutingDashboardPage from "@/pages/settings/routing";
import { apiClient } from "@/lib/api-client";

// Chakra v3 recipes clone their default recipe objects with structuredClone
// during render. The jest jsdom sandbox does not expose the Node global, so
// provide a JSON-based fallback (recipes are plain serializable objects).
if (typeof globalThis.structuredClone !== "function") {
  (globalThis as any).structuredClone = (value: unknown) => {
    if (typeof value !== "object" || value === null) return value;
    return JSON.parse(JSON.stringify(value));
  };
}

jest.mock("@/lib/api-client", () => ({
  apiClient: { get: jest.fn() },
}));

jest.mock("@/components/layout/Layout", () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

const mockGet = apiClient.get as jest.Mock;

const ENABLED_RESPONSE = {
  data: {
    enabled: true,
    ema_enabled: true,
    stats: {
      feedback_samples: 5123,
      model_success_rates: {
        "gpt-4o": 0.9,
        "claude-3.5": 0.55,
        "deepseek-v3": 0.2,
      },
      ema_scores: {
        "llama3:8b": { score: 0.4, success_rate: 0.5, avg_latency_ms: 300, avg_cost: 0.0001, samples: 50 },
        "gpt-4o": { score: 0.82, success_rate: 0.9, avg_latency_ms: 1200, avg_cost: 0.01, samples: 100 },
      },
    },
  },
};

const renderWithChakra = (ui: React.ReactElement) =>
  render(<ChakraProvider value={defaultSystem}>{ui}</ChakraProvider>);
describe("RoutingDashboardPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGet.mockResolvedValue(ENABLED_RESPONSE);
  });

  it("shows the loading skeleton while stats are pending", () => {
    mockGet.mockReturnValue(new Promise(() => {}));
    const { container } = renderWithChakra(<RoutingDashboardPage />);
    expect(container.querySelectorAll(".animate-pulse").length).toBe(3);
  });
  it("renders the disabled banner when routing is off", async () => {
    mockGet.mockResolvedValue({
      data: {
        enabled: false,
        ema_enabled: false,
        stats: { feedback_samples: 0, model_success_rates: {}, ema_scores: {} },
      },
    });

    renderWithChakra(<RoutingDashboardPage />);

    await waitFor(() => {
      expect(screen.getByText("Learning Router is off")).toBeInTheDocument();
    });
    expect(screen.getByText("ATOM_LEARNING_ROUTER=true")).toBeInTheDocument();
    expect(screen.getByText("ATOM_EMA_ROUTER_ENABLED=true")).toBeInTheDocument();
    // ML Predictor Status card shows Off
    expect(screen.getByText("ATOM_LEARNING_ROUTER=false")).toBeInTheDocument();
  });

  it("renders stat cards, EMA table and per-model success rates", async () => {
    renderWithChakra(<RoutingDashboardPage />);

    await waitFor(() => {
      expect(screen.getByText("5,123")).toBeInTheDocument();
    });
    expect(mockGet).toHaveBeenCalledWith("/api/chat/routing-stats");

    // Stat cards
    expect(screen.getByText("Feedback Samples")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument(); // Models Tracked (success rates)
    expect(screen.getByText("Active")).toBeInTheDocument(); // ML Predictor Status
    expect(screen.getByText("Blended")).toBeInTheDocument(); // EMA Telemetry

    // EMA table — sorted by score desc: gpt-4o (0.82) before llama3:8b (0.4)
    const rows = screen.getAllByRole("row");
    expect(rows[1]).toHaveTextContent("gpt-4o");
    expect(rows[1]).toHaveTextContent("82.0%");
    expect(rows[1]).toHaveTextContent("90%");
    expect(rows[1]).toHaveTextContent("1200 ms");
    expect(rows[1]).toHaveTextContent("$0.0100");
    expect(rows[1]).toHaveTextContent("100");
    expect(rows[2]).toHaveTextContent("llama3:8b");
    expect(rows[2]).toHaveTextContent("40.0%");

    // Per-model success rates with tiered badges ("90%" also appears in the
    // EMA table row for gpt-4o, so scope by the EMA row or use the all-query)
    expect(screen.getAllByText("90%").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("55%")).toBeInTheDocument();
    expect(screen.getByText("20%")).toBeInTheDocument();
  });

  it("shows the no-data message when there are no per-model stats", async () => {
    mockGet.mockResolvedValue({
      data: {
        enabled: true,
        ema_enabled: false,
        stats: { feedback_samples: 0, model_success_rates: {}, ema_scores: {} },
      },
    });

    renderWithChakra(<RoutingDashboardPage />);

    await waitFor(() => {
      expect(
        screen.getByText(/no per-model data yet/i)
      ).toBeInTheDocument();
    });
    // EMA table hidden when empty
    expect(screen.queryByText("EMA Protocol Telemetry (Real-Time)")).not.toBeInTheDocument();
    // EMA Telemetry card: collected but not blended
    expect(screen.getByText("Collected")).toBeInTheDocument();
  });

  it("refreshes stats when the refresh button is clicked", async () => {
    renderWithChakra(<RoutingDashboardPage />);
    await waitFor(() => expect(screen.getByText("5,123")).toBeInTheDocument());

    const callsAfterMount = mockGet.mock.calls.length;
    fireEvent.click(screen.getByRole("button", { name: /refresh/i }));

    await waitFor(() => {
      expect(mockGet.mock.calls.length).toBeGreaterThan(callsAfterMount);
    });
  });

  it("falls back to the disabled state when the fetch fails", async () => {
    mockGet.mockRejectedValue(new Error("boom"));

    renderWithChakra(<RoutingDashboardPage />);

    await waitFor(() => {
      expect(screen.getByText("Learning Router is off")).toBeInTheDocument();
    });
    expect(screen.getAllByText("0").length).toBeGreaterThanOrEqual(2); // Feedback Samples + Models Tracked fallbacks
    await waitFor(() => {
      expect(screen.getByText("No per-model data yet. Data appears here as users chat and submit feedback.")).toBeInTheDocument();
    });
  });
});
