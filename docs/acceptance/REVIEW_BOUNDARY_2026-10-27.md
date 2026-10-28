# Review boundary repair — 2026-10-27

Base: `f8792bf42` (`whole-app/successor-f5f`), with the uncommitted review
boundary repair and the concurrent local-provider fallback repair in the
working tree. **No deployment.**

The captured failure this slice closes is the post-restart assessment whose
model block parsed correctly (right subjects, evidence and decisions) but
omitted `policy_ids`. It was refused by the validator rather than having the
single available policy ID attached on the model's behalf.

## 1. What changed

### Exact captured-response regression

`test_captured_missing_policy_ids_response_stays_rejected` replays the
captured `CX-9101/2/3` response and pins:

- three parsed candidate assessments;
- the exact subjects, row evidence and `REJECT/REVIEW/REVIEW` decisions;
- empty `policy_refs` on every candidate;
- `ok=False`, `completion=incomplete`;
- exactly three `missing_policy_ids` errors.

No code path attaches the only policy ID when the model omitted one.

### Output contract and transport schema

- `review_result.ReviewAssessmentModel` / `ReviewPayloadModel` require
  `subject_id`, `decision`, non-empty `evidence_ids`, non-empty
  `policy_ids`, non-empty `basis`, and `unresolved_requirements`.
- `review_output_schema()` exposes the schema to the existing structured-output
  facility; `generate_structured_review()` uses one structured call and
  serializes the model's `explanation` plus the fenced assessment block.
- The feature is opt-in (`ATOM_REVIEW_STRUCTURED=1`) because the local Ollama
  route measured here rejects `instructor` TOOLS mode; the default path keeps
  the same generation call and prompt contract. The mocked-transport test
  proves the outgoing schema/message contract without changing the model.
- The prompt now explicitly requires a non-empty `policy_ids` array copied
  from the supplied policy index, and repeats the final block requirement at
  the generation boundary.
- `build_review_result` remains the sole authority for subject, evidence and
  policy references even when transport validation is available.

### Policy revision semantics

The accidental global rule (“Policy entries are NEWEST FIRST; the first is
current and later entries are superseded”) is removed. The prompt now says:

- policy entries are independent standing instructions, not an ordered log;
- a correction is authoritative only when it rewrites the same policy ID in
  place (the existing PATCH teaching-point path);
- a newer unrelated lesson never invalidates an older applicable rule;
- genuinely conflicting applicable rules stay explicit in `basis` and/or
  `unresolved_requirements` rather than being silently resolved by order.

Controls cover both the prompt and a newer-unrelated-policy case.

### Sibling teaching at the review boundary

- Review lesson assembly now calls `get_agent_lessons(include_workspace=False)`:
  only the operating hire's own teaching can supply allowed decisions and
  policy IDs for this assessment.
- General workspace/sibling knowledge remains available to ordinary callers
  and the memory block; its label changed from “applies here too” to
  “workspace background only, not authority for this task”.
- `build_policy_index` still requires an exact decision-vocabulary match, and
  a control proves the captured sibling `FUND/HOLD/DECLINE`, price-list and
  freight lessons cannot enter the active review policy index.

### Requested fields stay grounded

`extract_field_requests` canonicalises “Ask Amount” to `price` for column
matching. The accepted contract now uses `extract_field_labels`, preserving
the ask's literal label. The captured Ask Amount task records
`requested_fields=["Ask Amount"]`, not `["price"]`.

### Freshness is an obligation only when requested

`record_read_outcome` spawns a live-source freshness successor only when the
read carried `freshness_requested=True` or an actual freshness verdict.
A snapshot assessment of an uploaded version no longer manufactures
“re-verify … against the live source” work. Ask/direct read lanes record the
fact; genuine refresh/compare turns keep their verdict and successor.

### Effective revisions

`accepted_inputs.source_version` is filled from the validated evidence
identity when the bound source did not supply it, and the review contract now
also exposes `policy_revision` (`teaching_revision`) and `source_revision`.

## 2. Verification

### Green bounded run (completed)

`docs/acceptance/evidence/whole_app_20261027/review_boundary_20261027/run_summary_20261027.json`
records a public-API run in an isolated scratch world with a real backend
restart:

| Stage | Decisions | Review | Revisions |
|---|---|---|---|
| Baseline before correction | `CX-9101 REJECT`, `CX-9102 REVIEW`, `CX-9103 APPROVE` | `ok=true` | source `8d54f69…`; policy `bc9da77…` |
| In-place correction, unfamiliar case | `CX-9201 REJECT`, `CX-9202 REVIEW`, `CX-9203 REVIEW` | `ok=true` | source `2f194e5…`; policy `524680c…` |
| After real restart, same unfamiliar case | `CX-9201 REJECT`, `CX-9202 REVIEW`, `CX-9203 REVIEW` | `ok=true` | same source/policy revisions |

Policy `671fdcb0f0ae41f0a5f7d0eb7db6d93c` was rewritten in place; the
correction changed 10000+ from APPROVE to REVIEW. The run used
`llama3.1:8b` through the registered local Ollama route with
`ATOM_CHAT_STREAMING=false` and `ATOM_REVIEW_STRUCTURED=0`.

The green run did not need the block-recovery retry: baseline and restart
replies carried `review_result` fences; the unfamiliar reply used a `json`
fence with the same schema.

> The green run's raw response files were later overwritten by a separate
> diagnostic probe. `run_summary_20261027.json` is the authoritative green
> record; the probe is preserved under `probe_20261027/` and is not counted
> as a pass.

### Separate diagnostic probe (not counted as a pass)

`probe_20261027/` preserves a later bounded probe on the same fixture. It
reproduced the local model's format instability:

- baseline certified but produced wrong substantive labels
  (`REVIEW/APPROVE/APPROVE` instead of `REJECT/REVIEW/APPROVE`);
- after the in-place correction the unfamiliar case certified with the
  correct labels;
- the post-restart repeat returned no parseable block
  (`missing_structured_review` + missing decisions), so it was safely refused.

This probe is evidence for the residual generation-reliability item, not for
the green boundary result.

### Unit / contract controls

Focused suites pass:

- `tests/test_review_result.py`
- `tests/test_review_contract.py`
- `tests/test_job_work_ledger.py`
- `tests/test_review_retrieval_objective_resume.py`
- `tests/test_review_completion_contract.py`
- `tests/test_workspace_lesson_recall.py`
- `tests/test_launch_journey_captured.py`
- `tests/test_table_selection.py`
- `tests/test_core_domain_independence.py`
- `tests/test_content_read_findings_chain.py`
- `tests/test_pending_file_task_resume.py` (apart from the unrelated
  pre-existing failures noted below)

The provider fallback repair is covered by
`TestNonStreamingAbsoluteFallback` in
`tests/test_f5_local_planning_eligibility.py`.

## 3. Report by stage

| Stage | Result |
|---|---|
| **Generation** | Green run: baseline, corrected unfamiliar and post-restart generations produced the schema block. Probe: restart repeat lost the block; safely refused. |
| **Parsing** | Captured response parses three assessments. Missing block is distinguished from a produced-but-refused block. Fenced `review_result`, schema-carrying `json`, and bare structured objects are accepted; ambiguous/unrelated JSON is not. |
| **Reference validation** | Exact subjects; evidence bound to subject, source identity and retrieval execution; policy IDs must resolve in the supplied index. Captured missing-`policy_ids` response remains rejected with the precise codes. |
| **Substantive judgment** | Green run's corrected unfamiliar case follows the corrected rule (12000 → REVIEW). Probe baseline shows model judgment can still be wrong despite a structurally valid block; that is reported separately from validation. |
| **Persistence** | Green run: response, persisted review and fresh history agree; source and policy revisions are recorded and survive restart. Probe: failed post-restart generation leaves the deterministic rows and records the refusal, not a fabricated decision. |

## 4. Residual

- Restart generation reliability on the local 8B model remains mixed
  (CR-019 is not upgraded by this slice).
- The broader cross-domain judgment item (CR-009) is not upgraded.
- The structured-output path is opt-in; enabling it for a provider requires
  proving that provider's instructor/JSON support first.
- Three unrelated tests fail in this worktree; two
  (`test_non_price_fields_flow_through_the_same_pipeline`,
  `test_generality_contrast_fixtures`) also fail at baseline `2f3e0cd38`.
  The third reproduces with this slice's tracked diff stashed and is not
  caused by this repair.
