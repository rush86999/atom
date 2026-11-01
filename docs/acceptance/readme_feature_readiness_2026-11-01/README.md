# Integrated local candidate — 2026-11-01

Self-assessed breadth: **111/123 = 90.2%** frozen functional claims, plus the
practical local-employee gates. Independent verification remains the acceptance
authority.

| Artifact | Purpose |
|---|---|
| [`COVERAGE_REPORT_2026-11-01.md`](COVERAGE_REPORT_2026-11-01.md) | Result, 12-claim batch, failure-class coverage, campaigns, preserved limitations |
| [`CLAIM_INVENTORY.json`](CLAIM_INVENTORY.json) | Frozen 123-claim denominator and statuses |
| [`VERIFIER_REVIEW_REQUEST.md`](VERIFIER_REVIEW_REQUEST.md) | Three grouped verifier submissions |
| [`evidence/claims/INDEX.json`](evidence/claims/INDEX.json) | Claim → evidence → command → result |
| [`evidence/claims/`](evidence/claims/) | Runtime, product, install, OIDC, routing, graph and first-use evidence |
| [`evidence/campaigns/`](evidence/campaigns/) | Two-hour recovery, recovery browser, two-domain teaching |
| [`MANIFEST.json`](MANIFEST.json) | SHA-256 and byte count for every file in this directory |

## Source identity

- Runtime code: `a0fce85b0` (product tree unchanged from `8e999ab32` for the
  teaching runs; backend changes since the 99-claim baseline are the runtime
  enforcement, budget/wait accounting and first-use scoping commits).
- Final evidence commit: `95614234f` (docs/evidence only).
- Frontend production build: clean checkout at `a0fce85b0` (frontend files
  unchanged through the final commit), `BUILD_ID` `gVUTIhFCOe-IPrxsvBkAG`.
- Clean install: fresh worktree, own `backend/venv` and `node_modules`,
  `make setup`, empty data root, generated `.env`, documented uvicorn bootstrap,
  real restart.

## Measure the manifest

```bash
python - <<'PY'
import hashlib, json, os
root = 'docs/acceptance/readme_feature_readiness_2026-11-01'
m = json.load(open(os.path.join(root, 'MANIFEST.json')))
bad = []
for name, meta in m['files'].items():
    data = open(os.path.join(root, name), 'rb').read()
    if hashlib.sha256(data).hexdigest() != meta['sha256'] or len(data) != meta['bytes']:
        bad.append(name)
print('entries', len(m['files']), 'mismatches', bad)
PY
```
