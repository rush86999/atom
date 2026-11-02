# Verification claims batch 1 — results

Executed source: `6d62855d029acefa9b41520b88a45dcd5ee2e763` (clean).

## Commands

```bash
# TEAM-05
TESTING=1 pytest tests/test_org_politics_automation.py -q
# 21 passed

# ORACLE-01
TESTING=1 pytest tests/test_oracle_connected_mutations.py -q
# 2 passed

# affected neighborhood
TESTING=1 pytest tests/test_org_politics_automation.py \
  tests/test_oracle_connected_mutations.py \
  tests/test_covpush_w36_oracle_vfs.py \
  tests/test_covpush_w77b_graphrag_oracle.py \
  tests/test_covpush_w31_generic_agent.py \
  tests/test_generic_agent.py -q
# 271 passed
```

Logs: `team05-tests.log`, `oracle-team-tests.log`,
`oracle-team-neighborhood.log`.

## TEAM-05 controls

- Controlled alignment sweep over 3 scenarios × 3 structures × proposal/judge
  calls; green result computed from parsed policy scores.
- `approve` mode queues a finding; flags stay off.
- Nightly loop invokes the certification pass on its interval and exits on
  cancellation.
- Existing revocation/no-sweep/low-telemetry/approve/reject controls remain
  green.

## ORACLE-01 controls

Six registered mutating actions plus the existing task/workflow verifiers:

```text
connected.books.create_estimate
connected.books.create_bill
connected.outlook.create_draft
brennan.books.create_estimate
brennan.books.create_bill
brennan.outlook.create_draft
tasks.create
trigger_workflow
```

Positive: applied result + matching read receipt + digest + verified status.
Negative: uncertain outcome, mismatched read receipt, incomplete verification,
missing payload digest — all refuted.

See `oracle_registry.json`.

## Boundaries

No browser/UI rerun is claimed for these service/registry claims. No live
provider action. The remaining original claims and normal full-app journeys
are not closed by this batch.
