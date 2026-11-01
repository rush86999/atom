# Agent 1 — employee knowledge, quote preparation and durable work

Read the [shared work order](README.md) first. Base: public integration `587fbc251`.

## Product mission

An employee should receive an RFQ in Outlook, find the right business knowledge
in WorkDrive/OneDrive, combine it with Zoho customer/product facts, apply Brennan's
approved policies, ask targeted questions, prepare a quote, and continue the same
job through external waits and changes. The mechanism must work with another
customer/schema without developer-written plans or new intent regexes.

Your deliverable is a usable business loop, not a document-generation demo.
Agent 2 provides connected reads and typed writes; you own how work uses them.

## Ownership and existing mechanisms

| Area | Files to trace and extend |
|---|---|
| Plans, DAG and execution | [assignment_plan.py](../../../backend/core/assignment_plan.py), [assignment_planner.py](../../../backend/core/assignment_planner.py), [assignment_executor.py](../../../backend/core/assignment_executor.py) |
| Durable operations and obligations | [task_lifecycle.py](../../../backend/core/task_lifecycle.py) |
| Resource selection/access | [assignment_resources.py](../../../backend/core/assignment_resources.py) |
| Teaching/context | [student_learning_service.py](../../../backend/core/student_learning_service.py), [artifact_teaching.py](../../../backend/core/artifact_teaching.py), [conversation_learning.py](../../../backend/core/conversation_learning.py) |
| Deterministic policy/inputs | [assessment_rules.py](../../../backend/core/assessment_rules.py), [method_operands.py](../../../backend/core/method_operands.py) |
| Knowledge access | [documents_hybrid.py](../../../backend/core/hybrid_search/documents_hybrid.py), [knowledge_vfs.py](../../../backend/integrations/vfs/knowledge_vfs.py) |
| Employee UI | [AssignmentPanel.tsx](../../../frontend-nextjs/components/assignments/AssignmentPanel.tsx) and existing Training/canvas review panels |

Trace ordinary Chat, Assignments and artifact consumers before shared changes.
Do not patch Agent 2's adapters or accounting modules concurrently.

## Milestone A — relevant knowledge reaches the employee

Derive an evidence requirement from the objective and applicable teaching before
retrieval: subject/customer, fields, price basis, units, effective date, source
scope and required output. Use existing registries and retrieval mechanisms.

1. Discover permitted candidate resources, then resolve exact identities.
2. Read actual records/content, not filename summaries alone.
3. Verify whether evidence satisfies each requirement.
4. Carry source/version and sheet/row, paragraph/page or message references into
   calculations and deliverables.
5. Ask only for facts still absent, conflicting or inaccessible.

WorkDrive and OneDrive can contain overlapping names and different governing
versions. A supplier cost sheet, list price and customer agreement are different
bases. Apply taught precedence or clarify; never select whichever ranks first.
Preserve punctuation-sensitive identifiers and resolve aliases through evidence.

Maintain a bounded evidence packet rather than repeatedly injecting entire files.
Record selected and excluded sources with rationale, coverage and unresolved
requirements. Top-k retrieval does not establish absence from the whole corpus.
Use typed spreadsheet materializations for structured arithmetic and document
excerpts for prose; do not send Parquet to a workbook reader.

Create a fixed retrieval evaluation set: obsolete agreements, same-name customers,
SKU/pack distractors, missing records, conflicting revisions, revoked resources,
partial search and malicious instructions inside documents. Measure correct
source/record selection, evidence sufficiency, unsupported assertions and latency.
Keep the oracle independent of production ranking and calculation.

## Milestone B — complete quote preparation

Model the quote as ordinary registered capabilities in the existing plan:

Outlook RFQ → customer/contact/deal → inventory item/variant/unit → governing
agreement/pricing → taught calculation → quote document → proposed commercial
record/update → Outlook draft.

Required quote fields include exact customer and line identities, quantity,
unit/pack, price type, currency, policy references, discount/exception, freight,
tax treatment, delivery term and validity. Missing fields remain obligations.
Do not silently assume USD, zero tax, a delivery date or an exchange rate.

Agent 2 establishes which Zoho Books estimate or CRM quote operation is supported
and appropriate. Choose one canonical commercial record; link its ID from CRM.
A quote is not an invoice, payment, order or stock reservation.

Use Decimal and approved typed methods. Every amount needs an input-evidence
chain. Example independent fixture: A=2×100, B=3×50 with 5% discount on B only,
freight=20, explicitly no tax; expected total=362.50. Add unit/pack conflicts,
negative/zero/non-finite inputs and incompatible currencies. No implicit repairs.

Document, Zoho payload and email must use the same quote revision and totals.
Bind complete payloads and attachment bytes; diagnostic truncation must never
change executable content. Covered actions can execute under current bounded
authority. Unknown terms clarify; authority expansion does not come from teaching.

## Milestone C — complex teaching through ordinary interfaces

Teach standard policy, customer-specific agreement, product exception, margin or
discount limit, document/email protocol and effective dates through existing UI.

Prove:
- Matching context applies; wrong context and expired instructions are excluded.
- Missing qualification produces a durable targeted question.
- Equally governing conflicting lessons do not arbitrarily win.
- More specific exceptions apply only in their accepted scope.
- Active work retains its snapshot; new work adopts corrected teaching.
- Explicit reassessment invalidates affected descendants and stale action bindings.
- Referenced email/document text stays evidence until reviewed promotion.

Unsupported methods must remain unresolved, not be replaced by plausible model
arithmetic. Model interpretation and deterministic execution have separate receipts.

## Milestone D — multiple moving parts

Starting code finding to reproduce: execute() checks its first waiting step and
can return before ready_steps(). One unresolved wait can block independent work.
Extend existing DAG scheduling; no new queue or worker engine is needed.

Keep ready independent work progressing under the single-worker topology.
Persist separate correlation/requirement identities per subject and branch.
Changed evidence invalidates only affected descendants; preserve prior artifacts
and unaffected work. Recheck current resource and effect authority at consumption.

### Time and budget semantics

Separate per-step external waits, assignment idle intervals, absolute business
deadline, operation timeout, retry count and provider cost. A waiting branch must
not forgive working time on another branch. Credit the union of assignment idle
intervals once under CAS; never sum overlapping branch waits.

Timeline oracle: work at 0–40; all blocked at 40–80; work at 80–90; all blocked
at 90–100. At 100, working=50 and paused=50 seconds. Repeat across restart and
concurrent replies. Migrate ambiguous legacy timing conservatively, without
inventing credit. Keep trusted pre-dispatch cost reservations and uncertain-effect
reconciliation intact.

## Acceptance matrix

| Scenario | Required observation |
|---|---|
| Unfamiliar RFQ + agreement + workbook | Correct customer/product join and cited calculation |
| Same SKU, different packaging | Clarification before arithmetic |
| WorkDrive/OneDrive conflicting agreements | Taught governing-source choice or durable conflict |
| Supplier A waits; B ready | B completes without A's response |
| Two outstanding suppliers + restart | Same job, two exact pending identities |
| Duplicate/concurrent answer | One resolution, no duplicate downstream effect |
| Price changes while waiting | Only dependent outputs/actions require revision |
| Scope/grant withdrawn | Affected consumption/effect refuses; draft remains visible |
| Remote acceptance then connection loss | Uncertain; reconcile existing operation without resend |
| Cancel/deadline | No late event revives work; completed work/history preserved |

## Completion and handoff

First deliver a thin controlled quote loop using Agent 2's contract fixtures.
Then run the normal UI/public-route journey with connected/sandbox sources where
authorized. Include productive work before waiting, real browser closure/backend
restart, external changes, quote artifact, proposed/covered Zoho action, readback
and duplicate/cancellation controls. Use a real elapsed campaign for the new
business behavior; do not simulate elapsed time or rerun old campaigns unchanged.

Submit one source-bound bundle with independent arithmetic, evidence references,
lesson revisions, exact payload/artifact hashes and effect counts. Explain every
controlled boundary. Start the next assigned task after each pass rather than
pausing for another preparation report. Independent verifier acceptance is required.
