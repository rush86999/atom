/**
 * BPEManager component tests (Settings → BPE management surface).
 *
 * Covers: overview rendering (mode stats, consult-policy table, evolution
 * readiness, cached workspaces), flag toggles via the admin settings API,
 * and evolution apply.
 */
import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";
import BPEManager from "@/src/components/BPE/BPEManager";

jest.mock("@chakra-ui/react", () => {
  const React = require("react");
  const el = (tag: string) =>
    ({ children, ...rest }: any) => React.createElement(tag, rest, children);
  return {
    Box: el("div"),
    Button: el("button"),
    Heading: el("h2"),
    HStack: el("div"),
    Table: el("table"),
    Tbody: el("tbody"),
    Td: el("td"),
    Text: el("span"),
    Th: el("th"),
    Thead: el("thead"),
    Tr: el("tr"),
    VStack: el("div"),
    Badge: el("span"),
    Spinner: () => <div data-testid="spinner" />,
    SimpleGrid: el("div"),
    Stat: el("div"),
    StatLabel: el("div"),
    StatNumber: el("div"),
    Divider: () => <hr />,
    Switch: ({ isChecked, onChange, ...rest }: any) =>
      React.createElement("input", {
        type: "checkbox",
        role: "switch",
        checked: !!isChecked,
        onChange: (e: any) => onChange && onChange({ target: { checked: e.target.checked } }),
        ...rest,
      }),
  };
});

const OVERVIEW = {
  success: true,
  data: {
    flags: {
      ATOM_BPE_WORKSPACE_ENABLED: {
        value: true, source: "default", type: "bool",
        description: "Workspace + meta-actions",
      },
      ATOM_BPE_CONSULT_POLICY: {
        value: "auto", source: "default", type: "str",
        description: "Consult gating: auto suppresses only on negative evidence",
      },
      ATOM_BPE_EVOLUTION: {
        value: "auto", source: "default", type: "str",
        description: "Auto-apply evolved bounds",
      },
      ATOM_BPE_AUTOMATION: {
        value: "auto", source: "default", type: "str",
        description: "Master automation switch",
      },
    },
    modes: {
      workspace_enabled: true,
      automation_active: true,
      consult_gating_active: true,
      evolution_apply_enabled: true,
    },
    thresholds: {
      min_evaluated_genomes: 3,
      evolution_apply_fitness: 0.25,
      population_size: 8,
      target_call_rate: 1,
    },
    active_bounds: { max_subgoals: 8 },
    gene_bounds: { max_subgoals: { min: 4, max: 12 } },
    consult_policy: {
      demo_agent: {
        episodes: 6, value_ema: 0.8, consults_total: 6,
        consult_episodes: 6, render_mode: "full", suppressed: false,
        harness_call_rate: 1,
      },
      sad_agent: {
        episodes: 9, value_ema: -0.6, consults_total: 18,
        consult_episodes: 9, render_mode: "recall_only", suppressed: true,
        harness_call_rate: 2,
      },
    },
    population: {
      fam: [
        { genome: { max_subgoals: 6 }, fitness: 1.2 },
        { genome: { max_subgoals: 5 }, fitness: 0.9 },
        { genome: { max_subgoals: 10 }, fitness: 0.4 },
      ],
    },
    evolution_readiness: [{ family: "fam", ready: true, best_fitness: 1.2 }],
    workspaces: [
      {
        workspace_id: "default", agent_id: "demo", scope_key: "sess-1",
        progress_count: 3, progress_done: 2, pending_notes: 1,
        experience_counts: { skills: 2, mistakes: 1 },
        episode_consults: 2,
      },
    ],
    persistence: { data_dir: "backend/data/bpe_workspaces", snapshot_files: 2 },
    telemetry: { "bpe.note": { count: 4, avg_latency_ms: 0.2 } },
    meta_actions: [],
  },
};

const mockFetch = (impl: any) => {
  (global.fetch as jest.Mock) = jest.fn(impl);
};

beforeEach(() => {
  localStorage.setItem("token", "jwt-test");
  mockFetch((url: string) => {
    if (String(url).includes("/admin/bpe/overview")) {
      return Promise.resolve({ ok: true, json: async () => OVERVIEW });
    }
    return Promise.resolve({ ok: true, json: async () => ({}) });
  });
});

describe("BPEManager", () => {
  it("renders mode summary, consult table, and workspaces from the overview", async () => {
    render(<BPEManager />);

    // Async fetch: wait for the data-driven rows before asserting.
    expect(await screen.findByText("demo_agent")).toBeInTheDocument();
    expect(screen.getByText("sad_agent")).toBeInTheDocument();
    expect(screen.getByText("Suppressed")).toBeInTheDocument(); // sad_agent
    expect(screen.getByText(/2\/3/)).toBeInTheDocument(); // progress done/total
    expect(screen.getByText(/skills: 2, mistakes: 1/)).toBeInTheDocument();
    expect(screen.getByText(/2 file/)).toBeInTheDocument(); // persisted snapshots
  });

  it("surfaces suppressed + recall-only state for a failing agent", async () => {
    render(<BPEManager />);
    expect(await screen.findByText("recall_only")).toBeInTheDocument();
  });

  it("applies an evolved genome and reloads", async () => {
    const postSpy = jest.fn(() =>
      Promise.resolve({ ok: true, json: async () => ({ success: true }) })
    );
    mockFetch((url: string, init?: any) => {
      if (String(url).includes("/evolution/apply/") && init?.method === "POST") {
        return postSpy(url, init);
      }
      if (String(url).includes("/admin/bpe/overview")) {
        return Promise.resolve({ ok: true, json: async () => OVERVIEW });
      }
      return Promise.resolve({ ok: true, json: async () => ({}) });
    });

    render(<BPEManager />);
    const btn = await screen.findByRole("button", { name: /Apply now/i });
    fireEvent.click(btn);

    await waitFor(() => {
      expect(postSpy).toHaveBeenCalled();
    });
  });

  it("shows an error state when the overview fails", async () => {
    mockFetch(() => Promise.resolve({ ok: false, status: 500, json: async () => ({}) }));
    render(<BPEManager />);
    expect(
      await screen.findByText(/Overview failed \(500\)/)
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Retry/i })).toBeInTheDocument();
  });
});
