# Verified local workflows — honest demo guide

**Baseline:** accepted tag `accepted-local-2026-11-01-90pct`
(runtime `bec60978b`, evidence/docs `88bf413e8431`).

This guide separates three things that are easy to blur together:

| Kind | What it means |
|---|---|
| **Reproduce now** | Commands a new user can run from this checkout today |
| **Historical accepted evidence** | Recorded runs on the accepted source; not rerun by following this guide |
| **Controlled vs authorized live** | The demo uses controlled local effects; the separate accepted Outlook send and Microsoft read-only qualification are not repeated |

## First-use target — 15 minutes

**15 minutes is the cold-install target.** A fresh-worktree run on this host
measured **~5 min 15 s** with warm package caches on this host. The verified **13 seconds** measures only `make sample`
after the backend is already running; it does not include dependency
installation, the frontend build or login. See
[`FIRST_USE_TEST_2026-11-01.md`](FIRST_USE_TEST_2026-11-01.md).

Reproduce now from the branch that carries this guide:

```bash
git clone https://github.com/rush86999/atom.git && cd atom
git checkout successor/first-use-polish-2026-11-01
make setup                 # install dependencies, generate backend/.env
make dev                   # backend :8001 + frontend :3001
```

Python **3.11–3.13** is required. If the default `python3` is newer:

```bash
PYTHON=python3.11 make setup
```

If ports `8001`/`3001` are already in use, the same override must be used for
both processes so the browser talks to the backend `make dev` actually started:

```bash
BACKEND_PORT=8101 FRONTEND_PORT=3101 make dev
# second terminal:
make sample PORT=8101 FE_PORT=3101
```

Expected from the verified sample job:

- The loader prints `status: passed`.
- Result is `232990.00` from `sample-workspace/sample_quote.csv`.
- A DOCX artifact is available under **Assignments**.
- The sample employee and editable lessons are under **Agents → Sample Quote
  Analyst → Training**.
- No cloud key, connector or live send is used.

The sample is deterministic policy execution, not a model-quality demo.

## Historical accepted evidence

These are recorded runs on the accepted source. They are evidence for the
accepted milestone, not steps this demo repeats.

### Teach and correct

1. **Agents → Describe a job** and create an employee.
2. Open its **Training** panel and teach a document format and a business
   method.
3. Start quote work at standard scope.
4. Show a conflict/qualification refusal when teaching is ambiguous or a
   required qualification is missing.
5. Start licensed work, confirm the unfamiliar mapping, and download the DOCX.
6. While the run waits, teach a more specific revised format.
7. Show that the active run keeps its accepted snapshot (Arial 11) while new
   revised-scope work uses the correction (Calibri 14).

Evidence:

- `docs/acceptance/evidence/complex_teaching_20261101/`
- `docs/acceptance/readme_feature_readiness_2026-11-01/evidence/campaigns/teaching-two-domain/campaign.json`

Sales: `550.00` active / `610.00` revised.
Grants: `14687.50` active / `18650.00` revised.

### Unfamiliar workbook

1. Upload a workbook whose columns do not use the taught vocabulary.
2. Let the app surface the mapping candidates.
3. Confirm the compatible column in the UI.
4. Show the cited calculation and editable document.

Evidence:
`docs/acceptance/readme_feature_readiness_2026-11-01/evidence/campaigns/teaching-two-domain/grants/`
— a 25-row grant sheet mapped `Award Amount → Approved Amount` / `Awarded
Value`, with source citations and a DOCX.

### Leave, restart, resume, no duplicate effect

1. Start a durable assignment with a correlated missing fact.
2. Close the browser and stop the backend.
3. Restart against the same world.
4. Open the same assignment, deliver the reply, approve the exact controlled
   payload, and download the artifact.
5. Retry/duplicate the resume and deliver a late reply; show the controlled
   outbox remains at exactly one line.

Evidence:
`docs/acceptance/readme_feature_readiness_2026-11-01/evidence/campaigns/long-run/`
— wait started `13:40:04Z`, resumed after the genuine two-hour mark
`15:43:27Z`, completed `15:50:05Z`, result `550.00`, one controlled effect.

The historical run proves elapsed waiting and recovery. The repaired-source
budget controls separately prove that working time is not erased by retries:
`evidence/campaigns/budget-repair/`.

## Controlled effects vs separately authorized live qualifications

- This demo uses the **controlled outbox** and local controlled providers. It
  performs no live send and no connected-system write.
- Separately, **one specifically authorized Outlook send** and **Microsoft
  read-only ingestion** were previously accepted under their recorded
  authorizations. Those qualifications are closed and are not repeated here.
- **Broader live sending, autonomous live sending, connector breadth and
  recipient delivery beyond that qualification remain unqualified.**

## What is verified

- **111/123 frozen functional claims = 90.2%** within the documented local and
  controlled-provider scope.
- Complex teaching, correction, unfamiliar-data mapping, artifacts, durable
  waiting, restart/resume and bounded controlled actions.
- Checkout-verifiable evidence: 97 manifest entries, all tracked and hash
  matched from Git at the accepted evidence commit.

## What not to claim

- Universal reliability or every README surface.
- Qualified discretionary-model judgment. Deterministic taught methods and
  controlled providers are not model-quality evidence.
- Multi-worker execution or long soak behaviour.
- The unqualified live-send and connector breadth listed above.
- Hosted deployment or publication.

## Branch policy

The accepted tag is an immutable baseline. First-use polish, documentation and
demo material live on `successor/first-use-polish-2026-11-01`. New features must
not be added to the accepted candidate or its evidence bundle. Do not move
historical tags.
