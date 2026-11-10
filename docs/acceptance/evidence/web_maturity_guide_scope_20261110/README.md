# Maturity-guide read scope (GOV-01 bounded slice)

- Source before: `750f4221`
- Repair commit: `e8ee987f4a62849ca48aedce79122b9f9cc042d4`
- Scope: ordinary Agent Studio maturity/readiness read only.

## Runtime failure reproduced

A real scratch JWT/SQLite public GET on the unchanged source returned:

- foreign tenant/workspace principal, agent A: **200** with agent name,
  confidence, lesson count and mastery;
- owner same scope: **200**;
- unknown id: **404**.

The route resolved `AgentRegistry` by opaque id with no current
tenant/workspace scope.

## Repair

The route now reuses the existing agent-read authority and scope:

- lazily imports `_authoritative_reader` and `_scoped_agent` from
  `api.agent_routes`;
- re-reads the current active principal from the database;
- applies the existing tenant/workspace/personal-shared condition;
- returns the same indistinguishable 404 for foreign and unknown targets.

No graduation thresholds, exam/lifecycle, confidence 0.45 label, guided
creation or teaching routes changed. No new authority engine/store/router.

## Controls

- Scope controls: **6 passed**
- Onboarding + scope: **20 passed**
- Onboarding/read-scope/graduation neighborhood: **79 passed**
- Twins: owner, same-scope member, legacy shared, foreign tenant/workspace,
  unknown, deactivated principal, principal-moved, fresh-session readback,
  read no agent/learning mutation
- Original leak log and probe retained unchanged.

The unrelated `tests/test_teach_thread_reply.py` four failures reproduce on
the untouched baseline and are not attributed to this change.

## Open secondary

The guide's confidence-only `ready_for_graduation_review` still differs from
canonical multi-factor readiness. It is recorded as a separate open
diagnosis and was not changed here.

## Limits

No whole-graduation or goal completion claim, no browser/live DB/provider/
model/agent promotion, no CI/PR. Root independently verifies and delivers.
