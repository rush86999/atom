# Remaining work — tied to the original 12 goals

Identity: integrated candidate `bc164fb96632` (guided deterministic-rule
authoring; the post-repair journey and 24-sheet evidence executed on
`31ba9725e02a`). Configuration: local, single worker,
`ATOM_PRODUCT_PROFILE=core`, controlled transport. Hosted deployment and
publication remain owner-deferred and are not completion gates.

Overall completion awaits only the two current-candidate live qualifications:
Microsoft read-only connection/ingestion/agent retrieval, and the specifically
authorized Outlook send with exact account, recipient, payload/attachment and
reconciliation scope. Hosted deployment is deferred, not a completion gate.
Accepted local UI, workbook, deterministic-rule and durable-execution evidence
is closed; do not repeat those campaigns without a relevant source or product
change.

**Verifier closure (2026-11-01):** 248 entries across 27 manifests matched;
four frontend tests across two suites passed; the unforced teaching and guided
rule-authoring findings are closed within the tested scope. The guided smoke's
coordinate-click fallback means keyboard/accessibility coverage is not claimed.

This list separates **completed mechanisms** from what a practically usable
integrated product still needs. It is not a claim that the goals are met.

| # | Goal | Completed mechanism | Missing user-visible behavior | Owner | Next executable action | Evidence required | External dependency |
|---|---|---|---|---|---|---|---|
| 1 | Employee + method + unfamiliar source, second domain | Two-domain deterministic acceptance; browser journey | — | — | Keep as regression | `two-domain-autonomous-journey*` | none |
| 2 | Teaching method/exception/qualification/format/protocol/correction/transfer | Composite teaching journey, correction + restart tests, unforced stock-build teaching smoke 9/9 | — | — | Keep as regression | `employee-execution-06d80f834`, `employee-execution-unforced-teaching/` | none |
| 3 | Unfamiliar columns/units; confirm/correct mapping; resume | Browser recovery 5/5 (ambiguous mapping, revision refusal) | — | — | Keep as regression | `assignment-recovery-browser` | none |
| 4 | Upload/connect **authorized** data and retrieve for work | Controlled local uploads; resource-boundary controls; connected catalog binding | **Live Microsoft connection/ingest through normal Settings/Data UI** never demonstrated on this candidate | Agent 1 | Run the connector qualification script against one existing authorized connection; ingest one workbook + one email attachment | `employee-execution-connector-*` (new) | Owner: confirm which Microsoft account/tenant may be used read-only; token must be currently valid |
| 5 | Large/multi-sheet workbooks, supported formulas, calculate with citations | **Closed by executed evidence**: 24-sheet workbook (547 materialized rows, 500 data rows), leading-zero IDs, blanks, formula text, cross-sheet `SUM`, edit → recalculation → dependent cells, export and restart/reopen (`employee-execution-large-workbook/`) | General Excel compatibility beyond the published subset; genuine workbook through the live connector (blocked by 4) | — | No further local action for the fixture; connector run after Part A authorization | `employee-execution-large-workbook/` | Owner: Microsoft read-only access for the live workbook |
| 6 | Canvas create/bind/calculate/edit/export/reload | Capability adapter + XLSX readback; atomic approval; clarification | — | — | Keep as regression | `canvas-capability/`, assessment evidence | none |
| 7 | Grounded selection, calculation and **assessment** | **Deterministic taught-rule judgment qualified**: V1 **18/18**, V3 **19/19**, safe abstention passed (`employee-execution-deterministic-judgment/`). **Guided rule authoring** now builds, saves and assesses rules through the normal canvas panel without manifest JSON (`employee-execution-guided-rule-authoring/`) | Discretionary model judgment remains unqualified; guided rules cover the validator's supported vocabulary, not arbitrary prose | — | Keep as regression; optional funded model only for discretionary cases | `employee-execution-deterministic-judgment/`, `employee-execution-guided-rule-authoring/` | Optional funded model for discretionary cases only |
| 8 | Editable DOCX/PPTX + email draft | Renderers, taught formatting, controlled draft/send path | Real provider send (see 11) | Agent 1 | Reuse the prepared payload and request live qualification | `employee-execution-autonomy-boundaries/` | Owner: send authorization for named account/recipient |
| 9 | User-created canvases inherit supported capabilities | Two differently shaped canvases share operations | — | — | Keep as regression | `employee-execution-06d80f834` | none |
| 10 | Long-running multi-source assignment; restart; changed teaching; cancellation; uncertain effect | Browser 5/5 + two-domain restart/resume + reconciliation verdicts | Multi-worker/soak explicitly outside the declared single-worker topology | — | Enforce one-worker operationally (documented), no multi-worker claim | `assignment-recovery-browser`, `employee-execution-autonomy-boundaries` | none |
| 11 | Approval binds exact payload; duplicate approval idempotent; changed payload needs fresh review | Payload-bound approval, atomic claim, duplicate prevention, reconciliation | **Real transport** not exercised; only the controlled outbox opts into standing authority | Agent 1 | Wire the real transport adapter behind the same grant/claim/reconcile contract, then request one authorized live test | `employee-execution-execution-boundaries/` + live run | Owner: account/recipient/artifact scope authorization; provider acceptance and recipient delivery are separate claims |
| 12 | Install/start/login, restart/recover | Clean-install and restart evidence; local launch script | **Local functionality is complete for this goal.** Hosted deployment and publication are a separate, deferred decision | — | — | `install-final.json`, `INTEGRATED_LOCAL_CANDIDATE` | Owner-deferred (not a local gap) |

## Additional open items from the latest verification

- **Unforced teaching interaction**: **passed on the stock production build**
  at clean `bc164fb96632` (9/9 checks, `employee-execution-unforced-teaching/`).
  The lesson was typed without `force=True`, the optional fields were opened
  with a click, and the lesson survived reload. The earlier blocked run in
  `employee-execution-training-actionability/` used a string-retargeted build
  and is preserved as historical; its own limits note called for exactly this
  stock-build rerun.
- **Guided deterministic-rule authoring**: **passed on the stock production
  build** at clean `bc164fb96632` (13/13 checks,
  `employee-execution-guided-rule-authoring/`): field mapping, editable fields,
  ordered rules, server validation, deterministic assess and exact-content
  approval all through the ordinary panel. The raw manifest remains an
  Advanced path only.
- **Post-repair journey**: executed on clean source `31ba9725e02a` and recorded
  in `employee-execution-integrated-local-journey-repaired/`; it is accepted as
  execution evidence. Teaching usability is separately confirmed on the stock
  build (`employee-execution-unforced-teaching/`).

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