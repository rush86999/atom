# Accepted-information authority: personal empty scope and missing actor

Executed source: `7a7092aaa88cf56effdb548c9e0697a096a6d5ed` on
`codex/generic-recovery-authority-20261107` (base `c17e50b2a`, which remains
preserved as the rejected predecessor packet). The new failure-first twins and
the existing native authority controls report **99 passed**, actual exit0. The
real-process restart consumer reports **6 passed**, actual exit0.

This packet does not relabel or replace the `5dfb58a85`/`c17e50b2a` evidence.
The root review independently reproduced both defects on that predecessor:

- personal empty workspace: 1 failed / 14 passed
  (`/private/tmp/root-authority-personal-valid.log`);
- missing original actor: 1 failed
  (`/private/tmp/root-authority-missing-actor.log`).

## Defect 1: Python/SQL personal-scope drift at the real claim

`core.personal_scope.resolve_workspace_id` treats `None`, `""` and `"default"`
as the Personal Edition default. The Python authority pre-check therefore
accepted all three. The same conditional `AgentJob` claim UPDATE accepted only
`NULL` and `"default"`, so an actor carrying an empty workspace passed the read
and then lost the claim. The SQL predicate now binds the empty-string twin, so
Python and SQL agree without widening any real workspace.

## Defect 2: missing actor became wildcard execution authority

`current_actor_authority` returned `(None, "")` for an empty actor id and
`actor_authority_conditions` returned an empty predicate. An actorless wait
binding could therefore be resumed by an admin reviewer's answer. Missing
actors now return `actor_missing`; `_validate_recovery_target` always checks
current authority instead of skipping it; the claim predicate is unsatisfiable
without an actor; and the one production claim site no longer has optional
wildcard defaults. Legacy rows remain readable, but readability is not an
execution grant. No actorless service-authority path exists for these admitted
information waits, so absence is refused rather than invented.

## Controls

`backend/tests/test_lead_recovery_personal_authority.py` adds:

- the real resume-claim positive for `None`, `""` and `"default"` personal
  workspaces, preserving the exact admitted `default` scope;
- a foreign real-workspace negative, and an empty-workspace negative against
  a real (non-personal) workspace, so the default alias is not a wildcard;
- missing, empty and corrupt actor negatives through the normal answer path
  with an admin reviewer, and through real startup recovery;
- a direct claim-helper control proving the CAS itself fails closed without an
  actor.

The existing controls still cover the moved workspace/tenant, deactivated
actor, lost `AGENT_RUN`, forced move between pre-check and claim, and the real
public-admission Generic/registered `tasks.create` positive/negative twin.

## Reproduction

Project interpreter:
`/Users/rushiparikh/projects/atom/backend/venv314/bin/python`.

Every run used `TESTING=1`, a synthetic `SECRET_KEY`, `ENVIRONMENT=test`, and
fresh owned scratch `DATABASE_URL`, `ATOM_DATA_DIR`, `ATOM_OFFICE_DIR`,
`LANCEDB_URI`/`LANCEDB_URI_BASE`, `TMPDIR`, and pytest `--basetemp`. No live
database, world, app, model/provider, account, credential, send, spend,
download, or deployment was used.

Native selection (99 passed, exit0):

```
pytest tests/test_lead_recovery_personal_authority.py \
       tests/test_generic_information_wait_recovery_authority.py \
       tests/test_generic_information_wait_recovery.py \
       tests/test_agent_generic_information_wait.py \
       tests/test_agent_run_outcome_join_contract.py \
       tests/test_boot_recovery_not_gated_by_scheduler.py \
       tests/test_hitl_resume.py \
       tests/test_generic_information_recovery_batch_contract.py \
       tests/test_agent_job_outcome_projection.py
```

Process selection (6 passed, exit0):

```
pytest tests/test_agent_generic_information_wait_process.py
```

Logs and JUnit XML are preserved from those actual runs without regeneration.
No tokens or live credentials appear in this packet.
