# Substantive model-backed assessment — executed 2026-10-31

A real, model-backed assessment on six unfamiliar grant records under a taught
policy, with a policy correction and a fresh post-restart judgment. Every phase
dispatched to an actual served model and records its provenance.

This supersedes the earlier **blocked-external** status: the cloud keys are
still absent, but a readable local model store was found and served.

> **Judgment claims:** this run is the first pipeline demonstration on six
> records. The configuration's decision reliability is qualified separately on a
> frozen 24-record set in `../employee-execution-assessment-qualification/`:
> 17/18 determinate in every phase, with a stable error and one invented
> approval. Substantive recommendations from this configuration require human
> review.

## Model and world

| Item | Value |
|---|---|
| Served provider / model | `ollama` / `llama3.1:8b` |
| Model digest | `46e0c10c…` (Q4_K_M, 8.0B, 4.92 GB) |
| Runtime | separate `ollama serve` on `127.0.0.1:11435`, `OLLAMA_MODELS=~/.ollama/models-local`, CPU inference |
| Backend | `127.0.0.1:8071`, isolated world `assessment_campaign_20261031`, source `8d75173d2718` |
| Review config | `ATOM_REVIEW_MODEL=llama3.1:8b`, `ATOM_REVIEW_PROVIDER=ollama`, `ATOM_LOCAL_ONLY=true` |
| Cloud / connected systems | none used |

The packaged `Ollama.app` server on `:11434` returns HTTP 500 because it points
at an unmounted external volume. The readable store under
`~/.ollama/models-local` was verified with a direct `/api/chat` completion
before the campaign; `world-identity.json` records the exact identity.

## Records and policy

Six unfamiliar records (`A-201`…`A-206`; columns `Ref, Amount, Status, Risk,
Region`), bound into a fresh sheet canvas. The two records that isolate the
policy boundaries are:

- `A-204`: Amount **95**, Open, Risk Low → the `50-99` rule requires REVIEW.
- `A-205`: Amount **150**, Open, Risk **High**, North → the exception requires
  REVIEW under v1; removing the exception makes it APPROVE under v3.

The correction under test removes the `North + Risk High` exception
(`POLICY_V1` → `POLICY_V3`).

## Results

| Phase | Certification | Coverage | Provenance | Judgment |
|---|---|---|---|---|
| `create` (policy v1) | certified | 6/6 subjects, 0 unassessed | `ollama`/`llama3.1:8b` | **5/6 (0.8333)** |
| `correct` (policy v3) | certified | 6/6 subjects | `ollama`/`llama3.1:8b` | **6/6 (1.0)** |
| `after-restart` (policy v3) | certified | 6/6 subjects | `ollama`/`llama3.1:8b` | **6/6 (1.0)** |

System gates that passed at every phase: `success=true`, `certified=true`,
non-empty `served_provider`/`served_model`, exact subject coverage, and (for
`correct`) a changed `policy_revision`. Post-restart stability also held: the
served provider was unchanged, the request hash was identical
(`e3362adf…`), the decisions were identical, and the `execution_id` differed —
i.e. a genuinely new execution of the same inputs on a new backend process
(pid 93571 → 94951).

### The one judgment failure, stated plainly

`create` returned **APPROVE** for `A-204` (Amount **95**) and cited
`"Amount >= 100 and Risk Low"` as its basis. The row was rendered to the model
unambiguously as `Amount=95`, so this is a model reading error on the boundary
record, not a rendering or harness defect. Under the simpler corrected policy
the same model returned `A-204` = REVIEW and `A-205` = APPROVE, i.e. it tracked
both the removed exception and the amount band.

Consequence: the **pipeline** is verified end-to-end on a real model; the
**judgment quality** of `llama3.1:8b` on the more complex v1 policy is 5/6 and
is not sufficient to claim reliable boundary decisions. A stronger serving
model is required for that claim.

## Files

| File | Contents |
|---|---|
| `preflight.json` / `.log` | declared model/provider/key check — `ready` |
| `create-raw.json` | full `create` response (certification, route, assessments) |
| `correct-raw.json` | full `correct` response after the policy change |
| `after-restart-raw.json` | full post-restart response |
| `judgment-*.json` | expected vs actual decisions, mismatches, accuracy |
| `state.json` | canvas id, policy revisions, per-phase routes and judgments |
| `world-identity.json` | world/DB/pids, review configuration, model digest, runtime notes |
| `correct.log`, `after-restart.log` | harness stdout for those phases |

No credential, key or password appears in these files. `manifest.json` hashes
every entry.

## Reproduce

```bash
# 1. serve the readable local store on a separate port
OLLAMA_MODELS=~/.ollama/models-local OLLAMA_HOST=127.0.0.1:11435 ollama serve

# 2. launch the candidate in an isolated world with the review pin
WORLD=<worlds-root>/assessment_campaign_20261031 ADMIN_PASSWORD=<secret> \
  BACKEND_PORT=8071 FRONTEND_PORT=3130 \
  OLLAMA_BASE_URL=http://127.0.0.1:11435/v1 \
  ATOM_REVIEW_MODEL=llama3.1:8b ATOM_REVIEW_PROVIDER=ollama \
  bash scripts/acceptance/launch_integrated_local_candidate.sh

# 3. run the phases (restart the backend between correct and after-restart)
python scripts/acceptance/substantive_assessment_campaign.py --phase preflight --out-dir <out>
python scripts/acceptance/substantive_assessment_campaign.py --phase create \
  --frontend http://127.0.0.1:8071 --password-file <secret-file> --out-dir <out>
python scripts/acceptance/substantive_assessment_campaign.py --phase correct \
  --frontend http://127.0.0.1:8071 --password-file <secret-file> --out-dir <out> \
  --state <out>/state.json
python scripts/acceptance/substantive_assessment_campaign.py --phase after-restart \
  --frontend http://127.0.0.1:8071 --password-file <secret-file> --out-dir <out> \
  --state <out>/state.json
```

Without `--continue-on-judgment-mismatch` the harness stops at the first
decision mismatch (strict mode); the flags used here record accuracy and keep
the system gates hard.
