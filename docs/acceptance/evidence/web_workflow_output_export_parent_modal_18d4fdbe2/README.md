# Parent execution-modal export coverage — evidence packet

Packet: `docs/acceptance/evidence/web_workflow_output_export_parent_modal_18d4fdbe2/`

## Scope

The prior export UI tests only exercised the standalone
`ExecutionDetailView`. The ordinary `WorkflowAutomation` parent renders its own
Execution Details modal with a separate fetch/blob/download/error handler. This
checkpoint adds real parent-modal coverage and fixes one actual refusal-message
bug.

No backend/runtime change: the export definition-binding repair remains frozen
at `1c876b5f6`.

## Parent modal coverage

- Positive: completed execution `e2` opens in the real modal, downloads through
  `GET /api/v1/workflows/workflows/executions/e2/export`, uses the
  `Content-Disposition` filename, creates/revokes the blob, shows the success
  toast, and does **not** call any execute route.
- Typed refusals: 409 `{detail:{error,message}}` and 503
  `{detail:{error,message}}` render the server message in the modal's
  Download unavailable alert, with no blob creation.
- Running execution: download control is disabled.
- Existing parent tests are retained.

## Actual bug fixed

The parent refusal handler previously passed a structured `detail` object
through `extractApiErrorMessage`, which JSON-serialized it instead of showing
the error message. It now reads `detail.message` / `detail.error` first, then
falls back to the generic extractor. This is the only product change in this
checkpoint.

## Pre-existing failure (not caused by this change)

`shows error toast when workflow execution fails` expects the generic
“Failed to execute workflow” while the component (at base `7fd05261c` too)
truthfully shows the server error `nope`. It fails identically at the base
source; log under `pre_existing/base_7fd_parent_error_toast_failure.proof`.
It was left unchanged rather than weakened.

## Gates

| Gate | Result | Log |
|---|---|---|
| Parent export tests (targeted) | 4 passed | `gates/parent_export_targeted_4.proof` |
| Full parent suite | 46 passed, 1 pre-existing failure | `gates/parent_full_suite_46pass_1pre_existing_fail.proof` |
| Standalone ExecutionDetailView + AgentWorkflowGenerator | 36 passed | `gates/standalone_generator_36.proof` |
| TypeScript | not accepted from this sparse checkout | `gates/tsc_sparse_checkout_limitation.proof` |

The TypeScript run is reported honestly: the sparse checkout lacks
`frontend-nextjs/src` and other generated/imported modules, producing
module-resolution errors. No tsc-green claim is made.

## Claim boundary

- Scratch component tests only; no browser campaign, model, provider, install,
  send/spend or deployment.
- No CI YAML/ledger edits; root owns integrated CI, delivery and PR/merge.
- This is not whole-app acceptance; backend export runtime remains `1c876b5f6`.
