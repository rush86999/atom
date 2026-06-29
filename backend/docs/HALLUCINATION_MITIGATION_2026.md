# Hallucination Mitigation 2026 — Personal Edition Port

**Status:** PR 1 (cleanly-portable mitigations) — June 2026. PR 2 (verified
gating reconciliation) tracked separately.

## What this adds

Two independently flag-gated mitigations, default off → no behavior change
until ops flips a flag:

1. **Cascade routing** — on schema-validation failure inside
   `BYOKHandler.generate_structured_response`, retry once on the
   same-provider flagship. Provider family is a structural invariant.
2. **Self-consistency voting** — 3-sample majority vote on the structured
   action plan for irreversible actions. The voter never executes; the
   caller runs the winning plan exactly once.

## Why these two

These are the two Phase 2 mitigations that port cleanly from the SaaS
fork without touching the verified-outcome data model. The third
mitigation (verified graduation gate) is SaaS-specific: it relies on
`AgentCapabilityRegistry` columns and a SUM-over-table ratio formula.
Upstream's capability tracking is JSON-in-`AgentRegistry.configuration`
with absolute-count promotion thresholds, not ratios. Porting the
verified gate requires a design discussion about whether to add a
ratio-based gate alongside the existing 5/20/50 absolute-count gates —
deferred to PR 2.

Research basis: Wang et al., "Self-Consistency Improves Chain of Thought
Reasoning in Language Models" (ICLR 2023). Vectara hallucination
leaderboard and ScaleDown June 2026 coverage both flag
schema-validation failures as the most tractable hallucination mode.

## Flag matrix

| Flag | Env var | Default | Effect when on |
|---|---|---|---|
| Cascade routing | `ATOM_CASCADE_ROUTING` | `false` | One same-family retry on schema-validation failure |
| Self-consistency | `ATOM_SELF_CONSISTENCY` | `false` | 3-sample majority vote on irreversible actions |
| Sample count | `ATOM_SELF_CONSISTENCY_SAMPLES` | `3` | Per-call sample count |

**No per-tenant override layer.** This is the Personal / single-tenant
edition; the SaaS fork has an additional `tenant.metadata_json` override
that is intentionally not ported (multi-tenancy stays in the SaaS fork
per the sync guidelines).

## Where each piece lives

| Component | File | Notes |
|---|---|---|
| Flag resolver | `core/hallucination_config.py` | Env-var-only. No DB surface. |
| Cascade routing | `core/llm/byok_handler.py:generate_structured_response` | Loop extended with `cascade` kwarg. |
| Self-consistency voter | `core/llm/self_consistency_voter.py` | Imports only `BYOKHandler`. Never imports the executor. |
| LLMService wrapper | `core/llm_service.py:generate_structured` | Forwards `cascade=<flag>`; dispatches to voter when `enable_self_consistency=True`. |

## Architecture: why cascade lives inside `BYOKHandler`

The cascade retry decision is fundamentally about provider/credential/model
selection — which is exactly what `BYOKHandler` owns. Putting cascade at
the outer `LLMService` wrapper would force the outer layer to guess at
provider family via `get_provider(model)`, require instance state
(`_last_resolved_model`, `_last_call_failed_with_schema_error`) that is
thread-unsafe, and create a double-loop hazard against the existing
options iteration inside the handler.

Inside `BYOKHandler`, "same family" is structural: the frontier is the
flagship of the current failing provider, looked up via
`hallucination_config.get_frontier_model_for_provider(provider_id)`. The
same `self.clients[provider_id]` is reused, so BYOK credentials, cost
tracking, and rate limits stay constant across the retry.

## Hard invariant: voter never executes

`tests/unit/llm/test_self_consistency_voter.py::test_C1_voter_module_does_not_import_executor`
is an AST-level check that the voter module imports only `BYOKHandler`
and stdlib. It must never import `UnifiedActionExecutor` or any adapter.
If that breaks, the voter becomes a hidden execution path and the
"execute winning plan exactly once" guarantee is at risk.

## Performance budget

| Mitigation | Added cost |
|---|---|
| Cascade routing | Median: 0. Worst case: +1 frontier-tier LLM call (only on schema failure) |
| Self-consistency | +2 LLM calls per irreversible action decision (3× instead of 1×) |

## Test coverage

43 new tests across four files in `tests/unit/llm/`:

| File | Tests | Coverage |
|---|---|---|
| `test_hallucination_config.py` | 20 | Flag resolution, numeric tunables, frontier registry (incl. Ollama local fallback) |
| `test_cascade_routing.py` | 9 | All cascade guardrails (flag off, schema fail, transient, already-frontier, single retry, log format, family invariant) |
| `test_self_consistency_voter.py` | 12 | Import invariant, majority vote, tie-break, irreversible detection, per-sample failure isolation |
| `test_provider_family_invariant.py` | 2 | Structural invariant across cascade + voter |

## Rollback

```bash
unset ATOM_CASCADE_ROUTING
unset ATOM_SELF_CONSISTENCY
```

No migration needed. No data is lost when flags are off.

## What's not in this PR (tracked for PR 2)

- Verified graduation gate (hard floor on `verified_ratio` for
  supervised → autonomous promotion). Requires reconciling with
  upstream's JSON-based capability stats and absolute-count promotion
  thresholds. See upstream's existing
  `CapabilityGraduationService.record_usage` for the current
  `verified='verified'` gating.
- Soft blend of verified-ratio into the 7-factor readiness formula.
  Same dependency on a JSON-based ratio helper.

## See also

- `docs/architecture/CONTEXT_MEMORY.md` — upstream's existing
  string-tri-state verified-outcome infrastructure and episodic
  prefilter.
- `tests/test_outcome_verification.py` — upstream's existing
  verified-outcome test coverage.
