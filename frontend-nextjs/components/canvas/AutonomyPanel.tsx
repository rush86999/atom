"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import {
    Lock,
    Zap,
    RefreshCcw,
    Loader2,
    ShieldCheck,
    ShieldAlert,
    Plus,
    Trash2,
} from "lucide-react";
import { Switch } from "../ui/switch";

/**
 * Autonomy policy panel — the owner decides, per action topic, whether the
 * agent ALWAYS needs a human in the loop, may act autonomously once its
 * maturity tier allows, or acts autonomously UNTIL a human correction resets
 * the cycle (the hire proposes again and re-earns autonomy through verified
 * work). Backed by GET/PUT /api/autonomy/topics.
 *
 * Canvas-aware: with canvasId/agentId the backend flags the topics primary
 * for this canvas's type ("On this canvas" section) and attaches each
 * hire's live gate — owner mode × governance maturity × skill-scoped trust
 * × correction cycle — so the panel shows exactly what a turn would enforce
 * today.
 *
 * The optional "never autonomous" task baskets are owner-global, opt-in
 * vetoes. This panel only configures rules and renders the server verdict;
 * it never computes a match locally and never writes topic modes on behalf
 * of a rule.
 */
interface TaskProfile {
    difficulty?: string | null;
    category?: string | null;
    domain?: string | null;
    source?: string;
    signals?: Record<string, string>;
}

interface NeverAutonomousGate {
    applicable?: boolean;
    matched?: boolean;
    potential?: boolean;
    outcome?: string;
    rule_ids?: string[];
    rule_names?: string[];
    reason?: string;
    profile?: TaskProfile | null;
}

interface AutonomyGate {
    outcome: "execute" | "propose";
    reason: string;
    maturity: {
        known: boolean;
        maturity_level: string | null;
        required: string | null;
        ok: boolean;
    };
    trust: {
        enabled: boolean;
        trust: number | null;
        threshold: number;
        cold_start: boolean | null;
        ok: boolean;
    };
    cycle?: {
        reset: boolean;
        tier: string | null;
        required: string | null;
        ok: boolean;
        reason: string | null;
    } | null;
    never_autonomous?: NeverAutonomousGate;
}

interface AutonomyTopic {
    topic: string;
    label: string;
    description: string;
    default_mode: string;
    mode: string;
    canvas_relevant?: boolean;
    gate?: AutonomyGate;
}

type RuleDimension = "difficulty" | "category" | "domain";

interface NeverRuleMatch {
    difficulty?: string[];
    category?: string[];
    domain?: string[];
}

interface AutonomyRule {
    id: string;
    name: string;
    enabled: boolean;
    match: NeverRuleMatch;
    revision?: number;
    scope?: unknown;
    created_at?: string;
    updated_at?: string;
}

interface NeverDimensions {
    difficulty: string[];
    category: string[];
    domain: string[];
}

interface RuleDraft {
    name: string;
    enabled: boolean;
    match: {
        difficulty: string[];
        category: string[];
        domain: string[];
    };
}

type RulesLoadState = "loading" | "ready" | "error" | "unsupported" | "forbidden";
type SaveStatus = "idle" | "saving" | "error" | "conflict" | "saved";

interface SaveState {
    status: SaveStatus;
    message?: string;
    currentRevision?: number;
}

const DIMENSION_KEYS: RuleDimension[] = ["difficulty", "category", "domain"];
const NEW_RULE_KEY = "__new__";
const NAME_MAX = 120;
const DOMAIN_SLUG_RE = /^[a-z][a-z0-9_-]{1,63}$/;
const RULE_COLLECTION = "/api/autonomy/never-rules";

const DIFFICULTY_LABELS: Record<string, string> = {
    simple: "Simple",
    moderate: "Moderate",
    complex: "Complex",
    advanced: "Advanced",
};

const CATEGORY_LABELS: Record<string, string> = {
    code: "Code",
    math: "Math",
    qa: "Q&A",
    extraction: "Extraction",
    planning: "Planning",
    prose: "Prose",
};

function humanizeValue(value: string): string {
    return value
        .replace(/[-_]/g, " ")
        .replace(/\b\w/g, (character) => character.toUpperCase());
}

function dimensionLabel(dimension: RuleDimension, value: string): string {
    if (dimension === "difficulty") return DIFFICULTY_LABELS[value] || humanizeValue(value);
    if (dimension === "category") return CATEGORY_LABELS[value] || humanizeValue(value);
    return value;
}

function asStringArray(value: unknown): string[] | null {
    if (!Array.isArray(value)) return null;
    const result: string[] = [];
    for (const item of value) {
        if (typeof item !== "string") return null;
        const trimmed = item.trim();
        if (trimmed) result.push(trimmed);
    }
    return result;
}

function normalizeRuleMatch(match: unknown): RuleDraft["match"] | null {
    if (match === undefined || match === null) {
        return { difficulty: [], category: [], domain: [] };
    }
    if (typeof match !== "object" || Array.isArray(match)) return null;
    const raw = match as Record<string, unknown>;
    const result: RuleDraft["match"] = { difficulty: [], category: [], domain: [] };
    for (const dimension of DIMENSION_KEYS) {
        const value = raw[dimension];
        if (value === undefined || value === null) continue;
        const values = asStringArray(value);
        if (!values) return null;
        result[dimension] = values;
    }
    return result;
}

function parseRule(value: unknown): AutonomyRule | null {
    if (!value || typeof value !== "object" || Array.isArray(value)) return null;
    const raw = value as Record<string, unknown>;
    if (typeof raw.id !== "string" || !raw.id.trim()) return null;
    if (typeof raw.name !== "string") return null;
    if (typeof raw.enabled !== "boolean") return null;
    const match = normalizeRuleMatch(raw.match);
    if (!match) return null;
    return {
        id: raw.id,
        name: raw.name,
        enabled: raw.enabled,
        match,
        revision:
            typeof raw.revision === "number" && Number.isFinite(raw.revision)
                ? raw.revision
                : undefined,
        scope: raw.scope,
        created_at: typeof raw.created_at === "string" ? raw.created_at : undefined,
        updated_at: typeof raw.updated_at === "string" ? raw.updated_at : undefined,
    };
}

function parseRulesResponse(data: unknown): {
    rules: AutonomyRule[];
    dimensions: NeverDimensions;
} | null {
    if (!data || typeof data !== "object" || Array.isArray(data)) return null;
    const raw = data as Record<string, unknown>;
    if (!Array.isArray(raw.rules)) return null;
    if (!raw.dimensions || typeof raw.dimensions !== "object" || Array.isArray(raw.dimensions)) {
        return null;
    }
    const rawDimensions = raw.dimensions as Record<string, unknown>;
    const dimensions: NeverDimensions = { difficulty: [], category: [], domain: [] };
    for (const dimension of DIMENSION_KEYS) {
        // The server owns the taxonomy: an absent/malformed option list is an
        // unsupported response, never a prompt to guess a competing enum.
        const values = asStringArray(rawDimensions[dimension]);
        if (!values) return null;
        dimensions[dimension] = values;
    }
    const rules: AutonomyRule[] = [];
    for (const item of raw.rules) {
        const rule = parseRule(item);
        if (!rule) return null;
        rules.push(rule);
    }
    return { rules, dimensions };
}

function emptyDraft(): RuleDraft {
    return {
        name: "",
        enabled: true,
        match: { difficulty: [], category: [], domain: [] },
    };
}

function draftFromRule(rule: AutonomyRule): RuleDraft {
    return {
        name: rule.name,
        enabled: rule.enabled,
        match: {
            difficulty: [...(rule.match.difficulty || [])],
            category: [...(rule.match.category || [])],
            domain: [...(rule.match.domain || [])],
        },
    };
}

function sameValueSet(left: string[], right: string[]): boolean {
    const normalize = (values: string[]) =>
        Array.from(new Set(values.map((value) => value.trim()))).sort();
    const a = normalize(left);
    const b = normalize(right);
    return a.length === b.length && a.every((value, index) => value === b[index]);
}

function draftMatchesBaseline(draft: RuleDraft, baseline: RuleDraft): boolean {
    return (
        draft.name === baseline.name &&
        draft.enabled === baseline.enabled &&
        DIMENSION_KEYS.every((dimension) =>
            sameValueSet(draft.match[dimension], baseline.match[dimension])
        )
    );
}

function hasAnyFilter(match: RuleDraft["match"]): boolean {
    return DIMENSION_KEYS.some((dimension) =>
        match[dimension].some((value) => value.trim().length > 0)
    );
}

function validateDraft(draft: RuleDraft): { nameError: string | null; filterError: string | null } {
    const trimmedName = draft.name.trim();
    const nameError = !trimmedName
        ? "Give this rule a name."
        : trimmedName.length > NAME_MAX
          ? `Keep the name to ${NAME_MAX} characters or fewer.`
          : null;
    const filterError = hasAnyFilter(draft.match)
        ? null
        : "Pick at least one difficulty, category, or domain so this rule cannot match everything.";
    return { nameError, filterError };
}

function buildRulePayload(draft: RuleDraft): {
    name: string;
    enabled: boolean;
    match: Record<string, string[]>;
} {
    const match: Record<string, string[]> = {};
    for (const dimension of DIMENSION_KEYS) {
        const values = Array.from(
            new Set(
                draft.match[dimension]
                    .map((value) => value.trim().toLowerCase())
                    .filter(Boolean)
            )
        );
        if (values.length) match[dimension] = values;
    }
    return { name: draft.name.trim(), enabled: draft.enabled, match };
}

function shortErrorDetail(error: unknown): string | null {
    const detail = (error as any)?.response?.data?.detail;
    if (typeof detail !== "string") return null;
    const trimmed = detail.trim();
    return trimmed && trimmed.length <= 200 ? trimmed : null;
}

function errorStatus(error: unknown): number | undefined {
    return (error as any)?.response?.status;
}

function neverGateNeedsReview(never?: NeverAutonomousGate): boolean {
    if (!never) return false;
    return never.matched === true || never.outcome === "review";
}

function ruleNames(never: NeverAutonomousGate): string[] {
    if (!Array.isArray(never.rule_names)) return [];
    return never.rule_names.filter(
        (name): name is string => typeof name === "string" && name.trim().length > 0
    );
}

function NeverGateBanner({ never }: { never: NeverAutonomousGate }) {
    const names = ruleNames(never);
    const reason = typeof never.reason === "string" ? never.reason.trim() : "";
    let copy: string;
    let showNames = false;

    if (never.potential === true) {
        copy =
            "A never-autonomous rule may apply, but task classification data is unavailable. A human must review.";
        showNames = true;
    } else if (never.matched === true) {
        const subject =
            names.length > 1 ? "never-autonomous rules" : "a never-autonomous rule";
        copy = `This task matches ${subject}${
            names.length ? `: ${names.join(", ")}` : ""
        }. A human must approve this execution.`;
    } else {
        // Policy-store failure: review is required, but no rule is claimed.
        copy = "Autonomy policy is unavailable; execution requires human review.";
    }

    return (
        <div
            className="mt-1 rounded bg-background/70 px-1.5 py-1 text-[10px] leading-snug"
            data-testid="autonomy-gate-never"
            role="status"
            title={reason || undefined}
        >
            <p>{copy}</p>
            {showNames && names.length > 0 && (
                <p className="mt-0.5 text-muted-foreground">Rules: {names.join(", ")}</p>
            )}
            {reason && reason !== "never_autonomous_policy_unavailable" && (
                <p className="mt-0.5 text-muted-foreground">{reason}</p>
            )}
        </div>
    );
}

function GateChip({ gate }: { gate: AutonomyGate }) {
    const never = gate.never_autonomous;
    const requiresReview = neverGateNeedsReview(never);
    // A matched rule vetoes autonomy even if a stale raw outcome says execute.
    const execute = gate.outcome === "execute" && !requiresReview;
    const title = requiresReview && never?.reason ? never.reason : gate.reason;
    return (
        <div
            className={`mt-2 rounded px-2 py-1.5 text-[11px] leading-snug ${
                execute
                    ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400"
                    : "bg-amber-500/10 text-amber-700 dark:text-amber-400"
            }`}
            data-testid={`autonomy-gate-${execute ? "execute" : "propose"}`}
            title={title}
        >
            <div className="flex items-start gap-1.5">
                {execute ? (
                    <ShieldCheck className="mt-0.5 h-3 w-3 shrink-0" />
                ) : (
                    <ShieldAlert className="mt-0.5 h-3 w-3 shrink-0" />
                )}
                <span>
                    <strong>
                        {execute ? "Acts autonomously today." : "Proposes for your approval."}
                    </strong>
                    {!requiresReview && <> {gate.reason}</>}
                </span>
            </div>
            {requiresReview && never && <NeverGateBanner never={never} />}
        </div>
    );
}

function GateDetail({ gate }: { gate: AutonomyGate }) {
    const { maturity, trust, cycle, never_autonomous: never } = gate;
    const hasNever =
        !!never &&
        (never.matched === true ||
            never.outcome === "review" ||
            never.applicable === true ||
            !!never.profile);
    if (!maturity.known && !trust.enabled && !cycle?.tier && !hasNever) return null;
    const bits: string[] = [];
    if (maturity.known) {
        bits.push(
            `maturity ${maturity.maturity_level ?? "?"} (needs ${maturity.required ?? "?"})`
        );
    }
    if (trust.enabled) {
        bits.push(
            `trust ${(trust.trust ?? 0).toFixed(2)} / ${trust.threshold.toFixed(2)}${
                trust.cold_start ? " (no evidence yet)" : ""
            }`
        );
    }
    if (cycle?.tier) {
        bits.push(
            `cycle ${cycle.tier} (needs ${cycle.required ?? "?"})${
                cycle.reset ? " — reset by a correction" : ""
            }`
        );
    }
    return (
        <>
            {bits.length > 0 && (
                <p className="mt-1 text-[10px] text-muted-foreground">{bits.join(" · ")}</p>
            )}
            {never?.profile && (
                <p
                    className="mt-1 text-[10px] text-muted-foreground"
                    data-testid="autonomy-gate-profile"
                >
                    Task profile: difficulty {never.profile.difficulty || "not classified"} ·
                    category {never.profile.category || "not classified"} · domain{" "}
                    {never.profile.domain || "not classified"}
                </p>
            )}
        </>
    );
}

function TopicCard({
    topic,
    busy,
    onSetMode,
}: {
    topic: AutonomyTopic;
    busy: boolean;
    onSetMode: (topic: string, mode: string) => void;
}) {
    return (
        <div className="border rounded-lg p-3 bg-background" data-testid={`autonomy-${topic.topic}`}>
            <div className="flex items-start justify-between gap-2">
                <div>
                    <p className="text-sm font-medium">{topic.label}</p>
                    <p className="text-[11px] text-muted-foreground">{topic.description}</p>
                </div>
            </div>
            <div className="mt-2 grid grid-cols-3 gap-1">
                <button
                    onClick={() => onSetMode(topic.topic, "human_always")}
                    disabled={busy}
                    className={`flex items-center justify-center gap-1.5 rounded px-2 py-1.5 text-[11px] font-medium transition-colors ${
                        topic.mode === "human_always"
                            ? "bg-amber-500/15 text-amber-700 dark:text-amber-400 border border-amber-500/40"
                            : "bg-muted/60 text-muted-foreground border border-transparent hover:bg-muted"
                    }`}
                    data-testid={`autonomy-${topic.topic}-hitl`}
                >
                    <Lock className="h-3 w-3" /> Always require me
                </button>
                <button
                    onClick={() => onSetMode(topic.topic, "auto_if_mature")}
                    disabled={busy}
                    className={`flex items-center justify-center gap-1.5 rounded px-2 py-1.5 text-[11px] font-medium transition-colors ${
                        topic.mode === "auto_if_mature"
                            ? "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border border-emerald-500/40"
                            : "bg-muted/60 text-muted-foreground border border-transparent hover:bg-muted"
                    }`}
                    data-testid={`autonomy-${topic.topic}-auto`}
                >
                    <Zap className="h-3 w-3" /> Auto if mature
                </button>
                <button
                    onClick={() => onSetMode(topic.topic, "auto_until_corrected")}
                    disabled={busy}
                    title="Acts autonomously once mature; a human correction resets the cycle — the hire proposes again and re-earns autonomy through verified work."
                    className={`flex items-center justify-center gap-1.5 rounded px-2 py-1.5 text-[11px] font-medium transition-colors ${
                        topic.mode === "auto_until_corrected"
                            ? "bg-sky-500/15 text-sky-700 dark:text-sky-400 border border-sky-500/40"
                            : "bg-muted/60 text-muted-foreground border border-transparent hover:bg-muted"
                    }`}
                    data-testid={`autonomy-${topic.topic}-cycle`}
                >
                    <RefreshCcw className="h-3 w-3" /> Auto until corrected
                </button>
            </div>
            {topic.gate && <GateChip gate={topic.gate} />}
            {topic.gate && <GateDetail gate={topic.gate} />}
        </div>
    );
}

function FilterChip({
    groupLabel,
    label,
    checked,
    disabled,
    testId,
    onToggle,
}: {
    groupLabel: string;
    label: string;
    checked: boolean;
    disabled: boolean;
    testId: string;
    onToggle: () => void;
}) {
    return (
        <label
            className={`inline-flex cursor-pointer items-center gap-1 rounded border px-1.5 py-0.5 text-[10px] leading-tight transition-colors focus-within:ring-1 focus-within:ring-sky-500 ${
                checked
                    ? "border-sky-500/40 bg-sky-500/15 text-sky-700 dark:text-sky-400"
                    : "border-transparent bg-muted/60 text-muted-foreground hover:bg-muted"
            } ${disabled ? "cursor-not-allowed opacity-60" : ""}`}
        >
            <input
                type="checkbox"
                className="sr-only"
                checked={checked}
                disabled={disabled}
                onChange={onToggle}
                aria-label={`${groupLabel} ${label}`}
                data-testid={testId}
            />
            <span aria-hidden="true">{checked ? "✓" : "+"}</span>
            <span>{label}</span>
        </label>
    );
}

function FilterGroup({
    legend,
    hintId,
    descriptionId,
    options,
    selected,
    dimension,
    ruleIndex,
    disabled,
    onToggle,
}: {
    legend: string;
    hintId: string;
    descriptionId?: string;
    options: string[];
    selected: string[];
    dimension: RuleDimension;
    ruleIndex: number;
    disabled: boolean;
    onToggle: (dimension: RuleDimension, value: string) => void;
}) {
    const seen = new Set(options);
    const displayed = [
        ...options,
        ...selected.filter((value) => !seen.has(value)),
    ];
    return (
        <fieldset aria-describedby={descriptionId || hintId} disabled={disabled}>
            <legend className="text-[10px] font-medium text-foreground/80">{legend}</legend>
            <div className="mt-1 flex flex-wrap gap-1">
                {displayed.map((value) => {
                    const unknown = !seen.has(value);
                    return (
                        <FilterChip
                            key={value}
                            groupLabel={legend}
                            label={
                                unknown
                                    ? `${dimensionLabel(dimension, value)} (not suggested)`
                                    : dimensionLabel(dimension, value)
                            }
                            checked={selected.includes(value)}
                            disabled={disabled}
                            testId={`autonomy-never-rule-${ruleIndex}-${dimension}-${value}`}
                            onToggle={() => onToggle(dimension, value)}
                        />
                    );
                })}
            </div>
        </fieldset>
    );
}

function RuleCard({
    index,
    ruleId,
    draft,
    baseline,
    dimensions,
    saveState,
    showValidation,
    domainInput,
    domainError,
    onDraftChange,
    onToggleValue,
    onDomainInput,
    onAddDomain,
    onSave,
    onCancel,
    onDelete,
    onReload,
    onDismissConflict,
}: {
    index: number;
    ruleId: string;
    draft: RuleDraft;
    baseline: RuleDraft;
    dimensions: NeverDimensions;
    saveState: SaveState;
    showValidation: boolean;
    domainInput: string;
    domainError: string | null;
    onDraftChange: (patch: Partial<Pick<RuleDraft, "name" | "enabled">>) => void;
    onToggleValue: (dimension: RuleDimension, value: string) => void;
    onDomainInput: (value: string) => void;
    onAddDomain: () => void;
    onSave: () => void;
    onCancel: () => void;
    onDelete: () => void;
    onReload: () => void;
    onDismissConflict: () => void;
}) {
    const isNew = ruleId === NEW_RULE_KEY;
    const dirty = isNew || !draftMatchesBaseline(draft, baseline);
    const busy = saveState.status === "saving";
    const conflict = saveState.status === "conflict";
    const { nameError, filterError } = validateDraft(draft);
    const invalid = !!nameError || !!filterError;
    const nameId = `autonomy-never-rule-${index}-name`;
    const enabledId = `autonomy-never-rule-${index}-enabled`;
    const domainInputId = `autonomy-never-rule-${index}-domain-input`;
    const domainHintId = `autonomy-never-rule-${index}-domain-hint`;
    const domainErrorId = `autonomy-never-rule-${index}-domain-error`;
    const tid = (suffix: string) => `autonomy-never-rule-${index}-${suffix}`;

    return (
        <fieldset
            className="space-y-2 rounded border bg-background p-2"
            data-testid={`autonomy-never-rule-${index}`}
            aria-busy={busy || undefined}
        >
            <legend className="px-1 text-[10px] font-medium text-muted-foreground">
                Rule {index + 1}
            </legend>

            <div>
                <label htmlFor={nameId} className="text-[10px] font-medium text-foreground/80">
                    Name
                </label>
                <input
                    id={nameId}
                    value={draft.name}
                    onChange={(event) => onDraftChange({ name: event.target.value })}
                    maxLength={NAME_MAX}
                    autoFocus={isNew}
                    disabled={busy}
                    placeholder="e.g. Month-end financial reconciliation"
                    aria-describedby={showValidation && nameError ? `${tid("name-error")}` : undefined}
                    data-testid={tid("name")}
                    className="mt-0.5 w-full rounded border bg-transparent px-2 py-1 text-xs"
                />
                {showValidation && nameError && (
                    <p
                        id={tid("name-error")}
                        role="alert"
                        className="mt-0.5 text-[10px] text-red-500"
                    >
                        {nameError}
                    </p>
                )}
            </div>

            <div className="flex items-center gap-2">
                <Switch
                    id={enabledId}
                    checked={draft.enabled}
                    onCheckedChange={(checked) => onDraftChange({ enabled: checked })}
                    disabled={busy}
                    aria-label={`Enable rule ${index + 1}`}
                    data-testid={tid("enabled")}
                />
                <label htmlFor={enabledId} className="text-[10px] text-foreground/80">
                    Enabled
                </label>
                {!draft.enabled && (
                    <span
                        className="ml-auto text-[10px] text-muted-foreground"
                        data-testid={tid("disabled")}
                    >
                        Disabled — this rule never matches.
                    </span>
                )}
            </div>

            <FilterGroup
                legend="Difficulty"
                hintId="autonomy-never-match-help"
                options={dimensions.difficulty}
                selected={draft.match.difficulty}
                dimension="difficulty"
                ruleIndex={index}
                disabled={busy}
                onToggle={onToggleValue}
            />
            <FilterGroup
                legend="Category"
                hintId="autonomy-never-match-help"
                options={dimensions.category}
                selected={draft.match.category}
                dimension="category"
                ruleIndex={index}
                disabled={busy}
                onToggle={onToggleValue}
            />
            <FilterGroup
                legend="Business domain"
                hintId="autonomy-never-match-help"
                options={dimensions.domain}
                selected={draft.match.domain}
                dimension="domain"
                ruleIndex={index}
                disabled={busy}
                onToggle={onToggleValue}
            />

            <div>
                <label
                    htmlFor={domainInputId}
                    className="text-[10px] font-medium text-foreground/80"
                >
                    Add a business domain
                </label>
                <div className="mt-0.5 flex gap-1">
                    <input
                        id={domainInputId}
                        value={domainInput}
                        onChange={(event) => onDomainInput(event.target.value)}
                        onKeyDown={(event) => {
                            if (event.key === "Enter") {
                                event.preventDefault();
                                onAddDomain();
                            }
                        }}
                        disabled={busy}
                        placeholder="e.g. legal-ops"
                        aria-describedby={`${domainHintId}${domainError ? ` ${domainErrorId}` : ""}`}
                        data-testid={tid("domain-input")}
                        className="min-w-0 flex-1 rounded border bg-transparent px-2 py-1 text-xs"
                    />
                    <button
                        type="button"
                        onClick={onAddDomain}
                        disabled={busy}
                        data-testid={tid("domain-add")}
                        className="rounded border px-2 py-1 text-[10px] font-medium hover:bg-muted disabled:opacity-50"
                    >
                        Add
                    </button>
                </div>
                <p id={domainHintId} className="mt-0.5 text-[10px] text-muted-foreground">
                    Lower-case slug, e.g. finance or legal-ops. Suggestions above are not an
                    exhaustive list.
                </p>
                {domainError && (
                    <p
                        id={domainErrorId}
                        role="alert"
                        className="mt-0.5 text-[10px] text-red-500"
                        data-testid={tid("domain-error")}
                    >
                        {domainError}
                    </p>
                )}
            </div>

            {showValidation && filterError && (
                <p
                    role="alert"
                    className="text-[10px] text-red-500"
                    data-testid={tid("filter-error")}
                >
                    {filterError}
                </p>
            )}

            {saveState.status === "error" && saveState.message && (
                <div
                    role="alert"
                    className="rounded bg-red-500/10 px-1.5 py-1 text-[10px] text-red-600"
                    data-testid="autonomy-never-error"
                >
                    <p data-testid={tid("error")}>{saveState.message}</p>
                </div>
            )}

            {conflict && (
                <div
                    role="alert"
                    className="rounded bg-amber-500/10 px-1.5 py-1 text-[10px] text-amber-700 dark:text-amber-400"
                    data-testid="autonomy-never-conflict"
                >
                    <p>
                        This rule changed elsewhere. Your edits are still here. Reload this rule
                        before saving.
                    </p>
                    {typeof saveState.currentRevision === "number" && (
                        <p className="mt-0.5">Server revision: {saveState.currentRevision}</p>
                    )}
                    <div className="mt-1 flex flex-wrap gap-1">
                        <button
                            type="button"
                            onClick={onReload}
                            className="rounded border px-1.5 py-0.5 font-medium"
                            data-testid={tid("reload")}
                        >
                            Reload rule
                        </button>
                        <button
                            type="button"
                            onClick={onDismissConflict}
                            className="rounded border px-1.5 py-0.5"
                            data-testid={tid("keep-editing")}
                        >
                            Keep editing
                        </button>
                    </div>
                </div>
            )}

            <div className="flex flex-wrap items-center gap-1">
                <button
                    type="button"
                    onClick={onSave}
                    disabled={busy || conflict || !dirty || (showValidation && invalid)}
                    data-testid={tid("save")}
                    className="rounded bg-primary px-2 py-1 text-[10px] font-medium text-primary-foreground disabled:opacity-50"
                >
                    {busy ? "Saving…" : "Save"}
                </button>
                <button
                    type="button"
                    onClick={onCancel}
                    disabled={busy || (!dirty && !isNew)}
                    data-testid={tid("cancel")}
                    className="rounded border px-2 py-1 text-[10px] font-medium hover:bg-muted disabled:opacity-50"
                >
                    Cancel
                </button>
                <button
                    type="button"
                    onClick={onDelete}
                    disabled={busy}
                    aria-label={`Delete rule ${index + 1}`}
                    data-testid={tid("delete")}
                    className="ml-auto inline-flex items-center gap-1 rounded border px-2 py-1 text-[10px] font-medium text-red-600 hover:bg-red-500/10 disabled:opacity-50"
                >
                    <Trash2 className="h-3 w-3" /> Delete
                </button>
            </div>
        </fieldset>
    );
}

export function AutonomyPanel({
    canvasId,
    agentId,
}: {
    canvasId?: string;
    agentId?: string;
}) {
    const [topics, setTopics] = useState<AutonomyTopic[]>([]);
    const [loading, setLoading] = useState(true);
    const [busy, setBusy] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);

    const [rules, setRules] = useState<AutonomyRule[]>([]);
    const [dimensions, setDimensions] = useState<NeverDimensions | null>(null);
    const [rulesLoadState, setRulesLoadState] = useState<RulesLoadState>("loading");
    const [rulesError, setRulesError] = useState<string | null>(null);
    const [drafts, setDrafts] = useState<Record<string, RuleDraft>>({});
    const [saveStates, setSaveStates] = useState<Record<string, SaveState>>({});
    const [showValidation, setShowValidation] = useState<Record<string, boolean>>({});
    const [domainInputs, setDomainInputs] = useState<Record<string, string>>({});
    const [domainErrors, setDomainErrors] = useState<Record<string, string | null>>({});
    const [statusMessage, setStatusMessage] = useState("");

    const topicsSeq = useRef(0);
    const rulesSeq = useRef(0);
    const rulesRef = useRef<AutonomyRule[]>([]);

    useEffect(() => {
        rulesRef.current = rules;
    }, [rules]);

    const load = useCallback(
        async (showSpinner = true) => {
            const seq = ++topicsSeq.current;
            setError(null);
            if (showSpinner) setLoading(true);
            try {
                const { apiClient } = await import("../../lib/api-client");
                const params = new URLSearchParams();
                if (canvasId) params.set("canvas_id", canvasId);
                if (agentId) params.set("agent_id", agentId);
                const qs = params.toString();
                const res = await apiClient.get(`/api/autonomy/topics${qs ? `?${qs}` : ""}`);
                if (seq !== topicsSeq.current) return;
                const data = (res as any).data || res;
                setTopics(data?.topics || []);
            } catch {
                if (seq !== topicsSeq.current) return;
                setError("Could not load autonomy settings.");
            } finally {
                if (seq === topicsSeq.current) setLoading(false);
            }
        },
        [canvasId, agentId]
    );

    useEffect(() => {
        load();
        return () => {
            topicsSeq.current += 1;
        };
    }, [load]);

    const loadRules = useCallback(
        async (options: { replaceIds?: string[]; silent?: boolean } = {}) => {
            const seq = ++rulesSeq.current;
            const previousRules = rulesRef.current;
            if (!options.silent) {
                setRulesLoadState("loading");
                setRulesError(null);
            }
            try {
                const { apiClient } = await import("../../lib/api-client");
                const res = await apiClient.get(RULE_COLLECTION);
                if (seq !== rulesSeq.current) return;
                const data = (res as any).data || res;
                const parsed = parseRulesResponse(data);
                if (!parsed) {
                    // A malformed 200 is unsupported, never an empty list.
                    if (!options.silent) setRulesLoadState("unsupported");
                    else setRulesError("Task rules could not be read from this build.");
                    return;
                }
                setDimensions(parsed.dimensions);
                setRules(parsed.rules);
                setDrafts((previous) => {
                    const next: Record<string, RuleDraft> = {};
                    for (const rule of parsed.rules) {
                        const baseline = draftFromRule(rule);
                        const existing = previous[rule.id];
                        const previousRule = previousRules.find((item) => item.id === rule.id);
                        const isDirty =
                            existing &&
                            previousRule &&
                            !draftMatchesBaseline(existing, draftFromRule(previousRule));
                        const replace =
                            !existing ||
                            !previousRule ||
                            !isDirty ||
                            options.replaceIds?.includes(rule.id);
                        next[rule.id] = replace ? baseline : existing;
                    }
                    if (previous[NEW_RULE_KEY]) next[NEW_RULE_KEY] = previous[NEW_RULE_KEY];
                    return next;
                });
                setRulesLoadState("ready");
                if (options.replaceIds?.length) {
                    setSaveStates((previous) => {
                        const next = { ...previous };
                        for (const id of options.replaceIds || []) {
                            next[id] = { status: "idle" };
                        }
                        return next;
                    });
                    setShowValidation((previous) => {
                        const next = { ...previous };
                        for (const id of options.replaceIds || []) next[id] = false;
                        return next;
                    });
                    setDomainInputs((previous) => {
                        const next = { ...previous };
                        for (const id of options.replaceIds || []) next[id] = "";
                        return next;
                    });
                    setDomainErrors((previous) => {
                        const next = { ...previous };
                        for (const id of options.replaceIds || []) next[id] = null;
                        return next;
                    });
                    setStatusMessage("Rule reloaded.");
                }
            } catch (loadError) {
                if (seq !== rulesSeq.current) return;
                const status = errorStatus(loadError);
                if (options.silent) {
                    setRulesError("Could not refresh task rules.");
                    return;
                }
                if (status === 403) {
                    setRulesLoadState("forbidden");
                    setRulesError(null);
                } else if (status === 404 || status === 405 || status === 501) {
                    // Older builds do not expose the collection at all.
                    setRulesLoadState("unsupported");
                    setRulesError(null);
                } else {
                    setRulesLoadState("error");
                    setRulesError("Could not load task rules.");
                }
            }
        },
        []
    );

    useEffect(() => {
        loadRules();
        return () => {
            rulesSeq.current += 1;
        };
    }, [loadRules]);

    const setMode = async (topic: string, mode: string) => {
        setBusy(topic);
        try {
            const { apiClient } = await import("../../lib/api-client");
            await apiClient.put(`/api/autonomy/topics/${topic}`, { mode });
            setTopics((prev) => prev.map((t) => (t.topic === topic ? { ...t, mode } : t)));
            // Refresh gates silently — the outcome chip can flip with the mode.
            load(false);
        } catch {
            setError("Failed to save — try again.");
        } finally {
            setBusy(null);
        }
    };

    const updateSaveState = (id: string, state: SaveState) => {
        setSaveStates((previous) => ({ ...previous, [id]: state }));
    };

    const updateDraft = (id: string, patch: Partial<Pick<RuleDraft, "name" | "enabled">>) => {
        setDrafts((previous) => {
            const draft = previous[id];
            if (!draft) return previous;
            return { ...previous, [id]: { ...draft, ...patch } };
        });
        setShowValidation((previous) => ({ ...previous, [id]: true }));
        if (saveStates[id]?.status === "saved") {
            updateSaveState(id, { status: "idle" });
        }
        setStatusMessage("");
    };

    const toggleValue = (id: string, dimension: RuleDimension, value: string) => {
        setDrafts((previous) => {
            const draft = previous[id];
            if (!draft) return previous;
            const values = draft.match[dimension];
            const nextValues = values.includes(value)
                ? values.filter((item) => item !== value)
                : [...values, value];
            return {
                ...previous,
                [id]: {
                    ...draft,
                    match: { ...draft.match, [dimension]: nextValues },
                },
            };
        });
        setShowValidation((previous) => ({ ...previous, [id]: true }));
        if (saveStates[id]?.status === "saved") {
            updateSaveState(id, { status: "idle" });
        }
        setStatusMessage("");
    };

    const setDomainInput = (id: string, value: string) => {
        setDomainInputs((previous) => ({ ...previous, [id]: value }));
        setDomainErrors((previous) => ({ ...previous, [id]: null }));
    };

    const addDomain = (id: string) => {
        const raw = (domainInputs[id] || "").trim().toLowerCase();
        if (!DOMAIN_SLUG_RE.test(raw)) {
            setDomainErrors((previous) => ({
                ...previous,
                [id]:
                    "Use a lower-case slug that starts with a letter (2–64 characters: a–z, 0–9, _ or -).",
            }));
            return;
        }
        setDrafts((previous) => {
            const draft = previous[id];
            if (!draft) return previous;
            if (draft.match.domain.includes(raw)) return previous;
            return {
                ...previous,
                [id]: {
                    ...draft,
                    match: { ...draft.match, domain: [...draft.match.domain, raw] },
                },
            };
        });
        setDomainInputs((previous) => ({ ...previous, [id]: "" }));
        setDomainErrors((previous) => ({ ...previous, [id]: null }));
        setShowValidation((previous) => ({ ...previous, [id]: true }));
        if (saveStates[id]?.status === "saved") {
            updateSaveState(id, { status: "idle" });
        }
        setStatusMessage("");
    };

    const removeRuleLocally = (id: string) => {
        setRules((previous) => previous.filter((rule) => rule.id !== id));
        setDrafts((previous) => {
            const next = { ...previous };
            delete next[id];
            return next;
        });
        setSaveStates((previous) => {
            const next = { ...previous };
            delete next[id];
            return next;
        });
        setShowValidation((previous) => {
            const next = { ...previous };
            delete next[id];
            return next;
        });
        setDomainInputs((previous) => {
            const next = { ...previous };
            delete next[id];
            return next;
        });
        setDomainErrors((previous) => {
            const next = { ...previous };
            delete next[id];
            return next;
        });
    };

    const saveRule = async (id: string) => {
        const draft = drafts[id];
        if (!draft) return;
        const { nameError, filterError } = validateDraft(draft);
        setShowValidation((previous) => ({ ...previous, [id]: true }));
        if (nameError || filterError) {
            // Inline validation already renders these messages; do not duplicate
            // them as a request-failure alert.
            updateSaveState(id, { status: "idle" });
            setStatusMessage("");
            return;
        }

        const isNew = id === NEW_RULE_KEY;
        const existingRule = isNew ? null : rules.find((rule) => rule.id === id);
        if (!isNew && !existingRule) {
            removeRuleLocally(id);
            setRulesError("This rule is no longer available.");
            setStatusMessage("");
            return;
        }

        const payload = buildRulePayload(draft);
        updateSaveState(id, { status: "saving" });
        setStatusMessage("");
        try {
            const { apiClient } = await import("../../lib/api-client");
            let savedRule: AutonomyRule | null = null;
            if (isNew) {
                const res = await apiClient.post(RULE_COLLECTION, payload, { retry: false });
                savedRule = parseRule(((res as any).data || res)?.rule);
            } else if (existingRule) {
                const body =
                    typeof existingRule.revision === "number"
                        ? { ...payload, expected_revision: existingRule.revision }
                        : payload;
                const res = await apiClient.put(
                    `${RULE_COLLECTION}/${encodeURIComponent(id)}`,
                    body,
                    { retry: false }
                );
                savedRule = parseRule(((res as any).data || res)?.rule);
            }
            if (!savedRule) {
                // The request may have succeeded, but we cannot prove what was
                // saved. Keep the draft and never claim success.
                updateSaveState(id, {
                    status: "error",
                    message:
                        "The server did not return the saved rule. Your changes are still here; reload the list before saving again.",
                });
                return;
            }

            setRules((previous) => {
                const existingIndex = previous.findIndex(
                    (rule) => rule.id === savedRule!.id
                );
                if (existingIndex === -1) return [...previous, savedRule!];
                const next = [...previous];
                next[existingIndex] = savedRule!;
                return next;
            });
            setDrafts((previous) => {
                const next = { ...previous };
                delete next[id];
                next[savedRule!.id] = draftFromRule(savedRule!);
                return next;
            });
            setSaveStates((previous) => {
                const next = { ...previous };
                delete next[id];
                next[savedRule!.id] = { status: "saved" };
                return next;
            });
            setShowValidation((previous) => {
                const next = { ...previous };
                delete next[id];
                next[savedRule!.id] = false;
                return next;
            });
            setDomainInputs((previous) => {
                const next = { ...previous };
                delete next[id];
                next[savedRule!.id] = "";
                return next;
            });
            setDomainErrors((previous) => {
                const next = { ...previous };
                delete next[id];
                next[savedRule!.id] = null;
                return next;
            });
            setStatusMessage(isNew ? "Rule created." : "Rule saved.");
            // Keep the topic chips truthful without touching any topic mode.
            load(false);
        } catch (saveError) {
            const status = errorStatus(saveError);
            if (status === 409) {
                const currentRevision =
                    (saveError as any)?.response?.data?.current_revision;
                updateSaveState(id, {
                    status: "conflict",
                    currentRevision:
                        typeof currentRevision === "number" ? currentRevision : undefined,
                });
                setStatusMessage("");
                return;
            }
            if (status === 404) {
                removeRuleLocally(id);
                setRulesError("This rule is no longer available.");
                setStatusMessage("");
                loadRules({ silent: true });
                return;
            }
            if (status === 403) {
                updateSaveState(id, {
                    status: "error",
                    message: "Only the signed-in owner can change task rules.",
                });
                return;
            }
            const detail = shortErrorDetail(saveError);
            updateSaveState(id, {
                status: "error",
                message: detail
                    ? `Could not save this rule. ${detail}`
                    : "Could not save this rule. Your changes are still here.",
            });
            setStatusMessage("");
        }
    };

    const cancelRule = (id: string) => {
        if (id === NEW_RULE_KEY) {
            removeRuleLocally(id);
            setStatusMessage("");
            return;
        }
        const rule = rules.find((item) => item.id === id);
        if (!rule) {
            removeRuleLocally(id);
            return;
        }
        setDrafts((previous) => ({ ...previous, [id]: draftFromRule(rule) }));
        setSaveStates((previous) => ({ ...previous, [id]: { status: "idle" } }));
        setShowValidation((previous) => ({ ...previous, [id]: false }));
        setDomainInputs((previous) => ({ ...previous, [id]: "" }));
        setDomainErrors((previous) => ({ ...previous, [id]: null }));
        setStatusMessage("");
    };

    const deleteRule = async (id: string) => {
        if (typeof window !== "undefined") {
            const confirmed = window.confirm(
                "Delete this never-autonomous rule? Deleting removes it and its history, so the task follows its normal topic setting again. Disable it instead if you only want to stop it matching."
            );
            if (!confirmed) return;
        }
        updateSaveState(id, { status: "saving" });
        setStatusMessage("");
        try {
            const { apiClient } = await import("../../lib/api-client");
            await apiClient.delete(`${RULE_COLLECTION}/${encodeURIComponent(id)}`, {
                retry: false,
            });
            removeRuleLocally(id);
            setStatusMessage("Rule deleted.");
            load(false);
        } catch (deleteError) {
            const status = errorStatus(deleteError);
            if (status === 404) {
                removeRuleLocally(id);
                setRulesError("This rule is no longer available.");
                setStatusMessage("");
                loadRules({ silent: true });
                return;
            }
            updateSaveState(id, {
                status: "error",
                message: "Could not delete this rule. The rule is still here.",
            });
            setStatusMessage("");
        }
    };

    const addRuleDraft = () => {
        setDrafts((previous) => {
            if (previous[NEW_RULE_KEY]) return previous;
            return { ...previous, [NEW_RULE_KEY]: emptyDraft() };
        });
        setSaveStates((previous) => ({ ...previous, [NEW_RULE_KEY]: { status: "idle" } }));
        setShowValidation((previous) => ({ ...previous, [NEW_RULE_KEY]: false }));
        setDomainInputs((previous) => ({ ...previous, [NEW_RULE_KEY]: "" }));
        setDomainErrors((previous) => ({ ...previous, [NEW_RULE_KEY]: null }));
        setStatusMessage("New rule draft. Nothing is saved until you choose Save.");
    };

    if (loading) {
        return (
            <div className="p-4 flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" /> Loading autonomy settings…
            </div>
        );
    }

    const canvasTopics = topics.filter((t) => t.canvas_relevant);
    const generalTopics = topics.filter((t) => !t.canvas_relevant);
    const newDraft = drafts[NEW_RULE_KEY];
    const ruleCards: Array<{ key: string; rule: AutonomyRule | null }> = rules.map((rule) => ({
        key: rule.id,
        rule,
    }));
    if (newDraft) ruleCards.push({ key: NEW_RULE_KEY, rule: null });
    const canConfigureRules = rulesLoadState === "ready" && !!dimensions;

    return (
        <div className="flex-1 overflow-y-auto p-3 space-y-3" data-testid="autonomy-panel">
            <p className="text-[11px] text-muted-foreground leading-relaxed">
                Choose which agent actions <strong>always require you</strong>, which the
                agent may do autonomously <strong>once mature enough</strong>, and which run
                autonomously <strong>until a correction resets the cycle</strong> (the hire
                proposes again and re-earns autonomy through verified work). Immature hires
                always propose first and learn from your decisions.
            </p>

            <section
                className="space-y-2 rounded-lg border p-2"
                aria-labelledby="autonomy-never-heading"
                data-testid="autonomy-never-section"
            >
                <h3
                    id="autonomy-never-heading"
                    className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground"
                >
                    Tasks that never run autonomously
                </h3>
                <p className="text-[10px] text-muted-foreground leading-relaxed">
                    Matching tasks always ask for your approval — even after the agent
                    graduates or a capability matures. Other tasks keep their topic setting
                    and normal maturity/trust checks.
                </p>

                <p
                    id="autonomy-never-match-help"
                    className="text-[10px] text-muted-foreground leading-relaxed"
                >
                    In one rule, every dimension you set must match (difficulty AND category
                    AND domain); several values in one dimension are alternatives. Any enabled
                    rule is enough to require your approval.
                </p>
                <p
                    className="text-[10px] text-muted-foreground leading-relaxed"
                    data-testid="autonomy-never-invariant"
                >
                    A matching task always asks for your approval, even after the agent
                    graduates or a capability matures. The approval is for that specific
                    execution and never changes or widens the rule.
                </p>
                <details className="text-[10px] text-muted-foreground">
                    <summary className="cursor-pointer">How matching works</summary>
                    <p className="mt-1 leading-relaxed">
                        A rule only describes a task shape; it does not choose a topic mode.
                        Disabled rules stay saved but never match. With no enabled rules,
                        behavior is exactly the pre-existing topic and maturity policy.
                    </p>
                </details>

                <p
                    className="text-[10px] text-muted-foreground leading-relaxed"
                    data-testid="autonomy-never-unknown-note"
                >
                    “Not classified” is not “doesn’t match.” While any rule is enabled,
                    missing task metadata fails toward your review, and this panel never
                    computes a match or a match count itself.
                </p>

                {rulesError &&
                    rulesLoadState !== "unsupported" &&
                    rulesLoadState !== "forbidden" && (
                        <div
                            role="alert"
                            className="rounded bg-red-500/10 px-1.5 py-1 text-[10px] text-red-600"
                            data-testid="autonomy-never-error"
                        >
                            <p>{rulesError}</p>
                            <button
                                type="button"
                                onClick={() => loadRules()}
                                className="mt-1 rounded border px-1.5 py-0.5 font-medium"
                                data-testid="autonomy-never-retry"
                            >
                                Retry
                            </button>
                        </div>
                    )}

                {rulesLoadState === "loading" && (
                    <p
                        className="flex items-center gap-1.5 text-[10px] text-muted-foreground"
                        data-testid="autonomy-never-loading"
                    >
                        <Loader2 className="h-3 w-3 animate-spin" /> Loading task rules…
                    </p>
                )}

                {rulesLoadState === "unsupported" && (
                    <p
                        className="text-[10px] text-muted-foreground"
                        data-testid="autonomy-never-unsupported"
                    >
                        Task rules aren’t available in this build.
                    </p>
                )}

                {rulesLoadState === "forbidden" && (
                    <p
                        className="text-[10px] text-muted-foreground"
                        data-testid="autonomy-never-forbidden"
                    >
                        Only the signed-in owner can view or change task rules.
                    </p>
                )}

                {canConfigureRules && (
                    <>
                        {rules.length === 0 && !newDraft && !rulesError && (
                            <p
                                className="text-[10px] text-muted-foreground leading-relaxed"
                                data-testid="autonomy-never-empty"
                            >
                                No task rules yet. Everything follows its topic setting and
                                normal maturity gates. Add a rule only for tasks that must
                                always ask you.
                            </p>
                        )}

                        {ruleCards.map(({ key, rule }) => {
                            const draft = drafts[key];
                            if (!draft) return null;
                            const index = ruleCards.findIndex((item) => item.key === key);
                            return (
                                <RuleCard
                                    key={key}
                                    index={index}
                                    ruleId={key}
                                    draft={draft}
                                    baseline={rule ? draftFromRule(rule) : emptyDraft()}
                                    dimensions={dimensions!}
                                    saveState={saveStates[key] || { status: "idle" }}
                                    showValidation={!!showValidation[key]}
                                    domainInput={domainInputs[key] || ""}
                                    domainError={domainErrors[key] || null}
                                    onDraftChange={(patch) => updateDraft(key, patch)}
                                    onToggleValue={(dimension, value) =>
                                        toggleValue(key, dimension, value)
                                    }
                                    onDomainInput={(value) => setDomainInput(key, value)}
                                    onAddDomain={() => addDomain(key)}
                                    onSave={() => saveRule(key)}
                                    onCancel={() => cancelRule(key)}
                                    onDelete={() => deleteRule(key)}
                                    onReload={() => loadRules({ replaceIds: [key] })}
                                    onDismissConflict={() =>
                                        setStatusMessage(
                                            "Your edits are still here. Reload the rule before saving."
                                        )
                                    }
                                />
                            );
                        })}

                        <div className="flex flex-wrap items-center gap-2">
                            <button
                                type="button"
                                onClick={addRuleDraft}
                                disabled={!!newDraft}
                                data-testid="autonomy-never-add"
                                className="inline-flex items-center gap-1 rounded border px-2 py-1 text-[10px] font-medium hover:bg-muted disabled:opacity-50"
                            >
                                <Plus className="h-3 w-3" /> Add task rule
                            </button>
                            <p
                                className="text-[10px] text-muted-foreground"
                                role="status"
                                aria-live="polite"
                                data-testid="autonomy-never-status"
                            >
                                {statusMessage}
                            </p>
                        </div>
                    </>
                )}
            </section>

            {error && <p className="text-xs text-red-500">{error}</p>}
            {canvasTopics.length > 0 && (
                <>
                    <p
                        className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground"
                        data-testid="autonomy-canvas-section"
                    >
                        On this canvas
                    </p>
                    <div className="space-y-3">
                        {canvasTopics.map((t) => (
                            <TopicCard
                                key={t.topic}
                                topic={t}
                                busy={busy === t.topic}
                                onSetMode={setMode}
                            />
                        ))}
                    </div>
                </>
            )}
            {generalTopics.length > 0 && (
                <>
                    <p
                        className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground"
                        data-testid="autonomy-general-section"
                    >
                        General
                    </p>
                    <div className="space-y-3">
                        {generalTopics.map((t) => (
                            <TopicCard
                                key={t.topic}
                                topic={t}
                                busy={busy === t.topic}
                                onSetMode={setMode}
                            />
                        ))}
                    </div>
                </>
            )}
        </div>
    );
}
