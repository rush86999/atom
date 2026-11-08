# TASK-WAIT-01 — missing authoritative revision after acceptance

**Executed source:** `40f57791a059186c9b988d24e387e4a54609b759` (clean;
`dirty=False`). **Root negative source:** `72a27e540` with permanent test
`aab7a62cd`.
**Base:** prior accepted focused repair `5fb98e929`; earlier authority packet
`72a27e540` / `c218b070a`; main `36fa4ce39` merged.

## Root negative preserved

`root-missing-revision-negative.log` and
`root-missing-revision-negative.exit.json` are copied unchanged:

- **2 failed, actual exit 1**, 2.53s.
- After a valid accepted indexed receipt, SQL
  `IngestedDocument.source_content_hash` was set to `None` and then empty.
- The old condition `if expected and authoritative and expected !=
  authoritative` skipped comparison when current authority was missing, so
  `_source_consumption_gap` returned `None` and the old receipt could certify
  success.

Earlier negatives remain preserved: progress/extraction root (**3 failed**),
missing/unreadable source (**2 failed**) and deleted authoritative upload
(**1 failed**). Prior clean 11-pass log at `5fb98e929` is retained.

## Repair

The upload consumption branch now reuses the existing strict producer/consumer
contract `core.doc_freshness_service.current_extraction_revision` instead of a
local comparison:

- Current authoritative revision missing/None/empty → typed
  `stale_source_version` gap (unresolved, never the old receipt).
- Wrong revision kind, malformed `ev…` revision, mismatched extractor version,
  mismatched digest, or a missing/mismatched accepted pin → typed gap.
- Exact current `ev4:<digest>` and exact manual opaque revisions continue to
  pass; no prefix stripping, binary-hash coercion or namespace merging.
- Accepted pin missing entirely → typed `source_revision_missing` gap.
- Binary file hashes remain in their own binary namespace; extracted-text
  hashes remain in `extraction.text_sha256`.

The applied operation receipt remains immutable; only dependent work and the
final artifact are blocked. No new validator, store, engine, router or budget
API was added, and scope/authority gates were not relaxed.

## Focused actual results

Bounded profile, fresh scratch DB/data/Lance/output, `TESTING=1`:

| Log | Scope | Actual |
|---|---|---:|
| `focused-missing-revision-13.log` | root missing SQL None/empty (2); progress/extraction gap + valid ev4/manual (3); disappearance negatives (3); G2 refusal/newer/same-version (3); valid unchanged (2) | **13 passed**, exit 0 |
| `prior-focused-root-and-recovery-11.log` | prior clean 11-control root/recovery run at `5fb98e929` | **11 passed**, exit 0 (preserved) |

Root negative actual: **2 failed, exit 1**. No broad test, browser/model,
provider or live action was dispatched.

The public-route no-artifact boundary is already covered by the disappearance
and deletion negatives; this missing-revision negative exercises the same
applied-source consumption boundary directly. Root owns independent external
verification.

## Limits

TASK-WAIT-01 remains OPEN at whole-app scope; 143 claims and historical scores
unchanged. G1/G4 tests and the G3 proposal remain; no G3 implementation before
root accepts this source boundary. Root owns PR/CI/review/merge.
