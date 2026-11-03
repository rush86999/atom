# Reviewed improvement lifecycle — test results

## Lifecycle controls (5 new)

| # | Control | Expected | Actual | Result |
|---|---|---|---|---|
| 1 | Apply a pending candidate | refused `candidate_not_reviewed`; no package/registry row | ValueError raised; zero SkillExecution rows; no SKILL.md | PASS |
| 2 | Validation alone | candidate validated; nothing written; agent config unchanged | no package/registry row; config `{system_prompt: original}` | PASS |
| 3 | Apply a validated candidate | prompt-only package, registry Active, workspace assigned, candidate promoted | SKILL.md with instructions, no `.py`; retrieval returns the skill | PASS |
| 4 | Ordinary work after restart | new session retrieves the promoted skill | new session sees promoted candidate and retrieval output | PASS |
| 5 | Duplicate apply | idempotent; same skill id; one execution | `already_applied=true`; one SkillExecution | PASS |
| 6 | Reviewer authority | viewer 403; workspace_admin 200 | 403 / 200 with promoted status | PASS |
| 7 | Generated code | never applied | no `.py` in package; candidate code only in the candidate | PASS |

## Suites

| Suite | Command | Result | Log |
|---|---|---|---|
| Backend combined (29 files) | `TESTING=1 pytest <29 files> -q` | **475 passed** | `backend-tests.log` |
| Auto-dev/skill/evolution neighborhood | `pytest <8 files> -q` | **72 passed, 28 skipped** | `lifecycle-neighborhood.log` |
| Frontend canvas panels | `jest <3 canvas suites> --runInBand` | **7 passed** | `frontend-tests.log` |

## Local model probe

`OLLAMA_MODELS=/Volumes/Seagate Portable Drive/ollama/models`; the volume is
not mounted and `/api/tags` returns the exact `mkdir ... permission denied`
error. No model call was attempted. Planning/goal judgment remains
unqualified. Raw probe: `local-model-probe.log`.
