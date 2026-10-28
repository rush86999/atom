# Diagnostic probe — not the green acceptance run

These three files are a later bounded probe of the same fixture, not the
green run recorded by `../run_summary_20261027.json`.

They are preserved because they show the local model's **format instability**
and because the probe's failing post-restart reply is useful evidence:

- `baseline.json` — certified, but with wrong substantive labels
  (`REVIEW/APPROVE/APPROVE` where the original policy requires
  `REJECT/REVIEW/APPROVE`).
- `unfamiliar.json` — certified after the in-place correction, with the
  correct labels (`REJECT/REVIEW/REVIEW`).
- `after_restart.json` — no parseable block after a real restart; safely
  refused with `missing_structured_review` and missing decisions.

Do not count these as a pass. The authoritative green run is
`../run_summary_20261027.json`, whose raw response files were overwritten by
this later probe. See `docs/acceptance/REVIEW_BOUNDARY_2026-10-27.md`.
