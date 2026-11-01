# Remaining work — tied to the original 12 goals

Identity: integrated candidate `f2e809ba5` (merge of
`codex/employee-execution-readiness` `5b72c6f6d` and
`codex/readme-feature-readiness` `a666c83ba`). Configuration: local, single
worker, `ATOM_PRODUCT_PROFILE=core`, controlled transport. Hosted deployment
and publication remain owner-deferred.

This list separates **completed mechanisms** from what a practically usable
integrated product still needs. It is not a claim that the goals are met.

| # | Goal | Completed mechanism | Missing user-visible behavior | Owner | Next executable action | Evidence required | External dependency |
|---|---|---|---|---|---|---|---|
| 1 | Employee + method + unfamiliar source, second domain | Two-domain deterministic acceptance; browser journey | — | — | Keep as regression | `two-domain-autonomous-journey*` | none |
| 2 | Teaching method/exception/qualification/format/protocol/correction/transfer | Composite teaching journey, correction + restart tests | — | — | Keep as regression | `employee-execution-06d80f834` | none |
| 3 | Unfamiliar columns/units; confirm/correct mapping; resume | Browser recovery 5/5 (ambiguous mapping, revision refusal) | — | — | Keep as regression | `assignment-recovery-browser` | none |
| 4 | Upload/connect **authorized** data and retrieve for work | Controlled local uploads; resource-boundary controls; connected catalog binding | **Live Microsoft connection/ingest through normal Settings/Data UI** never demonstrated on this candidate | Agent 1 | Run the connector qualification script against one existing authorized connection; ingest one workbook + one email attachment | `employee-execution-connector-*` (new) | Owner: confirm which Microsoft account/tenant may be used read-only; token must be currently valid |
| 5 | Large/multi-sheet workbooks, supported formulas, calculate with citations | **Closed by executed evidence**: 24-sheet workbook (547 materialized rows, 500 data rows), leading-zero IDs, blanks, formula text, cross-sheet `SUM`, edit → recalculation → dependent cells, export and restart/reopen (`employee-execution-large-workbook/`) | General Excel compatibility beyond the published subset; genuine workbook through the live connector (blocked by 4) | — | No further local action for the fixture; connector run after Part A authorization | `employee-execution-large-workbook/` | Owner: Microsoft read-only access for the live workbook |
| 6 | Canvas create/bind/calculate/edit/export/reload | Capability adapter + XLSX readback; atomic approval; clarification | — | — | Keep as regression | `canvas-capability/`, assessment evidence | none |
| 7 | Grounded selection, calculation and **assessment** | **Deterministic taught-rule judgment qualified**: V1 **18/18**, V3 **19/19**, safe abstention passed (`employee-execution-deterministic-judgment/`) | **User-facing rule authoring** is still manifest JSON; discretionary model judgment remains unqualified | Agent 1 | Guided rule editor or teach → proposed rules → user confirmation via the validated manifest endpoint | New rule-authoring evidence (UI) | Optional funded model for discretionary cases only |
| 8 | Editable DOCX/PPTX + email draft | Renderers, taught formatting, controlled draft/send path | Real provider send (see 11) | Agent 1 | Reuse the prepared payload and request live qualification | `employee-execution-autonomy-boundaries/` | Owner: send authorization for named account/recipient |
| 9 | User-created canvases inherit supported capabilities | Two differently shaped canvases share operations | — | — | Keep as regression | `employee-execution-06d80f834` | none |
| 10 | Long-running multi-source assignment; restart; changed teaching; cancellation; uncertain effect | Browser 5/5 + two-domain restart/resume + reconciliation verdicts | Multi-worker/soak explicitly outside the declared single-worker topology | — | Enforce one-worker operationally (documented), no multi-worker claim | `assignment-recovery-browser`, `employee-execution-autonomy-boundaries` | none |
| 11 | Approval binds exact payload; duplicate approval idempotent; changed payload needs fresh review | Payload-bound approval, atomic claim, duplicate prevention, reconciliation | **Real transport** not exercised; only the controlled outbox opts into standing authority | Agent 1 | Wire the real transport adapter behind the same grant/claim/reconcile contract, then request one authorized live test | `employee-execution-execution-boundaries/` + live run | Owner: account/recipient/artifact scope authorization; provider acceptance and recipient delivery are separate claims |
| 12 | Install/start/login, restart/recover | Clean-install and restart evidence; local launch script | **Local functionality is complete for this goal.** Hosted deployment and publication are a separate, deferred decision | — | — | `install-final.json`, `INTEGRATED_LOCAL_CANDIDATE` | Owner-deferred (not a local gap) |

## Additional open items from the latest verification

- **Unforced teaching interaction**: the long journey uses `fill(..., force=True)`
  and direct DOM opening, which does not prove an ordinary user can operate the
  form. An unforced smoke was attempted and the canvas page became CPU-bound
  after the Training panel opened (trace and screenshot in
  `employee-execution-training-actionability/`). Treat teaching-surface
  usability as **unproven** until it is reproduced and profiled on a stock
  build.
- **Post-repair journey**: executed on clean source `31ba9725e02a` and recorded
  in `employee-execution-integrated-local-journey-repaired/`; it is accepted as
  execution evidence, with the teaching-interaction caveat above.

## Genuine external dependencies (one consolidated request)

See `EXTERNAL_QUALIFICATION_REQUEST_2026-10-31.md` for Parts A (Microsoft
read-only) and B (one live send).



1. **Microsoft read-only access** for goal 4/5: which tenant/account, and
   confirmation that its token is current.
2. **Optional model access** for discretionary judgment only. The deterministic
   path is qualified without it; the frozen set must never be edited to fit a
   model.
3. **One authorized live send** for goals 8/11: account, recipient, payload
   class, attachment hash, reconciliation window.
4. **Hosted deployment** (goal 12) — explicitly deferred.

## What this list does not do

It does not add requirements beyond the original goals: no universal connector
coverage, no every-Excel-feature claim, no multi-worker certification. It also
does not treat an absent authorization as permission.