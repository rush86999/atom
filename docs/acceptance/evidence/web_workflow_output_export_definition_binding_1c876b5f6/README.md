# Export definition-revision binding repair — evidence packet

Packet: `docs/acceptance/evidence/web_workflow_output_export_definition_binding_1c876b5f6/`

## Boundary repaired

Root’s independent definition-binding probe failed at `670277944`: a completed
execution retained its original compiler digest in
`WorkflowExecution.context.variables._workflow_definition_digest`, but changing
`Workflow.configuration.definition_digest` while preserving step ids still
exported HTTP 200 under the revised revision label.

Repair at `1c876b5f6`:

- Export requires the orchestrator-frozen executed definition id/digest in the
  durable execution context.
- That executed identity must equal the durable execution’s `workflow_id` and
  the authoritative `Workflow.configuration.definition_digest`.
- The authoritative configuration’s compiler digest is independently
  recomputed from the persisted definition material; it must equal its stored
  digest.
- Missing executed binding, missing authoritative digest, identity mismatch,
  contradictory context digest, changed authoritative revision, or a tampered
  configuration return typed 409 refusals. The current definition is never
  relabelled as the revision that executed.
- No parallel store, synthetic provenance or execution snapshot was added.
  The source of truth is the existing compiler digest + orchestrator context
  variables + durable `Workflow`/`WorkflowExecution` rows.

## Positive and negatives

- Failure-first negative: mutate the authoritative digest after execution →
  409 `execution_definition_binding_mismatch`.
- Positive: unmodified execution exports 200; provenance contains identical
  `definition_digest`, `executed_definition_digest`, executed definition id,
  and the explicit `executed-context-vs-authoritative-configuration` binding.
- Missing/contradictory controls: removed executed digest → 409
  `execution_definition_binding_missing`; contradictory context digest,
  different executed definition id, missing authoritative digest, or tampered
  configuration → 409 `execution_definition_binding_mismatch`.
- Original unchanged 7 export negatives still pass.
- Both prior negatives are preserved: the original `70cc3b7e7` seven-failure
  negative in the prior export packet, and this `670277944` definition-binding
  failure here.

## Gates at repaired checkpoint

| Gate | Result | Log |
|---|---|---|
| Export suite | 12 passed | `gates/export_suite_12.proof` |
| Combined handoff + export backend | 42 passed | `gates/combined_42.proof` |
| Affected workflow regression | 135 passed | `gates/affected_135.proof` |
| Root original 7 export probes | 7 passed | `gates/root_original_7.proof` |
| Root definition-binding probe locally | 1 passed | `gates/root_definition_binding_local_pass.proof` |

No frontend source changed in this repair; the prior 42 frontend
Execution-Details/page/generator evidence remains at its recorded source.

## Fresh-process determinism

Two separate fresh OS processes exported the same completed execution:

- 1,636 bytes
- SHA-256 `b4f512d9c41084db4fd2bc4e7c8030504dd867403fb7f1ea9fb905f8bcf735a2`
- same execution/workflow identity
- `model_calls: false`
- no scheduler jobs, no new execution rows

## Claim boundary

- Supported format is deterministic JSON only; no DOCX/PPTX/email generality.
- No served-model, browser, whole-app, PostgreSQL, soak or production claim.
- No new store/engine/schema/approval/filesystem artifact path.
- Root independently owns final acceptance, delivery/CI integration and
  PR/merge. This is not whole-app acceptance.

## Commands

```
TESTING=1 DATABASE_URL=sqlite:///<scratch>/export.db \
ATOM_DATA_DIR=<scratch>/data PYTHONPATH=<backend>:<plugins> \
python -m pytest backend/tests/test_workflow_output_export.py \
  -q -p no:cacheprovider -p no:randomly
```

```
python -m pytest /private/tmp/root-workflow-export-definition-binding-20261110.py \
  -q -p no:cacheprovider -p no:randomly
```

```
python -m pytest /private/tmp/root-workflow-export-independent-20261110.py \
  -q -p no:cacheprovider -p no:randomly
```
