# README feature-readiness — corrected 2026-10-31

Frozen-denominator coverage of the README-marketed functional surface, built
from the accepted `local-core-2026-10-30-final` checkpoint and corrected after
the verifier's first review.

| Artifact | Purpose |
|---|---|
| [`COVERAGE_REPORT_2026-10-31.md`](COVERAGE_REPORT_2026-10-31.md) | Corrected result, verifier findings, category breakdown, gaps, fixes, manifest |
| [`CLAIM_INVENTORY.md`](CLAIM_INVENTORY.md) | Human-readable claim matrix with corrected status and evidence |
| [`CLAIM_INVENTORY.json`](CLAIM_INVENTORY.json) | Machine-readable frozen denominator (123 eligible functional) |
| [`VERIFIER_REVIEW_REQUEST.md`](VERIFIER_REVIEW_REQUEST.md) | Correction summary and decision requested |
| [`NEXT_CLAIM_BATCHES_2026-10-31.md`](NEXT_CLAIM_BATCHES_2026-10-31.md) | Executed 17-claim wave plan; final outcome appended |
| [`evidence/CLAIM_AUDIT_2026-10-31.json`](evidence/CLAIM_AUDIT_2026-10-31.json) | Per-claim downgrade reasons |
| [`evidence/MANIFEST.md`](evidence/MANIFEST.md) | Final sha256 manifest, hash history, superseded artifacts |
| [`evidence/CLAIM_AUDIT_2026-10-31_final.json`](evidence/CLAIM_AUDIT_2026-10-31_final.json) | Five remaining final-audit downgrades |

**Integrated self-assessed result: 99 / 123 eligible functional claims
verified (80.5%).** Security is 8/8 separately. Twenty-four functional claims
remain partial/unverified/blocked/environment-limited or inaccurate and are
**not** counted. The denominator did not change. The broad campaign ran 130
claims with 0 failed and 0 group errors; GOAL-01 is now counted after its
status and downstream success semantics were integrated. Independent verifier
review is still required; no deployment or publication was performed. The 17-claim wave plan in `NEXT_CLAIM_BATCHES_2026-10-31.md` was executed to
this result (ASK-03, ROUTE-03 and GRAPH-05 were left partial rather than
counted; GOAL-01 and INT-05 are counted instead).

Harness: `backend/scripts/readme_acceptance/` (isolated marked worlds, bounded
local OpenAI/Anthropic/OAuth/MCP stub, no cloud credentials). Install/restart:
`scripts/acceptance/readme_local_install.py`. Inventory/merge/audit:
`scripts/acceptance/readme_claim_inventory.py`,
`scripts/acceptance/merge_readme_results.py`,
`scripts/acceptance/apply_readme_audit.py`.
