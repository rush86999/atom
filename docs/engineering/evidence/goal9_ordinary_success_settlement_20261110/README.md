# Goal 9 — ordinary BYOK success durable settlement

Date: 2026-11-10. Branch: `codex/goal9-ci-success-settlement-20261110`,
based on frozen CI-repair head
`0472eb9203a3d171c2b521a28c9a5f579397163f`. This is a CI-repair successor,
not Goal 9 acceptance. The atomic reservation WIP remains separate on
`codex/goal9-atomic-cap-20261110` (checkpoint history `bc8d7c10a`, newer
local WIP `bcc3c3a7b`); no atomic runtime is mixed into this branch.

## Root cause (runtime evidence)

The independent root probe (`retained_negative/root_goal9_ordinary_ci_probe.py`)
made two doubled ordinary `generate_response` calls. Both returned visible
answers, but the durable ledger held **two pending rows**:

```
billed=false, cost_usd=null, pricing_status="unknown",
prompt_tokens=0, completion_tokens=0
```

The success block only updated the in-memory tracker/cache/rate/feedback
surfaces. `_record_provider_usage` was called only on empty/no-choices
branches, so ordinary success never settled the pre-dispatch intent. The
pre-fix log and observation are retained in `retained_negative/`.

## Fix

After the real usage/pricing/cache block on a successful attempt, call the
existing durable helper `record_llm_usage` once with the exact pre-dispatch
`attempt_id`, `request_id`, provider/model, scope, `execution_id`, and
`chain_id`:

- known usage + cost -> `billed=true`, `priced` (or `free` for authoritative
  0.0), actual prompt/completion tokens;
- missing usage or unavailable pricing -> `billed=true`, `cost_usd=null`,
  `pricing_status="unknown"` (explicit liability, never a fabricated 0);
- a settlement write failure is logged/surfaced by the existing degraded
  marker; the pending intent remains and hard-stop keeps refusing across a
  restart;
- replay of the same attempt is idempotent; no second tracker/rate/cache or
  feedback write is added. The inline tracker/cache/rate/feedback surfaces
  are unchanged.

## Root probe result (fixed)

Two ordinary calls now produce two distinct settled rows:

```
billed=true, cost_usd=0.25, pricing_status="priced",
prompt_tokens=10, completion_tokens=5, execution_id=null,
workspace_id="root-budget-ws", tenant_id="root-budget"
```

SpendAggregation ledger = **0.5**. The root probe passes **2/2**
(`gates/root-probe-fixed.log`, `gates/root-probe-observation.json`).

## Tests / gates (scratch SQLite, doubled transport)

- Focused (two CI files + ordinary success contract): **62 passed**
- Bounded backend-core BYOK/route subset: **228 passed**
- Durable/upgrade regression: **29 passed**
- Root independent probe: **2 passed** (pre-fix negative retained)

`tests/test_goal9_ci_execution_contract.py` now has six controls:
missing execution -> `None`; exact provided execution; intent failure with
zero provider calls on both routes; two-success settlement (0.5 ledger,
10/5 tokens, distinct attempts, exact replay); missing usage -> explicit
unknown; settlement failure retains the intent and hard-stop refuses after
a fresh engine/restart.

## Additive CI gate

The existing c3 durable-settlement step is preserved unchanged. A new
additive backend-core step runs
`tests/test_goal9_ci_execution_contract.py`; the immutable CI baseline
fixture was not modified.

## Honest limits

- Scratch SQLite only; no hosted CI, live DB, provider/model, credential,
  send, spend, deploy, download, or dependency change.
- The fix is ordinary success settlement only; other success paths (e.g.
  structured/chat) have their own existing settlement calls and were not
  changed here.
- Root owns hosted CI, integration, and any merge. No self-accept/merge.
