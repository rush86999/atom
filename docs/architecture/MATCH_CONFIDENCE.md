# Pre-Action Match-Confidence Layer

> **Last Updated**: June 28, 2026
>
> **Status**: Phase 1–5 implemented; Phase 6 (shadow rollout) begins with
> `MATCH_CONFIDENCE_FORCE_PROPOSAL=false` (computation + audit on, gating off).

## The Problem

A redditor's critique landed cleanly: Atom's hidden a11y / canvas state
expresses **structure**, not **uncertainty**. When an agent clicks a field
that moved, loaded late, or partially matched, it had no way to say *"I
think this is the target because…"* before acting.

`browser_click` called `page.query_selector()` and silently took the first
match. Three near-identical submit buttons? Clicked the first. Late-loaded
modal? Took the underlying element. Text-only selector that matched
spinning loaders? Clicked a spinner.

The post-action `VerifiedOutcome` tri-state (`core/tool_outcome_verifier.py`)
catches silent no-ops *after* the fact — but by then the wrong element has
already been clicked. We needed a pre-action mirror.

## The Fix

A deterministic scorer + LLM tiebreaker that expresses match certainty
**before** the action runs, and routes ambiguous/partial matches through
the existing `AgentProposal` flow — **including for AUTONOMOUS agents**,
whose tier today is routed by history, not current-call certainty.

```
            ┌────────────────────────────────┐
            │  browser_click(selector)       │
            └────────────────────────────────┘
                          │
                          ▼
            ┌────────────────────────────────┐
            │  _resolve_selector_with_conf.  │  Phase 2
            │  page.locator() + .count()     │
            │  → MatchConfidence             │
            └────────────────────────────────┘
                          │
              ┌───────────┴───────────┐
              ▼                       ▼
        level=high           level=partial
              │                       │
              │                       ▼
              │           ┌──────────────────────┐
              │           │ attach_tiebreak()    │  Phase 3
              │           │ LLM picks best cand. │
              │           │ 2s timeout, breaker  │
              │           └──────────────────────┘
              │                       │
              │              ┌────────┴────────┐
              │              ▼                 ▼
              │        upgraded=high     still partial/ambiguous
              │              │                 │
              └──────────────┴─────────────────┘
                          │
                          ▼
            ┌────────────────────────────────┐
            │  _maybe_gate_with_proposal()   │  Phase 4
            │  FORCE_PROPOSAL AND            │
            │  level ∈ {partial, ambiguous}  │
            │  AND not override              │
            │  → ProposalService             │
            └────────────────────────────────┘
                          │
              ┌───────────┴───────────┐
              ▼                       ▼
        proceed                  requires_approval
                                       │
                                       ▼
                          ┌─────────────────────┐
                          │ Reviewer UI         │  Phase 5
                          │ MatchConfidenceRev. │
                          │ Approve / Modify /  │
                          │ Reject              │
                          └─────────────────────┘
                                       │ approve
                                       ▼
                          execute with override=True
                          (no re-gating)
```

## Tri-state Mirror

`MatchLevel ∈ {high, partial, ambiguous}` mirrors the post-action
`VerifiedOutcome ∈ {verified, unverified, failed_verification}`. Same shape:
frozen dataclass, never-raise parser, `coerce_*_for_storage` helper.

| Pre-action (`MatchConfidence`) | Post-action (`VerifiedOutcome`) |
|-------------------------------|---------------------------------|
| `high` — exactly the kind of match intended | `verified` — tool actively confirmed world changed |
| `partial` — multiple candidates; best plausibly correct | `unverified` — ran but didn't verify |
| `ambiguous` — can't tell; route to human | `failed_verification` — verify step FAILED |

The key divergence the redditor asked for: `match_confidence` is surfaced
to the LLM via `byok_handler.py` stringification into `tool_result.content`
(unlike `verified`, which is DB-only). The LLM sees the JSON rationale and
can reason about what happened on the next turn.

## Score Curve

```
score = max(0.0,
  1.0
  - 0.30 * (match_count - 1)         # multiplicity
  - 0.15 * is_text_only              # no #id / [data-testid / [aria-label / [role
  - 0.10 * (appeared_after_ms > 1000) # late load
)
```

Floored at 0.0 — no negative confidences. Penalties stack additively.

| Matches | Text-only? | Late? | Score | Level (default thresholds) |
|--------:|:----------:|:-----:|------:|:---------------------------|
| 1       | no         | no    | 1.00  | high (≥0.85)               |
| 1       | yes        | no    | 0.85  | high (boundary)            |
| 1       | yes        | yes   | 0.75  | partial                    |
| 2       | no         | no    | 0.70  | partial                    |
| 2       | yes        | yes   | 0.45  | ambiguous                  |
| 3       | no         | no    | 0.40  | ambiguous                  |
| 5+      | any        | any   | 0.00  | ambiguous (floored)        |

Thresholds (env-overridable, see
`docs/architecture/SELECTOR_CONFIDENCE_THRESHOLDS.md`):

| Flag | Default | Effect |
|---|---|---|
| `MATCH_CONFIDENCE_HIGH_THRESHOLD` | `0.85` | `>=` this is high |
| `MATCH_CONFIDENCE_PARTIAL_THRESHOLD` | `0.50` | `>=` this is partial; below is ambiguous |
| `MATCH_CONFIDENCE_FORCE_PROPOSAL` | `false` | Shadow mode default; gating off |

## Phase Summary

| Phase | Module | What it does |
|-------|--------|--------------|
| 1 | `core/selector_confidence_service.py` | Deterministic scorer + frozen dataclasses |
| 2 | `tools/browser_tool.py` | Locator resolver, BrowserAudit wiring, `match_confidence` in return dicts |
| 3 | `core/llm/match_confidence_tiebreaker.py` | Budget-tier LLM tiebreaker for partial band + circuit breaker |
| 4 | `tools/browser_tool.py` + `core/proposal_service.py` | AUTONOMOUS gating via ProposalService |
| 5 | Frontend | `MatchConfidenceReviewer` + `getMatchConfidence` accessor |
| 6 | Migration + rollout | `AgentRegistry.match_confidence_gating_enabled` column + per-tier enablement |

## Critical Files

| Path | Role |
|---|---|
| `backend/core/selector_confidence_service.py` | Scorer, dataclasses, flags, `attach_tiebreak` |
| `backend/core/llm/match_confidence_tiebreaker.py` | LLM tiebreaker + circuit breaker + result cache |
| `backend/tools/browser_tool.py` | Locator resolver, gating hook, audit writes |
| `backend/core/proposal_service.py` | Reviewer-visible candidates block in description |
| `backend/core/audit_service.py:136` | `create_browser_audit()` — now has writers (was unused) |
| `backend/core/tool_outcome_verifier.py` | Pattern mirror — do NOT modify |
| `frontend-nextjs/components/canvas/types/index.ts` | TS interfaces |
| `frontend-nextjs/hooks/useCanvasState.ts` | `getMatchConfidence(opId)` accessor |
| `frontend-nextjs/components/canvas/MatchConfidenceReviewer.tsx` | Reviewer UI |
| `frontend-nextjs/lib/matchConfidence.ts` | Pure helpers (badge color, ordering, payload) |

## Form Semantics

`browser_fill_form` gates the WHOLE form on any ambiguous field —
transactional integrity. Partial fills leave the page in an inconsistent
state (some fields filled with stale values, submit button enabled
prematurely). Two-pass implementation:

1. Resolve all fields, compute per-field confidence
2. If worst-case is partial/ambiguous → gate before any fill executes
3. Reviewer sees per-field confidence table in proposal description

## `extract_text` Exception

`browser_extract_text` is read-only. It annotates the result with
`match_confidence` but NEVER gates — gating AUTONOMOUS agents from
reading multi-match selectors would block legitimate scraping of
repeated patterns (e.g. all `div.price` on a listing page).

## AUTONOMOUS Override

This is the key fix. Before this layer, AUTONOMOUS agents always executed
browser actions directly — their tier is routed by *historical* clean
executions, not *current-call* certainty. A prompt-injected AUTONOMOUS
agent at 0.95 confidence could click any selector no matter how ambiguous.

With `MATCH_CONFIDENCE_FORCE_PROPOSAL=true` and an ambiguous selector,
AUTONOMOUS agents now route through human review on that one call.
Historical confidence still routes everything else; the layer only
intercepts the specific call where current-call certainty is low.

The `match_confidence_override=True` flag in `proposed_action` prevents
the infinite re-gating loop on post-approval execution.

## Kill Switch

```bash
# Disable gating instantly (keeps computation + audit for forensics):
MATCH_CONFIDENCE_FORCE_PROPOSAL=false

# Disable everything (revert to legacy Playwright API):
SELECTOR_CONFIDENCE_ENABLED=false BROWSER_LOCATOR_API_ENABLED=false
```

Single-misbehaving-agent opt-out: set
`AgentRegistry.match_confidence_gating_enabled=false` for that row
(migration `20260628_add_match_confidence_gating_flag.py`).

## Rollout Plan

1. **6a** — ship shadow (`FORCE_PROPOSAL=false`). Every browser action
   gets `match_confidence` in tool_result and audit row. Watch Prometheus:
   tool latency P99 (<5ms rise), tiebreaker LLM cost, audit-write error
   rate.
2. **6b** — enable gating for STUDENT/INTERN (additive — they already
   propose).
3. **6c** — enable for SUPERVISED. Watch proposal volume; if >2x
   baseline, tune `MATCH_CONFIDENCE_HIGH_THRESHOLD` down (0.85 → 0.75).
4. **6d** — enable for AUTONOMOUS. On-call watches reviewer UI first 24h.

## Not a Sandbox

**Match-confidence is NOT a sandbox.** AUTONOMOUS + high still has full
blast radius. Same caveat as the maturity system in `CLAUDE.md`:
bounding blast radius requires a deterministic sandbox layer
(filesystem scope, tool whitelist, egress allowlist, resource caps,
tripwires) that runs alongside the tier. See
`docs/security/TRUST_VS_SANDBOX.md`.
