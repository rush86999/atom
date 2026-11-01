# Verified local workflows — honest demo guide

**Baseline:** accepted tag `accepted-local-2026-11-01-90pct`
(runtime `bec60978b`, evidence/docs `88bf413e8431`).

This guide demonstrates only what the accepted evidence supports. It is a local,
single-worker, controlled-provider demo.

## 15-minute first use

```bash
git clone https://github.com/rush86999/atom.git && cd atom
git checkout accepted-local-2026-11-01-90pct
make setup
make dev
```

In a second terminal:

```bash
make sample
```

Expected:

- The loader prints `status: passed`.
- Result is `232990.00` from `sample-workspace/sample_quote.csv`.
- A DOCX artifact is available under **Assignments**.
- The sample employee and editable lessons are under **Agents → Sample Quote
  Analyst → Training**.
- No cloud key, connector or live send is used.

If `make dev` is already using the default ports, this is the only setup path
needed. The sample is deterministic policy execution, not a model-quality demo.

## Story 1 — teach and correct

**What to show**

1. **Agents → Describe a job** and create an employee.
2. Open its **Training** panel and teach a document format and a business
   method.
3. Start quote work at standard scope.
4. Show a conflict/qualification refusal when the teaching is ambiguous or a
   required qualification is missing.
5. Start licensed work, confirm the unfamiliar mapping, and download the DOCX.
6. While the run waits, teach a more specific revised format.
7. Show that the active run keeps its accepted snapshot (Arial 11) while new
   revised-scope work uses the correction (Calibri 14).

**Accepted evidence**

- `docs/acceptance/evidence/complex_teaching_20261101/`
- `docs/acceptance/readme_feature_readiness_2026-11-01/evidence/campaigns/teaching-two-domain/campaign.json`

Sales: `550.00` active / `610.00` revised.
Grants: `14687.50` active / `18650.00` revised.

## Story 2 — unfamiliar workbook

**What to show**

1. Upload a workbook whose columns do not use the taught vocabulary.
2. Let the app surface the mapping candidates.
3. Confirm the compatible column in the UI.
4. Show the cited calculation and editable document.

**Accepted evidence**

`docs/acceptance/readme_feature_readiness_2026-11-01/evidence/campaigns/teaching-two-domain/grants/`
— a 25-row grant sheet mapped `Award Amount → Approved Amount` / `Awarded
Value`, with source citations and a DOCX.

## Story 3 — leave, restart, resume, no duplicate effect

**What to show**

1. Start a durable assignment with a correlated missing fact.
2. Close the browser and stop the backend.
3. Restart against the same world.
4. Open the same assignment, deliver the reply, approve the exact controlled
   payload, and download the artifact.
5. Retry/duplicate the resume and deliver a late reply; show the controlled
   outbox remains at exactly one line.

**Accepted evidence**

`docs/acceptance/readme_feature_readiness_2026-11-01/evidence/campaigns/long-run/`
— wait started `13:40:04Z`, resumed after the genuine two-hour mark
`15:43:27Z`, completed `15:50:05Z`, result `550.00`, one controlled effect.

The historical run proves elapsed waiting and recovery. The repaired-source
budget controls separately prove that working time is not erased by retries:
`evidence/campaigns/budget-repair/`.

## What is verified

- **111/123 frozen functional claims = 90.2%** within the documented local and
  controlled-provider scope.
- Complex teaching, correction, unfamiliar-data mapping, artifacts, durable
  waiting, restart/resume and bounded controlled actions.
- Checkout-verifiable evidence: 97 manifest entries, all tracked and hash
  matched from Git.

## What not to claim

- Universal reliability or every README surface.
- Qualified discretionary-model judgment. Deterministic taught methods and
  controlled providers are not model-quality evidence.
- Multi-worker execution or long soak behaviour.
- Broader live sending, autonomous live sending, connector breadth or
  recipient delivery beyond the accepted qualification.

Separately accepted under their recorded authorizations: **one specifically
authorized Outlook send** and **Microsoft read-only ingestion**. Those records
are closed and are not evidence of broader live-send reliability.

Hosted deployment and publication remain deferred.

## Branch policy

The accepted tag is an immutable baseline. First-use polish, documentation and
demo material live on the successor branch
`successor/first-use-polish-2026-11-01`. New features must not be added to the
accepted candidate or its evidence bundle; they belong on a separate successor
branch. Do not move historical tags. Hosted deployment, publication and broader
live effects remain deferred.
