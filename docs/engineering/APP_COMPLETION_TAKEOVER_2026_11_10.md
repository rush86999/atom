# Atom app completion — takeover reference (2026-11-10)

## Read this first

This is a continuity checkpoint, not app acceptance. The owner reports only 8% Codex usage remaining. Conserve root/model usage: use the two existing native OpenCode Go DeepSeek Flash sessions for implementation; model-free scripts for CI observation. Do not create duplicate agents or repeatedly rerun accepted campaigns. This file is a dated snapshot: re-read current Git, processes, CLI session state and GitHub before acting.

The complete objective remains all original **143 claims / 18 goals**, not a smaller core release. Canonical goals: [APP_GOALS_INDEX.json](APP_GOALS_INDEX.json). Preserve its original goal_catalog and explicit_user_requirements. Root acts as independent verifier, senior engineer and product manager. Single tenant; web first/mobile last. Graduation destination is unrestricted autonomy with domain exceptions, not permanent reduction of the goal. Historical 111/123, planner5/5, goal-router1/2 and alignment3.0 remain unchanged.

## First five actions

1. Read this file, repo AGENTS.md/CLAUDE.md and local notes/AGENT_COORDINATION.md. Do not clean/reset the root worktree.
2. Run `python3 /private/tmp/atom-agent-cli/root_native_session_snapshot.py`. Inspect actual processes and `native_worker_state.session_active`; a quiet stdout file is NOT a stopped worker.
3. Inspect `/private/tmp/atom-agent-cli/heavy-test-gate.json` and its actual PID. Existing tests/browser work are serialized. Do not kill/restart a live gate owner or duplicate queued tests.
4. Read final permanent graduation gate result at `/private/tmp/root-graduation-final-permanent-gate-20261110-31ub0c6n/review.json` when it exists, and the approvals-copy test log below. Until then these are pending, not passed.
5. Collect native email repair and graduation UI outcomes. Finish/fix concrete negatives, independently review, push coherent checkpoints, submit PRs and follow exact-head CI. Do not end after preparation or wait for owner prompting when independent authorized work is available.

## Current Git and PRs

- Last verified remote main: `0d5132c2e060a5f2ac338bca143c5e138e607658` (PR824). All12 post-merge Actions were verified green. Fetch again before relying on this identity.
- Dirty historical root repo `/Users/rushiparikh/projects/atom`: do NOT stage others' work. Main development is in isolated worktrees below.
- PR829: https://github.com/rush86999/atom/pull/829 — draft, exact head `7fb2645c9f86c696b104bcfe62f4a8ed5e276a64`. All13 required checks passed, but **HOLD MERGE** for legacy nested-email overwrite repair. Body records this explicitly.
- PR826 and827 retained as drafts, not independently merged; combined829 includes them. PR828 closed/superseded: unchanged CI test-key line reintroduced in history caused scanner incident34917391. Clean829 has identical final tree and green scanner. No waiver/history rewrite. Close old drafts only after accepted successor actually merges.
- PR829 worktree `/private/tmp/atom-web-office-export-reviewed-delivery-20261110`, branch `codex/web-office-email-personal-clean-delivery-20261110`.
- Root graduation worktree `/private/tmp/atom-web-graduation-reviewed-delivery-20261110`, branch `codex/web-graduation-reviewed-delivery-20261110`; last committed code `f8155821f2142a49e1c0cdd61bcc32976297341b`. No graduation PR yet.

## Native CLI workers (resume these, do not clone sessions)

Binary `/Users/rushiparikh/.opencode/bin/opencode`; configured model `opencode-go/deepseek-v4.1-flash`. Recent recorded cost0; no observed quota/auth failure. Use configured GLM fallback only after actual quota/auth evidence; discover actual installed/configured model/CLI rather than inventing ZCode flags or assuming desktop login proves CLI works. Never dump credential configs.

### Graduation ordinary UI worker

- Session `ses_e3d4a9359ffeGvQQH64gpzd8Is`.
- Worktree `/private/tmp/atom-web-graduation-qualification-join-20261110`, branch `codex/web-graduation-ordinary-ui-20261110`.
- Frozen product/source `6da3374abd2fdd2d88df5cfae1635f4d495301d8` (runtime f3/cef); do NOT relabel browser as later DB/replay repairs.
- Supervisor prefix `/private/tmp/atom-agent-cli/root-graduation-ordinary-ui-20261110`; original native PID27766, recheck actual state.
- Driver `scripts/acceptance/browser_graduation_qualification_ui.py`; logs `/private/tmp/grad-ui-run5.log`, `grad-ui-run6.log`; most recent output `/private/tmp/atom-graduation-ordinary-ui-1794315381/journey.json`.
- Original environment/onboarding failures preserved. Run5 onboarding modal intercepted Teach. Run6 reached real pending qualification, Approvals displayed rubric/task/output, review produced receipt `qualification:9a19f509-86a2-4770-a016-4f913e25542d`, valid state/no stale pending; **then failed: no enabled promote control after valid receipt**. Notification null, no completed UI promotion claim.
- Root steered: preserve negatives, inspect retained readiness/agent state; continue SAME retained world/agent through supported wizard, no DB/API promotion/onboarding shortcut, no fresh full-world campaign merely to hide a failure. Do not edit active product source; report actual product gap if present.
- Controlled work/output seeds are disclosed fixtures, NOT fresh model competence. Never seed qualification receipt, approved review or promoted tier. No send/provider/model/live DB.

### Email compatibility repair worker

- Session `ses_e3d5d4851ffeY0fe8DjW2a6fkr`.
- Worktree `/private/tmp/atom-goal11-office-browser-20261110`; current branch `codex/email-normalizer-legacy-draft-precedence-20261110` from evidence commit `013209bfab6d4d48e1b377e5781ad1be33f12b94`.
- Current resumed supervisor prefix `/private/tmp/atom-agent-cli/root-email-legacy-final-followthrough-20261110`, supervisor PID39403 at dispatch (recheck).
- Runtime WIP: `backend/core/chat_draft_classifier.py` general normalizer resolves present top-level fields before nested draft (including explicit empties), refreshes nested view/preserves provenance. `backend/tools/canvas_crud_tool.py` avoids read-side resurrection of cleared current fields from stale details.draft. Tests: classifier, shared writer, new `test_email_legacy_draft_precedence.py`.
- Root found real compatibility gap in original browser negative; do NOT dismiss it as harness-only just because ordinary-shape seed passes. Historical nested shape is explicitly supported by normalizer.
- First gate `/private/tmp/email-normalizer-bounded-gate.log`: 110pass/2fail, preserved. Worker fixing failures and running its own follow-through; pending until actual exit/receipt.
- WIP packet `docs/acceptance/evidence/email_legacy_draft_precedence_1d762c2f3/`. Wait coherent source/evidence push, inspect changed bytes, run decisive independent boundary control, integrate829 and reset exact-head CI. No Send/provider/browser replay is authorized for this repair slice.

## Graduation implementation and latest verification

Feature requires exact scoped reviewed actual task/output before upward maturity by default. Existing GraduationExam/HITL/Intervention/PromotionHistory/runtime policy/CAS, not parallel stores. Experience/transport/schema/grounding support alone is not capability success. Owner exceptions must be explicit exact-agent/reason-bound, never counted as qualification. All upward writers share gate; legacy history/passed flag alone fails. Public promote notification is awaited after commit; do not overclaim notification parity across every internal writer.

Recorded progression:
- `f3c284aaee856220d44e6c41e74806542b1f4ffb`: final21 independent cases passed,15runtime source hashes matched. Packet main integration at6da has43/43 Git checks.
- `918e7a17c`: root SAVEPOINT caller-work repair. Original actual promotion probe2failed/2passed: nested commit/rollback cleared marker and promotion committed unrelated caller User edit. Repaired unchanged4/4; permanent110/110 same-source scratch gate.
- `f8155821f`: root promotion replay repair. Commit result included last_exam_id/promotion_count but replay used old state material; verified commit replay incorrectly returned503. Shared promotion material now used on commit/replay. Changed receipt/count negatives refute. Focused8/8 pass, same-source.
- Old manual promotion tests migrated: explicit exact-agent owner exception only for receipt/CAS tests; unit adapters assert shared writer, not retired direct history writes. Added missing-qualification refusal twins; no production gate weakened.

Important scratch proofs:
- Original savepoint negative `/private/tmp/root-graduation-savepoint-independent-20261110-z9zrd6rp/review.json`.
- Fixed4 `/private/tmp/root-graduation-savepoint-independent-20261110-c6ytt21i/review.json`.
- Permanent110 `/private/tmp/root-graduation-delivery-gate-20261110-858l5jzx/review.json`.
- Broad initial `/private/tmp/root-graduation-savepoint-consumers-20261110-nr3iizzq/review.json`:163pass/11fail. Seven known training failures match main; remainingfour reproduce on pre-savepoint6da `/private/tmp/root-graduation-pre-savepoint-four-baseline-20261110-oy3dfl37/review.json`.
- Adapted6 `/private/tmp/root-graduation-adapted-six-controls-20261110-xg2s2ldc/review.json`:1fail/5pass exposed real replay defect.
- Fixed8 `/private/tmp/root-graduation-adapted-eight-controls-20261110-pgqtfva2/review.json`:8pass/same-source.
- Follow-through21 `/private/tmp/root-graduation-review-followthrough-controls-20261110-uszuvlok/review.json`: tests21pass, BUT same_source=false because root added CI controls/docstring while queued. Runner exits2. Preserve as supporting only, **not frozen-source acceptance**.
- Final combined runner `/private/tmp/root-run-graduation-final-permanent-gate-20261110.py`; world `/private/tmp/root-graduation-final-permanent-gate-20261110-31ub0c6n/`, root exec handle53642. Expected121 controls (73qualification/assessment/notification+13transaction+8promotion+27CI). Was queued/live at handoff. Must inspect actual result, not assume count/pass.
- Approvals-copy Jest process41339, log `/private/tmp/root-graduation-approvals-copy-gate-20261110.log`: pending. Existing deps symlink, no install.

Root dirty WIP (DO NOT discard):
- `.github/workflows/ci.yml`, `backend/tests/fixtures/ci_backend_additions.json`: additive permanent promotion selectors, preserve original immutable CI ledger/all jobs.
- `backend/tests/test_caller_transaction_ownership.py`:13 real SQLAlchemy controls, new3 cover begin_nested implicit flush, Session.commit/close with nested work.
- `backend/core/agent_decision_write_service.py`: docstring only after f815 clarifies flushed writes are conservatively caller-owned; owned parameter excludes only pending unflushed ORM objects.
- `frontend-nextjs/pages/approvals.tsx`: screenshot exposed old walkthrough promising automatic promotion after3sessions. Root changed copy to readiness+actual evidence+qualification review+successful promotion; no backend behavior. Frozen6da browser keeps old screenshot/source identity.
- `docs/acceptance/evidence/graduation_savepoint_ownership_20261110/`: retained negative/positive summaries, pending classification additions.
Private safety copy `/private/tmp/brennan-brief/root-graduation-uncommitted-20261110.patch` was captured before this reference; later changes may not be in it. Current worktree is authoritative; never blindly apply patch over it.

Independent native review: `/private/tmp/savepoint-ownership-independent-review-20261110.md`. Ordinary nested commit/rollback/close transfer correct; noted missing3controls (now added). `owned` flushed work conservatively classified unrelated; no ordinary false-negative found. Exotic savepoint-inside-flush not observed; do not claim universal proof. Production begin_nested caller contribution_credit; confidence writer owns agent but must not commit unrelated work.

## Accepted bounded Office/email browser evidence

- Product `1d762c2f3daee7746cf2430cd3ae37e8971364f7`, tree parity clean829 verified for actual served files.
- World `office_ordinary_browser_1d762c2f3d_1794309563`, retained run `run-b25cb62b465c`. Marked canonical local world; no arbitrary deletion.
- Office packet `docs/acceptance/evidence/office_email_ordinary_browser_1d762c2f3/`, evidence `ca1bfb2b6`:29/29 strictGit (9sources20artifacts). Normal NULL/NULL bootstrap Personal admin; UI DOCX/PPTX output, UI content edit/current DOCX download. Current body/table9/8 and no oldvalue; UI/API/download hashes matched. Root rendered actual DOCX and visually checked readability. Initial detached Save button timeout preserved; same-run continuation read durable autosave, not duplicate edit. Owner servers stopped.
- Ordinary email packet `docs/acceptance/evidence/email_draft_ordinary_browser_1d762c2f3/`, evidence013209bfa:14/14 Git artifacts verified. Four UI autosavePUT200/verified; current To/clearedCc/subject/body match publicGET/currentaudit/freshbrowsercontext. APIseed disclosed, no UIcreate claim; zero sendrequests. Earlier legacy-nested negative is real compatibility boundary now under repair; do not erase.
- Neither packet proves wholeGoal11/general Office quality/model competence.

## Safety, resources and commands

- NEVER run adhoc scripts on live devDB. Set TESTING=1, PYTEST_CURRENT_TEST plus explicit DATABASE_URL and scratch data/office paths **before imports**. Read-only SQLite must use URI mode=ro (wrong default path otherwise creates empty DB).
- World storage intentionally LOCAL. `ATOM_WORLD_STORAGE_PATHS=/Users/rushiparikh/projects/atom/backend/config` before imports. Canonical `/Users/rushiparikh/projects/atom/backend/data/acceptance_worlds`. Keep shared storage guard/maintenance lock; never bypass or replace with empty localworld root. Respect existing symlink in worktrees.
- Last free disk25GiB. No deps install/download/new world copies unless needed; never delete evidence/liveworlds blindly. User portable drive state must be rechecked, not assumed.
- Python3.11 `/usr/local/bin/python3.11`; Node20 `/Users/rushiparikh/.nvm/versions/node/v20.20.2/bin/node`; pytest PYTHONPATH `/private/tmp/root-py311-plugins:<backend>`, `-p no:randomly -p pytest_freezegun`.
- Test serialization `/usr/local/bin/python3.11 /private/tmp/atom-agent-cli/run_bounded_test_gate.py --cwd WORKTREE/backend --profile bounded -- COMMAND`. Real lock owner and children may outlive launching CLI.
- Native read-only observer above reads actual opencode.db, not stale stdout. Server liveness: import `session_active` from `/private/tmp/atom-agent-cli/native_worker_state.py` and call with session/worktree. CLI session.status/session.messages do NOT exist. Never dump full session DB/prompts/auth tokens.
- Resume only terminal process+serverinactive verified. `/private/tmp/atom-agent-cli/native_worker_bounded_supervisor.py --worktree WT --session ID --task 'ACTUAL PROMPT TEXT' --prefix PREFIX --max-continuations 0`. **--task takes literal text, not file contents**; to use a file explicitly read its text. No blind kill/retry on observation timeout.
- Root owns definitive verification/product scope; workers cannot self-accept. No live model/provider/account/credential/send/spend/deployment actions. Native CLI model inference is authorized only within configured subscription.
- User authorizes merges of independently verified exact heads with all13 required checks green. Normal merge first; admin override authorized for required separate review only when self-approval impossible, NOT failed CI/scanner/protection changes. Never merge current829 while known defect unresolved.
- Model-free CI observer `/private/tmp/root-watch-exact-all-required-checks-20261110.py --pr NUMBER --head FULL --prefix PREFIX --cwd WT`. New head does not inherit CI green. Do not rerun browser merely for evidence-only/head changes with proven relevant-byte parity.
- Strict evidence: every manifest artifact must actually be Git-tracked (`git show REF:path`), hash sources against executed source and artifacts against evidence ref. Ignored txt/log require secret review and explicit force-add. No regenerated historical logs, tokens/passwords/rawWebSocketlogs. No scanner waivers/history rewrites; keep original negatives.

## Immediate continuation after pending results

1. Resolve graduation UI missing enabled control using retained exact state; readiness may be missing a real requirement. Do not turn qualification alone into readiness. Capture/use actual result; do not fake UI promotion.
2. Finish native legacy email repair, independently test current/empty/legacy-only/provenance/publicsave-readback twins; integrateinto829 with allCI preserved and exact source parity. Push and let model-free observer handle CI while continuing independent work.
3. Verify final graduation121 and approvalscopy tests. Rerun meaningful broader consumers after latest runtime repair; preserve seven named pre-existing training failures, do not suppress/xfail or relax gate. Commit/push only scoped root WIP after checks; build strict source/evidence manifest, then draftPR.
4. Reconcile original143claims/18goals against current main/evidence; continue genuinely unclosed requirements. Long-task idle budget already has retained97/97 regression evidence at419ab9f44; do not repeat old campaigns just because stale audit names a row. Whole-app ORACLE, broader adaptive judgment, provider/connector breadth, operations/performance/profile breadth/mobile have not been universally accepted.
5. Keep short quick_reference accurate per delivery, full goal catalog unchanged. README/diagrams must distinguish measured capabilities from goals. Update this takeover snapshot if new results materially supersede it.


## Addendum: next verified checkpoint
Final permanent gate completed121/121, actual exit0/same_source=true at31ub0c6n. Email worker finished/pushedf2789bef93394fda4cab28d7c270899a11c4986f: initial110pass/2pre-existing-dictfailures; aligned focused9pass. Full repaired selection and root independent review remain needed before829integration/merge. Root ordinary approvals-copy test remains pending; frontend copy not part of backend acceptance.

Approvals walkthrough copy test finished17/17. Copy now describes actual readiness plus scoped capability review and successful promotion, rather than fixed3sessions/automaticpromotion. Existing6da UI capture is unchanged. Root backend121 checkpoint pushed2e856973d; current email native follow-through supervisor43668/prefix root-email-legacy-full-regression-20261110 is active.
