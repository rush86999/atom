# 04 — Consolidated Orchestration Contracts (the spine)

Status: the single documented chain the finalization slice implements
against. Artifacts 00–03 remain as baseline evidence and slice spec,
subordinate to this document. Harness changes after this point are
permitted ONLY to fix defects that produce false passes; cosmetic
accounting refinements are debt, not work.

## 1. Principle

**Domain-independent control; domain-aware data and capabilities.**
The orchestrator understands OBJECTIVES, OPERATIONS, EVIDENCE,
VERIFICATION, and DELIVERY — never manufacturers, invoice amounts,
attendees, or certifications as such. Those meanings enter through four
declared channels: user context, source schemas (e.g. dataset column
names and bases — the invoice a-priori pattern), tool contracts (e.g.
action-specific confirmation requirements), and configurable adapters.
A case that requires new business vocabulary in the orchestrator is a
design failure, not a fixture.

The existing manufacturer/position/capitalization heuristics and regex
completion-claim guards are LEGACY PROTECTION — preserved at the pinned
revision with their known failures recorded, NOT expanded. They are not
the correctness boundary; the contracts below are.

## 2. The chain: objective → operation → evidence/result → verification → delivery

Every stage owns specific facts. Every handoff threads identity downward
and unresolved-work upward. Constraints flow down; ambiguity is never
dropped silently.

### Stage 1 — Objective (owned by task resolution)
- **Identity**: `objective_id`; `supersedes_objective_id` (revision
  lineage — refinement is a new revision, never a silent overwrite).
- **Facts**: goal (user's words + turn), typed entities and requested
  fields (from source schemas), source constraints, authorized actions,
  clarification state.
- **Provenance**: originating turn(s); which user words supplied each
  entity/constraint.
- **Unresolved carried forward**: ambiguous entities, pending
  clarifications, inferred constraints marked as inferred (they rank,
  never resolve).

### Stage 2 — Operation (owned by execution)
- **Identity**: `operation_id` (one per action — multi-action turns do
  NOT collapse); binds `objective_id` + `execution_id`; idempotency key
  for mutations; `finalizer_version` stamped at turn start.
- **Facts**: requested read/change spec; capability/tool contract invoked;
  deadline and budget; approval state (attempted ≠ applied ≠ reviewed).
- **Provenance**: caller, tool contract, authorization source.
- **Unresolved**: pending, superseded (a new user turn supersedes),
  background continuation ids.

### Stage 3 — Evidence / Result (owned by the evidence layer)
- **Identity**: `evidence_id`; binds `operation_id`; source identity
  (resource id, content hash, ingested_at, schema version).
- **Facts**: coverage against requested fields (found / ambiguous /
  absent-with-scope — never unscoped absence); per-entity outcomes;
  computation traceability (inputs → derived values, formula-expressed).
- **Provenance**: source snapshot identity; extraction contract version.
- **Unresolved**: gaps list; contradictory evidence flagged, not averaged.

### Stage 4 — Verification (owned by the verifier registry)
- **Identity**: verdict per operation AND per objective criterion; binds
  `operation_id`/`evidence_id`; records which registered verifier ran.
- **Facts**: `verified | unverified | unsupported` — computed through the
  trusted-provenance registry (`task_outcome_contract`), mutations via
  canonical audit-first readback with review state separate; idempotent
  writes; unknown stays unknown.
- **Provenance**: verifier identity + the evidence ids it consumed.
- **Unresolved**: unverified is a first-class outcome, never rounded to
  success or failure.

### Stage 5 — Delivery (owned by the finalizer — the slice)
- **Identity**: `delivery_id`; binds `execution_id` (+ continuation id
  for background completion); delivery tiers available / transport /
  ack; streamed content gated before emission.
- **Facts**: the delivered text asserts ONLY what stage-4 verdicts
  support; pending work surfaces as pending (never claimed complete);
  age/freshness of evidence disclosed.
- **Provenance**: finalizer version; the verdict set the text renders
  from.
- **Unresolved**: `pending_continuation` bound to its operation; offline
  acks remain retrievable, never execution failure.

## 3. Component ownership (existing modules; no new frameworks)

| Stage / fact | Owner today (pinned rev) | Slice adds |
|---|---|---|
| Objective state | `_build_turn_task_outcome` objective_state | revision lineage; resolver service |
| Execution records | `AgentExecution` + `_start/_finish_chat_execution` | per-operation rows; lifecycle events (03 §6a) |
| Operation identity/idempotency | canvas `operation_id` stamping; `AsyncContinuationClaim` | general operation registry |
| Evidence/coverage | `workbook_read_artifact` coverage; evidence ledgers | schema-declared binding (invoice pattern) |
| Verification | verifier registry (`task_outcome_contract`); canvas guard (legacy) | canonical-resolver readback as the general producer |
| Delivery | streaming inside `_get_qwen_response`; 13 outcome classes | the finalizer: one contract, four-dimension outcome |

## 4. Cross-domain acceptance (generality is an acceptance CONDITION)

The same contracts must handle all five task structures with ZERO new
orchestrator vocabulary:

| Structure | Status at baseline |
|---|---|
| Retrieve fields from a document | HAVE (workbook + invoice fixtures; a-priori provenance on the latter) |
| Calculate a result from traceable inputs | QUEUED (derivation-verification lane exists at the pinned rev; case to be authored on a frozen fixture) |
| Modify an artifact preserving constraints | QUEUED (mutation overlap — old-path observable readback/persistence/duplicates) |
| Schedule/send with action-specific confirmation | PARTIAL (planner-down no-apply is the degenerate form; full form via the rig) |
| Resume/refine after interruption | QUEUED (restart recovery of continuations; pending-task resume already pinned in unit tests) |

## 5. Learning boundary

A correction about one price is a CONTEXTUAL FACT bound to its objective.
A preference is SCOPED TO ITS OWNER. A strategy change is a CANDIDATE
REQUIRING EVALUATION. **No incident automatically becomes a global
behavioral rule** — the contracts enforce this by requiring scope fields
(objective / owner / evaluated-candidate) on anything the learning loop
consumes, and the frozen learning evaluation stays untouched by the
migration.

## 6. Milestone (ends the patch-review treadmill)

**M1 — a small, working finalization slice with authoritative outcomes,
passing cross-domain acceptance.** Exit criteria: the slice live behind
the capability flag on the frozen baseline; the five task structures
passing the same user-visible criteria on both paths where the old path
can run them; old-path failures correctly measured, not repaired.
Remaining baseline work before M1 starts: mutation overlap and restart
recovery (observable outcomes only) — then the baseline FREEZES as-is.
