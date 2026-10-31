# README feature-readiness — 2026-10-31

Frozen-denominator coverage of the README-marketed functional surface, built
from the accepted `local-core-2026-10-30-final` checkpoint.

| Artifact | Purpose |
|---|---|
| [`COVERAGE_REPORT_2026-10-31.md`](COVERAGE_REPORT_2026-10-31.md) | Result, method, category breakdown, gaps, fixes, evidence manifest |
| [`CLAIM_INVENTORY.md`](CLAIM_INVENTORY.md) | Human-readable claim matrix with status and evidence |
| [`CLAIM_INVENTORY.json`](CLAIM_INVENTORY.json) | Machine-readable frozen denominator |
| [`VERIFIER_REVIEW_REQUEST.md`](VERIFIER_REVIEW_REQUEST.md) | Questions and decision requested from the independent verifier |
| [`evidence/`](evidence/) | Merged results and per-world evidence with sha256 hashes |

**Self-assessed result: 100 / 123 eligible functional claims verified (81.3%).**
Security is 8/8 separately. Twenty-three functional claims remain
partial/unverified/blocked/environment-limited or inaccurate and are **not**
counted. The figure is not declared accepted until the independent verifier
responds; no deployment or publication was performed.

Harness: `backend/scripts/readme_acceptance/` (isolated worlds, bounded local
OpenAI/Anthropic/OAuth/MCP stub, no cloud credentials). Install/restart:
`scripts/acceptance/readme_local_install.py`. Inventory/merge:
`scripts/acceptance/readme_claim_inventory.py` and
`scripts/acceptance/merge_readme_results.py`.
