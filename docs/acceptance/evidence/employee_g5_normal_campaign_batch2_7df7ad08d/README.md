# Employee G5 capability/eligibility batch — source 7df7ad08d

Status: **bounded API-level campaign passed 18/18 checks on a clean source.
This is not the normal app/browser UI journey.** The backend capability,
missing-prerequisite and source-settlement repairs are complete; UI exercise
remains with the product/UI owner.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/brennan-full-app-20261102` |
| Product source | `7df7ad08d` |
| Worktree | `/private/tmp/atom-full-app` (clean at run) |
| Transport | real assignment routes + real `AssignmentExecutor`, scratch SQLite world, controlled local fixtures |
| Model | `ollama/llama3.1:8b`, 16k context, pinned |
| Raw traces | `attempts.jsonl` (prompt/schema, parsed, raw completion) |

The campaign harness started the controlled acceptance server and called the
normal assignment routes over HTTP. It supplied only objective, authorized
source references, teaching terms and one authorized invoice source after the
model's question. No rows, expected totals, step patches or final plans were
supplied.

## Repairs in this batch

- **Contract-based evidence eligibility:** accepted applied results with
  tabular rows, structured objects or text are routed to adaptation; business
  header names no longer filter evidence. `Product / Units / ApprovedCost`
  works end to end.
- **Capability status:** quote/invoice capabilities expose
  `ready`/`missing`/`ambiguous`/`unavailable` with missing roles and known
  identities. Missing capabilities remain visible but do not expose executable
  work-request schemas.
- **Actionable missing prerequisite:** an empty or progress-free model reply
  gets one bounded repair; if it still does not ask, a deterministic
  `missing_evidence` obligation names the missing role and known PO identity.
- **Same-job source answer:** the normal source route resolves the matching
  obligation only when the added source makes the capability ready. Duplicate
  source addition is idempotent. A source for a different PO is refused and
  cannot settle the question. Expected-version mismatch refuses stale bytes.
- **Mechanical mapping safety:** quote columns are validated against accepted
  values; text→quantity/price swaps and currency-code misuse are corrected from
  value shape when unambiguous. Invoice/PO/receiving roles are resolved from
  structured fields and must share the accepted PO identity.
- **Harness safety:** the campaign runner never deletes an arbitrary `--world`.
  It creates a fresh unique scratch world by default; an existing world must
  carry the launcher marker and `--reset-world` before deletion.

## Campaign — 18/18 checks

| Check | Observed |
|---|---|
| Quote initial model proposal | `model` |
| Quote typed work adopted | `quote_calculation`, applied |
| Quote total | **370.00** |
| Quote changed evidence | **485.00** |
| Restart | **485.00** survives |
| Cancellation | terminal `cancelled` |
| Invoice reconciliation | **270.00** |
| Missing invoice fabricated? | no; model asked a targeted question |
| Question names missing role and PO | `invoice`, `PO-8` |
| Source answer resolves obligation | yes |
| Duplicate source | `already_present`, no new step |
| Recovery | model reconciliation **270.00** |

The quote workbook used unfamiliar `Product / Units / ApprovedCost / Currency`
headers; the model performed the semantic mapping and the compiler repaired a
type-swapped mapping deterministically.

## Focused controls

- Focused typed-work/adaptation/executor/routes suite: **167 passed**.
- Independent evidence-eligibility probe: **2 passed**.
- World-guard refusal controls: disposable sentinel preserved; marked reset
  only with explicit flag.
- Deterministic two-domain campaign and uncertain-effect reconciliation remain
  separately covered at their prior sources.

## Boundaries

No cloud/live provider, credential, consent, send, spend or deployment was
used. This is an API-level campaign; normal app/login/browser upload and UI
question/answer remain open. Historical `111/123`, planner 5/5, goal router 1/2
and alignment gap 3.0 are unchanged.
