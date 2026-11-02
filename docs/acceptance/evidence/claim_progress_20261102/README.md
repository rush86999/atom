# Claim progress — ORACLE-01, TEAM-05, MEM-07

Status: **submitted for independent verification; no claim verdict is changed
here.** These are executed slices with named remaining gaps, not declarations
that the claims are complete.

## ORACLE-01 — postcondition oracle

**Defect found.** `ATOM_ORACLE_VERIFIER_ENABLED` resolved to `True`, but the
production dispatch path registered nothing:

```
$ python -c 'import core.generic_agent; from core.oracle import _VERIFIERS; print(_VERIFIERS)'
enabled True
registered []
```

Only `scripts/readme_acceptance/groups_governance.py` imported
`core.oracle.postcondition_verifiers`, so `get_postcondition()` returned
`None` in the served app and the oracle was inert.

**Fix (commit `3f2373ab6`).**
- `core.oracle` imports the verifier module after defining the registry, so
  enabling the oracle always loads its verifiers.
- `canvas.present_markdown` has a verifier that reads the `canvas_audit` row
  written by the same dispatch. The tool's own success flag and websocket
  broadcast are not evidence; a missing row, unreadable DB, missing canvas id
  or component mismatch refutes.
- The assignment executor passes an applied mutation through a registered
  verifier before the step may settle applied. A refutation returns
  `uncertain` with the remote identity preserved, so it blocks and reconciles
  instead of retrying or claiming success.

**Positive control (normal app).** The 15-check full-app campaign passed at
`3f2373ab6` with the gate active; the declared canvas action dispatched once
and settled applied only after its audit row verified:

```
remote id  b819f56c-6be4-4a9f-8ecd-e9c055b69d5d
audit row  present | markdown
```

**Negative controls.** Four verifier tests (verified row, missing row,
component mismatch, missing identity) and a refuted-postcondition assignment
control: the step blocks `uncertain`, preserves `remote_id`, reconciles with
readback evidence, completes, and leaves exactly one provider draft.

**Remaining gap.** Verifiers cover `trigger_workflow`, `tasks.create` and
`canvas.present_markdown`. The README's "every mutating action is re-derived"
is still not established; other mutations stand on their explicit envelopes
and readback contracts.

## TEAM-05 — nightly alignment sweep

The scheduled entry point (`run_auto_certification`, which opens its own
session) is now exercised, not just the inner `certify(db)` helper:

- **notify** — a controlled green sweep with flowing telemetry records the
  notification set, writes **no** `org_politics_actions` row, and leaves the
  flags off.
- **approve** — pending approvals are read back from a **new session**, all
  flags remain off, and a second scheduled pass does not requeue the same
  flags.

**Remaining gap.** The sweep's LLM transport is injected here (the verdict is
controlled); the sweep's own `chat_fn` tests cover judge parsing. A real
24-hour scheduling boundary was not observed.

## MEM-07 — tool error to pending evolution candidate

**Gap found.** Nothing in the served agent path turned a tool error into an
evolution candidate: the evolution loop is only called explicitly, and
`ATOM_AGENT_EVOLUTION_ENABLED` appeared only as a product-profile default.
There was no candidate store or tool-error hook.

**Slice (commit `ad8069b2a`).** A flag-gated `capture_tool_failure` writes a
**PENDING** `HITLAction` (`agent_evolution_candidate`) with the tool, error and
a bounded proposed scope. It never edits code or configuration, and dedupes
per (agent, tool, error). Both failure paths in the generic-agent wrapper
(raised exception and error-string result) call it, guarded so capture never
changes the tool result.

**Remaining gap.** The approval → apply path and the AlphaEvolver/Memento
consumer are not implemented in this slice; candidates are queued only. No
evidence yet that an approved candidate is consumed after restart.

## Commands

```bash
# ORACLE verifier + canvas assignment controls
TESTING=1 pytest tests/test_oracle_canvas_postcondition.py \
  tests/test_canvas_assignment_integration.py -q     # 17 passed

# TEAM-05 automation + scheduled entry
TESTING=1 pytest tests/test_org_politics_automation.py \
  tests/test_org_politics_scheduled_entry.py -q      # 21 passed

# MEM-07 capture
TESTING=1 pytest tests/test_agent_evolution_candidates.py -q   # 3 passed

# ORACLE-01 positive control (normal app, ports 8096/3137)
python scripts/acceptance/full_app_quote_journey.py ...
```

## Exclusions

- No live LLM/provider call; the TEAM-05 verdict is injected by the control.
- No code or configuration is applied by MEM-07; the candidate is a pending
  approval row.
- The full-app evidence for the taught-artifact batch remains bound to
  `6f697cd9d`; this bundle does not alter it.
