# Generic source answers — finite contract checkpoint

**Successor branch:** `codex/generic-source-answer-20261107`
**Executed source:** `fb231c9962ab4660912afa865b1440e9194d652c` (clean).
**Stack base:** `7d38d2ac946ca8b4470bde8edd72ed00ef49497d` (the frozen
source-consumption branch). The source branch was not edited; this successor
is pushed separately and must be stacked on that base.

Work order read/executed:
`/private/tmp/brennan-brief/GENERIC_SOURCE_ANSWER_WORK_ORDER_20261107.md`.

## Contract implemented

- `AgentInformationAnswer` now accepts optional typed `source` alongside text;
  at least one meaningful text/source input is required. Exact job, wait,
  `correlation_id`, actor/workspace/tenant checks remain mandatory.
- Sources resolve through the existing `resolve_assignment_source` with public
  filesystem paths disabled, then read through the existing
  `document.text`/`dataset.read` readers with bounded material and a verified
  read receipt. Upload id/version, dataset identity, coverage and authority are
  retained.
- The accepted source id, version, content hash, display label and receipt are
  frozen in the same atomic durable HITL status claim. Source-only answers use
  a server-owned label; model prose is never authority.
- At resume/recovery the source is resolved/read again through the same
  authority/reader path; missing, revoked, foreign, stale or changed material
  refuses before model work. Duplicate exact source answers are idempotent;
  changed material refuses and never overwrites the snapshot.
- Generic receives bounded source content as explicitly untrusted evidence
  (`information_source` trusted context key), with no control/effect authority.
- Upload/filesystem paths alone never settle a wait; there is no global-upload
  hook. Text-only answers remain unchanged.
- UI adds one optional authorized-source picker on the displayed question,
  fetching the existing `/api/assignments/sources` inventory. The text answer
  remains; selection is bound to the exact current wait correlation.

No new engine/store/router/review lifecycle/budget API; no dependency install;
no live application model/provider/account/credential/send/spend/deploy.

## Focused actual results (bounded profile)

Fresh scratch DB/data/Lance/output, global gate serialization, `TESTING=1`:

| Log | Selection | Actual |
|---|---|---:|
| `backend-focused-12.log` | source-only valid same-job verified effect; wrong correlation; duplicate exact source; changed-material refusal; existing text wait/recovery contracts | **12 passed**, exit 0 |
| `ui-agent-job-wait-11.log` | all existing panel text journeys plus source-picker selection bound to exact wait | **11 passed**, exit 0 |

Executed/committed source is clean; the backend process reported
`source_id=fb231c9962ab revision=fb231c9962ab dirty=False`. The frontend used
the existing installed dependency tree via a wall-local symlink; no install or
download occurred.

## Explicit remaining verification limits

Local focused evidence does not claim the full work-order matrix. Root/CI must
independently verify at least:

- dataset-source valid twin (reader path implemented through existing
  `dataset.read`, but local valid fixture covers the uploaded document path);
- removed/revoked/foreign/stale source and current-authority-after-offline-gap
  for the Generic route specifically;
- source accepted before restart and after restart;
- requested output withheld until all required results verify, and one usable
  receipt-backed result on the same execution;
- the single ordinary UI source-selection episode (root-owned).

These are not claimed complete. TASK-WAIT-01/full app remain OPEN; no
self-acceptance. Root owns PR/CI/independent review/merge.
