# Playbook User Journey — Training-Tab UX

Design doc for surfacing playbooks (procedural memory) to humans. The backend
capture/approval machinery is complete (Installation Adaptation Plan Phases
3–4); the frontend has **zero** playbook UI today — drafts accumulate in the
DB invisibly and approval is API-only. This doc defines the user journey, the
Training-tab UI, and the build order. Home: the canvas right-panel **Training
tab** (`frontend-nextjs/components/canvas/TrainingPanel.tsx`, mounted from
`frontend-nextjs/pages/canvas/[id].tsx`).

---

## 1. Current state (grounding — what the system already does)

| Mechanism | Trigger | Result | Code |
|---|---|---|---|
| Authored | `POST /api/playbooks` | `approved` immediately | `backend/api/playbook_routes.py:62` |
| Taught | `/teach` with `as_playbook: true` (opt-in; UI never sends it) | `draft` (source=taught); lesson text split into steps/questions | `backend/api/agent_onboarding_routes.py:375`, `core/playbook_service.py:185` |
| Learned — per-correction | ANY deduped supervisor correction of agent canvas work | `draft` (source=learned) with template-filled rule + **instant** per-agent work-time lesson (no approval wait for the correcting supervisor's own agent) | `core/correction_reflection_service.py`, called from `services/canvas_context_service.py:443`; the human edit of an agent-authored canvas draft IS the correction (`api/canvas_routes.py:183`) |
| Learned — recurring | `IncidentEval.occurrences >= 3` (sleep-time job; ≤3 new drafts/cycle; idempotent version bumps) | `draft` (source=learned) | `core/exchange_memory_maintenance.py:290` |
| Activation | `approval_state=approved` + `ATOM_PLAYBOOKS=shadow` (default) | advisory prompt leg on trigger match (canvas type + keywords) | `core/playbook_service.py:250` |
| HITL gate | `POST /api/playbooks/{id}/approve` | eval-gated promotion (shadow records replay; `enforce` blocks on failing origin evals → HTTP 409) | `backend/api/playbook_routes.py:89` |

Key properties the UX must respect:

- **A correction is effective instantly for the agent that was corrected**
  (work-time lesson rides the very next turn). Approval only gates promoting
  the rule **install-wide** as a playbook. The UX must not make supervisors
  feel blocked.
- **Drafts never enter prompts on their own.** Recurrence hardens a draft;
  it does not approve it. The one exception is the **autonomy latch**
  (§6): with `ATOM_PLAYBOOKS_AUTO_APPROVE` explicitly on, a `learned`
  draft whose origin evals replay clean 3× **and** whose surface passes
  the same agent-maturity autonomy gate as actions promotes without a
  click. Default off.
- Trigger matching is `trigger_canvas_type` + `trigger_keywords`; prompts get
  the playbook as **advisory** (shadow). `enforce` (send/edit gates) is
  reserved.

## 2. Personas

- **Supervisor** — approves/retires drafts, authors playbooks, teaches. Sees
  the full review queue. (`viewer_is_supervisor` already reaches
  TrainingPanel via `GET /api/maturity/training/context`.)
- **Employee / any signed-in human** — teaches lessons and corrects canvas
  work; their taught drafts wait for supervisor approval.
- **Agent** — the consumer: work-time lessons immediately; approved playbooks
  as advisory process guidance on trigger match.

## 3. Journeys

### Journey A — Capture a process that worked (author/teach)

*The "data discovery went well, keep doing this" moment.*

1. A discovery → canvas task finishes well. User opens the canvas **Training
   tab**.
2. In the existing **Teach a lesson** form they write the process as
   imperative steps (one per line) and clarifying questions. They flip the new
   **Save as playbook** toggle — canvas type auto-fills from the open canvas,
   topic becomes suggested keywords.
3. The draft appears immediately in the new **Playbooks ▸ Drafts** queue below
   (source badge `taught`), editable inline. The user hits **Approve** →
   active.
4. Alternative entry point: **New playbook** button → 4-field mini-wizard
   (name / when-to-use: canvas type + keywords / steps one-per-line /
   template questions). Authored directly = active immediately (matches
   backend default).

### Journey B — Correct → the rule drafts itself (the auto loop)

1. Supervisor edits the agent's canvas draft (or sends corrective feedback
   via `ChatFeedbackControls`). The human save **is** the correction.
2. Backend classifies the failure taxonomy, files a replayable incident eval,
   drafts the rule playbook (fingerprint-deduped), and journals the instant
   work-time lesson.
3. **UX:** toast — *"Rule drafted from your correction — review in Training"*
   with a deep link; the Training tab button gains a draft-count badge.
4. Supervisor opens Training ▸ **Drafts**: card shows taxonomy badge, the
   templated rule (their own diff token embedded), the instruction they gave
   (`instruction` hint), occurrence/version count, and an origin link into the
   canvas **Journey** tab.
5. One click **Approve** (eval gate replay summary shown; 409-blocked state
   keeps the draft and surfaces the failing evals) or **Retire** / **Edit
   steps first**.

### Journey C — Recurrence hardens the rule

- The same correction pattern recurs → the sleep-time job **bumps** the
  existing draft's version (never stacks rows). The draft card shows
  **"seen 4×"** — the supervisor gets escalating evidence to approve.
- "Enough data switches it on?" **Not by itself — but maturity does.** The
  journey follows the same autonomy contract as the agent's actions
  (`core/autonomy_policy.py`): while any hire on the surface still
  *proposes* (below the maturity/trust bar, or the topic is
  human-always), the rule waits for a human click right alongside their
  actions. Once the crew's autonomy gate says *execute* and the origin
  evals replay clean, the latch (§6) promotes the rule without one. The
  draft card shows the latch counting up (`auto-latch 2/3`) or why it's
  paused — the same "why" the Autonomy tab gives for a held action.

### Journey D — Approved playbook at work

- On a trigger-matching task (canvas type/keywords), the playbook renders as
  an advisory leg in the edit plan / chat context.
- **Transparency (needs a small backend addition):** the canvas edit result
  and chat response metadata gain `matched_playbooks: [id, name]`; the UI
  shows a *"Following playbook: name"* chip on the edited canvas and in the
  co-editor transcript, deep-linking to the playbook card.
- Lifecycle: an Active card can be **Retired** (immediately stops entering
  prompts); recurring corrections after retirement re-draft for review.

## 4. UI spec — Training tab

```
Training tab
├─ Agent card (tier · confidence · progress)            [exists]
├─ Training session / proposal                           [exists]
├─ Teach a lesson                                        [exists + toggle]
│    lesson textarea · topic ·  [✓] Save as playbook
│    (canvas type chip auto-set from open canvas)
├─ ★ Playbooks                                           [NEW]
│    ┌ Drafts (2) │ Active (5) │ Retired ┐   ← segmented control
│    │
│    │ ┌───────────────────────────────────────────────┐
│    │ │ [process] include ROI table      taught · v1  │
│    │ │ "Process: include the supervisor's required   │
│    │ │  steps (ROI table) in drafts of this kind…"   │
│    │ │ trigger: spreadsheet · keywords: roi, quote   │
│    │ │ instruction: "always add the ROI table"       │
│    │ │ origin: canvas 8f3a… → Journey                │
│    │ │ [Approve]  [Edit]  [Retire]                   │
│    │ └───────────────────────────────────────────────┘
│    │ ┌─ [grounding] "in stock"   learned · v4 · seen 4× ─┐
│    │ └─ …                                                ┘
│    └─ Active card: name · trigger chips · steps n · [Retire]
└─ Graduation (readiness · promote)                      [exists]
```

Interaction states:

- **Approve in flight** → spinner; on success the card animates to Active.
- **Eval-gate blocked (409)** → amber banner with the gate summary
  (`ran/passed/failed`), card stays in Drafts. Copy: "Originating evals
  regressed — fix or retire the rule."
- **Empty states** — Drafts: "Corrections you make on canvases draft rules
  here for one-click approval." Active: "Approved processes appear here and
  guide matching tasks (advisory)."
- **Badges** — source (`taught`/`learned`/`authored`), taxonomy chip,
  `seen n×` when version bumped by recurrence.
- **Latch progress** — a learned draft under the autonomy latch (§6) shows
  `auto-latch 2/3` as clean replays accrue, or `auto-approve paused` (with
  the blocking reason on hover) while the autonomy gate holds it: crew
  still maturing, or a human-always surface.
- **Mode footer** — one line: "Playbooks: advisory (shadow) — approved
  processes guide matching tasks" (+ link to this doc).

## 5. Build order

| Phase | Work | Files |
|---|---|---|
| **P1 — review queue** (closes the invisible-drafts gap) | `lib/playbook-api.ts` (list `?include_drafts=true` / approve / retire) + Playbooks section with Drafts/Active/Retired + tab badge + correction toast deep-link | new `components/canvas/PlaybookSection.tsx`, `PlaybookCard.tsx`; `pages/canvas/[id].tsx` |
| **P2 — teach→playbook** | `Save as playbook` toggle → `as_playbook` + `playbook_canvas_type` (canvas type of the open canvas) in `teachAgent` | `lib/maturity-api.ts`, `TrainingPanel.tsx` |
| **P3 — transparency chip** | backend: emit `matched_playbooks` in canvas-edit result + chat metadata; UI: chip on canvas + transcript | `core/chat_canvas_editor.py`, `chat_orchestrator.py`, `ChatFeedbackControls.tsx` |
| **P4 — authoring wizard** | New-playbook mini-wizard → `POST /api/playbooks` | `PlaybookSection.tsx` |
| **P5 — autonomy latch** (built, default off) | learned drafts promote without a click only when §6's gate clears: autonomy (mode × crew maturity × trust) AND a 3× clean origin-eval streak | `core/exchange_memory_maintenance.py` (`_auto_approve_playbooks`), `core/autonomy_policy.py` (`tenant_gate_for_topic`), setting `ATOM_PLAYBOOKS_AUTO_APPROVE` |

Access-control parity note: `/api/playbooks` approve/retire currently accept
any authenticated user; P1 should add the supervisor gate (mirror
`viewer_is_supervisor`) so the UI and API enforce the same rule.

## 6. When does a rule promote WITHOUT a human click? (decision)

The HITL approve click is the default and stays on for everything
external. Beyond it, the playbook journey follows the **same agent-
maturity autonomy contract as actions**
(`core/autonomy_policy.py`): a mature hire already acts unattended on
internal surfaces (`auto_if_mature` — canvas edits, tasks, PDFs execute;
immature ones propose); the rules distilled from that same work get the
same treatment. **Autonomy allows actions — and the rules that shape
them — without human gating.**

The latch (`ATOM_PLAYBOOKS_AUTO_APPROVE`, default off — the owner's
switch, the rule-shaped analog of the Autonomy panel's topic modes)
promotes a `learned` draft without a click only when ALL of these hold:

1. **Autonomy allows it** — the draft's trigger canvas type maps to
   autonomy topics (`topics_for_canvas`); every primary topic must be
   `auto_if_mature` with **all active hires in the tenant clearing the
   maturity×trust bar** (`tenant_gate_for_topic` — the same
   `gate_for_topic` the runtime enforces on their actions, aggregated
   over the crew the rule will steer). An email-surface rule (send/CRM
   are `human_always`) or a tenant where any hire still proposes the
   topic stays human-gated: one gate for actions and rules alike. While
   blocked, the evidence streak **freezes** (not resets) and the card
   says why; it resumes when the crew matures.
2. **Evidence proves it** — the draft's ORIGIN incident evals pass 3
   consecutive nightly replays (`approved_by=auto_latch:evidence`);
   any failing — or all-skip, i.e. nothing runnable — replay resets
   the streak (same convention as the approval-time eval gate).

Never latch, regardless of settings: `taught`/`authored` drafts (their
approval was the supervisor's own act), drafts without replayable origin
evals, and retired rules (a recurring correction re-drafts for review).

Why a flag at all: a playbook is install-wide — every hire inherits it —
so the flag is the owner opting in to no-human-gating for rule promotion
the same way the Autonomy panel is opting in per topic for actions. The
flag alone changes nothing without a mature crew (the gate holds it);
with one, review queues stop growing without giving up the evidence
gate. This supersedes the earlier "default answer: no" framing: the
answer is now **"humans approve until maturity doesn't need them to."**
