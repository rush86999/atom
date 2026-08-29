import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ChakraProvider, defaultSystem } from "@chakra-ui/react";
import { BpeAdminPage } from "@/pages/admin/bpe";
import {
  applyBpeGenome,
  getBpeOverview,
  getBpeWorkspaceDetail,
} from "@/lib/bpe-api";
import { resetSetting, updateSetting } from "@/lib/runtime-settings-api";
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

jest.mock("@/lib/bpe-api", () => ({
  getBpeOverview: jest.fn(),
  getBpeWorkspaceDetail: jest.fn(),
  applyBpeGenome: jest.fn(),
}));

jest.mock("@/lib/runtime-settings-api", () => ({
  updateSetting: jest.fn(),
  resetSetting: jest.fn(),
}));

jest.mock("@/components/ui/use-toast", () => ({
  useToast: jest.fn(() => ({ toast: jest.fn() })),
}));

const mockToast = jest.fn();
const mockOverview = getBpeOverview as jest.Mock;
const mockDetail = getBpeWorkspaceDetail as jest.Mock;
const mockApply = applyBpeGenome as jest.Mock;
const mockUpdate = updateSetting as jest.Mock;
const mockReset = resetSetting as jest.Mock;

const OVERVIEW = {
  flags: {
    ATOM_BPE_WORKSPACE_ENABLED: {
      value: true,
      source: "default",
      type: "bool",
      description: "Workspace + meta-actions",
    },
    ATOM_BPE_CONSULT_POLICY: {
      value: "auto",
      source: "default",
      type: "str",
      description: "Consult value-gate",
    },
    ATOM_BPE_EVOLUTION: {
      value: "auto",
      source: "default",
      type: "str",
      description: "Genome application",
    },
    ATOM_BPE_EVOLUTION_ENABLED: {
      value: "auto",
      source: "default",
      type: "str",
      description: "Legacy per-family apply override",
    },
    ATOM_BPE_AUTOMATION: {
      value: "auto",
      source: "default",
      type: "str",
      description: "Master automation mode",
    },
    ATOM_BPE_DATA_DIR: {
      value: "backend/data/bpe_workspaces",
      source: "default",
      type: "str",
      description: "Durable snapshot directory",
    },
  },
  modes: {
    workspace_enabled: true,
    automation_active: true,
    consult_gating_active: true,
    evolution_apply_enabled: true,
  },
  thresholds: {
    min_episodes_for_value_gate: 5,
    recall_only_share: 0.1,
    recall_only_min_episodes: 10,
    min_evaluated_genomes: 3,
    evolution_apply_fitness: 0.25,
    population_size: 8,
    target_call_rate: 1,
  },
  active_bounds: { max_subgoals: 8, recall_top_k: 3 },
  gene_bounds: { max_subgoals: { min: 4, max: 12 }, recall_top_k: { min: 2, max: 5 } },
  consult_policy: {
    "sales-agent": {
      episodes: 12,
      value_ema: 0.4,
      consults_total: 15,
      commit_note_total: 1,
      consult_episodes: 9,
      updated_at: 1756400000,
      render_mode: "recall_only",
      suppressed: false,
      harness_call_rate: 1.25,
    },
  },
  population: {
    "sales-agent": [
      {
        genome: { max_subgoals: 8, recall_top_k: 3 },
        fitness: 0.5,
      },
    ],
  },
  evolution_readiness: [
    { family: "sales-agent", evaluated_genomes: 3, best_fitness: 0.5, apply_ready: true },
  ],
  workspaces: [
    {
      workspace_id: "ws-ui",
      agent_id: "sales-agent",
      scope_key: "sess-1",
      progress_count: 2,
      progress_done: 1,
      pending_notes: 1,
      experience_counts: { skills: 2, task_skills: 0, mistakes: 1, priors: 0 },
      episode_consults: 3,
    },
  ],
  persistence: { data_dir: "backend/data/bpe_workspaces", snapshot_files: 4 },
  telemetry: {
    window_spans: 2,
    aggregate: {
      "bpe.recall": { count: 2, avg_latency_ms: 1.5, error_count: 0 },
    },
    automation_flips: [
      { at: 1756400000, detail: { flip: "evolution_apply", family: "sales-agent" } },
    ],
  },
  meta_actions: [
    { name: "workspace.track", description: "Read belief state", parameters: {} },
    { name: "workspace.commit", description: "Commit a subgoal", parameters: {} },
    { name: "workspace.recall", description: "Recall experience", parameters: {} },
    { name: "workspace.note", description: "Buffer a note", parameters: {} },
  ],
};

const renderPage = () =>
  render(
    <ChakraProvider value={defaultSystem}>
      <BpeAdminPage />
    </ChakraProvider>
  );

describe("BpeAdminPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (useToast as jest.Mock).mockReturnValue({ toast: mockToast });
    mockOverview.mockResolvedValue(OVERVIEW);
    mockDetail.mockResolvedValue({
      workspace_id: "ws-ui",
      agent_id: "sales-agent",
      scope_key: "sess-1",
      progress: [
        { title: "draft invoice email", status: "done", committed_at: 0, updated_at: 0 },
      ],
      pending_notes: ["check Q3 totals"],
      experience: {
        skills: [{ content: "always CC finance", uses: 2, added_at: 0 }],
        task_skills: [],
        mistakes: [],
        priors: [],
      },
    });
  });

  it("renders guidance, mode cards, flag rows and meta-actions", async () => {
    renderPage();

    await waitFor(() =>
      expect(screen.getAllByText(/BPE Agent Workspace/).length).toBeGreaterThan(0)
    );
    expect(screen.getByTestId("bpe-guidance")).toBeInTheDocument();
    expect(screen.getByText("workspace.track")).toBeInTheDocument();
    expect(screen.getByText("workspace.note")).toBeInTheDocument();
    expect(screen.getByTestId("bpe-card-workspace")).toHaveTextContent("enabled");
    expect(screen.getByTestId("bpe-card-automation")).toHaveTextContent(
      "self-regulating"
    );
    expect(screen.getByLabelText("Consult policy mode")).toHaveValue("auto");
    expect(screen.getByText(/durable snapshots/i)).toBeInTheDocument();
  });

  it("renders consult policy rows with gate status", async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText("sales-agent")).toBeInTheDocument());
    expect(screen.getByText("recall-only")).toBeInTheDocument();
    expect(screen.getByText("rendering")).toBeInTheDocument();
    expect(screen.getByText("1.25")).toBeInTheDocument();
  });

  it("shows empty state copy when nothing has been recorded", async () => {
    mockOverview.mockResolvedValue({
      ...OVERVIEW,
      consult_policy: {},
      evolution_readiness: [],
      population: {},
      workspaces: [],
      telemetry: { window_spans: 0, aggregate: {}, automation_flips: [] },
    });
    renderPage();

    await waitFor(() =>
      expect(
        screen.getByText(/no episodes recorded yet/i)
      ).toBeInTheDocument()
    );
    // Inactive tab panels stay unmounted (custom Tabs impl) — switch to each.
    fireEvent.click(screen.getByRole("button", { name: /workspaces/i }));
    expect(screen.getByText(/no workspaces cached yet/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /telemetry/i }));
    expect(screen.getByText(/no spans in the buffer yet/i)).toBeInTheDocument();
  });

  it("saves a flag override through the runtime-settings API", async () => {
    mockUpdate.mockResolvedValue({});
    mockOverview.mockResolvedValue({ ...OVERVIEW });
    renderPage();

    await waitFor(() =>
      expect(screen.getByLabelText("Consult policy mode")).toBeInTheDocument()
    );
    fireEvent.change(screen.getByLabelText("Consult policy mode"), {
      target: { value: "false" },
    });

    await waitFor(() =>
      expect(mockUpdate).toHaveBeenCalledWith("ATOM_BPE_CONSULT_POLICY", "false")
    );
    await waitFor(() =>
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Setting saved", variant: "success" })
      )
    );
    expect(mockOverview).toHaveBeenCalledTimes(2); // initial + post-save refresh
  });

  it("locks env-managed flags and explains why", async () => {
    mockOverview.mockResolvedValue({
      ...OVERVIEW,
      flags: {
        ...OVERVIEW.flags,
        ATOM_BPE_CONSULT_POLICY: {
          ...OVERVIEW.flags.ATOM_BPE_CONSULT_POLICY,
          source: "env",
        },
      },
    });
    renderPage();

    await waitFor(() =>
      expect(screen.getByLabelText("Consult policy mode")).toBeDisabled()
    );
    expect(
      screen.getByText(/remove it from .env to manage here/i)
    ).toBeInTheDocument();
  });

  it("applies the best genome for a ready family", async () => {
    mockApply.mockResolvedValue({ applied: true, bounds: { max_subgoals: 10 } });
    renderPage();

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /evolution/i })).toBeInTheDocument()
    );
    fireEvent.click(screen.getByRole("button", { name: /evolution/i }));
    await waitFor(() =>
      expect(screen.getByText("Apply best genome")).toBeInTheDocument()
    );
    fireEvent.click(screen.getByText("Apply best genome"));

    await waitFor(() => expect(mockApply).toHaveBeenCalledWith("sales-agent"));
    await waitFor(() =>
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Genome applied" })
      )
    );
  });

  it("opens workspace detail from the scopes table", async () => {
    renderPage();

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /workspaces/i })).toBeInTheDocument()
    );
    fireEvent.click(screen.getByRole("button", { name: /workspaces/i }));
    await waitFor(() => expect(screen.getByText("ws-ui")).toBeInTheDocument());
    fireEvent.click(screen.getByText("ws-ui").closest("tr")!);

    await waitFor(() =>
      expect(mockDetail).toHaveBeenCalledWith("ws-ui", "sales-agent", "sess-1")
    );
    await waitFor(() =>
      expect(screen.getByText("draft invoice email")).toBeInTheDocument()
    );
    expect(screen.getByText(/always CC finance/)).toBeInTheDocument();
    expect(screen.getByText("Workspace state —")).toBeInTheDocument();
  });

  it("shows the error card with retry when the overview fails", async () => {
    mockOverview.mockRejectedValue(new Error("boom"));
    renderPage();

    await waitFor(() => expect(screen.getByTestId("bpe-error")).toBeInTheDocument());
    expect(screen.getByText("boom")).toBeInTheDocument();

    mockOverview.mockResolvedValue(OVERVIEW);
    fireEvent.click(screen.getByText("Retry"));
    await waitFor(() =>
      expect(screen.getByTestId("bpe-guidance")).toBeInTheDocument()
    );
  });
});
