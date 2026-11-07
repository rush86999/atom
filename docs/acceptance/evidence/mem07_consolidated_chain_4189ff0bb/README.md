# MEM-07 consolidated local chain — natural-event / authenticated successor

Executed source: `4189ff0bb` (normal merge of `origin/main` `36fa4ce39` into
`codex/mem07-consolidated-20261107`). Test successor: `fe07b615b`.

This supersedes the component-only control at `cb81bd4ca` for source
attribution, without modifying that earlier packet. Root's independent probe
`81b94a7e1` ran against `cb81` plus an uncommitted natural-event test; this
packet reruns the clean final source.

## Natural producer/consumer boundary

The consolidated test no longer inserts an `EpisodeSegment`, constructs a
`TaskEvent`, or calls `ReflectionEngine.process_failure` directly. On one
`asyncio.run` loop it:

1. runs the real `GenericAgent` failing-tool dispatch (controlled synthetic
   tool only) so the durable `tool_errors` signal is recorded;
2. calls the real `EpisodeService.create_episode_from_execution`, which lowers
   the nominal success to `partial` and emits the real failure event;
3. drains the REAL registered `ReflectionEngine` consumer (registered on the
   existing event bus, fresh sessions), which produces the canonical pending
   Memento `SkillCandidate` via the real `MementoEngine`.

Only the Memento model transport is doubled with controlled generated-code
text. Both controlled seams are labeled: the synthetic failing tool and the
Memento model leaf.

## Authenticated review/apply boundary

Review/apply go through the actual mounted `api.autodev_review_routes.router`
in a FastAPI app with:

- real normal JWT bearer auth (`get_current_user`) and real
  `get_current_tenant` resolution from real `User`/`Tenant` rows;
- real workspace authority (`require_role`/`_candidate_agent`);
- only `get_db` pointed at the scratch SQLite factory.

There is no `current_user` or tenant dependency override. Normal guards are
exercised: missing bearer token -> 401, real viewer JWT -> 403, real
workspace-admin JWT -> 200.

## Preserved twins

- pending candidate cannot apply (409, no Skill/SkillExecution);
- rejected candidate cannot apply;
- changing generated code after review invalidates the exact review binding
  (`stale_review`, 409);
- repeat apply is idempotent (one Skill, one SkillExecution);
- generated code is never written/imported/executed/promoted;
- agent `configuration` remains byte-identical;
- fresh session consumes the exact reviewed description in ordinary-work
  `GenericAgent._retrieve_skill_instructions`, with generated code absent.

No runtime/product fix was needed; the accepted production mechanisms already
support the natural chain.

## Exact run

`run_and_capture.py` uses the existing Python 3.14.7, `TESTING=1`, explicit
fresh scratch SQLite/data/LANCE/output/basetemp/skills, and blank provider keys.

Focused affected set (consolidated control + existing MEM-07/review/consumption/
tool-error/review-route suites): **56 passed, exit 0** (`focused.log`,
`focused-exit.json`).

## Source provenance

- Root natural-event probe: `81b94a7e1` (1 passed) against `cb81` plus an
  uncommitted test.
- Earlier component packet: `cb81bd4ca`
  (`mem07_consolidated_chain_f069a944a`) remains preserved byte-for-byte.
- This packet binds the clean merged source `4189ff0bb` and hashes all relevant
  production consumer files in `MANIFEST.json`, not only the test file.

## Boundaries

- No live model/provider/network/sandbox/account/credential/spend/send/install/
  deploy.
- No second HITL/review/store/evolution engine.
- No OS process restart claimed; MEM requires fresh-session consumption, which
  is covered.
- Original pieces `c1074f0a9`/`952fcbdf8` and `5538a654d`/`d30130d1f` remain
  intact.
- Root owns independent acceptance and merge.
