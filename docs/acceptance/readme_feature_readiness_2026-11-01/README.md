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
- Final evidence commit: `dce03d804` (docs/evidence only).
- Frontend production build: clean checkout at `a0fce85b0` (frontend files
  unchanged through the final commit), `BUILD_ID` `gVUTIhFCOe-IPrxsvBkAG`.
- Clean install: fresh worktree, own `backend/venv` and `node_modules`,
  `make setup`, empty data root, generated `.env`, documented uvicorn bootstrap,
  real restart.

## Measure the manifest

Every manifest entry is tracked in Git (force-added where the repository's
global `*.log`/`*.txt` ignore rules would otherwise hide evidence). Verify from
the committed tree, not the working directory:

```bash
python - <<'PY'
import hashlib, json, subprocess
root = 'docs/acceptance/readme_feature_readiness_2026-11-01'
manifest = subprocess.check_output(
    ['git', 'show', f'HEAD:{root}/MANIFEST.json'], text=True)
m = json.loads(manifest)
missing, bad = [], []
for name, meta in m['files'].items():
    path = f'{root}/{name}'
    if subprocess.run(['git', 'ls-files', '--error-unmatch', '--', path],
                      capture_output=True).returncode != 0:
        missing.append(name)
        continue
    blob = subprocess.check_output(['git', 'show', f'HEAD:{path}'])
    if hashlib.sha256(blob).hexdigest() != meta['sha256'] or len(blob) != meta['bytes']:
        bad.append(name)
print('entries', len(m['files']), 'untracked', missing, 'mismatches', bad)
PY
```
