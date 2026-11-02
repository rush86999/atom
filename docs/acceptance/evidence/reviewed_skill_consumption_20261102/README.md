# Reviewed-skill ordinary-work consumption — evidence

Status: **submitted for independent verification; not self-accepted.**

Test-only successor of the accepted prompt-skill lifecycle source
`c1074f0a9`. Product code is byte-identical; this bundle proves the accepted
skill is consumed by real ordinary-work prompt paths, not only the retrieval
service utility.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/brennan-full-app-20261102` |
| Executed source | `5538a654dd1660fb20c9882eed74e51c3fe7c0b0` |
| Product equivalence | zero diff from accepted `c1074f0a9` across backend/core, backend/api, frontend, scripts |
| Worktree | `/private/tmp/atom-consolidated-clean` |
| Tree at execution | clean |
| Added | `tests/test_reviewed_skill_agent_consumption.py` only |

## Consumption controls

| Control | Expected | Result |
|---|---|---|
| GenericAgent prompt | promoted prompt skill appears in `_retrieve_skill_instructions`; generated code absent | passed |
| GenericAgent workspace block | assigned skill name appears in `WORKSPACE-ASSIGNED SKILLS` | passed |
| New session | a fresh session still injects the skill | passed |
| Meta-agent prompt | `AtomMetaAgent._retrieve_skill_instructions` consumes the skill | passed |
| Workspace isolation | another workspace gets an empty block; the owning workspace still gets the skill | passed |

## Suites

| Suite | Command | Result | Log |
|---|---|---|---|
| Backend combined (31 files) | `TESTING=1 pytest <31 files> -q` | **491 passed** | `backend-tests.log` |
| Consumption controls | `pytest tests/test_reviewed_skill_agent_consumption.py -q` | **4 passed** | `consumption-controls.log` |
| Frontend canvas panels | `jest <3 canvas suites> --runInBand` | **7 passed** | `frontend-tests.log` |

## Scope

No live provider call, credential, spend, send or reseed. This is prompt
injection/retrieval consumption, not a claim of arbitrary behavior-quality
improvement, generated-code execution or a real-process restart campaign.
Historical 111/123 and prior accepted sources/tags are unchanged.
