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
import { useToast } from "@/components/ui/use-toast";
import {
  GraduationCap,
  RefreshCw,
  ShieldCheck,
  ThumbsUp,
  ThumbsDown,
  CheckCircle2,
  PauseCircle,
  HelpCircle,
  BookOpen,
} from "lucide-react";
import { apiClient } from "@/lib/api";
import {
  getSettings,
  resetSetting,
  updateSetting,
  type SettingEntry,
} from "@/lib/runtime-settings-api";

/**
 * Learning & Verification — admin surface (guidance + management).
 *
 * Two self-improving subsystems, explained and managed in one place:
 *  1. Rated-exchange learning — thumbs up/down on chat answers become
 *     permanent examples (approved answers = demonstrations, rejected
 *     patterns = cautions); comment-bearing rejections also teach student
 *     agents as permanent correction lessons.
 *  2. Verification panel — 3 AI judges vote on whether mission-critical /
 *     complex answers are grounded in their evidence.
 *
 * Management = the runtime-settings flags (env vars always win) + health
 * stats. Backend: GET /api/v1/admin/settings/learning-status and the shared
 * settings API (admin role required).
 * Long-form guide: docs/guides/LEARNING_VERIFICATION_GUIDE.md
 */

const SOURCE_LABELS: Record<string, string> = {
  env: "env override",
  db: "UI setting",
  default: "default",
};

const MODE_OPTIONS = [
  { value: "off", label: "Off — disabled" },
  { value: "shadow", label: "Shadow — learns/checks quietly, answers unchanged (recommended)" },
  { value: "enforce", label: "Enforce — actively shapes answers" },
];

const ON_OFF_OPTIONS = [
  { value: "true", label: "On" },
  { value: "false", label: "Off" },
];

interface FlagDef {
  key: string;
  label: string;
  hint: string;
  kind: "select" | "number";
  options?: { value: string; label: string }[];
  step?: number;
}

const FLAGS: FlagDef[] = [
  {
    key: "ATOM_EXCHANGE_MEMORY",
    label: "Learning from your ratings",
    hint: "Off / Shadow / Enforce — see the guide card below for what each mode does.",
    kind: "select",
    options: MODE_OPTIONS,
  },
  {
    key: "ATOM_EXCHANGE_AUTO_PROMOTE",
    label: "Auto-promote learning",
    hint: "Lets the hourly maintenance switch shadow → enforce by itself once there are enough rated exchanges (20+, at least 3 of each).",
    kind: "select",
    options: ON_OFF_OPTIONS,
  },
  {
    key: "ATOM_EXCHANGE_DISTILL_MIN",
    label: "Corrections per lesson",
    hint: "How many similar thumbs-down answers with a comment are distilled into one permanent lesson for student agents.",
    kind: "number",
  },
  {
    key: "ATOM_VERIFY_PANEL",
    label: "Answer verification panel",
    hint: "Off / Shadow / Enforce — 3 AI judges check mission-critical & complex answers against their evidence.",
    kind: "select",
    options: MODE_OPTIONS,
  },
  {
    key: "ATOM_VERIFY_PANEL_AUTO_PROMOTE",
    label: "Auto-promote panel",
    hint: "Lets the hourly maintenance switch shadow → enforce by itself once the panel's run record is healthy. Turning the panel ON at all stays a manual choice (it costs extra AI calls per turn).",
    kind: "select",
    options: ON_OFF_OPTIONS,
  },
  {
    key: "ATOM_VERIFY_PANEL_MIN_RUNS",
    label: "Panel gate: minimum runs",
    hint: "Recorded panel runs required before auto-promotion health is evaluated.",
    kind: "number",
  },
  {
    key: "ATOM_VERIFY_PANEL_MIN_RAN_RATE",
    label: "Panel gate: completion rate",
    hint: "Fraction of runs that must complete (0-1). Below this the panel is considered flaky.",
    kind: "number",
    step: 0.05,
  },
  {
    key: "ATOM_VERIFY_PANEL_MIN_AGREEMENT",
    label: "Panel gate: judge agreement",
    hint: "Minimum mean judge agreement (0-1) for votes to count as meaningful.",
    kind: "number",
    step: 0.05,
  },
];

interface LearningStatus {
  exchange: {
    mode: string;
    source: string;
    env_locked: boolean;
    auto_promote: boolean;
    counts: { positive: number; negative: number; total: number };
  };
  panel: {
    mode: string;
    source: string;
    env_locked: boolean;
    auto_promote: boolean;
    stats: { total: number; ran: number; ran_rate: number; mean_agreement: number };
  };
}

async function fetchStatus(): Promise<LearningStatus> {
  const res = await apiClient.fetch("/api/v1/admin/settings/learning-status");
  const body = await res.json().catch((): null => null);
  if (!res.ok || !body?.success) {
    throw new Error(body?.detail || "Learning status unavailable");
  }
  return body.data as LearningStatus;
}

function ModeBadge({
  mode,
}: {
  mode?: string;
}) {
  const on = mode === "enforce";
  const active = mode === "shadow" || on;
  const label = mode === "enforce" ? "enforce" : mode === "shadow" ? "shadow" : "off";
  return (
    <Badge colorScheme={!active ? "gray" : on ? "green" : "blue"} display="inline-flex" alignItems="center" gap={1}>
      {!active ? <PauseCircle className="h-3 w-3" /> : <CheckCircle2 className="h-3 w-3" />}
      {label}
    </Badge>
  );
}

function SourceBadge({ source }: { source?: string }) {
  if (!source) return null;
  return (
    <Badge
      colorScheme={source === "env" ? "amber" : source === "db" ? "blue" : "gray"}
      fontSize="10px"
    >
      {SOURCE_LABELS[source] ?? source}
    </Badge>
  );
}

function FlagRow({
  def,
  entry,
  busy,
  onSave,
  onReset,
}: {
  def: FlagDef;
  entry?: SettingEntry;
  busy: boolean;
  onSave: (key: string, value: string) => void;
  onReset: (key: string) => void;
}) {
  const envLocked = entry?.source === "env";
  const isDefault = entry?.source === "default";
  const value = entry?.value === null || entry?.value === undefined ? "" : String(entry.value);

  return (
    <Box py={3} borderBottomWidth={1} borderColor="gray.600" _last={{ borderBottom: "none" }}>
      <Box display="flex" alignItems="center" justifyContent="space-between" gap={4} flexWrap="wrap">
        <Box minWidth="260px" maxWidth="640px">
          <Text fontWeight="medium" fontSize="sm">
            {def.label} <Code fontSize="xs">{def.key}</Code>
          </Text>
          <Text fontSize="xs" color="gray.400" mt={0.5}>
            {def.hint}
          </Text>
        </Box>
        <Box display="flex" alignItems="center" gap={2}>
          <SourceBadge source={entry?.source} />
          {def.kind === "select" ? (
            <select
              aria-label={def.label}
              data-testid={`lv-flag-${def.key}`}
              value={value || "false"}
              disabled={envLocked || busy}
              onChange={(e) => onSave(def.key, e.target.value)}
              className="h-8 rounded-md border border-border bg-background px-2 text-sm disabled:cursor-not-allowed disabled:opacity-50"
            >
              {(def.options ?? []).map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          ) : (
            <NumSave
              ariaLabel={def.label}
              testId={`lv-flag-${def.key}`}
              initial={value}
              step={def.step}
              disabled={envLocked || busy}
              onSave={(v) => onSave(def.key, v)}
            />
          )}
          {!isDefault && !envLocked && (
            <Button variant="ghost" size="sm" disabled={busy} onClick={() => onReset(def.key)}>
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

function NumSave({
  ariaLabel,
  testId,
  initial,
  step,
  disabled,
  onSave,
}: {
  ariaLabel: string;
  testId: string;
  initial: string;
  step?: number;
  disabled: boolean;
  onSave: (value: string) => void;
}) {
  const [val, setVal] = useState(initial);
  useEffect(() => setVal(initial), [initial]);
  return (
    <Box display="flex" alignItems="center" gap={2}>
      <input
        aria-label={ariaLabel}
        data-testid={testId}
        type="number"
        step={step ?? 1}
        value={val}
        disabled={disabled}
        onChange={(e) => setVal(e.target.value)}
        className="h-8 w-24 rounded-md border border-border bg-background px-2 text-sm disabled:cursor-not-allowed disabled:opacity-50"
      />
      <Button variant="outline" size="sm" disabled={disabled || val === initial} onClick={() => onSave(val)}>
        Save
      </Button>
    </Box>
  );
}

const LearningVerificationPage = () => {
  const [status, setStatus] = useState<LearningStatus | null>(null);
  const [settings, setSettings] = useState<Record<string, SettingEntry>>({});
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [flagBusy, setFlagBusy] = useState(false);
  const { toast } = useToast();

  const fetchAll = useCallback(async () => {
    setRefreshing(true);
    setLoadError(null);
    try {
      const [statusData, settingsData] = await Promise.all([fetchStatus(), getSettings()]);
      setStatus(statusData);
      const byKey: Record<string, SettingEntry> = {};
      for (const s of settingsData.settings ?? []) byKey[s.key] = s;
      setSettings(byKey);
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  const saveFlag = async (key: string, value: string) => {
    setFlagBusy(true);
    try {
      await updateSetting(key, value);
      toast({
        title: "Setting saved",
        description: `${key} → ${value}. Takes effect within a minute (settings cache) — at the next turn for prompt changes.`,
        variant: "success",
      });
      await fetchAll();
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
      await fetchAll();
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

  const exchange = status?.exchange;
  const panel = status?.panel;

  return (
    <>
      <Head>
        <title>Learning &amp; Verification | Atom</title>
      </Head>
      <Container maxW="container.xl" py={8}>
        <Box mb={6} display="flex" justifyContent="space-between" alignItems="center">
          <Box>
            <Heading as="h1" size="xl" mb={2} display="flex" alignItems="center" gap={2}>
              <GraduationCap className="h-8 w-8 text-blue-500" /> Learning &amp; Verification
            </Heading>
            <Text color="gray.500">
              How your agents learn from every rating you give — and how AI judges verify the
              answers that matter most. Guidance first, management below.
            </Text>
          </Box>
          <Button variant="outline" onClick={fetchAll} disabled={refreshing}>
            <RefreshCw className={`h-4 w-4 mr-2 ${refreshing ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </Box>

        {loadError && (
          <Card className="mb-6" data-testid="lv-error">
            <CardContent>
              <Text color="red.400" fontSize="sm">
                {loadError} — both features require an admin role; if you are one, check that the
                backend is running.
              </Text>
            </CardContent>
          </Card>
        )}

        <Card className="mb-6" data-testid="lv-guidance">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <HelpCircle className="h-5 w-5 text-blue-400" /> What am I looking at?
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Text fontSize="sm" color="gray.400" mb={3}>
              Every time you rate a chat answer with thumbs up or thumbs down, that exchange — your
              question and the full answer — is remembered as a permanent example. Over time the
              agents build a library of <strong>answers you approved</strong> (patterns to imitate)
              and <strong>answers you rejected</strong> (patterns to avoid). This is learning from
              positive and negative examples, and both halves matter: approvals teach the shape of a
              good answer, rejections draw the line it must not cross.
            </Text>
            <ul className="mb-3 space-y-2 text-sm text-gray-300">
              <li className="flex items-start gap-2">
                <ThumbsUp className="h-4 w-4 mt-0.5 text-green-400 shrink-0" />
                <span>
                  <strong>Thumbs up</strong> — the pair is stored and the agent&apos;s mastery of
                  that topic grows, so extra training scaffolding gradually withdraws.
                </span>
              </li>
              <li className="flex items-start gap-2">
                <ThumbsDown className="h-4 w-4 mt-0.5 text-red-400 shrink-0" />
                <span>
                  <strong>Thumbs down</strong> — the pair is stored as a caution.{" "}
                  <strong>If you also write a comment, it becomes a correction the agent is
                  taught</strong> — a permanent instruction that survives graduation and is applied
                  on every later turn. Comments genuinely are corrections; a bare thumbs-down is
                  kept as a caution but never turned into a vague lesson.
                </span>
              </li>
              <li className="flex items-start gap-2">
                <BookOpen className="h-4 w-4 mt-0.5 text-blue-400 shrink-0" />
                <span>
                  <strong>Recurring problems are distilled</strong> — when several similar rejected
                  answers pile up on the same topic, the hourly maintenance merges them into one
                  pattern-level lesson instead of letting them stack.
                </span>
              </li>
              <li className="flex items-start gap-2">
                <ShieldCheck className="h-4 w-4 mt-0.5 text-purple-400 shrink-0" />
                <span>
                  <strong>Verification panel</strong> — on mission-critical or complex turns, three
                  AI judges independently check the answer against the evidence it was written from
                  and vote. In enforce mode, an answer a judge majority finds ungrounded is
                  regenerated once; if it still fails, an honest caveat is attached.
                </span>
              </li>
            </ul>
            <Text fontSize="sm" color="gray.400" mb={3}>
              <strong>The three modes</strong> (used by both features):{" "}
              <Code fontSize="xs">off</Code> does nothing;{" "}
              <Code fontSize="xs">shadow</Code> learns and checks quietly while every answer stays
              exactly what it would have been — this is the recommended starting point;{" "}
              <Code fontSize="xs">enforce</Code> lets the accumulated examples and verdicts actually
              shape replies. Learning itself (storage, lessons, mastery) happens in shadow and
              enforce alike — the flag only controls whether answers are shaped.
            </Text>
            <Text fontSize="sm" color="gray.400">
              Auto-promotion is opt-in per feature: when armed, the hourly maintenance flips{" "}
              <Code fontSize="xs">shadow → enforce</Code> by itself once the evidence is healthy
              (enough rated exchanges, or a healthy judge record). It never flips the other way, it
              never turns a paid feature on from off, and an environment variable always overrides
              this page — that is the kill-switch. Full guide:{" "}
              <Code fontSize="xs">docs/guides/LEARNING_VERIFICATION_GUIDE.md</Code>.
            </Text>
          </CardContent>
        </Card>

        <SimpleGrid columns={{ base: 1, md: 2 }} gap={6} mb={6}>
          <Card data-testid="lv-card-exchange">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Learning from ratings</CardTitle>
              <GraduationCap className="h-4 w-4 text-blue-500" />
            </CardHeader>
            <CardContent>
              {exchange ? (
                <>
                  <ModeBadge mode={exchange.mode} />
                  <p className="text-xs text-muted-foreground mt-1">
                    {exchange.mode === "off"
                      ? "Nothing is learned from ratings right now."
                      : exchange.mode === "shadow"
                      ? "Ratings are being learned from; answers are unchanged."
                      : "Approved examples and rejected patterns also shape answers."}
                  </p>
                  <Box mt={3} display="flex" gap={4} alignItems="center" flexWrap="wrap">
                    <Badge colorScheme="green" display="inline-flex" gap={1} alignItems="center">
                      <ThumbsUp className="h-3 w-3" /> {exchange.counts.positive} approved
                    </Badge>
                    <Badge colorScheme="red" display="inline-flex" gap={1} alignItems="center">
                      <ThumbsDown className="h-3 w-3" /> {exchange.counts.negative} rejected
                    </Badge>
                    <Badge colorScheme="gray">{exchange.counts.total} examples total</Badge>
                  </Box>
                  {exchange.auto_promote && (
                    <Text fontSize="xs" color="blue.300" mt={2}>
                      Auto-promotion armed — enforce latches automatically once the corpus is
                      healthy.
                    </Text>
                  )}
                </>
              ) : (
                <Text>—</Text>
              )}
            </CardContent>
          </Card>

          <Card data-testid="lv-card-panel">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Verification panel</CardTitle>
              <ShieldCheck className="h-4 w-4 text-purple-500" />
            </CardHeader>
            <CardContent>
              {panel ? (
                <>
                  <ModeBadge mode={panel.mode} />
                  <p className="text-xs text-muted-foreground mt-1">
                    {panel.mode === "off"
                      ? "High-stakes answers are not verified."
                      : panel.mode === "shadow"
                      ? "Judges vote on every high-stakes answer; replies unchanged."
                      : "Ungrounded answers are regenerated once, with an honest caveat if still ungrounded."}
                  </p>
                  <Box mt={3} display="flex" gap={3} alignItems="center" flexWrap="wrap">
                    <Badge colorScheme="gray">{panel.stats.total} runs recorded</Badge>
                    <Badge colorScheme={panel.stats.ran_rate >= 0.9 ? "green" : "amber"}>
                      {Math.round(panel.stats.ran_rate * 100)}% completed
                    </Badge>
                    <Badge
                      colorScheme={panel.stats.mean_agreement >= 0.5 ? "green" : "amber"}
                    >
                      {Math.round(panel.stats.mean_agreement * 100)}% mean agreement
                    </Badge>
                  </Box>
                  {panel.auto_promote && (
                    <Text fontSize="xs" color="blue.300" mt={2}>
                      Auto-promotion armed — enforce latches automatically once the run record is
                      healthy.
                    </Text>
                  )}
                </>
              ) : (
                <Text>—</Text>
              )}
            </CardContent>
          </Card>
        </SimpleGrid>

        <Card data-testid="lv-flags">
          <CardHeader>
            <CardTitle className="text-lg">Manage the learning loop</CardTitle>
            <CardDescription>
              Changes take effect within a minute and apply to every chat surface. Values set by an
              environment variable are locked — remove the variable to manage them here.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {loading ? (
              <Text color="gray.500" fontSize="sm">
                Loading…
              </Text>
            ) : (
              FLAGS.map((def) => (
                <FlagRow
                  key={def.key}
                  def={def}
                  entry={settings[def.key]}
                  busy={flagBusy}
                  onSave={saveFlag}
                  onReset={resetFlag}
                />
              ))
            )}
          </CardContent>
        </Card>
      </Container>
    </>
  );
};

export default dynamic(() => Promise.resolve(LearningVerificationPage), {
  ssr: false,
});
