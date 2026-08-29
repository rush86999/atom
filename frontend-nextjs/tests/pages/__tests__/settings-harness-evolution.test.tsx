import React from "react";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { ChakraProvider, defaultSystem } from "@chakra-ui/react";
import HarnessEvolutionPage from "@/pages/settings/harness-evolution";
import { apiClient } from "@/lib/api-client";
import { useToast } from "@/components/ui/use-toast";

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
  apiClient: { get: jest.fn(), post: jest.fn() },
}));

jest.mock("@/components/layout/Layout", () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

jest.mock("@/components/ui/use-toast", () => ({
  useToast: jest.fn(() => ({ toast: jest.fn() })),
}));

const mockGet = apiClient.get as jest.Mock;
const mockToast = jest.fn();

const RESPONSE = {
  data: {
    success: true,
    mined_weaknesses: [
      {
        step_type: "agent_execution",
        tool: "browser_tool",
        failure_count: 12,
        examples: [
          { thought: "x", observation: "y", verification_evidence: "Selector went stale" },
        ],
      },
      {
        step_type: "llm_process",
        tool: "byok_handler",
        failure_count: 3,
        examples: [
          { thought: "", observation: "Response truncated", verification_evidence: "" },
        ],
      },
    ],
    active_patches: [
      {
        agent_id: "a1",
        agent_name: "Payroll Guardian",
        patch_id: "patch-7f3a",
        target_component: "tools.browser",
        mutation_payload: { timeout_seconds: 30 },
        model_scope: "gpt-4o",
      },
    ],
  },
};

const renderPage = () =>
  render(
    <ChakraProvider value={defaultSystem}>
      <HarnessEvolutionPage />
    </ChakraProvider>
  );

describe("HarnessEvolutionPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (useToast as jest.Mock).mockReturnValue({ toast: mockToast });
    mockGet.mockResolvedValue(RESPONSE);
  });

  it("renders stat cards, weakness table and patch table from the API", async () => {
    renderPage();

    await waitFor(() => expect(screen.getByText("Self-Evolving Harness")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("12")).toBeInTheDocument());

    expect(mockGet).toHaveBeenCalledWith("/api/chat/harness-evolution");

    // Stat cards: 1 active patch, 2 mined weaknesses, 100% gate
    expect(screen.getByText("Active Patches Deployed")).toBeInTheDocument();
    expect(screen.getByText("Mined Weaknesses")).toBeInTheDocument();
    expect(screen.getByText("Sandbox Validation Gate")).toBeInTheDocument();
    expect(screen.getByText("100%")).toBeInTheDocument();

    // Weakness table content
    expect(screen.getByText("agent_execution")).toBeInTheDocument();
    expect(screen.getByText("browser_tool")).toBeInTheDocument();
    expect(screen.getByText("Selector went stale")).toBeInTheDocument();
    // Second weakness falls back to observation when verification_evidence is empty
    expect(screen.getByText("Response truncated")).toBeInTheDocument();

    // Patch table content
    expect(screen.getByText("Payroll Guardian")).toBeInTheDocument();
    expect(screen.getByText("patch-7f3a")).toBeInTheDocument();
    expect(screen.getByText("tools.browser")).toBeInTheDocument();
    expect(screen.getByText("gpt-4o")).toBeInTheDocument();
    expect(screen.getByText(JSON.stringify({ timeout_seconds: 30 }))).toBeInTheDocument();
  });

  it("shows the healthy empty states when no weaknesses or patches exist", async () => {
    mockGet.mockResolvedValue({
      data: { success: true, mined_weaknesses: [], active_patches: [] },
    });

    renderPage();

    await waitFor(() => {
      expect(
        screen.getByText(/no repeating failure patterns detected in the lookback window/i)
      ).toBeInTheDocument();
    });
    expect(
      screen.getByText(/no micro-patches currently deployed/i)
    ).toBeInTheDocument();
    expect(screen.getAllByText("0").length).toBeGreaterThanOrEqual(1);
  });

  it("shows a toast error when the status fetch fails", async () => {
    mockGet.mockRejectedValue(new Error("network down"));

    renderPage();

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: "Error",
          description: "Failed to retrieve self-healing harness status.",
          variant: "error",
        })
      );
    });
  });

  it("re-mines on demand: posts to the miner endpoint, refetches and toasts with counts", async () => {
    const mockPost = (apiClient as any).post as jest.Mock;
    mockPost.mockResolvedValue({
      data: {
        success: true,
        pattern_count: 2,
        total_failures: 7,
        lookback_hours: 48,
        mined_weaknesses: [],
      },
    });
    renderPage();

    await waitFor(() => expect(screen.getByText("Self-Evolving Harness")).toBeInTheDocument());
    expect(mockGet).toHaveBeenCalledTimes(1);

    // The button renders spinner-only while the initial fetch is refreshing.
    fireEvent.click(await screen.findByRole("button", { name: /re-mine now/i }));

    await waitFor(() =>
      expect(mockPost).toHaveBeenCalledWith("/api/chat/harness-evolution/mine")
    );
    await waitFor(() => expect(mockGet).toHaveBeenCalledTimes(2));
    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({
        title: "Re-mine complete",
        description: expect.stringContaining("2 failure pattern(s)"),
        variant: "success",
      })
    );
  });

  it("shows an error toast when the re-mine call fails", async () => {
    const mockPost = (apiClient as any).post as jest.Mock;
    mockPost.mockRejectedValue(new Error("network down"));
    renderPage();

    await waitFor(() => expect(screen.getByText("Self-Evolving Harness")).toBeInTheDocument());
    fireEvent.click(await screen.findByRole("button", { name: /re-mine now/i }));

    await waitFor(() =>
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: "Re-mine failed",
          variant: "error",
        })
      )
    );
  });
});
