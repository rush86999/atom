# Reviewed-improvement boundary repair — results

Executed source: `52549c51a217b2cdc7200ca64f96389b83dcfb05` (clean).

## Five withheld probes

`boundary-controls.log` — **5 passed**:

| Control | Result |
|---|---|
| Viewer approves pending candidate | 403; candidate remains pending |
| TEAM_LEAD applies employee moved to another workspace | 403; service not called |
| Injected failure at `workspace_skills` insert | rollback; no Active `SkillExecution`; package removed |
| Session B stale candidate after session A apply | returns A's skill id; one execution |
| Candidate material changed after review | ValueError fresh re-review; no activation |

`reviewed-improvement.log` — **5 passed**: pending refusal, validation alone
changes nothing, typed prompt apply, ordinary retrieval + fresh session,
idempotent duplicate, viewer refusal.

`backend-tests.log` — **158 passed** across reviewed-improvement, Memento, the
five boundary probes, oracle/presentation, assignment, direct canvas route
families and all frozen-request/readback probes.

`frontend-tests.log` — **7 passed**.

## Local model

`local-model-tags.json`: `llama3.1:8b`, size 4,920,753,328 bytes, Q4_K_M.
`local-model-pin-probe.log`: pin `ollama/llama3.1:8b`; served provider
`ollama`; served model `llama3.1:8b`; structured payload
`{"assessments":[{"subject":"Ref A-1","decision":"APPROVE"}]}`; status
`passed`. Separate server at `127.0.0.1:11435`; owner `11434` untouched.

This is availability evidence, not a planning-quality claim. The failed
discretionary-judgment verdict remains.

## Reachable map

`reachable_mutation_map/reachable_mutation_map.json`: 1,605 paths, 821
mutation-shaped mounted routes, 693 bypass candidates. Dispatch:
direct/unknown 530, direct provider 168, direct canvas 69, shared action
registry 25, assignment executor 16, direct goal 9, oracle consumer 4.
Complete row list is tracked.

## Boundaries

No live provider action. Map is discovery evidence, not runtime coverage.
Whole-app ORACLE-01 remains open.
