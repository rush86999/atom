# Employee proof-binding repair — source c6ac292f3

Status: **new product source submitted for independent verification.** Batch A
acceptance and served adaptive employee capability remain unclaimed.

This source completes the typed proof-binding and correlated Sent Items matrix
that the `a770ced10` review withheld, including observed coverage (not merely a
coverage claim inside the verification envelope) and artifact/local durable
proof profiles.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/brennan-full-app-20261102` |
| Worktree | `/private/tmp/atom-full-app` |
| Executed source | `c6ac292f3` (full SHA in `MANIFEST.json`) |
| Prior reviewed source | `a770ced10` / evidence tip `02e0c569f` |
| Transport | controlled local service/DB; no live provider |

## Repaired proof contracts

### Typed verified-receipt profiles

A `require=verified` receipt selects a material profile from the consumed step:

- **source read** — observed resource/source identity and version/hash, plus
  complete, known, non-truncated population coverage. Coverage must be observed
  on the durable result/receipt, not asserted only inside the verification
  envelope. Requested `resource_id`/version must match. Population counts must
  be finite, integral, present as a pair and fully accepted.
- **external mutation** — operation identity plus remote/provider/message
  identity; declared account/message bindings must match.
- **artifact** — the actual persisted artifact revision and sha256.
- **local calculation** — a material value or calculation receipt.

Missing required identity/coverage is unknown; a material mismatch is false;
status-only, boolean-only and empty proof are not substitutes. Applied status
alone never satisfies `verified`.

### Sent Items correlation

Each applicable expected identity is compared in its own namespace:

- operation id to observed operation id;
- provider/message reference to observed provider/message reference;
- message id and account/mailbox when expected.

Presence without correlation is unknown. A correct operation id with a wrong
message id is refuted. Bare `sent_record_confirmed` booleans and boolean
`sent_items` shortcuts are no longer proof. Provider acceptance, Sent Items
observation and recipient delivery remain separate.

### Fact qualification and durability

An established fact must bind a stable source reference that resolves against
the assignment's accepted source scope, or an explicit authored authority. A
model-supplied `evidence_state` or free-form note does not establish it.

Executor step results retain verification, coverage, readback and identity
fields (`operation_id`/`resource_id`/`version`/`message_id`/`account`) so a
dependent criterion still resolves after a fresh executor/session.

## Results

| Scope | Result |
|---|---|
| Integrated backend selection | **573 passed** |
| Frontend assignment/goal/approvals | **54 passed** |
| Focused affected suites | **225 passed** |
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
