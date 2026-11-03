# Test results — G5 two-domain probe 80e3bd702

| Scope | Result |
|---|---|
| Frozen-source independent verifier probes | **20 passed** |
| Frozen-source focused typed-work/proof/adaptation suite | **124 passed** |
| Deterministic two-domain mechanism campaign | **4 passed** |
| Served quote smoke | **passed**, calculated **370.00** |
| Served two-domain evidence selection | industrial **pass**; procurement **negative** |
| Full held-out two-domain adaptive journey | **not established** |

## Served call detail

- Quote evidence selection: parsed `EmployeeWorkProposal`, model source.
- Quote typed work: parsed `WorkAdaptationProposal`, model source, adopted,
  executed to `370.00`.
- Procurement evidence selection: parsed `EmployeeWorkProposal` but the
  proposal mixed `source_id` and `action` on one read and omitted
  `invoice-v1`; production rejected it and fell back deterministically to
  `purchase-order` only.

## Not run

Invoice reconciliation, corrected-invoice waiting, supported bill preparation
and the final two-domain completion were not reached because procurement
source selection failed first. No retry or model substitution was performed.
