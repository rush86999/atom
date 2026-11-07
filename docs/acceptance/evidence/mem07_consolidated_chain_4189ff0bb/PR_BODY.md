# MEM-07: natural emitted event + authenticated review/apply chain

## Summary

Upgrades the MEM-07 consolidated control to the real boundaries root requested:

- real failing-tool signal -> real `EpisodeService` emitted failure event ->
  registered `ReflectionEngine` consumer in fresh sessions -> pending Memento
  candidate (no manual `EpisodeSegment`, `TaskEvent`, or `process_failure`);
- actual mounted Auto-Dev HTTP router with real JWT/user/tenant/workspace
  authority (no current_user/tenant overrides; only scratch DB dependency);
- existing typed-prompt apply -> fresh-session ordinary-work prompt consumption.

## Twins

Pending/rejected/changed-code candidates cannot apply; repeat apply is
idempotent; generated code is never promoted; agent config is unchanged;
fresh-session consumption sees the exact reviewed description. Normal auth
guards: 401 without token, 403 for a real viewer JWT, 200 for workspace admin.

## Verification

- Focused affected set: 56 passed, exit 0.
- Only the controlled Memento model leaf and synthetic failing tool are seams.
- Fresh scratch SQLite/data/LANCE/output/basetemp; no live model/provider/
  network/sandbox/account/credential/spend/send/install/deploy.
- No runtime fix needed.

## Provenance

Executed merged source `4189ff0bb`; test successor `fe07b615b`; prior packet
`cb81bd4ca` preserved. Standard `evidence_git_check` manifest hashes all
relevant production consumer files plus the test.

Root owns independent acceptance/merge.
