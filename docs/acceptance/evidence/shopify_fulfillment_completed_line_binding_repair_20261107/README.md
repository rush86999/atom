# Shopify fulfillment — completed line identity binding

Finite repair packet for root's new permanent probe at `147e66c29`:

`tests/test_lead_shopify_fulfillment_rest_shape.py::test_completed_official_line_id_cannot_be_overridden_by_optional_line_item_id`

- Pre-repair source: `147e66c29`
- Repair commit: `0556c7478`
- Current main: `2d251acdf` (already merged in the prior repair)
- Branch: `codex/shopify-fulfillment-lead-review-20261107`

Root's prior six-pass review of `d973d1b24` is preserved, not relabeled. This
packet closes the newly reproduced false positive.

## Contract

For a completed `Fulfillment.line_items[]` entry:

| Field | Meaning | Binding rule |
| --- | --- | --- |
| `id` | official order-line identity | **required and authoritative** |
| `line_item_id` | optional provider echo | may confirm `id`, never override it |

- `id` only → valid official shape.
- `id` + matching `line_item_id` → valid.
- `id` + different `line_item_id` → contradiction, refuted in **either**
  direction.
- missing `id` → genuinely missing required identity, unverified/unknown even
  if an optional alias is present.

The source `FulfillmentOrder` namespace is unchanged: source `id` is the FO-line
id and source `line_item_id` is the order-line id; the source validator still
requires `line_item_id` before POST.

## Repair

`backend/core/shopify_mutations.py`:

- `_fulfillment_observed_line_identity` now returns the official completed
  `id` only.
- `_fulfillment_completed_line_binding` records:
  - `line_item_identity_conflict` with both values when both identities are
    present and differ;
  - `line_item_identity_missing` when the required official id is absent;
  - `line_item_id_alias` when an unusable optional alias is present without the
    official id.
- `fulfillment_plan_mismatches` refutes any observed line carrying a
  missing/contradictory binding marker. Producer, Oracle receipt check and
  durable replay already reuse this shared material/plan proof.

No wrong material is normalised to the expected plan and no contradictory field
is silently dropped.

## New twins

- valid official `id` only;
- valid matching `id` + `line_item_id`;
- contradiction where the official `id` is wrong and the alias matches the plan;
- contradiction where the official `id` matches the plan and the alias is wrong;
- missing required official `id`, with and without an optional alias.

## Actual process results

`run_and_capture.py` uses the existing interpreter, `TESTING=1`, a fresh scratch
SQLite URL, `ENABLE_SCHEDULER=false`, and a scratch pytest basetemp. Only the
provider HTTP leaf is doubled.

| Phase | Source | Result | Exit |
| --- | --- | --- | --- |
| Failure-first completed alias | `147e66c29` | 1 failed | **1** |
| Exact permanent controls | clean `0556c7478` | 7 passed | **0** |
| Affected controls | clean `0556c7478` | 77 passed | **0** |

The 77 affected controls are the prior 72 controls plus the five new binding
twins. The earlier 72 remain green.

## Preserved evidence

- Original five negatives and the root-added two probes:
  `backend/tests/test_lead_shopify_fulfillment_rest_shape.py`
- Prior source packets remain unchanged:
  - `docs/acceptance/evidence/shopify_fulfillment_lead_repair_20261107/`
  - `docs/acceptance/evidence/shopify_fulfillment_line_namespace_repair_20261107/`

`MANIFEST.json` uses the current standard fields
`executed_source` / `source_files` / `artifacts`; old files-map packets were not
rewritten.

## Safety and disclosure

- No live provider, model, server, browser, account, credential, spend, install
  or send action was made.
- No live/shared database was used.
- Existing permissions/config (`opencode.jsonc`) remains unchanged and contains
  no credentials; it is not part of this packet or repair.
- Root acceptance remains withheld pending independent re-verification.

## Finite delivery

The completed-line identity namespace is now bound exactly in producer,
receipt, Oracle and durable-replay paths. The contradictory optional alias can
no longer certify a wrong official line.
