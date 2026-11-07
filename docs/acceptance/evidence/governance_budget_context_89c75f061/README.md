# Configured budget scope at the real governed MCP boundary

The normal Generic request now reaches the real governance and MCP consumers,
not a doubled transport. In the baseline, allowed work and capability denial
pass, but a configured exceeded hard stop still creates the MiniApp and its
audit receipt. Independently calling BudgetEnforcementService for the same
account correctly refuses. The governance consumer passed workspace_id as
tenant_id, so ordinary registrations with distinct opaque ids looked like an
unconfigured account. This is a product defect; the earlier prototype's wrong
creator attribute was a fixture error and is not used as evidence.

Repaira5cabd207 reuses core.personal_scope.resolve_tenant_id over the current
scoped agent and workspace, with explicit service account identity and
contradiction checks. Legacy null personal scope and genuinely unconfigured
budgets keep their existing behavior. No SaaS deployment requirement, schema,
router, financial engine or new store is introduced. Only configured approval
mode can propose action review; hard_stop, soft_stop and unresolved scope do
not turn an ordinary action approval into spending permission.

## Executed comparisons

- Actual MCP negative at runtime2e95a94cf:1fail/2pass, actualexit1; the controls
  were then committed at2dafb82dd. Real governance/MCP/registry, scratch rows,
  no pre_approved bypass, model, provider or guest execution.
- Identical affected selection: predecessor5ff044ef6(runtime/test/CI bytes
  verified identical2e95) gives87pass/7fail/1skip; candidatea5cabd207 gives
  93pass/1fail/1skip. Six repaired failures, no new failure identities. New
  candidate controls are explicitly external in the baseline; source and
  test hashes are retained rather than relabelled as old committed tests.
- The remaining failure is the pre-existing w29 register_new_agent0.5
  confidence assertion. The skipped old BudgetEnforcementService module is
  not counted as coverage. Full logs/exits/JUnit are retained.
- Final normal-CI gate at89c75f061:31passed, actualexit0 (14real MCP/scope/mode
  controls plus17existing budget controls). Includes explicit tenant, agent
  fallback, workspace fallback, personal-null default, wrong scope, missing
  configuration and all four configured modes. This gate is added to CI.

The real host effect/receipt and zero-effect negatives are checked from the
scratch store; no result comes from model or handler self-report. Initial
negative bytes, both affected logs and exact commands/source ids are retained.
These checks do not qualify concurrent spend allocation, changed budgets
mid-dispatch, provider charging, browser workflows, Postgres/multiworker, or
all existing fail-open degradation behavior. Full app acceptance remainsopen.
No credential, purchase, provider-call, send, guest or deployment action occurred.
