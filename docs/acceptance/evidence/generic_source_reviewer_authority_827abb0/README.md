# Generic source answer: current reviewer authority

Source under test: `827abb049a261d8f32040c13b3f0e37ee9fa1271` on `codex/generic-source-scope-cas-20261107`
(parent `dcdb31e8b`, which exposed the race at executed `20d2f1e77`).

## Finding and repair

Root reproduced a **current reviewer** race at `20d2f1e77`: an unchanged
admin proxy answering a member's durable wait passed the pre-read admin gate,
then the proxy was demoted, disabled, or moved to another workspace **after
the real `_load_generic_source_payload` read but before the HITL claim**. The
claim bound only the admitted owner, so it still approved, resumed, and
created an actual task. Root's permanent probe was `3FAIL1PASS` (only
`unchanged` passed); the raw log, spec, and exit proof are included verbatim.

The repair re-reads the *actual reviewer* from SQL with `populate_existing`
before any source await and freezes its raw `status`, `is_active`, `role`,
`tenant_id`, and `workspace_id`. Those exact predicates are part of the same
conditional `HITLAction` UPDATE as the full wait material CAS and the
admitted-owner authority condition, so the original admitted actor and the
actual proxy reviewer are both bound in one statement. The resume/job claim
carries the same frozen proxy authority; approved replay and zero-CAS rechecks
re-read the current reviewer and never accept replay with revoked authority.

Same-actor ordinary-member and Personal `NULL`/empty/default answers keep the
established admitted-owner authority semantics, including their existing 409
refusals; reviewer exactness applies only to a real proxy (answerer != admitted
owner). The agent answer route retains its existing admin proxy rule, and
shared HITL approval callers retain the existing `AGENT_MANAGE` rule. No new
roles, gates, stores, or engines were added.

## Evidence

| Run (source-bound) | Result | Raw log |
|---|---|---|
| Root permanent negatives at `20d2f1e77`, before | 3 failed / 1 passed | `root-generic-source-reviewer-authority-permitted.log` |
| Permanent reviewer probe at `827abb049a261d8f32040c13b3f0e37ee9fa1271` | 7 passed | `after-reviewer7-pass.log` |
| Existing source-answer/scope family | 52 passed | `after-final52-pass.log` |
| Existing recovery/personal-authority family | 37 passed | `after-recovery37-pass.log` |

Every pytest run used `/private/tmp/atom-agent-cli/run_bounded_test_gate.py`
(`--profile bounded`), the existing `venv314` interpreter, a fresh unique
`TESTING=1` DB/data/office/Lance/output/basetemp world, and a synthetic
`SECRET_KEY`. No dependency install, live model/provider/account/send/spend,
world, live database, browser, or deploy. Root owns independent review and
merge; this packet is not self-acceptance.
