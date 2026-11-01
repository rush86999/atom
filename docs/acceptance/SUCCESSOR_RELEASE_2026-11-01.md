# Recommended successor — 2026-11-01

**This is a recommended successor to the accepted baseline. It is not a new
acceptance and does not move the accepted tag or its evidence.**

## Link from the immutable baseline

| Ref | Value |
|---|---|
| Accepted baseline tag | `accepted-local-2026-11-01-90pct` |
| Accepted evidence/docs | `88bf413e843193cbe7a034028232b7e6f2b4e7f9` |
| Accepted runtime | `bec60978b03774f190d4e33d130a7fdf1fe60cd6` |
| Recommended successor branch | `successor/first-use-polish-2026-11-01` |
| Recommended successor tag | `successor-first-use-2026-11-01` |
| Successor relation | Direct descendant of the acceptance-record commit; accepted tag is unchanged |

Check out the recommended successor with:

```bash
git fetch --tags
git checkout successor-first-use-2026-11-01
```

The accepted baseline remains available at
`accepted-local-2026-11-01-90pct`. No historical tag was moved.

## What the successor contains

### Verified correctness retained

- Idempotent durable-wait budget accounting (each wait credited once by
  persisted identity; repeated/concurrent/restart retries do not duplicate
  credit).
- Terminal cancellation in the shared run projection.
- C2 harness corrections and the preserved historical two-hour closure.
- Accepted runtime `bec60978b` and its 111/123 claim bundle remain the
  correctness baseline.

### First-use fixes

- Launcher memory path: both `LANCEDB_URI` and `LANCEDB_URI_BASE` point inside
  the isolated world; no repository-shared memory fallback. The recorded smoke
  resolves `<world>/data/atom_memory/default_shared` and finds zero
  repository-shared path occurrences. Its dirty launcher state was disclosed
  and is now committed in `d8120737e`.
- Python prerequisite documented (`PYTHON=python3.11 make setup` when the
  default interpreter is outside 3.11–3.13).
- Port overrides keep the browser API base, CORS origin and host allow-list on
  the backend `make dev` actually started.
- First Assignments visit waits for the NextAuth token bridge and populates
  without a manual reload.
- Dev launcher no longer aborts on a one-line `.env.local`.
- README and demo guide now separate reproducible steps, historical acceptance
  evidence, and controlled versus separately authorized live qualifications.

## Measurement and target — keep these distinct

| Claim | Status |
|---|---|
| **Measured:** ~5 min 15 s with warm package caches | Setup, startup, sample job and browser access on one host; sample `232990.00` |
| **Target only:** 15-minute cold installation | Not measured; cold network/build time is not guaranteed |
| **Separate follow-up:** memory-path and first-visit smoke | Focused check at `d8120737e`; **not** a repeat of the entire installation |
| **Unchanged:** accepted tag and evidence | `88bf413e8431` and its 97-entry manifest remain intact |

The full first-use journey was measured at `8b1abd7e6`; the memory-path and
first-visit panel check was a later focused smoke at `d8120737e`. The full
install/sample job was not repeated after the memory-path fix because that fix
does not change the install or sample-job path.

## Verification notes

- `AssignmentPanel` suite: **4/4 passed** (regression checks).
- Both launcher scripts pass `bash -n` syntax checks.
- The browser journey supplies the first-login usability evidence; the four
  frontend tests are not a substitute for it.
- The accepted two-hour run remains elapsed-waiting/recovery evidence on its
  recorded source. The repaired budget controls separately establish budget
  enforcement.

## Unchanged boundaries

- One specifically authorized Outlook send and Microsoft read-only ingestion
  were previously accepted under their recorded authorizations and remain
  closed.
- Broader live sending, autonomous live sending, connector breadth and
  discretionary-model judgment remain unqualified.
- Hosted deployment remains deferred. The repository is already published on
  GitHub; a new release announcement or downloadable package is optional.
- No new broad campaign was run for this successor.

## Reproduce the accepted demo

```bash
git checkout successor-first-use-2026-11-01
make setup                 # PYTHON=python3.11 make setup if needed
make dev                   # add BACKEND_PORT/FRONTEND_PORT if busy
make sample                # same port overrides if used above
```

See `docs/demo/VERIFIED_WORKFLOWS.md` and
`docs/demo/FIRST_USE_TEST_2026-11-01.md`.
