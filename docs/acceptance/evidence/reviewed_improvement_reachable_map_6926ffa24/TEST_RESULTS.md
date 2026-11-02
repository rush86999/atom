# Reviewed improvement + reachable map — results

Executed source: `6926ffa24445...` (clean).

## Reviewed improvement controls

`reviewed-improvement.log` — **5 passed**:

| Control | Result |
|---|---|
| Pending candidate cannot be applied | refused; no `SkillExecution`, no package |
| Validation alone changes nothing | no registry row, no package, agent config unchanged |
| Explicit apply writes typed prompt skill | package + registry + `workspace_skills`; generated code absent |
| Ordinary retrieval consumes it | `SkillRetrievalService` sees the lesson; fresh session sees promoted candidate |
| Duplicate apply | idempotent, same skill id, one registry row |
| Viewer authority | 403; workspace admin apply succeeds |

`backend-tests.log` — **172 passed**, including the reviewed-improvement,
Memento, oracle/presentation, assignment, direct canvas family controls and
all original/frozen-request/presentation probes.

`frontend-tests.log` — **7 passed**.

## Reachable mutation map

`reachable_mutation_map/reachable_mutation_map.json`:

- 1,605 OpenAPI paths;
- 821 mutation-shaped mounted routes;
- 84 read-only-looking POSTs;
- 326 unknown-effect rows;
- 411 mutation-shaped rows;
- 693 bypass candidates;
- full row list with path, method, operation id, function, source file,
  family, effect and dispatch.

Dispatch counts: direct/unknown 530, direct provider 168, direct canvas 69,
shared action registry 25, assignment executor 16, direct goal 9, oracle
consumer 4.

Direct canvas family control: exact `PUT /api/canvas/{id}` material is
persisted in `Canvas.content` and exactly one new `CanvasAudit` row is
appended; existing IDOR/restore controls pass in the same run.

## Boundaries

No live provider action. The map is discovery evidence, not proof that all
821 routes are reachable or effectful. Whole-app ORACLE-01 remains open.
