# Registered-action ORACLE coverage

Source: `b205fc151`

This is a source-bound registry/verifier matrix, not a qualification run. It records the trusted effect declaration of every registered action and whether an independent postcondition verifier exists.

## Registered actions

- Total registered actions: **90**
- Declared mutating actions: **26** (21 covered, 5 uncovered)
  - external/provider mutations: **10** (6 covered)
  - local durable-state mutations: **16** (15 covered)
  - unscoped mutations: **0** (0 covered)
- Plan-output validators: **1** (1 covered; structural, not persisted execution proof)
- Explicit read-only actions: **63**
- Undeclared actions: **0**

The 90-action surface matches `core.action_registry` + `core.connected_actions` (the baseline import). Lazy modules `core.agent_radio.radio_actions` and `core.bpe.actions` also declare effects but are registered only when their surfaces load; their mutations remain unverified and follow the same uncertain-after-dispatch rule.

## Covered mutations

- `brennan.books.create_bill`
- `brennan.books.create_estimate`
- `brennan.outlook.create_draft`
- `connected.books.create_bill`
- `connected.books.create_estimate`
- `connected.outlook.create_draft`
- `canvas.present_chart`
- `canvas.present_markdown`
- `canvas.restore_version`
- `canvas.update`
- `goal_runs.start`
- `goals.create`
- `goals.evaluate`
- `mini_app_db_write`
- `mini_app_install`
- `mini_app_publish`
- `mini_app_revert_logic`
- `mini_app_scaffold`
- `mini_app_set_tests`
- `mini_app_write_logic`
- `tasks.create`

## Uncovered declared mutations

- `shopify_create_article`
- `shopify_create_blog`
- `shopify_create_fulfillment`
- `shopify_create_product`
- `mini_app_run`

## Highest-priority next verifiers

- Add independent readback verifiers for the remaining local mini-app mutations or keep them out of mutating assignment dispatch.
- Provider mutations (Shopify) need authoritative readback before they can be applied through the assignment path.
- Plan-output validation remains structural; add persistence postconditions only where an action actually persists state.

## Boundary

This inventory does not close a whole-app ORACLE promise. It makes the remaining uncovered registered mutations explicit and keeps plan-output validation separate from persisted execution proof.
