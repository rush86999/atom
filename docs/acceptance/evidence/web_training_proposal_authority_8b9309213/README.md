# Training proposal authority repair — 8b9309213

**Status: submitted, withheld; root independent review is still required.**

Executed source: `8b9309213` on `codex/web-training-proposal-authority-20261110`
(from `origin/main` `63dab46b5`). Canvas branches and packets are unchanged.

## Findings repaired

1. A default-scope lead could list a foreign-tenant training proposal attached
   to a null-scope agent even though detail refused it. The null agent masked
   the effective proposal tenant.
2. An expired proposal could be approved and created a training session.

## Repair

- Reads use the current active User; review uses the current active TEAM_LEAD+
  User. Members keep same-scope reads and get 403 on review.
- One effective scope resolver is used by list predicates and detail: agent
  tenant first, proposal tenant fallback; null/null remains legacy Personal;
  contradictory non-null tenants are excluded. Real moved workspace is
  refused; null/default compatibility is preserved.
- Review mutations conditionally claim the exact active User, authoritative
  Agent row (tenant/workspace/owner/status), and proposal identity/material/
  status/expiry before any session or rejection effect. A competing actor,
  agent, material or expiry change yields 409 with no session.
- Expired approval is refused before mutation. Expired rejection is explicitly
  allowed to clear the queue, with no session. None expiry remains valid.
  List/detail expose `expires_at`/`expired` so expired approval is not hidden.
- Direct `StudentTrainingService` consumers use the same gates. No new store,
  schema, clock, router or parallel review lifecycle. Training start/complete/
  graduation and manager notifications are unchanged.

## Root controls

Original withheld negative (unchanged):

- result: **2 failed in 4.83s**
- JSON: `/private/tmp/root-training-heldout-negative-20261110.json`
- log: `/private/tmp/root-training-heldout-20261110-wc8k5fy_/tests.private.log`

Root repaired run (exact same held-out probe, no assertion changes):

- result: **2 passed in 4.49s**
- review: `/private/tmp/root-training-heldout-repaired-review-20261110.json`
- log: `/private/tmp/root-training-heldout-repaired-20261110-b_ts1_15/tests.private.log`
- service/route/test digests: `347d7974…`, `5654306f…`, `4b6e1c00…`

The final test file adds the explicit expired `approve:false` zero-session
twin and is digest `772d83c2…`; root may rerun the exact 2 controls at final
freeze. The production service/route bytes are unchanged from the root run.

## Root original public-route probe (repaired runtime)

The original standalone probe ran positive on unchanged repaired runtime bytes:

- result: **passed**
- review envelope: `/private/tmp/root-training-original-repaired-review-20261110.json`
- raw report: `/private/tmp/root-training-original-repaired-20261110-1gz55f8m/verification.json`
- same-scope owner list/detail 200; foreign list 200 absent; foreign detail
  and reject 404; fresh proposal pending with reviewer None.
- Root review envelope binds the actual `agent_maturity_routes.py` and
  `student_training_service.py` digests and records that source files were
  unchanged during the run.

The preserved raw report still contains its probe's hardcoded historical
baseline label `63dab46b5`. That is a legacy probe label, not the executed
source of this repaired run; the root review envelope's runtime digests are
authoritative.

## Local affected gates

- New real-SQL/JWT controls: **16 passed**.
- Affected route consumers: **96 passed**.
- Approval service subset: **17 passed**.
- Exact root held-out probe locally on final bytes: **2 passed in 4.06s**.

Raw logs, scratch databases and tokens remain private under `/private/tmp`.

## Limits

- No browser, live DB, provider/model, account, install, deployment, PR or
  merge.
- No broad-suite or Python 3.14 claim.
- Root final independent binding remains required.
