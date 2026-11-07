# MEM-07 consolidated local chain — exact-source evidence

Executed source: `f069a944a` on `codex/mem07-consolidated-20261107`, based on
`origin/main` `2d251acdf`.

This packet proves one finite local goal end to end:

real tool-error signal -> canonical pending Memento candidate -> normal
authenticated Auto-Dev review -> existing typed-prompt apply -> fresh-session
ordinary-work prompt consumption.

It is test-only: **no runtime defect or product-code change was needed**. The
current accepted mechanism already supports the chain.

## Reconciliation / existing evidence

Current code and accepted evidence were inspected before editing:

- `mem07_workspace_clean_20261107` covers the workspace-authority gate;
- `test_tool_error_memento_lifecycle.py` covers the real tool-error ->
  episode partial -> pending candidate path;
- `test_memento_candidate_review.py` covers pending/review rejection without
  agent mutation;
- `test_reviewed_improvement_apply.py` covers typed-prompt apply plus direct
  retrieval;
- `test_reviewed_skill_agent_consumption.py` covers fresh-session GenericAgent
  prompt consumption of an already-promoted skill;
- `reviewed_skill_consumption_20261102` and original pieces
  `c1074f0a9`/`952fcbdf8` and `5538a654d`/`d30130d1f` remain intact.

No single already-accepted control joined the real tool-error producer to the
authenticated review/apply and fresh-session ordinary-work consumer. This
packet adds that consolidated control; it does not replace or relabel the
pieces above.

## Chain control

`backend/tests/test_mem07_consolidated_chain.py` uses:

- real `GenericAgent` failing tool dispatch -> durable `tool_errors` on the
  `AgentExecution`;
- real `EpisodeService.create_episode_from_execution` (nominal success with a
  tool error becomes `partial`, `success=False`);
- real `ReflectionEngine` -> `MementoEngine` pending `SkillCandidate`;
- real authenticated `api.autodev_review_routes.approve_skill_candidate` and
  `apply_skill_candidate` functions with a real workspace-admin `User`;
- real `apply_reviewed_skill` typed-prompt package/registry/candidate promotion;
- fresh SQLAlchemy session + real `GenericAgent._retrieve_skill_instructions`.

Only the Memento model transport is doubled: it returns controlled text
`def repair_unknown_tool(): return 1`. The test labels that simulated model
choice explicitly. No live model/provider/network/sandbox is used.

## Negatives / valid twins

- pending candidate cannot apply (409, no Skill/SkillExecution);
- rejected candidate cannot apply;
- changing generated code after review invalidates the exact review binding
  (`stale_review`, 409), with no package/registry/agent mutation;
- repeat apply is idempotent (one Skill, one SkillExecution);
- the valid twin consumes the exact reviewed description in the fresh-session
  prompt, while the generated code is absent from the package and prompt;
- agent `configuration` remains byte-identical throughout.

## Exact run

`run_and_capture.py` uses the existing Python 3.14.7, `TESTING=1`, explicit
fresh scratch SQLite/data/LANCE/output/basetemp/skills, and blank provider keys.

Focused affected set (consolidated control + existing MEM-07/review/consumption/
tool-error/review-route suites): **55 passed, exit 0** (`focused.log`,
`focused-exit.json`).

## Boundaries

- No live model/provider/network/sandbox/account/credential/spend/send/install/
  deploy.
- No second HITL/review/store/evolution engine; the existing routes, Memento
  engine, review binding, apply, skill registry and prompt retrieval are used.
- Generated code is stored on the candidate for review binding but is never
  written, imported, executed or promoted; only typed prompt material is applied.
- No OS process restart is claimed for this chain; fresh-session consumption is
  the required boundary and is covered. Existing accepted process/restart
  packets remain authoritative for their own scopes.
- Root owns independent acceptance and merge.
