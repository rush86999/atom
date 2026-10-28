# Core release UI loop — DeepSeek configuration — 2026-10-28 — BLOCKED

Candidate code: `9e6886563` on `whole-app/successor-f5f`.
World: `core_release_deepseek_20261028`, run `run-d9be5d4534b8`.
Production UI: `:3114`; isolated backend: `:8061`.

## Declared configuration

- DeepSeek direct `https://api.deepseek.com/v1`, model `deepseek-v4-pro`
- provider policy `selected`, allowed `["deepseek"]`, no Ollama/other fallback
- `ATOM_REVIEW_MODEL=deepseek-v4-pro`
- `ATOM_CHAT_STREAMING=false`, `ATOM_REVIEW_STRUCTURED=0` for the main run
  (attempt 4 separately diagnosed structured output with `=1`)
- `ATOM_CHAT_TURN_BUDGET_SECONDS=180`, client timeout `300000 ms`
- isolated local-only exception only; global local-only, provider policy,
  stored credentials and the pilot are unchanged

## Attempts preserved

| Attempt | Result |
|---|---|
| 1 | Substance, calculation, correction, restart, fresh assessment and zero writes passed. Model identity failed because contract-only recovery switched from `deepseek-v4-pro` to `deepseek-flash`. |
| 2 | Same functional pass; CORS/upload failure diagnosed (backend child allowed `:3115`, UI on `:3114`). Recovery still switched to flash. |
| 3 | Model identity passed for every review. Grant assessment passed; vendor assessment produced no parseable review block. Harness also crashed writing a missing attempt directory after the failed turn. |
| 4 | Vendor, fresh post-restart, calculation, correction, restart, persistence and zero-write checks passed on `deepseek-v4-pro`. **First grants assessment returned no parseable `review_result` block.** Structured output (`ATOM_REVIEW_STRUCTURED=1`) did not fix it; the structured dispatch produced no trace and the text fallback still lacked a block. |

All three assessment turns in attempt 4 were routed to the declared
`deepseek-v4-pro` / `deepseek` route (response metadata and provider logs).
No decision label was rewritten, no evidence/policy ID was auto-attached, and
no semantic retry was added.

## What passed in attempt 4

- admin login, agent creation, UI upload of both fixtures;
- canvas creation/agent attachment, policy taught through UI;
- in-place correction (one teaching point retained);
- different unfamiliar vendor assessment: `IN-7301 DECLINE`, `IN-7302 HOLD`,
  `IN-7303 HOLD`, review `ok=true`;
- deterministic calculation: **22200.00** over the three Open rows, with row
  and cell citations and source version `0a84a5f50661`;
- real backend restart; corrected policy and pre-restart history survived;
- fresh post-restart vendor assessment: same three correct decisions,
  review `ok=true`, declared route;
- zero unauthorized writes (all side-effect tables zero, no forbidden
  invocation kinds).

## What failed

Only the first grants assessment: the model response had no parseable
`review_result` block, so the validator correctly refused it with
`missing_structured_review` and three `missing_decision` errors. The same
grants case passed in attempts 1–3, so this is a format/reliability boundary,
not a substantive judgment error. Enabling structured output did not make it
reliable.

## Decision

**No release, no ledger upgrade, no deployment.** The candidate's intended AI
configuration is DeepSeek direct `deepseek-v4-pro`, non-streaming, with
`ATOM_REVIEW_MODEL=deepseek-v4-pro` and DeepSeek-only provider policy.

The remaining launch blocker is the review-block format boundary under the
full product prompt. Another full UI campaign should not be launched until
that boundary is fixed at the transport/contract layer and tested. This run
must not be counted as a core-release pass.

Raw evidence: `ui_loop_final.json`, `pre_restart_final.json`,
`fresh_after_restart_ui.text`, `final_after_restart.png`, `db_check.json`,
`run_stdout.text`. Prior attempts are in the sibling `attempt2` directory and
the earlier `core_release_ui_loop_deepseek_20261028` directory.
