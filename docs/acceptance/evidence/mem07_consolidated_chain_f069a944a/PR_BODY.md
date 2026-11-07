# MEM-07: consolidated tool-error -> reviewed prompt-skill chain

## Summary

Adds one consolidated MEM-07 control proving the current accepted mechanism
already connects:

real tool-error signal -> canonical pending Memento candidate -> normal
authenticated Auto-Dev review -> existing typed-prompt apply -> fresh-session
ordinary-work consumption.

No product/runtime change was needed. Pending/rejected/changed-material
candidates cannot apply; repeat apply is idempotent; generated code is never
promoted; agent configuration is unchanged.

## Verification

- Focused affected set: 55 passed, exit 0.
- Only the Memento model transport is doubled with labeled controlled text.
- Fresh scratch SQLite/data/LANCE/output/basetemp; no live model/provider/
  network/sandbox/account/credential/spend/send/install/deploy.

## Evidence

`docs/acceptance/evidence/mem07_consolidated_chain_f069a944a/` with standard
`evidence_git_check` manifest, source file hash, logs, exit JSON and JUnit XML.

Root owns independent acceptance/merge.
