import React, { useCallback, useEffect, useState } from "react";
import dynamic from "next/dynamic";
import Head from "next/head";
import {
  Badge,
  Box,
  Container,
  Heading,
  Text,
  SimpleGrid,
  Code,
} from "@chakra-ui/react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/use-toast";
import {
  Brain,
  RefreshCw,
  Gauge,
  Sparkles,
  ShieldCheck,
  Database,
  Activity,
  CheckCircle2,
  PauseCircle,
  HelpCircle,
} from "lucide-react";
import {
  applyBpeGenome,
  getBpeOverview,
  getBpeWorkspaceDetail,
  type BpeFlagState,
  type BpeOverview,
  type BpeWorkspaceDetail,
  type BpeWorkspaceSummary,
} from "@/lib/bpe-api";
import { resetSetting, updateSetting } from "@/lib/runtime-settings-api";

/**
 * BPE (Belief / Progress / Experience) Agent Workspace — admin surface.
 *
 * The subsystem is self-regulating (consult gating and genome application
 * flip themselves from recorded episode evidence), so this page is
 * primarily observability + guidance, with narrow management: the four
 * mode flags (via the shared runtime-settings API; env vars always win)
 * and the evidence-gated "apply best genome" action.
 *
 * Backend: /api/v1/admin/bpe/* (admin role required).
 */

const SOURCE_LABELS: Record<string, string> = {
  env: "env override",
  db: "UI setting",
  default: "default",
};

// The four operator-facing mode flags. DATA_DIR is ops-only and shown
// read-only; the workspace master flag gets its own on/off select.
const MODE_FLAGS: {
  key: string;
  label: string;
  options: { value: string; label: string }[];
}[] = [
  {
    key: "ATOM_BPE_CONSULT_POLICY",
    label: "Consult policy",
    options: [
      { value: "auto", label: "Auto — evidence-driven (recommended)" },
      { value: "true", label: "Always gate (force on)" },
      { value: "false", label: "Shadow only — never gate" },
    ],
  },
  {
    key: "ATOM_BPE_EVOLUTION",
    label: "Genome application",
    options: [
      { value: "auto", label: "Auto — evidence-gated (recommended)" },
      { value: "true", label: "Force-apply as soon as a genome exists" },
      { value: "false", label: "Proposal-only (never apply)" },
    ],
  },
  {
    key: "ATOM_BPE_EVOLUTION_ENABLED",
    label: "Per-family apply override",
    options: [
      { value: "auto", label: "Auto — defer to the mode above" },
      { value: "true", label: "Force-apply" },
      { value: "false", label: "Hold" },
    ],
  },
  {
    key: "ATOM_BPE_AUTOMATION",
    label: "Master automation",
    options: [
      { value: "auto", label: "On — subsystem self-regulates" },
      { value: "off", label: "Off — kill all automatic flips" },
    ],
  },
];

function ModeBadge({ on, onLabel = "active", offLabel = "off" }: { on: boolean; onLabel?: string; offLabel?: string }) {
  return (
    <Badge colorScheme={on ? "green" : "gray"} display="inline-flex" alignItems="center" gap={1}>
      {on ? <CheckCircle2 className="h-3 w-3" /> : <PauseCircle className="h-3 w-3" />}
      {on ? onLabel : offLabel}
    </Badge>
  );
}

function FlagRow({
  flagKey,
  label,
  options,
  state,
  busy,
  onSave,
  onReset,
}: {
  flagKey: string;
  label: string;
  options: { value: string; label: string }[];
  state?: BpeFlagState;
  busy: boolean;
  onSave: (key: string, value: string) => void;
  onReset: (key: string) => void;
}) {
  const envLocked = state?.source === "env";
  const currentValue = String(state?.value ?? "auto");
  const isDefault = state?.source === "default";
  return (
    <Box py={3} borderBottomWidth={1} borderColor="gray.600" _last={{ borderBottom: "none" }}>
      <Box display="flex" alignItems="center" justifyContent="space-between" gap={4} flexWrap="wrap">
        <Box minWidth="240px">
          <Text fontWeight="medium" fontSize="sm">
            {label} <Code fontSize="xs">{flagKey}</Code>
          </Text>
          <Text fontSize="xs" color="gray.400" mt={0.5}>
            {state?.description}
          </Text>
        </Box>
        <Box display="flex" alignItems="center" gap={2}>
          {state && (
            <Badge
              colorScheme={state.source === "env" ? "amber" : state.source === "db" ? "blue" : "gray"}
              fontSize="10px"
            >
              {SOURCE_LABELS[state.source] ?? state.source}
            </Badge>
          )}
          <select
            aria-label={`${label} mode`}
            data-testid={`bpe-flag-${flagKey}`}
            value={currentValue}
            disabled={envLocked || busy}
            onChange={(e) => onSave(flagKey, e.target.value)}
            className="h-8 rounded-md border border-border bg-background px-2 text-sm disabled:cursor-not-allowed disabled:opacity-50"
          >
            {options.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          {!isDefault && !envLocked && (
            <Button variant="ghost" size="sm" disabled={busy} onClick={() => onReset(flagKey)}>
              Reset
            </Button>
          )}
        </Box>
      </Box>
      {envLocked && (
        <Text fontSize="xs" color="amber.400" mt={1}>
          Set by an environment variable — remove it from .env to manage here (env always wins).
        </Text>
      )}
    </Box>
  );
}

const SUBGOAL_STATUS_SCHEMES: Record<string, string> = {
  done: "green",
  in_progress: "blue",
  blocked: "red",
  pending: "gray",
};

function WorkspaceDetailPanel({ detail }: { detail: BpeWorkspaceDetail }) {
  const totalExperience = Object.values(detail.experience).reduce(
    (sum, entries) => sum + (entries?.length ?? 0),
    0
  );
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg flex items-center gap-2">
          <Database className="h-5 w-5 text-blue-500" /> Workspace state —{" "}
          <Code fontSize="sm">
            {detail.workspace_id} / {detail.agent_id} / {detail.scope_key || "execution"}
          </Code>
        </CardTitle>
        <CardDescription>
          The policy-facing (Belief, Progress, Experience) state the agent sees in its prompt.
          Belief is answered live by adapters; Progress and Experience are shown below.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <Box>
          <Text fontWeight="semibold" fontSize="sm" mb={2}>
            Progress — committed subgoals ({detail.progress.length})
          </Text>
          {detail.progress.length === 0 ? (
            <Text color="gray.500" fontSize="sm">
              No subgoals committed yet. The agent creates them via the{" "}
              <Code fontSize="xs">workspace.commit</Code> meta-action when it plans multi-step work.
            </Text>
          ) : (
            <ul className="space-y-1 text-sm">
              {detail.progress.map((s, i) => (
                <li key={i} className="flex items-center gap-2">
                  <Badge colorScheme={SUBGOAL_STATUS_SCHEMES[s.status] ?? "gray"} fontSize="10px">
                    {s.status}
                  </Badge>
                  {s.title}
                </li>
              ))}
            </ul>
          )}
        </Box>
        <Box>
          <Text fontWeight="semibold" fontSize="sm" mb={2}>
            Notes awaiting consolidation ({detail.pending_notes.length})
          </Text>
          {detail.pending_notes.length === 0 ? (
            <Text color="gray.500" fontSize="sm">
              Buffer empty — notes are drained into Experience by the nightly consolidation sweep.
            </Text>
          ) : (
            <ul className="space-y-1 text-sm text-gray-300">
              {detail.pending_notes.map((n, i) => (
                <li key={i}>• {n}</li>
              ))}
            </ul>
          )}
        </Box>
        <Box>
          <Text fontWeight="semibold" fontSize="sm" mb={2}>
            Experience store ({totalExperience} entries across 4 categories)
          </Text>
          {totalExperience === 0 ? (
            <Text color="gray.500" fontSize="sm">
              No consolidated experience yet. Entries appear after consolidation merges the agent&apos;s
              notes and episode outcomes into skills, task skills, mistakes, and search priors.
            </Text>
          ) : (
            <SimpleGrid columns={{ base: 1, md: 2 }} gap={4}>
              {Object.entries(detail.experience).map(([cat, entries]) =>
                entries.length > 0 ? (
                  <Box key={cat} borderWidth={1} borderColor="gray.600" borderRadius="md" p={3}>
                    <Text fontWeight="semibold" fontSize="xs" textTransform="uppercase" color="gray.400">
                      {cat}
                    </Text>
                    <ul className="mt-2 space-y-1 text-xs">
                      {entries.slice(0, 5).map((e, i) => (
                        <li key={i}>
                          • {e.content} <span className="text-gray-500">({e.uses} uses)</span>
                        </li>
                      ))}
                    </ul>
                  </Box>
                ) : null
              )}
            </SimpleGrid>
          )}
        </Box>
      </CardContent>
    </Card>
  );
}

const BpeAdminPage = () => {
  const [overview, setOverview] = useState<BpeOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [flagBusy, setFlagBusy] = useState(false);
  const [applyingFamily, setApplyingFamily] = useState<string | null>(null);
  const [selectedWorkspace, setSelectedWorkspace] = useState<BpeWorkspaceSummary | null>(null);
  const [workspaceDetail, setWorkspaceDetail] = useState<BpeWorkspaceDetail | null>(null);
  const { toast } = useToast();

  const fetchOverview = useCallback(async () => {
    setRefreshing(true);
    setLoadError(null);
    try {
      setOverview(await getBpeOverview());
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchOverview();
  }, [fetchOverview]);

  const openWorkspace = async (ws: BpeWorkspaceSummary) => {
    setSelectedWorkspace(ws);
    setWorkspaceDetail(null);
    try {
      setWorkspaceDetail(
        await getBpeWorkspaceDetail(ws.workspace_id, ws.agent_id, ws.scope_key)
      );
    } catch (err) {
      toast({
        title: "Could not load workspace",
        description: err instanceof Error ? err.message : String(err),
        variant: "error",
      });
    }
  };

  const saveFlag = async (key: string, value: string) => {
    setFlagBusy(true);
    try {
      await updateSetting(key, value);
      toast({
        title: "Setting saved",
        description: `${key} → ${value}. Takes effect on the next agent step.`,
        variant: "success",
      });
      await fetchOverview();
    } catch (err) {
      toast({
        title: "Save failed",
        description: err instanceof Error ? err.message : String(err),
        variant: "error",
      });
    } finally {
      setFlagBusy(false);
    }
  };

  const resetFlag = async (key: string) => {
    setFlagBusy(true);
    try {
      await resetSetting(key);
      toast({
        title: "Setting reset",
        description: `${key} fell back to its default.`,
        variant: "success",
      });
      await fetchOverview();
    } catch (err) {
      toast({
        title: "Reset failed",
        description: err instanceof Error ? err.message : String(err),
        variant: "error",
      });
    } finally {
      setFlagBusy(false);
    }
  };

  const applyGenome = async (family: string) => {
    setApplyingFamily(family);
    try {
      const result = await applyBpeGenome(family);
      toast({
        title: result.applied ? "Genome applied" : "Genome held",
        description: result.applied
          ? `New workspace bounds are live for new scopes: ${JSON.stringify(result.bounds)}`
          : result.reason ?? "Evidence thresholds not met.",
        variant: result.applied ? "success" : "default",
      });
      await fetchOverview();
    } catch (err) {
      toast({
        title: "Apply failed",
        description: err instanceof Error ? err.message : String(err),
        variant: "error",
      });
    } finally {
      setApplyingFamily(null);
    }
  };

  const modes = overview?.modes;
  const policyEntries = Object.entries(overview?.consult_policy ?? {});
  const readiness = overview?.evolution_readiness ?? [];
  const population = overview?.population ?? {};
  const telemetry = overview?.telemetry;
  const dataDirFlag = overview?.flags?.ATOM_BPE_DATA_DIR;

  return (
    <>
      <Head>
        <title>BPE Agent Workspace | Atom</title>
      </Head>
      <Container maxW="container.xl" py={8}>
        <Box mb={6} display="flex" justifyContent="space-between" alignItems="center">
          <Box>
            <Heading as="h1" size="xl" mb={2} display="flex" alignItems="center" gap={2}>
              <Brain className="h-8 w-8 text-blue-500" /> BPE Agent Workspace
            </Heading>
            <Text color="gray.500">
              The Belief / Progress / Experience harness every agent consults mid-run — with a
              self-regulating consult policy and an offline bounds-evolution search. No operator
              flips required; this page makes it observable and gives you the kill-switches.
            </Text>
          </Box>
          <Button variant="outline" onClick={fetchOverview} disabled={refreshing}>
            <RefreshCw className={`h-4 w-4 mr-2 ${refreshing ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </Box>

        <Card className="mb-6" data-testid="bpe-guidance">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <HelpCircle className="h-5 w-5 text-blue-400" /> What am I looking at?
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Text fontSize="sm" color="gray.400" mb={3}>
              Every agent run keeps three pieces of policy-facing state — <strong>Belief</strong>{" "}
              (task-relevant facts), <strong>Progress</strong> (committed subgoals, capped) and{" "}
              <strong>Experience</strong> (reusable skills, mistakes and priors, capacity-bounded
              with LFU eviction). Agents touch it through four metered meta-actions that consume
              step budget, so consultation has a cost:
            </Text>
            <ul className="mb-3 space-y-1 text-sm text-gray-300">
              {(overview?.meta_actions ?? []).map((a) => (
                <li key={a.name} className="flex items-start gap-2">
                  <CheckCircle2 className="h-4 w-4 mt-0.5 text-blue-400 shrink-0" />
                  <span>
                    <Code fontSize="xs">{a.name}</Code> — {a.description}
                  </span>
                </li>
              ))}
              {(overview?.meta_actions ?? []).length === 0 && (
                <li className="text-gray-500">
                  Meta-action definitions appear once the backend registers the workspace tools.
                </li>
              )}
            </ul>
            <Text fontSize="sm" color="gray.400">
              You do not need to tune any of this: the consult policy learns from episode outcomes
              when to hide the workspace (and un-hides it when agents recover), and the evolution
              search only applies new bounds once the evidence clears the thresholds below. Use the
              flags to intervene, the tables to audit.
            </Text>
          </CardContent>
        </Card>

        <SimpleGrid columns={{ base: 1, md: 4 }} gap={6} mb={6}>
          <Card data-testid="bpe-card-workspace">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Workspace</CardTitle>
              <Brain className="h-4 w-4 text-blue-500" />
            </CardHeader>
            <CardContent>
              {modes ? (
                <ModeBadge on={modes.workspace_enabled} onLabel="enabled" offLabel="shadow only" />
              ) : (
                <Text>—</Text>
              )}
              <p className="text-xs text-muted-foreground mt-1">
                {modes?.workspace_enabled
                  ? "Meta-actions are exposed to agents (INTERN+ maturity and up)."
                  : "Prompt unchanged; consult telemetry still recorded."}
              </p>
            </CardContent>
          </Card>
          <Card data-testid="bpe-card-consult">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Consult policy</CardTitle>
              <Gauge className="h-4 w-4 text-purple-500" />
            </CardHeader>
            <CardContent>
              {modes ? (
                <ModeBadge
                  on={modes.consult_gating_active}
                  onLabel="gating"
                  offLabel="shadow only"
                />
              ) : (
                <Text>—</Text>
              )}
              <p className="text-xs text-muted-foreground mt-1">
                Suppresses rendering for agents whose episodes prove consults hurt — resumes
                automatically on recovery.
              </p>
            </CardContent>
          </Card>
          <Card data-testid="bpe-card-evolution">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Bounds evolution</CardTitle>
              <Sparkles className="h-4 w-4 text-amber-500" />
            </CardHeader>
            <CardContent>
              {modes ? (
                <ModeBadge
                  on={modes.evolution_apply_enabled}
                  onLabel="apply allowed"
                  offLabel="proposal only"
                />
              ) : (
                <Text>—</Text>
              )}
              <p className="text-xs text-muted-foreground mt-1">
                Offline population search over workspace bounds; applies only with enough evaluated
                evidence.
              </p>
            </CardContent>
          </Card>
          <Card data-testid="bpe-card-automation">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Automation</CardTitle>
              <ShieldCheck className="h-4 w-4 text-green-500" />
            </CardHeader>
            <CardContent>
              {modes ? (
                <ModeBadge
                  on={modes.automation_active}
                  onLabel="self-regulating"
                  offLabel="killed"
                />
              ) : (
                <Text>—</Text>
              )}
              <p className="text-xs text-muted-foreground mt-1">
                Master mode: automatic consult/evolution flips, each announced as an auditable{" "}
                <Code fontSize="xs">bpe.automation</Code> span.
              </p>
            </CardContent>
          </Card>
        </SimpleGrid>

        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="text-lg">Mode flags</CardTitle>
            <CardDescription>
              UI overrides persist to the runtime-settings store; an explicit environment variable
              always wins (kill-switch semantics). Changes take effect on the next agent step — no
              restart. The full catalog also lives in Admin → Settings under
              &ldquo;BPE Agent Workspace&rdquo;
              {dataDirFlag?.value ? (
                <>
                  {" "}
                  — durable snapshots: <Code fontSize="xs">{String(dataDirFlag.value)}</Code>{" "}
                  {overview ? `(${overview.persistence.snapshot_files} files)` : ""}
                </>
              ) : (
                "."
              )}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {overview && (
              <>
                <FlagRow
                  flagKey="ATOM_BPE_WORKSPACE_ENABLED"
                  label="Workspace"
                  state={overview.flags.ATOM_BPE_WORKSPACE_ENABLED}
                  busy={flagBusy}
                  onSave={saveFlag}
                  onReset={resetFlag}
                  options={[
                    { value: "true", label: "Enabled (default)" },
                    { value: "false", label: "Shadow-only (opt out)" },
                  ]}
                />
                {MODE_FLAGS.map((f) => (
                  <FlagRow
                    key={f.key}
                    flagKey={f.key}
                    label={f.label}
                    options={f.options}
                    state={overview.flags[f.key]}
                    busy={flagBusy}
                    onSave={saveFlag}
                    onReset={resetFlag}
                  />
                ))}
              </>
            )}
          </CardContent>
        </Card>

        {loadError && (
          <Card className="mb-6 border-red-400" data-testid="bpe-error">
            <CardContent className="py-6 text-center">
              <Text color="red.400" mb={3}>
                {loadError}
              </Text>
              <Button onClick={fetchOverview}>Retry</Button>
            </CardContent>
          </Card>
        )}

        {loading ? (
          <Text color="gray.500">Loading subsystem status…</Text>
        ) : (
          overview && (
            <Tabs defaultValue="consult">
              <TabsList className="mb-4">
                <TabsTrigger value="consult">Consult policy</TabsTrigger>
                <TabsTrigger value="evolution">Evolution</TabsTrigger>
                <TabsTrigger value="workspaces">
                  Workspaces ({overview.workspaces.length})
                </TabsTrigger>
                <TabsTrigger value="telemetry">Telemetry</TabsTrigger>
              </TabsList>

              <TabsContent value="consult">
                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">Per-agent consult value</CardTitle>
                    <CardDescription>
                      Value EMA is the running reward of episodes run with consults (+1 success
                      with sane step efficiency, −1 otherwise). Below{" "}
                      {overview.thresholds.min_episodes_for_value_gate} episodes the gate stays
                      open (no gating on noise); a negative EMA suppresses rendering until episodes
                      recover. Recall-only mode is the annealing signature: commit/note share
                      below {Math.round(overview.thresholds.recall_only_share * 100)}% after{" "}
                      {overview.thresholds.recall_only_min_episodes} episodes.
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    {policyEntries.length === 0 ? (
                      <Text color="gray.500" textAlign="center" py={6}>
                        No episodes recorded yet. Per-agent states appear here after agents run
                        with the workspace enabled — outcome feedback flows in at every run
                        close-out.
                      </Text>
                    ) : (
                      <div className="overflow-x-auto">
                        <table className="w-full text-left text-sm border-collapse">
                          <thead>
                            <tr className="border-b font-medium text-muted-foreground">
                              <th className="py-2 px-3">Agent</th>
                              <th className="py-2 px-3">Episodes</th>
                              <th className="py-2 px-3">Value EMA</th>
                              <th className="py-2 px-3">Consults</th>
                              <th className="py-2 px-3">Calls / episode</th>
                              <th className="py-2 px-3">Render</th>
                              <th className="py-2 px-3">Gate</th>
                            </tr>
                          </thead>
                          <tbody>
                            {policyEntries.map(([agentId, s]) => (
                              <tr key={agentId} className="border-b last:border-0 hover:bg-muted/50">
                                <td className="py-2 px-3">
                                  <Code fontSize="xs">{agentId}</Code>
                                </td>
                                <td className="py-2 px-3">{s.episodes}</td>
                                <td className="py-2 px-3">
                                  <Badge colorScheme={s.value_ema >= 0 ? "green" : "red"}>
                                    {s.value_ema}
                                  </Badge>
                                </td>
                                <td className="py-2 px-3">{s.consults_total}</td>
                                <td className="py-2 px-3">{s.harness_call_rate}</td>
                                <td className="py-2 px-3">
                                  <Badge
                                    colorScheme={s.render_mode === "full" ? "blue" : "purple"}
                                  >
                                    {s.render_mode === "full" ? "full" : "recall-only"}
                                  </Badge>
                                </td>
                                <td className="py-2 px-3">
                                  {s.suppressed ? (
                                    <Badge colorScheme="orange">suppressed</Badge>
                                  ) : (
                                    <Badge colorScheme="green">rendering</Badge>
                                  )}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="evolution">
                <Card className="mb-6">
                  <CardHeader>
                    <CardTitle className="text-lg">Population readiness</CardTitle>
                    <CardDescription>
                      Auto-apply fires when a family holds ≥{" "}
                      {overview.thresholds.min_evaluated_genomes} distinct evaluated genomes and its
                      best fitness clears {overview.thresholds.evolution_apply_fitness}. Fitness =
                      consult value EMA penalized as the call rate drifts from the{" "}
                      {overview.thresholds.target_call_rate}/episode annealing target. Applying is
                      always gated — the button below uses the same rules as the automatic path.
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    {readiness.length === 0 ? (
                      <Text color="gray.500" textAlign="center" py={6}>
                        No families in the population yet. Genomes land here as the offline search
                        evaluates candidate bounds per agent family.
                      </Text>
                    ) : (
                      <div className="overflow-x-auto">
                        <table className="w-full text-left text-sm border-collapse">
                          <thead>
                            <tr className="border-b font-medium text-muted-foreground">
                              <th className="py-2 px-3">Family</th>
                              <th className="py-2 px-3">Evaluated genomes</th>
                              <th className="py-2 px-3">Best fitness</th>
                              <th className="py-2 px-3">Auto-apply</th>
                              <th className="py-2 px-3" />
                            </tr>
                          </thead>
                          <tbody>
                            {readiness.map((r) => (
                              <tr key={r.family} className="border-b last:border-0 hover:bg-muted/50">
                                <td className="py-2 px-3">
                                  <Code fontSize="xs">{r.family}</Code>
                                </td>
                                <td className="py-2 px-3">{r.evaluated_genomes}</td>
                                <td className="py-2 px-3">{r.best_fitness}</td>
                                <td className="py-2 px-3">
                                  {r.apply_ready ? (
                                    <Badge colorScheme="green">ready</Badge>
                                  ) : (
                                    <Badge colorScheme="gray">evidence pending</Badge>
                                  )}
                                </td>
                                <td className="py-2 px-3 text-right">
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    disabled={!r.apply_ready || applyingFamily === r.family}
                                    onClick={() => applyGenome(r.family)}
                                  >
                                    Apply best genome
                                  </Button>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </CardContent>
                </Card>
                {Object.keys(population).length > 0 && (
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-lg">Candidate bounds (population)</CardTitle>
                      <CardDescription>
                        Elite pool per family (cap {overview.thresholds.population_size}). Active
                        bounds for new workspaces:{" "}
                        <Code fontSize="xs">{JSON.stringify(overview.active_bounds)}</Code>
                      </CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="overflow-x-auto">
                        <table className="w-full text-left text-sm border-collapse">
                          <thead>
                            <tr className="border-b font-medium text-muted-foreground">
                              <th className="py-2 px-3">Family</th>
                              <th className="py-2 px-3">Genome</th>
                              <th className="py-2 px-3">Fitness</th>
                            </tr>
                          </thead>
                          <tbody>
                            {Object.entries(population).flatMap(([family, individuals]) =>
                              individuals.map((ind, i) => (
                                <tr
                                  key={`${family}-${i}`}
                                  className="border-b last:border-0 hover:bg-muted/50"
                                >
                                  <td className="py-2 px-3">
                                    <Code fontSize="xs">{family}</Code>
                                    {i === 0 && (
                                      <Badge colorScheme="green" ml={2} fontSize="10px">
                                        best
                                      </Badge>
                                    )}
                                  </td>
                                  <td className="py-2 px-3">
                                    <Code fontSize="xs">{JSON.stringify(ind.genome)}</Code>
                                  </td>
                                  <td className="py-2 px-3">{ind.fitness}</td>
                                </tr>
                              ))
                            )}
                          </tbody>
                        </table>
                      </div>
                    </CardContent>
                  </Card>
                )}
              </TabsContent>

              <TabsContent value="workspaces">
                <Card className={selectedWorkspace ? "mb-6" : ""}>
                  <CardHeader>
                    <CardTitle className="text-lg">Active workspace scopes</CardTitle>
                    <CardDescription>
                      One scope per (workspace, agent, session/execution). Progress and Experience
                      survive restarts via durable snapshots (LRU-bounded); the registry below is
                      the live in-process view. Click a row to inspect its state.
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    {overview.workspaces.length === 0 ? (
                      <Text color="gray.500" textAlign="center" py={6}>
                        No workspaces cached yet. A scope appears here after the first agent step
                        that renders or consults the workspace.
                      </Text>
                    ) : (
                      <div className="overflow-x-auto">
                        <table className="w-full text-left text-sm border-collapse">
                          <thead>
                            <tr className="border-b font-medium text-muted-foreground">
                              <th className="py-2 px-3">Workspace</th>
                              <th className="py-2 px-3">Agent</th>
                              <th className="py-2 px-3">Scope</th>
                              <th className="py-2 px-3">Subgoals</th>
                              <th className="py-2 px-3">Pending notes</th>
                              <th className="py-2 px-3">Experience</th>
                              <th className="py-2 px-3">Consults (episode)</th>
                            </tr>
                          </thead>
                          <tbody>
                            {overview.workspaces.map((w) => {
                              const expTotal = Object.values(w.experience_counts).reduce(
                                (a, b) => a + b,
                                0
                              );
                              const selected =
                                selectedWorkspace?.workspace_id === w.workspace_id &&
                                selectedWorkspace?.agent_id === w.agent_id &&
                                selectedWorkspace?.scope_key === w.scope_key;
                              return (
                                <tr
                                  key={`${w.workspace_id}-${w.agent_id}-${w.scope_key}`}
                                  className={`border-b last:border-0 cursor-pointer hover:bg-muted/50 ${
                                    selected ? "bg-primary/10" : ""
                                  }`}
                                  onClick={() => openWorkspace(w)}
                                >
                                  <td className="py-2 px-3">
                                    <Code fontSize="xs">{w.workspace_id}</Code>
                                  </td>
                                  <td className="py-2 px-3">{w.agent_id}</td>
                                  <td className="py-2 px-3">{w.scope_key || "execution"}</td>
                                  <td className="py-2 px-3">
                                    {w.progress_done}/{w.progress_count} done
                                  </td>
                                  <td className="py-2 px-3">{w.pending_notes}</td>
                                  <td className="py-2 px-3">{expTotal}</td>
                                  <td className="py-2 px-3">{w.episode_consults}</td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </CardContent>
                </Card>
                {selectedWorkspace && workspaceDetail && (
                  <WorkspaceDetailPanel detail={workspaceDetail} />
                )}
              </TabsContent>

              <TabsContent value="telemetry">
                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg flex items-center gap-2">
                      <Activity className="h-5 w-5 text-blue-500" /> Harness telemetry
                    </CardTitle>
                    <CardDescription>
                      Recent <Code fontSize="xs">bpe.*</Code> spans: every workspace read/write is
                      metered (count, errors, latency), and automatic flips are announced as
                      auditable events. Paper annealing target: ~1 consult per episode.
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    {telemetry && telemetry.window_spans === 0 ? (
                      <Text color="gray.500" textAlign="center" py={6}>
                        No spans in the buffer yet — they start flowing with the first workspace
                        action.
                      </Text>
                    ) : (
                      telemetry && (
                        <>
                          <div className="overflow-x-auto mb-6">
                            <table className="w-full text-left text-sm border-collapse">
                              <thead>
                                <tr className="border-b font-medium text-muted-foreground">
                                  <th className="py-2 px-3">Span</th>
                                  <th className="py-2 px-3">Count</th>
                                  <th className="py-2 px-3">Errors</th>
                                  <th className="py-2 px-3">Avg latency</th>
                                </tr>
                              </thead>
                              <tbody>
                                {Object.entries(telemetry.aggregate).map(([name, agg]) => (
                                  <tr key={name} className="border-b last:border-0">
                                    <td className="py-2 px-3">
                                      <Code fontSize="xs">{name}</Code>
                                    </td>
                                    <td className="py-2 px-3">{agg.count}</td>
                                    <td className="py-2 px-3">
                                      {agg.error_count > 0 ? (
                                        <Badge colorScheme="red">{agg.error_count}</Badge>
                                      ) : (
                                        0
                                      )}
                                    </td>
                                    <td className="py-2 px-3">{agg.avg_latency_ms} ms</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                          <Text fontWeight="semibold" fontSize="sm" mb={2}>
                            Automatic flips (audit trail)
                          </Text>
                          {telemetry.automation_flips.length === 0 ? (
                            <Text color="gray.500" fontSize="sm">
                              None yet — the subsystem flips itself only when recorded evidence
                              clears the thresholds, and every flip lands here.
                            </Text>
                          ) : (
                            <ul className="space-y-1 text-sm">
                              {telemetry.automation_flips.map((f, i) => (
                                <li key={i} className="flex items-start gap-2">
                                  <CheckCircle2 className="h-4 w-4 mt-0.5 text-green-400 shrink-0" />
                                  <span>
                                    {f.at ? new Date(f.at * 1000).toLocaleString() : ""} —{" "}
                                    <Code fontSize="xs">{JSON.stringify(f.detail)}</Code>
                                  </span>
                                </li>
                              ))}
                            </ul>
                          )}
                        </>
                      )
                    )}
                  </CardContent>
                </Card>
              </TabsContent>
            </Tabs>
          )
        )}
      </Container>
    </>
  );
};

// Named export gives tests the raw component (no dynamic-loading wait).
export { BpeAdminPage };
export default dynamic(() => Promise.resolve(BpeAdminPage), {
  ssr: false,
});
