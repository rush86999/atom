# Core UI loop — DeepSeek Flash — 2026-10-28 — PASS

Candidate app code `ec5ca78b8` with the repaired review transport and launch
fixes. World `core_release_deepseek_20261028`, run `run-d9be5d4534b8`.
Production UI `:3114`; isolated backend `:8061`.

Configuration: DeepSeek direct `deepseek-flash`, provider policy selected to
`deepseek` only, `ATOM_REVIEW_MODEL=deepseek-flash`, structured review on,
streaming off, 180 s turn and request deadlines, 300,000 ms client timeout.
No Pro or local fallback is configured.

All **28/28** checks passed:

- grants assessment `FUND / HOLD / DECLINE`, certified;
- in-place correction;
- vendor assessment `DECLINE / HOLD / HOLD`, certified;
- calculation **22200.00** with row/cell citations and source hash;
- real restart; teaching and history persisted;
- fresh post-restart assessment `DECLINE / HOLD / HOLD`, certified;
- zero unauthorized writes.

All three review turns report actual `deepseek-flash` / `deepseek` provenance.
This is a demonstrated core-release workflow, not universal reliability.
No deployment. Evidence: `ui_loop_final.json`, `pre_restart_final.json`,
`fresh_after_restart_ui.text`, `final_after_restart.png`, `db_check.json`,
`run_stdout.text`.
