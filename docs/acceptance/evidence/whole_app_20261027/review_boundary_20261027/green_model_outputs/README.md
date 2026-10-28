# Green run transport captures

These are the review-generation inputs, outputs and runtime logs from the
green run recorded by `../run_summary_20261027.json` (execution IDs
`4c5249c6…`, `afaa8ef3…`, `bfd45765…`).

The run's raw API response files (`baseline.json`, `unfamiliar.json`,
`after_restart.json`) were later overwritten by the separate diagnostic probe
preserved in `../probe_20261027/`. These transport captures and the
authoritative `run_summary` are what remains of the green run. They are not a
substitute for the overwritten API bodies and are not counted as new runs.

- `baseline_*` — original policy, `CX-9101 REJECT`, `CX-9102 REVIEW`,
  `CX-9103 APPROVE`.
- `unfamiliar_*` — after the in-place correction, `CX-9201 REJECT`,
  `CX-9202 REVIEW`, `CX-9203 REVIEW`.
- `after_restart_*` — same unfamiliar fixture after the real backend restart,
  same corrected decisions.
- `run_stdout.text`, `after_restart_server.text` — process output from the run;
  the server log covers the post-restart process only.

Source identity for this run is in `../source_manifest_20261027.json` and
`../source_state_at_run.patch`; it is explicitly a dirty-tree snapshot at
`f8792bf42bf0`, not the later freeze commit.
