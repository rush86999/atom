# Native-chat Learning ordinary-UI milestone at `e5d2fdb32`

- Source commit: `e5d2fdb323273a2436b39a6c224b14a116cd8bbe`
- Accepted learning commit: `33b8e99317bc0563b153d379f177a133c0a0a914`
- Captured at: `2026-11-10T06:09Z`
- Packet prepared at: `2026-11-10T06:23:51Z`
- Branch: `codex/web-learning-native-chat-20261110`
- Scope: **limited ordinary-UI milestone**, not whole-app or full-harness
  acceptance.

## What is supported

Retained checkpoints from the `a5lqiv_l` world support this actual sequence:

- ordinary signup and onboarding through the visible UI
- one selected typed `native_chat` source and the seeded student employee
- visible draft form -> real `POST` candidate create (`200`, `review_ready`)
- explicit visible Confirm -> `confirmed`
- explicit visible Promote -> `promoted`
- the same candidate remained promoted across a real backend stop/restart
  (`pid` changed, health `200`, source hashes unchanged)
- canonical SDK session / backend `/me` / DB identity checks, cookie
  encryption, HttpOnly, generation checks
- normal `get_agent_lessons` returned the exact lesson text, returned row id
  and provenance for candidate `lc-0f7e8850ce3a4eed` and lesson
  `76b60e582e504e7a9e90f7b68ade8660`
- root independent read-only SQLite proof corroborates owner/workspace/tenant,
  candidate presence, lesson id and lesson text

Lesson text: `When reporting a result, include evidence links.`

The fixture is a disclosed synthetic owned `ChatSession` plus user/assistant
rows and one scoped StudentAgent inserted through real SQL after signup. It is
not model chat generation, and this packet makes no model or GeneralAgent
inference claim.

## What failed and remains failed

The original overall browser verifier **FAILED**, not passed:

- 10 capture checks were false:
  `screenshot_draft`, `screenshot_confirmed`, `screenshot_promoted`,
  `screenshot_reload_after`, `ui_before_candidate_present`,
  `ui_before_list_lesson`, `ui_before_list_promoted_entry_id`,
  `ui_before_list_revision`, `ui_before_list_status`,
  `ui_before_visible_matches_list`.
- 131 other checks were true.
- The four safe region images are missing.
- The pre-restart candidate-list capture is missing.
- No image was manufactured or regenerated to fill those gaps.
- The original full failure screenshot is **not committed** because a synthetic
  identity is visible. It remains a private receipt only.

**Unknowns, not guesses:**

- The historical region-screenshot exception cause is unknown; the executed
  helper swallowed the exception. No strict-mode or two-`main` claim is made.
- The exact pre-restart list-capture cause is unknown; no response body was
  retained. No in-flight-selection claim is made.

A separate supplemental same-world capture was approved and executed once.
It **FAILED** at the ordinary reset page (`#password` timeout). The reset
token existed unused/unexpired and backend `verify-token` returned `200`, but
the page text and verify body were not captured. Cause is unknown. It made no
candidate/lesson writes: candidate events stayed at three and the lesson
config stayed at one entry.

## Separately preserved negatives

1. **Wrong helper DB mismatch** (`jecriakh`): helper imported `core.database`
   under `TESTING=1`, used `backend/test_integration.db`, and stopped at
   fixture seed. Learning product was not reached. Not a product failure.
2. **Correct missing-price refusal** (`nob5dlsj`): the prior quote fixture
   mentioned an unprovided “current price” resource; product correctly
   returned `needs_clarification` and disabled Confirm/Promote. This is a
   safety negative, not a product failure and not a positive episode. The gate
   was not weakened and the lesson was not swapped to fake readiness.
3. **Four accepted API negative controls** remain preserved in the earlier
   packets: quoted authority, empty authority, foreign owner read, foreign
   owner reject. Root recorded `4 passed in 4.76s`.

These are separate identities and are not relabeled as passing UI evidence.

## Source and controls

- All eight learning files are byte-identical at accepted `33b8e9931` and
  integrated `e5d2fdb32`; hashes are in `api/source_map.json`.
- Controlled API/SQLite/component controls already accepted are retained in
  `api/component_api_controls.json` and `logs/`: 13 native/API, 74 combined
  conversation-learning, 5 frontend, `tsc` and ESLint clean.
- Root proofs are copied under `root-proofs/`: independent durability readback,
  independent eight-file integration proof, and the controlled API acceptance.
- The historical harness bytes for the executed failed runs are **not
  archived**; only their recorded hashes are noted in `verification.json`.
  No matching archive is invented. The current prepared harness is not
  evidence of the historical run.

## Limits

- No claim that all browser checks passed.
- No claim of general lesson quality, model inference, full teaching
  completion, or GeneralAgent behavior.
- `ChatSession` remains user-global in the personal app; no per-workspace
  source isolation is claimed.
- Staleness revalidation is on review/load/promote touch, not a background
  watcher.
- Raw private world DB, auth material, env, mail and logs are not committed.
- No product edit, provider/model call, PR, merge or root CI/ledger edit.
