import React, { useCallback, useEffect, useState } from "react";
import {
  Box, Button, Heading, Text,
  Badge, Spinner,
} from "@chakra-ui/react";
import { authHeaders } from "@/lib/auth-headers";

/**
 * BPE Workspace management (Settings → BPE).
 *
 * Surface for the Belief/Progress/Experience runtime workspace
 * (docs/architecture/BPE_WORKSPACE_PLAN.md): live flag states, per-agent
 * consult-policy metrics, evolution population readiness with manual
 * apply, and cached workspace scopes.
 *
 * All data comes from the admin BPE overview endpoint; the flag toggles
 * persist through the admin runtime-settings API (env always wins over a
 * UI override — the page surfaces the resolution source per flag).
 */

const OVERVIEW_URL = "/api/v1/admin/bpe/overview";
const APPLY_URL = "/api/v1/admin/bpe/evolution/apply";
const SETTING_URL = "/api/v1/admin/settings";

interface FlagState {
  value: unknown;
  source: string;
  type: string;
  description: string;
}

interface AgentPolicyState {
  episodes?: number;
  value_ema?: number;
  consults_total?: number;
  consult_episodes?: number;
  render_mode?: string;
  suppressed?: boolean;
  harness_call_rate?: number;
}

interface Individual {
  genome: Record<string, number>;
  fitness: number;
}

interface WorkspaceSummary {
  workspace_id: string;
  agent_id: string;
  scope_key: string;
  progress_count: number;
  progress_done: number;
  pending_notes: number;
  experience_counts: Record<string, number>;
  episode_consults: number;
}

interface EvolutionReadiness {
  family: string;
  ready: boolean;
  best_fitness?: number;
  genome_count?: number;
}

interface Overview {
  flags: Record<string, FlagState>;
  modes: {
    workspace_enabled: boolean;
    automation_active: boolean;
    consult_gating_active: boolean;
    evolution_apply_enabled: boolean;
  };
  thresholds: Record<string, number>;
  active_bounds: Record<string, number>;
  gene_bounds: Record<string, { min: number; max: number }>;
  consult_policy: Record<string, AgentPolicyState>;
  population: Record<string, Individual[]>;
  evolution_readiness: EvolutionReadiness[];
  workspaces: WorkspaceSummary[];
  persistence: { data_dir: string; snapshot_files: number };
  telemetry: Record<string, { count: number; avg_latency_ms: number }>;
  meta_actions: Array<Record<string, unknown>>;
}

const FLAG_LABELS: Record<string, string> = {
  ATOM_BPE_WORKSPACE_ENABLED: "Workspace (track/commit/recall/note)",
  ATOM_BPE_CONSULT_POLICY: "Consult gating (auto-suppress on negative evidence)",
  ATOM_BPE_EVOLUTION: "Evolution (auto-apply evolved bounds)",
  ATOM_BPE_AUTOMATION: "Automation master switch",
};

function Toggle({ checked, disabled, onChange }: {
  checked: boolean;
  disabled?: boolean;
  onChange: (next: boolean) => void;
}) {
  return (
    <input
      type="checkbox"
      role="switch"
      checked={checked}
      disabled={!!disabled}
      onChange={(e) => onChange(e.target.checked)}
      style={{ width: 18, height: 18, cursor: disabled ? "not-allowed" : "pointer" }}
    />
  );
}

const cardStyle: React.CSSProperties = {
  background: "rgba(130,130,150,0.08)",
  padding: 16,
  borderRadius: 8,
};

const rowStyle: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  padding: "8px 0",
  width: "100%",
};

const tableStyle: React.CSSProperties = {
  width: "100%",
  fontSize: "0.875rem",
  borderCollapse: "collapse",
  marginBottom: 32,
};

const cellStyle: React.CSSProperties = { padding: 6, textAlign: "left" };

const BPEManager: React.FC = () => {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toggling, setToggling] = useState<string | null>(null);
  const [applying, setApplying] = useState<string | null>(null);
  const [flagError, setFlagError] = useState<string | null>(null);
  const [applyMsg, setApplyMsg] = useState<string | null>(null);
  const [applyError, setApplyError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setError(null);
      const res = await fetch(OVERVIEW_URL, { headers: authHeaders() });
      if (!res.ok) throw new Error(`Overview failed (${res.status})`);
      const body = await res.json();
      setOverview(body?.data?.flags ? body.data : body);
    } catch (err: any) {
      setError(err?.message || "Failed to load BPE status");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const setFlag = async (key: string, value: unknown, label: string) => {
    setToggling(key);
    try {
      const res = await fetch(`${SETTING_URL}/${key}`, {
        method: "PUT",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({ value }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        throw new Error(detail?.detail || `HTTP ${res.status}`);
      }
      await load();
    } catch (err: any) {
      setFlagError(`${label}: ${err?.message || "update failed"}`);
    } finally {
      setToggling(null);
    }
  };

  const applyGenome = async (family: string) => {
    setApplying(family);
    try {
      const res = await fetch(`${APPLY_URL}/${encodeURIComponent(family)}`, {
        method: "POST",
        headers: authHeaders(),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setApplyMsg(`New workspace bounds deployed for ${family}.`);
      await load();
    } catch (err: any) {
      setApplyError(err?.message || "Apply failed");
    } finally {
      setApplying(null);
    }
  };

  const renderFlagRow = (key: string) => {
    if (!overview) return null;
    const flag = overview.flags[key];
    if (!flag) return null;
    const enabled = flag.value === true || flag.value === "true";
    const isAuto = flag.value === "auto";
    const label = FLAG_LABELS[key] || key;
    // Tri-state "auto" flags manage as on/off; the resolved mode shows in
    // the source badge ("auto" means evidence-driven).
    const nextValue = enabled || isAuto ? false : true;
    return (
      <div key={key} style={rowStyle}>
        <div>
          <Text fontSize="sm" fontWeight="medium">{label}</Text>
          <Text fontSize="xs" color="gray.500">{flag.description}</Text>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <Badge
            colorScheme={
              flag.source === "env" ? "purple" : flag.source === "db" ? "blue" : "gray"
            }
          >
            {flag.source}
          </Badge>
          <Toggle
            checked={enabled || isAuto}
            disabled={toggling === key}
            onChange={(next) => setFlag(key, next, label)}
          />
        </div>
      </div>
    );
  };

  if (loading) {
    return (
      <Box p={6}>
        <Spinner size="lg" />
        <Text mt={4}>Loading BPE workspace status…</Text>
      </Box>
    );
  }

  if (error) {
    return (
      <Box p={6}>
        <Text color="red.500">{error}</Text>
        <Button mt={3} onClick={load}>Retry</Button>
      </Box>
    );
  }

  const policyRows = Object.entries(overview?.consult_policy || {}).sort(
    (a, b) => (b[1].episodes || 0) - (a[1].episodes || 0)
  );
  const families = Object.keys(overview?.population || {});

  return (
    <Box p={6} data-testid="bpe-manager">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <Heading size="lg">BPE Workspace</Heading>
        <Button size="sm" onClick={load}>Refresh</Button>
      </div>
      <Text color="gray.500" mb={6} maxW="3xl">
        The BPE (Belief / Progress / Experience) workspace gives every agent a
        live memory it can consult and update while it works: Belief = facts
        about the environment, Progress = committed subgoals, Experience =
        consolidated lessons. Gating and evolution are automatic — they
        self-regulate from episode evidence, and every automatic decision is
        logged. See docs/architecture/BPE_WORKSPACE_PLAN.md.
      </Text>

      {/* Mode summary */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 16, marginBottom: 24 }}>
        {[
          ["Workspace", overview?.modes.workspace_enabled ? "On" : "Off"],
          ["Consult gating", overview?.modes.consult_gating_active ? "Active" : "Shadow"],
          ["Evolution apply", overview?.modes.evolution_apply_enabled ? "Enabled" : "Held"],
          ["Automation", overview?.modes.automation_active ? "Auto" : "Off"],
        ].map(([label, value]) => (
          <div key={label} style={cardStyle}>
            <div style={{ fontSize: "0.75rem", color: "gray.500" }}>{label}</div>
            <div style={{ fontSize: "1.5rem", fontWeight: 700 }}>{value}</div>
          </div>
        ))}
      </div>

      {/* Status messages */}
      {(flagError || applyMsg || applyError) && (
        <div style={{ marginBottom: 16 }}>
          {flagError && <Text color="red.500" fontSize="sm">{flagError}</Text>}
          {applyError && <Text color="red.500" fontSize="sm">{applyError}</Text>}
          {applyMsg && <Text color="green.500" fontSize="sm">{applyMsg}</Text>}
        </div>
      )}

      {/* Flag toggles */}
      <Heading size="md" mb={2}>Switches</Heading>
      <Text fontSize="sm" color="gray.500" mb={3}>
        Toggles persist as UI overrides. An environment variable of the same
        name always wins (badge shows the winning source: env / db / default).
      </Text>
      <div style={{ ...cardStyle, marginBottom: 32 }}>
        {Object.keys(FLAG_LABELS).map(renderFlagRow)}
      </div>

      {/* Consult policy per agent */}
      <Heading size="md" mb={2}>Consult policy (per agent)</Heading>
      <Text fontSize="sm" color="gray.500" mb={3}>
        value EMA &lt; 0 for 5+ episodes suppresses that agent's workspace
        until episodes recover. Harness-call rate trends toward ~1 per
        episode.
      </Text>
      <table style={tableStyle}>
        <thead>
          <tr>
            <th style={cellStyle}>Agent</th>
            <th style={cellStyle}>Episodes</th>
            <th style={cellStyle}>Value EMA</th>
            <th style={cellStyle}>Consults/episode</th>
            <th style={cellStyle}>Render mode</th>
            <th style={cellStyle}>Status</th>
          </tr>
        </thead>
        <tbody>
          {policyRows.length === 0 && (
            <tr><td style={cellStyle} colSpan={6}>No agent has consulted the workspace yet.</td></tr>
          )}
          {policyRows.map(([agent, s]) => (
            <tr key={agent}>
              <td style={cellStyle}>{agent}</td>
              <td style={cellStyle}>{s.episodes ?? 0}</td>
              <td style={cellStyle}>{(s.value_ema ?? 0).toFixed(2)}</td>
              <td style={cellStyle}>{(s.harness_call_rate ?? 0).toFixed(2)}</td>
              <td style={cellStyle}>{s.render_mode || "full"}</td>
              <td style={cellStyle}>
                {s.suppressed ? (
                  <Badge colorScheme="red">Suppressed</Badge>
                ) : (
                  <Badge colorScheme="green">Active</Badge>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div style={{ height: 32 }} />

      {/* Evolution */}
      <Heading size="md" mb={2}>Evolution</Heading>
      <Text fontSize="sm" color="gray.500" mb={3}>
        Searches for better workspace bounds (subgoal cap, recall depth,
        experience capacity, render budget). Applies automatically when a
        family has {overview?.thresholds.min_evaluated_genomes ?? 3} distinct
        evaluated genomes and best fitness ≥{" "}
        {overview?.thresholds.evolution_apply_fitness ?? 0.25}; "Apply now"
        force-deploys the current best.
      </Text>
      <div style={{ display: "flex", flexDirection: "column", gap: 12, marginBottom: 32 }}>
        {families.length === 0 && (
          <Text fontSize="sm" color="gray.500">
            No evolution families evaluated yet — genomes appear as agents
            accumulate episodes.
          </Text>
        )}
        {families.map((family) => {
          const inds = overview!.population[family] || [];
          const best = inds.length
            ? Math.max(...inds.map((i) => i.fitness || 0))
            : 0;
          const ready = (overview?.evolution_readiness || []).find(
            (r) => r.family === family
          );
          return (
            <div
              key={family}
              style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderWidth: 1, borderRadius: 8, padding: 12 }}
            >
              <div>
                <Text fontWeight="medium">{family}</Text>
                <Text fontSize="xs" color="gray.500">
                  {inds.length} genomes · best fitness {best.toFixed(2)} ·{" "}
                  {ready?.ready ? "ready to apply" : "evidence pending"}
                </Text>
              </div>
              <Button
                size="sm"
                disabled={!inds.length || applying === family}
                onClick={() => applyGenome(family)}
              >
                {applying === family ? "Applying…" : "Apply now"}
              </Button>
            </div>
          );
        })}
      </div>

      {/* Workspaces */}
      <Heading size="md" mb={2}>Cached workspaces</Heading>
      <table style={tableStyle}>
        <thead>
          <tr>
            <th style={cellStyle}>Workspace</th>
            <th style={cellStyle}>Agent</th>
            <th style={cellStyle}>Scope</th>
            <th style={cellStyle}>Subgoals (done)</th>
            <th style={cellStyle}>Pending notes</th>
            <th style={cellStyle}>Experience</th>
            <th style={cellStyle}>Consults (episode)</th>
          </tr>
        </thead>
        <tbody>
          {(overview?.workspaces || []).length === 0 && (
            <tr><td style={cellStyle} colSpan={7}>No cached workspaces yet.</td></tr>
          )}
          {(overview?.workspaces || []).map((w) => (
            <tr key={`${w.workspace_id}/${w.agent_id}/${w.scope_key}`}>
              <td style={cellStyle}>{w.workspace_id}</td>
              <td style={cellStyle}>{w.agent_id}</td>
              <td style={cellStyle}>{w.scope_key || "—"}</td>
              <td style={cellStyle}>{w.progress_done}/{w.progress_count}</td>
              <td style={cellStyle}>{w.pending_notes}</td>
              <td style={cellStyle}>
                {Object.entries(w.experience_counts)
                  .filter(([, n]) => n > 0)
                  .map(([cat, n]) => `${cat}: ${n}`)
                  .join(", ") || "—"}
              </td>
              <td style={cellStyle}>{w.episode_consults}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Telemetry */}
      <Heading size="md" mb={2}>Harness telemetry</Heading>
      <table style={tableStyle}>
        <thead>
          <tr>
            <th style={cellStyle}>Span</th>
            <th style={cellStyle}>Count</th>
            <th style={cellStyle}>Avg latency (ms)</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(overview?.telemetry || {}).length === 0 && (
            <tr><td style={cellStyle} colSpan={3}>No bpe.* spans recorded yet.</td></tr>
          )}
          {Object.entries(overview?.telemetry || {}).map(([name, s]) => (
            <tr key={name}>
              <td style={cellStyle}>{name}</td>
              <td style={cellStyle}>{s.count}</td>
              <td style={cellStyle}>{s.avg_latency_ms}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <Text fontSize="xs" color="gray.500">
        Persisted snapshots: {overview?.persistence.snapshot_files ?? 0} file(s)
        under {overview?.persistence.data_dir || "backend/data/bpe_workspaces"}.
      </Text>
    </Box>
  );
};

export default BPEManager;
