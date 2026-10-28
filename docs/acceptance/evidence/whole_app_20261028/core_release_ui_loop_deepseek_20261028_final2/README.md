# Core release UI loop — DeepSeek V4 Pro — 2026-10-28 — PASS

Candidate app code: `ec5ca78b8` (on `whole-app/successor-f5f`), with the
launch/harness fixes through `9a588e1bf` and the 180 s request-deadline binding
`0640b95e2`. World `core_release_deepseek_20261028`, run
`run-d9be5d4534b8`. Production UI `:3114`; isolated backend `:8061`.

## Configuration

- DeepSeek direct `https://api.deepseek.com/v1`, model `deepseek-v4-pro`
- provider policy selected, allowed `["deepseek"]`, no Ollama/other fallback
- `ATOM_REVIEW_MODEL=deepseek-v4-pro`, `ATOM_REVIEW_STRUCTURED=1`
- `ATOM_CHAT_STREAMING=false`
- `ATOM_CHAT_TURN_BUDGET_SECONDS=180`,
  `ATOM_CHAT_REQUEST_DEADLINE_SECONDS=180`, client timeout `300000 ms`
- isolated local-only exception only; global local-only, provider policy,
  stored credentials and the pilot unchanged

## Result: passed

Every check in the unchanged core loop passed:

- admin login, agent creation, both fixture uploads through the UI;
- canvas creation/agent attachment, policy taught through the UI;
- first grants assessment: `GR-2026-014 FUND`, `GR-2026-021 HOLD`,
  `GR-2026-033 DECLINE`, review `ok=true`, route `deepseek-v4-pro`;
- in-place correction saved on the same teaching point;
- different vendor assessment: `IN-7301 DECLINE`, `IN-7302 HOLD`,
  `IN-7303 HOLD`, review `ok=true`, route `deepseek-v4-pro`;
- deterministic calculation: **22200.00** over the three Open rows, with row
  and cell citations and source version `0a84a5f50661`;
- real backend restart; corrected teaching and pre-restart history survived;
- fresh post-restart vendor assessment: same three correct decisions, review
  `ok=true`, route `deepseek-v4-pro`;
- zero unauthorized writes.

## Transport repair that made this pass

The preserved first-grants failure was **not** a DeepSeek Flash failure. The
structured review was never dispatched: the route was skipped as
`model_inflight`, the helper silently returned `None`, and later the streaming
leg / `response_data` seam could replace the structured payload.

Fixed in this slice:

1. full ordered messages now pass through the scoped structured service;
2. provider/model is pinned with the existing scoped pin helper;
3. instructor JSON mode and a bounded sibling-claim wait are explicit;
4. typed `LAST_STRUCTURED_REVIEW` diagnostics distinguish transport, empty
   payload and validation failures;
5. the streaming leg is skipped when a structured answer exists;
6. the structured answer is written into `response_data`, so grounding,
   validation, persistence and fresh history consume the same payload;
7. structured successes stamp actual provider/model provenance;
8. the 180 s request deadline is now bound explicitly (previously the hidden
   default was 95 s).

Narrow reproduction: the exact previously intermittent grants request passed
in `core_release_narrow_grants_20261028_attempt8/` with a certified review and
actual `deepseek-v4-pro` provenance.

## Scope of the claim

This is the demonstrated core-release loop, not whole-app certification. The
screening set was 7/7 substantive and certified; this UI loop passed once. A
single pass is not a general reliability guarantee. No deployment is
authorized.

Raw evidence: `ui_loop_final.json`, `pre_restart_final.json`,
`fresh_after_restart_ui.text`, `final_after_restart.png`, `db_check.json`,
`dispatch_evidence.txt`, `run_stdout.text`.
