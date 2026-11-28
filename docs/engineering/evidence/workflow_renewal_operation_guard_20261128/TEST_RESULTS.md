# Exact renewal operation transition proof

Executed runtime: `f2bede4c0`. Frozen Python3.11 result:

```text
= 533 passed, 625 deselected, 108 warnings, 18 subtests passed in 433.18s (0:07:13) =
```

All39 selected source/test/CI hashes stayed unchanged and match Git objects. The exact command is in frozen-verification.json. The unchanged625 real_gate_shell controls are deselected locally. No Python3.14, PostgreSQL, multi-worker, live provider or days-long result is implied.

Git-bound baseline `4208c35b246c9983c354bca43fefd44c8267c0b2` records24failed/1passed. Its original25-control file remains byte-identical as the prefix of the final file. Six peer field changes (tenant, workspace, operation, action, run, idempotency) were injected during preflight or provider PATCH success/refusal/timeout. Previously dispatch/acknowledgement could use the moved row. The final tests require the original operation identity, unknown/do_not_repeat, peer material/status/result retained, zero premature PATCH, no lease/audit commit, and one PATCH at most after dispatch.

The existing scalar/raw-JSON source-operation claim is shared by enrollment and renewal. It freezes exact tenant/workspace/operation/run/key/type/hash/status/result in the caller-owned transaction, preserving timestamps and semantic JSON equivalence before observed-storage CAS. Source/audit and original enrollment proof are claimed before the renewal operation. Generic arbiter semantics are unchanged; no new ledger/table/queue/runner/migration was added.

Inspection also occurs inside the existing generic allocation transaction. A development-working-tree negative reproduced one allocation failure (workspace move) plus one already-protected operation-ID twin between preliminary inspection and allocation. Its separate hashes/log are retained, honestly labeled as uncommitted development evidence. The repaired twins pass2/2. This is not a claim that arbitrary operation deletion or simultaneous destruction of every discoverable identity is qualified.

Dispatch, stale-target refusal, confirmed refusal, timeout, success persistence and GET-only uncertain reconciliation claim the exact pending row before status CAS. A failed claim cannot relabel an unverified effect as none. Safe supersession preserves existing authority/material/audit requirements and refuses a peer-moved original without retiring it or allocating another row. Replay after a moved row stays unknown; restoring original material reconciles by GET only, retaining the original identity and one PATCH. Valid renewal, current-lease proof, multi-generation/fresh-process recovery and original enrollment guards remain in the expanded gate.

Intermediate52/81-control development passes were followed by additional allocation changes; the final frozen gate above is authoritative. One tools-denied OpenCode Go DeepSeek review used only a byte-verified already-public GitHub source packet after an initial unverified export was rejected and not sent. Root rejected fictitious test APIs and incorrect physical-JSON/reconciliation suggestions; no worker patch was applied. Provenance records the public blob identity and one request without fallback. No quota-free claim is made.

Open: encrypted canonical first-observation payload shared by callback/delta, durable opaque cursor and complete reservation coverage, temporal/bootstrap/reset semantics, missing-pending-operation integrity, safe initial/expired/removed/legacy source succession and owner-visible recovery. Full-main/fresh-rule browser, second-domain, scoped forwarding, days-offline/PostgreSQL/multi-worker/soak/live acceptance and whole-app completion remain open. A separate development callback replay probe already identifies the next canonical-payload gap; it is not part of this renewal qualification. No merge, deployment, credential/account action or live application provider/model campaign was performed.

See [renewal work order](../../work_orders/WORKFLOW_EVENT_RENEWAL_2026_11_28.md). Existing mechanism references: [SQLAlchemy CAST](https://docs.sqlalchemy.org/en/20/core/sqlelement.html#sqlalchemy.sql.expression.cast) and [transaction row locks](https://docs.sqlalchemy.org/en/20/core/selectable.html#sqlalchemy.sql.expression.GenerativeSelect.with_for_update).
