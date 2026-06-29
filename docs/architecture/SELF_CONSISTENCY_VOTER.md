# Self-Consistency Voter

> Pre-execution certainty layer for **structured action plans**.
> Parallel to [`MATCH_CONFIDENCE.md`](./MATCH_CONFIDENCE.md) — that layer
> scores selector certainty *within* a single LLM call; this layer scores
> plan certainty *across* N LLM calls.

**Last Updated**: June 29, 2026

---

## What it does

`SelfConsistencyVoter` (`core/llm/self_consistency_voter.py`) implements the
[Wang et al. 2022 self-consistency pattern](https://arxiv.org/abs/2203.11171)
for structured action plans. Given a single prompt, it:

1. Samples the same handler **N times** at varying temperatures
   (`[0.6, 0.7, 0.8]` for N=3, centered on 0.7).
2. Hash-normalizes each plan (`json.dumps(sort_keys=True)`) so superficial
   field-order differences don't fragment the vote.
3. Picks the modal plan (majority hash, ties → first-seen = lowest temp).
4. Returns a `VoteResult` carrying the modal plan **plus** agreement
   metadata: ratio, tri-state level, sample counts, hashes.

The caller executes the winning plan **exactly once**. The voter never
executes anything — that firebreak is AST-enforced by test C1.

## When it fires

The voter only runs when **both** conditions hold:

| Gate | Where | Default |
|---|---|---|
| `enable_self_consistency=True` kwarg | Caller asserts the action is irreversible | `False` |
| `ATOM_SELF_CONSISTENCY=true` env (or tenant override) | Feature-flag rollout | `False` |

When either is false, `LLMService.generate_structured` falls through to the
normal single-sample path. The voter module adds zero import-graph cost
when dormant (lazy import inside `generate_structured`).

The caller is responsible for asserting irreversibility. The
`SelfConsistencyVoter.is_irreversible(action_plan)` heuristic is provided as
a helper — it pattern-matches action-type fields against
`_IRREVERSIBLE_PATTERNS` (`send_`, `create_`, `update_`, `delete_`, `bulk_`,
`transfer`, `payment`, `charge`, `refund`, `purchase`, `deploy`, `execute_`,
`publish`, `submit_`). Read-only verbs (`search`, `browse`, `get`, `list`)
are intentionally absent — the voter should never burn 3× cost on a
read-only action.

## What it does NOT do

- **Does not import the executor.** Hard AST-enforced invariant (test C1).
  The voter may import only `hallucination_config` + stdlib + typing.
  `UnifiedActionExecutor`, `atom_meta_agent`, `generic_agent`,
  `core.api.*`, and `core.proposal_service` are forbidden at import time.
- **Does not call ProposalService.** Gating (routing to a human reviewer)
  is the caller's responsibility, mirroring the match-confidence pattern
  where `browser_tool._maybe_gate_with_proposal` decides, not
  `selector_confidence_service`.
- **Does not retry failed samples.** Per-sample failures are logged and the
  vote proceeds with the survivors. If every sample fails, the voter
  returns `VoteResult(winner=None, is_no_samples=True)`.
- **Does not normalize semantic equivalence.** `json.dumps(sort_keys=True)`
  handles field-order differences but not numeric (`1.0` vs `1`) or
  semantic (`click` vs `press`) equivalence. RFC 8785 JCS is the documented
  future hardening — see [§ Normalization](#normalization).

## Relation to match-confidence

Two pre-action certainty layers, addressing different questions:

| Layer | Question | Scope | Mechanism |
|---|---|---|---|
| Match-confidence ([`MATCH_CONFIDENCE.md`](./MATCH_CONFIDENCE.md)) | "Which selector should I click?" | Within one LLM call | Deterministic scorer + LLM tiebreaker |
| Self-consistency voter (this doc) | "Which plan should I execute?" | Across N LLM calls | Hash-normalized majority vote |

Both gate via `ProposalService`. Both default to shadow mode (compute +
audit always on, gating off). Both expose a tri-state
(`high` / `partial` / `ambiguous`) using the same thresholds
(`HIGH_THRESHOLD=0.85`, `PARTIAL_THRESHOLD=0.50`). Both have a
force-proposal knob (`MATCH_CONFIDENCE_FORCE_PROPOSAL`,
`ATOM_SELF_CONSISTENCY_FORCE_PROPOSAL`) and a master kill switch
(`SELECTOR_CONFIDENCE_ENABLED`, `ATOM_SELF_CONSISTENCY`).

They compose: an irreversible action first resolves its selectors through
match-confidence (does the LLM know what to click?), then the assembled
plan goes through the voter (do N LLM calls agree on what to do?). Either
layer can independently route the action to `ProposalService`.

## Tri-state levels

`VoteResult.level` maps `agreement_ratio = winner_count / valid_count`:

| Ratio | Level | Example (N=3) | Example (N=5) |
|---|---|---|---|
| `agreement ≥ 0.85` | `high` | 3/3 = 1.0 | 5/5 = 1.0 |
| `0.50 ≤ agreement < 0.85` | `partial` | 2/3 = 0.667 | 3/5 = 0.6, 4/5 = 0.8 |
| `agreement < 0.50` | `ambiguous` | 1/3 = 0.333 (all distinct) | 2/5 = 0.4 |

Properties on `VoteResult`:

- `is_high` → True for `level == "high"`
- `requires_review` → True for `level in {partial, ambiguous}`
- `is_no_samples` → True when every sample failed (winner is None)

Callers that gate on the level should branch on `requires_review`, not on
the raw ratio — the threshold is env-overridable and may shift.

## Shadow mode + audit

Default behavior (`ATOM_SELF_CONSISTENCY_FORCE_PROPOSAL=false`):

1. Voter runs (3 samples).
2. Modal plan returned to caller.
3. **Audit row always written** to `self_consistency_votes` table
   (`SelfConsistencyVote` model in `core/models.py`).
4. Caller executes the modal plan — even on `partial` / `ambiguous`.

This gives operators telemetry on agreement rates *before* flipping the
gate. After observing the distribution for a pilot period, flip the
force-proposal flag to start routing low-agreement votes to reviewers.

Force-proposal mode (`ATOM_SELF_CONSISTENCY_FORCE_PROPOSAL=true`) is the
**caller's** concern, not the voter's. The caller reads
`vote_result.requires_review` and, when true, calls
`ProposalService.create_action_proposal(...)` instead of executing. The
caller then updates the audit row with `gated=True` and
`proposal_id=<returned-id>`. (The voter itself does not see
`ProposalService` — that would violate the C1 import invariant.)

For an example of this caller pattern, see
`tools/browser_tool.py:_maybe_gate_with_proposal` (match-confidence's
equivalent).

## Normalization

`_hash_sample` uses `json.dumps(payload, sort_keys=True, default=str)`. This
handles:

- Pydantic v1 / v2 / dict / namespace input shapes (uniform payload
  extraction).
- Recursive key ordering (so `{a: 1, b: 2}` and `{b: 2, a: 1}` collide).
- Non-serializable values stringified via `default=str`.

It does **not** handle:

- **Numeric equivalence**: `1.0` ≠ `1` ≠ `1.00` after serialization.
- **Semantic equivalence**: `click` ≠ `press` ≠ `tap`; `text=Submit` ≠
  `button:has-text("Submit")`.
- **Argument-set reordering**: `[fill("name"), fill("email")]` ≠
  `[fill("email"), fill("name")]` when order doesn't actually matter.

The first is solved by [RFC 8785 JSON Canonicalization Scheme
(JCS)](https://www.rfc-editor.org/info/rfc8785/) (`pip install jcs`). The
second and third require a domain-specific synonym map and an
unordered-set normalizer — both are future work, tracked in § Future
hardening.

For the current N=3 default, false-disagreement rate is low enough that
`partial` outcomes reliably indicate genuine model uncertainty. As N
scales past 5, normalization depth becomes more critical.

## Cost model

For one irreversible action with N=3 samples:

- **Token cost**: 3× a single call.
- **Wall-clock latency**: ~1× a single call (parallel via `asyncio.gather`).
- **Provider rate limits**: spread across the same provider (atom's
  BYOKHandler preserves the provider-family invariant — all N samples hit
  the same family, no credential drift).

To reduce cost without losing the safety property, future work could route
the N samples to the **budget tier** (`CognitiveTier.MICRO`) and only
escalate the winner to a premium model for final shaping. This is the same
pattern atom's `cache_aware_router` uses elsewhere.

## Failure modes (and what to do about them)

These are well-documented in the literature. The most important ones:

### 1. All N samples share the same systematic error

The core limitation. Self-consistency reduces **variance**, not **bias**.
If the model has a systematic hole (training-data gap, prompt framing
bias), all N stochastic samples will reproduce the same wrong answer and
the vote will report `high` agreement on the wrong plan.

**Mitigation (BYOK superpower)**: atom's BYOK multi-provider setup can
spread the N samples across providers (2× OpenAI + 1× Anthropic at N=3) —
architecturally independent models don't share systematic errors. The
voter currently uses a single handler instance for all N samples; the
future cross-provider fan-out is tracked in § Future hardening.

Reference: [Too Consistent to Detect (EMNLP 2025)](https://aclanthology.org/2025.emnlp-main.238/)
— studies exactly this failure mode.

### 2. Mode collapse at low temperature

If `temperature < 0.5`, all N samples collapse to the greedy path and the
vote becomes a rubber stamp. The voter's `_temperatures_for(n, base=0.7)`
guarantees the spread starts at `0.6` for N=3, so this is structurally
prevented — **unless the caller passes a non-default `temperature`**. If
you call `vote(temperature=0.2, ...)`, the spread becomes `[0.1, 0.2, 0.3]`
and you've defeated the diversity. Don't do this.

### 3. Cost plateaus

Diminishing returns past N=10. For structured action plans, N=3 is the
sweet spot — 2/3 majority is well-defined, 3× cost ceiling is acceptable
for irreversible actions.

References:
- [Diminishing Returns and Rising Costs in Modern LLMs (arXiv 2511.00751)](https://arxiv.org/html/2511.00751v2)
- [Wang et al. 2022 (original)](https://arxiv.org/abs/2203.11171)

### 4. Position-bias prompts

Self-consistency **amplifies** position bias on tasks like "is A or B
better?" — every sample votes for the same position.

Reference: [Self-Consistency Falls Short! (TACL)](https://direct.mit.org/tacl/article/doi/10.1162/TACL.a.625/136156/Self-Consistency-Falls-Short-The-Adverse-Effects)

**Mitigation**: don't apply the voter to position-bias-prone prompts. The
voter is designed for *action plans* (what to do), not *judgment calls*
(which is better).

## Rollout strategy

Mirrors the match-confidence layer's Phase 6 rollout:

1. **Dormant default** (current state): `ATOM_SELF_CONSISTENCY=false`.
   Voter module present, `enable_self_consistency` kwarg accepted but
   flag-off callers never dispatch. Zero cost.
2. **Shadow mode**: flip `ATOM_SELF_CONSISTENCY=true` in staging. Voter
   runs, audit rows accumulate. Modal plan still returned to caller
   (force-proposal off). Operators query `self_consistency_votes` to
   observe agreement-rate distribution.
3. **Per-tenant pilot**: set
   `tenant.metadata_json["hallucination_mitigations"]["self_consistency"]=true`
   on one tenant for production shadow mode.
4. **Force-proposal pilot**: with a tenant that has both
   `self_consistency=true` and `self_consistency_force_proposal=true` in
   metadata, callers that opt into `enable_self_consistency=True` will
   route `partial`/`ambiguous` votes through `ProposalService`.
5. **Global flip**: `ATOM_SELF_CONSISTENCY=true` and
   `ATOM_SELF_CONSISTENCY_FORCE_PROPOSAL=true` in production env.

### Kill switches

| Switch | Effect |
|---|---|
| `ATOM_SELF_CONSISTENCY=false` | Voter never runs (kwarg ignored). |
| `enable_self_consistency=False` (per-call) | Voter skipped for this call. |
| `ATOM_SELF_CONSISTENCY_FORCE_PROPOSAL=false` | Shadow mode — vote computed + audited, modal plan returned regardless of level. |

## Workstream A and B (ported config, not yet wired)

`hallucination_config.py` ships the full surface from atom-saas:

- **Workstream A** (verified graduation gate):
  `is_verified_gate_enabled`, `get_verified_ratio_floor`,
  `get_verified_blend_weight`. Backed by the `verified` column on
  `AgentReasoningStep` (migration `20260624_reasoning_verified`) and
  `CapabilityGraduationService`. **Integration into the graduation
  decision is a follow-on task** — the resolvers are present but
  `CapabilityGraduationService.record_usage` does not yet consult them.
- **Workstream B** (cascade routing): `is_cascade_routing_enabled`,
  `FRONTIER_MODELS`, `is_frontier_model`, `get_frontier_model_for_provider`.
  **Integration into `LLMService.generate_structured` (retry on
  schema-validation failure) is a follow-on task** — the registry and
  resolvers are present but the retry path is not yet wired.

Only Workstream C (the voter) is fully wired by this port.

## Future hardening

Tracked as follow-on work, not blockers for the initial port:

1. **RFC 8785 JCS canonicalization** — replace `json.dumps(sort_keys=True)`
   with `jcs.canonicalize()` for proper numeric equivalence. `pip install
   jcs`, ~10-line change in `_hash_sample`.
2. **Cross-provider fan-out** — instead of N samples through one handler,
   spread N samples across M providers (BYOK superpower for breaking
   systematic-error correlation). Requires extending the voter constructor
   to accept a list of handlers.
3. **Synonym fold** — domain-specific equivalence map for selector verbs
   (`click` ≡ `press` ≡ `tap`) and tool names. Requires a curated map per
   tool family.
4. **Universal SC fallback** — when no two samples hash-collide (the
   "all-distinct" case), feed all N plans to a judge LLM and ask "which is
   most consistent with the others?" instead of falling back to the
   lowest-temp sample. Adds one LLM call but recovers signal from
   otherwise-wasted votes. Reference: [Universal Self-Consistency (Chen
   2023)](https://arxiv.org/abs/2311.17311).
5. **Workstream A integration** — gate
   `CapabilityGraduationService.record_usage` on
   `is_verified_gate_enabled` + the agent's verified-ratio floor.
6. **Workstream B integration** — wrap the
   `handler.generate_structured_response` call in `generate_structured`
   with a same-family frontier retry on `instructor.exceptions.InstructorRetryException`.

## File map

| File | Purpose |
|---|---|
| `backend/core/hallucination_config.py` | Flag resolvers + registries (all 3 workstreams). |
| `backend/core/llm/self_consistency_voter.py` | Voter module — `SelfConsistencyVoter`, `VoteResult`, tri-state level constants. |
| `backend/core/llm_service.py` | `generate_structured` (kwarg dispatch), `generate_structured_with_consensus` (returns metadata), `_run_self_consistency_vote`, `_write_self_consistency_audit`. |
| `backend/core/models.py` | `SelfConsistencyVote` audit model (search for `class SelfConsistencyVote`). |
| `backend/alembic/versions/20260629_add_self_consistency_votes.py` | Guarded migration. |
| `backend/tests/test_self_consistency_voter.py` | 24 tests — C1-C8 ported + C9-C15 new for shadow/audit. |

## References

- [Wang et al. 2022 — Self-Consistency Improves Chain of Thought Reasoning in Language Models](https://arxiv.org/abs/2203.11171)
- [Universal Self-Consistency (Chen 2023, ICML 2024)](https://arxiv.org/abs/2311.17311)
- [Soft Self-Consistency Improves Language Model Agents (ACL 2024)](https://aclanthology.org/2024.acl-short.28.pdf)
- [Confidence Improves Self-Consistency in LLMs / CISC (arXiv 2502.06233)](https://arxiv.org/html/2502.06233v2)
- [Too Consistent to Detect (EMNLP 2025)](https://aclanthology.org/2025.emnlp-main.238/)
- [Self-Consistency Falls Short! (TACL)](https://direct.mit.org/tacl/article/doi/10.1162/TACL.a.625/136156/Self-Consistency-Falls-Short-The-Adverse-Effects)
- [Diminishing Returns and Rising Costs (arXiv 2511.00751)](https://arxiv.org/html/2511.00751v2)
- [RFC 8785 JSON Canonicalization Scheme](https://www.rfc-editor.org/info/rfc8785/)
- atom-saas source of truth: `backend-saas/core/llm/self_consistency_voter.py`
