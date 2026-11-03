# Reviewed-improvement boundary repair + local model availability

Status: **submitted for independent verification; not self-accepted.**

This successor source repairs the five withheld reviewed-improvement boundary
findings on `6926ffa24` and records the local `llama3.1:8b` availability probe.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/brennan-full-app-20261102` |
| Worktree | `/private/tmp/atom-full-app` |
| Executed source | `52549c51a217b2cdc7200ca64f96389b83dcfb05` |
| Tree at execution | clean |
| Runtime identity | `source_id=52549c51a217` |
| Map API | `http://127.0.0.1:8100` (`/api/v1/openapi.json`) |
| Local model port | `127.0.0.1:11435` (separate; owner `11434` untouched) |
| Transport | controlled local service/DB; no live provider |

## Five boundary repairs

1. **Viewer approval** — approve/reject/apply now require team-lead authority
   on the actual routes. A viewer gets 403 and the candidate stays pending.
2. **Moved employee** — the candidate's CURRENT employee is re-authorized
   before any mutation. A TEAM_LEAD whose employee moved to another workspace
   gets 403; the service is not called and the target workspace is not used as
   the reviewer's authority. ADMIN+ cross-tenant-workspace review is an
   explicit separate policy.
3. **Failed apply atomicity** — registry import/promote use caller-owned
   transactions. Prompt package, `Skill`, `SkillExecution`, `workspace_skills`
   and candidate promotion commit together; a failure rolls back, leaves no
   Active registry row, and removes only the newly created package.
4. **Stale-session idempotency** — apply ends the stale read snapshot, reloads
   the authoritative candidate, claims only the validated revision with a
   conditional update, and returns the original applied skill id if another
   session already promoted it. One package, one execution, one skill id.
5. **Changed material** — review stores an exact material+scope digest
   (name, description, failure pattern, source episode, target employee,
   tenant, workspace, generated-code digest). Apply recomputes and requires the
   same digest; changed instructions/name/target/source require fresh review.

The five independent boundary probes now pass, along with positive apply,
ordinary-work retrieval in a fresh session, idempotent duplicate apply, and
viewer refusal.

## Local model availability

The configured `11434` service was left untouched. A separate Ollama server was
started on `127.0.0.1:11435` with:

```text
OLLAMA_HOST=127.0.0.1:11435
OLLAMA_MODELS=/Users/rushiparikh/.ollama/models-local
```

`local-model-tags.json` shows `llama3.1:8b` (4,920,753,328 bytes, Q4_K_M).
The existing cheap pin probe (`scripts/acceptance/probe_ollama_pin.py`) passed:
resolved pin `ollama/llama3.1:8b`, served provider `ollama`, served model
`llama3.1:8b`, structured decision returned. This is **availability evidence
only**, not planning/model-quality qualification. The failed discretionary-
judgment verdict is preserved; no planning campaign is claimed here.

## Reachable mutation map

Active core profile: **1,605 OpenAPI paths**, **821 mutation-shaped mounted
routes**, **693 bypass candidates**. Full rows are in
`reachable_mutation_map/reachable_mutation_map.json`. Direct canvas HTTP family
control verifies exact persisted material and one appended audit row.

## Tests

| Scope | Result |
|---|---|
| Reviewed improvement positive suite | **5 passed** |
| Five independent boundary probes | **5 passed** |
| Combined backend neighborhood | **158 passed** |
| Frontend canvas panels | **7 passed** |

## Boundaries

No live provider lookup, refresh, write, send, credential, consent or spend.
No whole-app ORACLE-01, planning-quality, soak, multi-worker or live-provider
claim. Historical 111/123 and accepted tags unchanged.
