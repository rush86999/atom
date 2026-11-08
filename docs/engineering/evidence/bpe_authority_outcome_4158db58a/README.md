# Authority denial and truthful BPE execution outcomes

Executed integrated source: `4158db58a`. This combines current-principal BPE
checks, admitted governance-tier issuance, producer-owned note receipts and
independent durable verification, plus terminal actor/scope denial handling.

## Actual verification

- Original `actor-outcome-negative`: 1 failed, 1 passed. A disabled actor
  produced no note but the public run falsely completed successfully.
- Delivered `391`: 19 passed on Python 3.14. Root review then found that a
  later authority refusal could hide an earlier uncertain effect.
- Corrected `a8a`: 20 passed on Python 3.14 and Python 3.11. This includes
  the original admitted public run, actual registered tool, real durable
  approval consumer and active/refused twins, plus uncertainty precedence.
- Full integrated primary selection at `415`: 951 passed, 1 skipped on
  Python 3.11. It includes both authority modules and the existing primary
  regression. Counts overlap; do not add them.
- Earlier `415` full-run exit 75 is explicitly NOT DISPATCHED: free space was
  below the existing four-GiB floor. After byte-verified completed-world
  archival, the separate `415-admitted` run actually executed and passed.

Each log has its original spec and exit record. `focused-source-equivalence`
records that a8a → 415 changes only CI and review notes, not runtime/test bytes.
The 3.11 helper plugins are exact copies from the existing local environment;
no dependency was installed. Tests use scratch SQLite and controlled model
responses, never live app data or provider inference.

## Boundaries

A later proven no-effect authority denial cannot erase earlier uncertain
operations: reconciliation remains required. Recoverable argument mistakes
can still be corrected. Actor revocation is not model failure or model success
for maturity feedback. No claim that in-flight workers physically stopped.

This is not general multi-day coordination, model-quality, crash durability,
multi-worker or soak qualification. The earlier product negatives remain at
their original sources. Hosted checks and final independent review are separate.
