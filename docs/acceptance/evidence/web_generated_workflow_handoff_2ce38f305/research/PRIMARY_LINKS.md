# Primary research links and repo tradeoff

## Primary sources

1. Camunda glossary — process definition vs process instance
   - https://docs.camunda.io/docs/reference/glossary/
   - Principle used: a deployed/versioned process definition is distinct from a
     process instance. Atom therefore treats the persisted compiled blueprint
     as the definition and manual execution / scheduled execution as separate
     instances. Deployment verification is not the same as starting a run.

2. Camunda getting started — deploy and verify deployment
   - https://docs.camunda.org/get-started/quick-start/deploy/
   - Principle used: verify that a definition was deployed before treating it
     as runnable. Atom's Deploy response is only `deployed` when the scoped
     catalog reference is persisted and read back exactly; otherwise it returns
     `pending_approval`, a refusal, or `committed_unverified`.

## Repo-specific tradeoff

- **Reuse, do not add a framework.** Atom already has a scoped compiled
  blueprint (`Workflow`/`WorkflowStep`, status `designed`), a durable HITL
  decision store, a JSON workflow catalog, the canonical orchestrator, and an
  explicit scheduler. The handoff is a thin server-side adapter over those
  mechanisms.
- **JSON catalog is a reference/projection, not the execution engine.** The
  generated catalog row records the canonical workflow id, definition digest,
  executor, owner, scope, approval and authority claim. Manual execution
  reloads the scoped SQL definition, recomputes the existing compiler digest,
  re-registers through the existing blueprint consumer (fresh process included)
  and dispatches the canonical orchestrator. Client node JSON is never
  execution authority.
- **No auto-schedule.** Deploy stores a manually runnable entry with
  `triggers_activated: false`. Scheduling is the existing explicit command.
- **Rejected alternatives.** Installing Camunda or another workflow framework
  would add a second engine/store and contradict the existing architecture.
  Treating the JSON row as the executable definition would reinterpret compiled
  steps through a different legacy engine and lose the ORCH-01 checkpoint
  binding. A read-only deployment decision without guarded SQL authority would
  race actor/executor revocation against the file commit.
- **Claim boundary.** The controls exercise real compile/persistence/canonical
  execution with only model transport doubled. No served-model, browser,
  whole-app, PostgreSQL, multi-worker or production claim is made.
