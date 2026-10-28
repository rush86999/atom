# Core UI loop — DeepSeek Flash — fixed transport — 2026-10-28 — PASS

Tested app code `35860a7f0` (includes fail-closed review pins, scoped
provenance and structured-payload restoration), with the repaired launch/harness
configuration. World `core_release_deepseek_20261028`, run `run-d9be5d4534b8`.
Production UI `:3114`; isolated backend `:8061`.

Configuration: DeepSeek direct `deepseek-flash`, provider policy selected to
`deepseek` only, `ATOM_REVIEW_MODEL=deepseek-flash`, structured review on,
streaming off, 180 s turn and request deadlines, 300,000 ms client timeout.

**All 28/28 checks passed.** The three assessment/review payloads report actual
`deepseek-flash` / `deepseek` provenance; calculation is **22200.00** with
row/cell citations and source hash; correction, restart persistence, fresh
post-restart assessment and zero unauthorized writes all pass.

Auxiliary planning/verification calls on the same DeepSeek provider may use a
different served model; the certified assessment payload is Flash and is
pinned fail-closed. This is a demonstrated core-release workflow, not universal
reliability. No deployment.
