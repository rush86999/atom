# Normal-app UI G5 campaign — source cf840c14d

Status: **both employee objectives started from the normal Assignments UI,
using ordinary login, UI uploads and multi-source selection. Quote completed
at 370.00; procurement asked an actionable question, survived a real process
restart while waiting, and the same waiting run recovered to 270.00 after the
invoice source answer. Full general G5 remains unqualified.**

## Source and serving identity

| Item | Value |
|---|---|
| Branch | `codex/brennan-full-app-20261102` |
| Product source | `cf840c14d51628cf45066e7ee74006727ae6e0c5` |
| Backend | `/private/tmp/atom-full-app/backend`, normal `main_api_app` |
| Frontend | `next build --webpack`, `NEXT_PUBLIC_API_URL=http://127.0.0.1:8085` |
| World | `backend/data/acceptance_worlds/g5-ui-final-20261103` |
| Model | `ollama/llama3.1:8b`, 16k context, pinned |
| Auth | normal admin login at `/login` |
| Raw traces | `attempts.jsonl` |

No internal-path flag, fixed-user dependency override, supplied rows, StepPatch
JSON or final plan was used. Sources were uploaded through the Assignments UI
input and selected through the UI source checkboxes. Teaching terms were
entered in the UI teaching-terms field.

## Quote objective — 370.00

- Uploaded `price-book.xlsx` with unfamiliar `Product / Units / ApprovedCost /
  Currency` headers through the UI.
- Selected the workbook as the only source; supplied taught currency/freight/tax
  terms; started the employee-decided objective.
- The model selected evidence and a typed `quote_calculation`; the executor
  completed **370.00 USD**, business outcome `satisfied`.
- Evidence: `quote-completed.png`, `quote-page.txt`.

## Procurement objective — question, restart, answer, 270.00

- Uploaded purchase-order and receiving JSON documents through the UI.
- Selected exactly those two sources. The model asked the actionable question
  naming the missing invoice evidence for the purchase order.
- The real backend/frontend processes were stopped and relaunched against the
  same scratch world while the job was waiting. After reload/login, the open
  question was still present (`question-after-restart.png`).
- Uploaded the invoice through the UI; selected it in the answer-source control
  and clicked “Use selected source”. The same waiting run resumed, the model
  chose `invoice_reconciliation`, and the executor completed **270.00 USD**,
  business outcome `satisfied`.
- Evidence: `procurement-question-before.*`, `procurement-question-after-restart.*`,
  `procurement-completed.png`, `procurement-final.txt`,
  `procurement-summary.json`.

## Cancellation

The UI Cancel control produced terminal `cancelled` on an independent blocked
assignment (`cancellation.png`, `cancellation.txt`).

## Controlled provider-lost confirmation

Agent 2’s normal-application controlled effect evidence remains separately
recorded at `employee_g5_uncertain_normal_app_9f3c3b8dd`: provider accepted,
confirmation lost, process restart, same operation reconciled, exactly one
effect, no resend. It is not relabelled as live-provider evidence.

## Boundaries

The requested objectives asked for exact totals, not a document or bill
artifact, so the displayed verified calculation is the requested output. No
live/cloud provider, credential, consent, send, spend or deployment was used.
Historical `111/123`, planner 5/5, goal router 1/2 and alignment gap 3.0 are
unchanged.

## Checkout packaging (successor)

- The six text/log artifacts named by the manifest are force-tracked from the
  original local browser run without regeneration: `quote-page.txt`,
  `procurement-question-before.txt`, `procurement-question-after-restart.txt`,
  `procurement-final.txt`, `cancellation.txt`, `server.log`. The legacy
  `.gitignore` patterns (`*.txt`, `*.log`) caused them to be omitted from the
  first evidence commit.
- Frontend build identity: Next.js `BUILD_ID=Sqe_aXJSKB66cAJQ3fniG`, built
  with `next build --webpack` and `NEXT_PUBLIC_API_URL=http://127.0.0.1:8085`.
- First process identity: backend pid `71839`, frontend pid `71853`,
  source `cf840c14d516`, world
  `g5-ui-final-20261103`.
- Browser-recovery process identity: backend pid `72066`, frontend pid
  `72085`, same source and world. The procurement question survived this
  restart and run `303d5db2-9727-4473-bc31-b66fcbac3ce9` recovered to 270.00.
- Evidence remains at the original `cf840c14d` execution identity. The later
  `637a6e178` extraction-identity repair is a successor source, not part of
  this browser run and not relabelled here.
