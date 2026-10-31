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
| [`evidence/CLAIM_AUDIT_2026-10-31.json`](evidence/CLAIM_AUDIT_2026-10-31.json) | Per-claim downgrade reasons |
| [`evidence/MANIFEST.md`](evidence/MANIFEST.md) | Final sha256 manifest, hash history, superseded artifacts |

**Corrected self-assessed result: 83 / 123 eligible functional claims verified
(67.5%).** Security is 8/8 separately. Forty functional claims remain
partial/unverified/blocked/environment-limited or inaccurate and are **not**
counted. This replaces the earlier 100/123 figure; the denominator did not
change. Independent verifier review is still required; no deployment or
publication was performed.

Harness: `backend/scripts/readme_acceptance/` (isolated marked worlds, bounded
local OpenAI/Anthropic/OAuth/MCP stub, no cloud credentials). Install/restart:
`scripts/acceptance/readme_local_install.py`. Inventory/merge/audit:
`scripts/acceptance/readme_claim_inventory.py`,
`scripts/acceptance/merge_readme_results.py`,
`scripts/acceptance/apply_readme_audit.py`.
