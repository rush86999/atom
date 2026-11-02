# Reviewed improvement consumption + reachable mutation map

Status: **submitted for independent verification; not self-accepted.**

This successor source continues from the accepted presentation-binding source
`0d8767e3a`. It adds the reviewed-improvement apply/consumption lifecycle and a
reachable mutation/dispatch map for the active core profile.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/brennan-full-app-20261102` |
| Worktree | `/private/tmp/atom-full-app` |
| Executed source | `6926ffa24445...` |
| Related product commit | `94c7eaa9d` (reviewed candidate apply) |
| Tree at execution | clean |
| Runtime identity | `source_id=6926ffa24445` |
| Map API | `http://127.0.0.1:8100` (`/api/v1/openapi.json`) |
| Transport | controlled local service/database; no live provider |

## Reviewed improvement lifecycle

The canonical Memento path is preserved:

1. real tool failure → execution signal → episode → ReflectionEngine/Memento →
   pending `SkillCandidate`;
2. authenticated reviewer approves pending → `validated` (no code/config
   change);
3. explicit `POST /api/autodev/skills/{id}/apply` requires team-lead authority
   and applies only a **typed prompt skill**; generated executable code is not
   written, imported or run;
4. the typed skill is written as a package, registered in the canonical skill
   registry, mirrored into `Skill`/`workspace_skills`, and the candidate is
   marked `promoted`;
5. ordinary work retrieval (`SkillRetrievalService`) sees the prompt lesson in
   a fresh session; agent configuration is unchanged; duplicate apply is
   idempotent; pending candidates and viewers are refused.

The controls prove pending ≠ permission, validation alone changes nothing, and
promotion consumes code only through the explicit typed-skill path.

## Reachable mutation map

The active core profile OpenAPI document exposes **1,605 paths** and **821
mutation-shaped mounted routes**. The map records all rows (not a sample) with
family, effect shape, source file/function and dispatch classification:

| Dispatch | Count |
|---|---:|
| direct or unknown | 530 |
| direct provider service | 168 |
| direct canvas service | 69 |
| shared action registry | 25 |
| assignment executor | 16 |
| direct goal service | 9 |
| oracle consumer | 4 |

**693** rows are bypass candidates (mutation-shaped but direct-service/unknown).
This is a discovery/dispatch map, not runtime coverage proof; the complete row
list is in `reachable_mutation_map/reachable_mutation_map.json`.

A direct canvas HTTP family control now verifies that `PUT /api/canvas/{id}`
persists the exact material in the canvas mirror and appends exactly one audit
row, complementing existing IDOR/restore controls.

## Tests

| Scope | Result |
|---|---|
| Reviewed improvement + Memento + oracle/presentation + assignment + canvas families + probes | **172 passed** |
| Frontend canvas panels | **7 passed** |

## Boundaries

No live provider lookup, refresh, write, send, credential, consent or spend.
The map counts declarations/routes, not proven reachable effects. Whole-app
ORACLE-01 remains open. Historical 111/123 and accepted sources/tags unchanged.
