# Reviewed improvement lifecycle — explicit typed application and consumption

Status: **submitted for independent verification; no claim verdict changed.**

Continues the canonical Memento lifecycle past "validated": review is separate
from permission to apply, application is an explicit authorized step, and
ordinary work retrieval consumes the applied skill across a restart.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/brennan-full-app-20261102` |
| Executed source | `94c7eaa9d55318b71a6b872bcbe8efdfcaf8d90c` |
| Tree at execution | clean (`0 modified, 0 untracked` in the isolated worktree) |
| Worktree used | `/private/tmp/atom-consolidated-clean` |
| Applied source files | `core/reviewed_improvement.py`, `api/autodev_review_routes.py`, `tests/test_reviewed_improvement_apply.py` |

## Lifecycle now enforced

- **pending** — applying is refused (`409 candidate_not_reviewed`). No package,
  registry row, skill assignment or agent change.
- **validate/approve** — marks the candidate validated. Nothing is written;
  the agent configuration is untouched.
- **apply** — `POST /api/autodev/skills/{id}/apply`, TEAM_LEAD+ authority,
  validated candidates only. Writes a **prompt-only** `SKILL.md` package
  (metadata + instructions, `scripts={}`), imports and activates it in the
  canonical skill registry, mirrors it into `skills` + `workspace_skills`, and
  marks the candidate `promoted` with the applied skill id.
- **generated code** — deliberately never written, imported or executed by
  this path. The candidate's code stays reviewable; applying executable code
  would need a separate explicit code-modification authority.
- **duplicate apply** — idempotent: returns `already_applied=true` with the
  same skill id, no second package/execution.
- **ordinary work** — `SkillRetrievalService.retrieve_top_skills` returns the
  Active, workspace-assigned skill; a new session after application still
  retrieves it.

## Controls on this source

| Control | Result |
|---|---|
| Pending candidate refused; no package/registry/agent change | passed |
| Validation alone changes nothing | passed |
| Apply writes prompt-only package; no `.py`; registry Active; workspace assigned | passed |
| Ordinary retrieval consumes the skill; new session/restart still consumes it | passed |
| Duplicate apply idempotent (one registry execution) | passed |
| Viewer apply 403; TEAM_LEAD/workspace_admin apply succeeds | passed |
| Agent configuration unchanged by approve/apply | passed |

Logs: `lifecycle-neighborhood.log` (5 new controls + 67 adjacent
auto-dev/skill/evolution tests, 72 passed / 28 skipped), `backend-tests.log`
(475 passed combined), `frontend-tests.log` (7 passed).

## Local model probe (planning/goal claims)

`OLLAMA_MODELS=/Volumes/Seagate Portable Drive/ollama/models`.
`GET http://127.0.0.1:11434/api/tags` returns:

```
{"error":"mkdir /Volumes/Seagate Portable Drive: permission denied: ensure path elements are traversable"}
```

The volume is not mounted (`ls` → No such file or directory; no Seagate mount).
No model call was attempted; no live provider is authorized. Planning/goal
discretionary judgment remains **unqualified**, not newly claimed.

## Open

Local-model planning/goal qualification (model store unavailable); whole-app
HTTP/provider oracle coverage; TEAM-05 real sweep; MINI Linux/KVM; INT/ROUTE
live authorization. No live action, credential, spend or reseed. Historical
111/123 and the 123-claim denominator are unchanged.
