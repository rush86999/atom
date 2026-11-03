# Employee proof-binding repair — source 74acbd2b8

Status: **new product source submitted for independent verification.** Batch A
acceptance and served adaptive employee capability remain unclaimed.

This is not an unchanged resubmission. It adds the typed proof profiles and
correlated Sent Items binding that the `a770ced10` review withheld, plus the
fact-qualification scope check and restart/durable-proof controls.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/brennan-full-app-20261102` |
| Worktree | `/private/tmp/atom-full-app` |
| Executed source | `74acbd2b8` (full SHA in `MANIFEST.json`) |
| Prior reviewed source | `a770ced10` / evidence tip `02e0c569f` |
| Transport | controlled local service/DB; no live provider |

## Repaired proof contracts

### Typed verified-receipt profiles

A `require=verified` receipt now selects a material profile from the consumed
step rather than trusting whichever fields the returned verification happens
to include:

- **source read** — observed resource/source identity and version/hash, plus
  complete, known, non-truncated population coverage matching the requested
  `resource_binding` where one is declared; population counts must be finite,
  integral, present as a pair and fully accepted;
- **external mutation** — operation identity and remote/provider/message
  identity;
- **artifact** — the persisted artifact revision and sha256 receipt;
- **local calculation** — a material value or calculation receipt.

Missing required identity/coverage is unknown; any material mismatch is false;
empty/status-only/boolean-only proof is not a substitute. Applied status alone
never satisfies `verified`.

### Sent Items correlation

`sent_record_confirmed_evidence` now requires each applicable expected
identity in its own namespace:

- operation id must match the observed operation id;
- provider/message reference must match the observed provider/message
  reference;
- message id and account/mailbox must match when expected.

Presence without correlation is unknown. A correct operation id paired with a
wrong message id is refuted. Bare `sent_record_confirmed` booleans and boolean
`sent_items` shortcuts are no longer proof. Provider acceptance, Sent Items
observation and recipient delivery remain separate.

### Fact qualification scope

An established fact must bind a stable source reference that resolves against
the assignment's accepted source scope, or an explicit authored authority. A
model-supplied `evidence_state` or free-form note does not establish it.

### Durable proof on restart

Executor step results retain verification, coverage, readback and identity
fields (`operation_id`/`resource_id`/`version`/`message_id`/`account`) so a
dependent verified receipt or Sent Items criterion still resolves after a
fresh executor/session.

## Results

| Scope | Result |
|---|---|
| Integrated backend selection | **572 passed** |
| Frontend assignment/goal/approvals | **54 passed** |
| Focused affected suites | **224 passed** |
| Proof-binding matrix | **11 passed** |
| Two-domain deterministic campaign | **4 passed** |
| Patch invariants | **8 passed** |
| Independent evidence/G0/binding probes | **12 passed** |
| Corrected patch-freshness probe | **3 passed** |

The independent binding probe is the exact three-case probe from the
`a770ced10` review: status-only verified source, uncorrelated Sent Items
presence, and matching operation id with wrong message id. All three now
refuse/return unknown as required.

## Remaining boundaries

- Served-model adaptive-choice G5, held-out model campaign and ordinary-product
  two-domain journey are not run; adaptive employee capability remains
  unqualified.
- Batch A acceptance remains withheld pending this independent review.
- Four `test_task_lifecycle.py` controls fail identically to the parent/base;
  disclosed, not counted.
- No model inference or live provider action/send/credential/consent/spend;
  planner 5/5, goal router 1/2, alignment gap 3.0 and historical `111/123`
  unchanged.
