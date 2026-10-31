# SUPERSEDED as a status — cloud blocker record

This directory records the **failed-closed cloud attempts** of 2026-10-31 and
remains accurate about them: `DEEPSEEK_API_KEY` is empty, OpenRouter returned
HTTP 402 "requires more credits", and the packaged Ollama server's model store
was unreadable.

It is **no longer the current assessment status**. A readable local model store
was found at `~/.ollama/models-local`, served separately, and the full campaign
then ran with real `served_provider`/`served_model` provenance:
`../employee-execution-substantive-assessment/`.

The campaign harness described below is the one that ran; its preflight is
`ready` for the local model, not blocked.

---

# Substantive assessment — external blocker

The grant journey's calculation is valid cross-schema evidence, but it is not a
discretionary assessment. A current, model-backed assessment was attempted on
an unfamiliar six-record grant dataset with a declared policy, decision labels,
source snapshot and row evidence.

The assessment could not be completed because no usable model infrastructure is
available on this host:

1. **DeepSeek direct** — the env file contains `DEEPSEEK_API_KEY` but its value
   is empty; no deepseek client was built (`pin_unavailable`).
2. **OpenRouter / `deepseek/deepseek-v4-pro`** — the scoped pin resolved and the
   dispatch was attempted, but OpenRouter returned HTTP 402 "requires more
   credits" for the 6000-token review request; fallback models also returned
   402. The assessment failed closed with `empty_payload`.
3. **Local Ollama** — model storage is on an unreadable/unmounted external
   volume; `/api/tags` returns a permission error.

This is recorded as an **external blocker**, not completed coverage. The
smallest required input is a funded provider key with a declared review model,
or a readable local Ollama model store. No assessment-quality claim is made
until that input exists.

Preserved artifacts: `assess-failed-openrouter.json` (full failed-closed
response), `openrouter-402-sanitized.log` (provider errors with user/org IDs
redacted), and `blocker.json` (configuration attempts, dataset hash, policy and
expected decision schema).

## Prepared campaign (blocked at preflight)

`scripts/acceptance/substantive_assessment_campaign.py` is the executable
campaign for the day a usable model exists. Phases:

```bash
# 1. declared model/key preflight
python scripts/acceptance/substantive_assessment_campaign.py \
  --phase preflight --out-dir <evidence>

# 2. create canvas + bind unfamiliar records + assess policy v1
python scripts/acceptance/substantive_assessment_campaign.py \
  --phase create --frontend http://127.0.0.1:3130 \
  --password-file <password> --out-dir <evidence>

# 3. correct the policy (remove the North/High exception) and re-assess
python scripts/acceptance/substantive_assessment_campaign.py \
  --phase correct --frontend http://127.0.0.1:3130 \
  --password-file <password> --out-dir <evidence> --state <evidence>/state.json

# 4. restart the backend against the same world, then:
python scripts/acceptance/substantive_assessment_campaign.py \
  --phase after-restart --frontend http://127.0.0.1:3130 \
  --password-file <password> --out-dir <evidence> --state <evidence>/state.json
```

The campaign requires a certified assessment with real
`served_provider`/`served_model` provenance, exact expected decisions, a
changed policy revision after correction, and the corrected judgment after a
real restart. `campaign-preflight.json` records the current blocker: no
`ATOM_REVIEW_MODEL`/`ATOM_REVIEW_PROVIDER` is configured.
