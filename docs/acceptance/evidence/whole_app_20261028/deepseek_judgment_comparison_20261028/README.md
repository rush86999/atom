# DeepSeek judgment comparison — executed once, passed screening

Status: **pass (diagnostic screening)**. The owner authorized one isolated
exception to local-only operation. Seven fixed cases were sent once each to
`deepseek/deepseek-v4-pro`; no semantic or transport retries were made. The
application's local-only default, provider policy, stored credentials and the
pilot remain unchanged. This is a diagnostic direct-endpoint comparison, not
application acceptance evidence.

## Result

| Case | Expected | Raw decision | Substantive | Certified |
|---|---|---:|---:|---:|
| Preserved full context | DECLINE / HOLD / HOLD | DECLINE / HOLD / HOLD | yes | yes |
| Preserved 3200 | DECLINE | DECLINE | yes | yes |
| Unfamiliar 4321.25 | DECLINE | DECLINE | yes | yes |
| Boundary 4999.99 | DECLINE | DECLINE | yes | yes |
| Boundary 5000 | HOLD | HOLD | yes | yes |
| Boundary 9999 | HOLD | HOLD | yes | yes |
| Boundary 10000 | HOLD | HOLD | yes | yes |

- route/transport success: **7/7**
- parseable output: **7/7**
- substantive correctness: **7/7**
- reference validity: **6/7 initial, 7/7 after offline revalidation**
- latency: **3.5–21.5 s** per case, average **6.5 s**
- usage: **8,900 input + 3,529 output = 12,429 tokens**
- estimated cost: **$0.028** at conservative catalog rates
- retries: **0 semantic, 0 transport**

The initial 6/7 reference result was a harness bug: the full-context validator
was given only `IN-7301` instead of the accepted three subjects, so the correct
`IN-7302` and `IN-7303` assessments were reported as `unrequested_subject`.
`revalidated_results.json` re-runs the same saved response through the product
validator with the accepted subject set and gets `ok=true`, no errors. No model
call and no decision rewrite occurred.

Screening manifest: `SCREENING_MANIFEST.json`.

## Frozen comparison

`SPEC.json` fixes:

- the exact preserved full-context request (14 messages);
- the same six complete minimal cases used in the local diagnosis;
- policy `044d2b537b4d4a2593dbaca52c64b8da`, its verbatim lesson, the
  `FUND/HOLD/DECLINE` vocabulary and the same review output contract;
- expected decisions from that lesson's own thresholds, with no label ranking;
- provider `deepseek` direct (`https://api.deepseek.com/v1`), model
  `deepseek-v4-pro`;
- temperature `0.7`, `max_tokens=6000`, non-streaming, 300 s request timeout;
- **one attempt per case**, zero semantic retries, zero transport retries;
- no prompt or setting changes mid-run.

`PREPARED_REQUESTS.json` records the SHA-256 of every frozen request. The
full-context request is the essential case: it is the one where a wrong
`HOLD` previously passed structural certification.

## Credential

The failed UI world's BYOK store contains only Ollama. The existing active
DeepSeek credential is in the main app's encrypted store and the harness reads
it **read-only**:

- key id `tenant_default_deepseek_default_production`
- key hash `cc1d28eb8b34001a845fbf176096e4124985bca4763ce44953fbe712727f32ee`
- provider catalog reports `deepseek` served `[deepseek-flash,
  deepseek-v4-pro]`, `auth_ok=true`

A presence-only check succeeded with `credential_present=true`,
`decrypted=false`, `external_call_made=false`. The key value is never written
to output, the repository or the app configuration.

The `DEEPSEEK_API_KEY` line in the repo env file is empty; the encrypted store
is the existing authorized credential source.

## Authorization gate

The harness refuses even to read/decrypt the credential unless both gates are
present:

```bash
ATOM_AUTHORIZE_DEEPSEEK_COMPARISON_20261028=1 \
python backend/scripts/orchestration_acceptance/compare_deepseek_judgment.py \
  --out-dir docs/acceptance/evidence/whole_app_20261028/deepseek_judgment_comparison_20261028 \
  --byok-store /Users/rushiparikh/projects/atom/backend/data/byok_keys.json \
  --byok-key-file /Users/rushiparikh/projects/atom/backend/data/byok_encryption_key \
  --authorize-deepseek-exception
```

This is the command that was run after the owner authorized the one
comparison. The script refuses to overwrite an existing `results.json` and
still requires both gates for any future run.

## Outputs after an authorized run

- `results.json` — provider/model identity, effective settings, authorization
  scope, request hashes, per-case latency, token usage, HTTP status and
  transport-retry count;
- `cases/<case>_request.json`, `_response.json`, `_review.json` — exact
  request, raw response and validator errors;
- `analysis.json` — raw judgment correctness and product-format/reference
  validity recorded separately:

```bash
python backend/scripts/orchestration_acceptance/analyze_minimal_judgment.py \
  docs/acceptance/evidence/whole_app_20261028/deepseek_judgment_comparison_20261028
```

## Decision rules after the comparison

- **Substantive mistake** — preserve it and report the limitation. Do not
  launch a UI campaign and do not tune against the failed answers.
- **Correct judgments, failed output/reference compliance** — diagnose that
  specific contract boundary.
- **All judgments and certification checks pass** — declare the candidate's
  intended AI configuration explicitly, then verify that configuration through
  the real scoped product route.
- Only after product-route verification: run the unchanged core UI loop once
  on a clean frozen candidate (calculation, correction, unfamiliar work, fresh
  assessment after restart).

A seven-case pass is a screening result, not a general reliability guarantee.
Launch claims remain limited to the demonstrated workflows. No deployment is
authorized.
