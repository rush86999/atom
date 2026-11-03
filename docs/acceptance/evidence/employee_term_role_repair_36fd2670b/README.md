# Employee monetary-term role and live-validity repair

Status: **the two reproduced term-binding defects are repaired and the
independent probes pass. G5 remains open; this is deterministic contract
evidence, not adaptive campaign acceptance.**

## Source

| Item | Value |
|---|---|
| Branch | `codex/brennan-full-app-20261102` |
| Product source | `36fd2670b` |
| Reproduced defects | tax-rate term authorizing freight; expiry between compile and consumption ignored |
| Inference | none used for this repair |

## Repair

- Shared money-term contract in `core/employee_money_terms.py`:
  `currency`, `freight_amount`, `tax_rate` (dimensionless 0..1),
  `tax_amount` and `tax_exemption` are distinct roles/dimensions.
- Existing teaching/fact keys resolve through an explicit trusted alias
  table. A record may declare `role`/`term_role` at top level or in
  `validity`; unknown explicit roles refuse instead of being guessed.
- The compiler checks the expected role for each field and binds role,
  dimension, source, source identity, revision and validity into
  `term_receipt`. A tax rate or tax amount cannot authorize freight.
- The executor supplies the job assignment and accepted facts to
  `quote.calculate`. At consumption the receipt term is re-resolved from the
  job's accepted teaching snapshot/facts and rechecked for role, current
  scope, teaching revision, source identity, effective/expiry dates, value
  and currency. A stripped, forged, expired, replaced, revoked or
  unverifiable typed receipt blocks before arithmetic. Legacy callers
  without a receipt retain their documented contract.
- The accepted job snapshot remains authoritative; new teaching for new work
  does not silently replace an active job's terms.

## Results

| Scope | Result |
|---|---|
| Independent term probes `test_verifier_terms_20f.py` | **2/2 passed** |
| Independent verifier suite | **22 passed** |
| Focused compiler/executor/adaptation suite | **179 passed** |
| Affected backend selection | **789 passed**, 8 known WebSocket tests deselected |
| Executor expiry negative | step not applied; no calculated value; assignment not completed |

Controls cover role swaps across currency/freight/tax rate/tax amount/tax
exemption, explicit aliases and unknown roles, fact role metadata, expiry
between compile and consumption, source replacement, teaching revision
change, JSON restart round-trip and receipt tampering.

## Boundaries

No model inference, cloud provider, credential, consent, send, spend or
deployment was used. Full G5 remains unqualified; prior deterministic
acceptance `28afe7248` and historical `111/123`, planner 5/5, goal router 1/2
and alignment gap 3.0 are unchanged.
