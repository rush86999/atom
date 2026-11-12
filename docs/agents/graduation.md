# Agent Graduation Guide

## Product goal and current implementation

**The end goal of graduation is unrestricted autonomy, with exceptions in
certain domains.** A graduated agent should independently plan, act, coordinate
long-running work, obtain missing information and complete the result without
routine human approval. Domain-specific rules may still require human review,
restricted actions or specialist supervision. Those exceptions should be
explicit policies rather than an assumption that every task needs approval.

This is the product destination. The current implementation has scoped
readiness checks, scoped capability qualification, supervisor-authorized
promotion and per-capability maturity; an AUTONOMOUS status alone does not
establish the full end goal. Existing user, workspace, data-access,
action-policy and budget checks remain applicable today. Current maturity does
not remove those checks.

For a concise introduction, see [Agent training and graduation](TRAINING_AND_GRADUATION.md).
This comprehensive guide retains the criteria, worked examples and engineering
background. Use the current
[public routes](../../backend/api/episode_routes.py),
[readiness and promotion service](../../backend/core/agent_graduation_service.py)
and [capability service](../../backend/core/capability_graduation_service.py)
for exact operating contracts. Older illustrative examples below are not
proof of universal competence or regulatory compliance.

An agent-level upward transition now needs **both**:

1. **Experience readiness** for the requested tier, computed from scoped
   episode evidence; and
2. **Scoped capability qualification** for actual candidate work, established
   by a current authorized human review of selected task/context plus actual
   durable output under the owner's current assessment policy.

Readiness alone does not promote. The historical exam endpoint reviews
authorized recorded traces; it does not execute or qualify a new candidate.
A legacy history-statistics exam is not a capability qualification receipt.
Capability maturity counts verified successes within its current epoch,
including reset/revocation rules. Separately,
[`GraduationService`](../../backend/core/graduation_service.py) records successful
skill paths in `promoted_skills`; that record is not an agent-wide permission
grant and must not be confused with either graduation decision.

## Overview

The Agent Graduation Framework provides a rigorous, data-driven approach to promoting AI agents through maturity levels (STUDENT → INTERN → SUPERVISED → AUTONOMOUS). It uses episodic memory to track agent performance, validate constitutional compliance, and generate audit trails for governance requirements.

## Table of Contents

- [Why Graduation Matters](#why-graduation-matters)
- [Two Types of Graduation](#two-types-of-graduation) ⚡ **IMPORTANT**
- [Graduation Criteria](#graduation-criteria)
- [Scoped capability qualification](#scoped-capability-qualification)
- [Owner assessment policy](#owner-assessment-policy)
- [Upward writers and the shared gate](#upward-writers-and-the-shared-gate)
- [Notifications and replay](#notifications-and-replay)
- [How Graduation is Triggered](#how-graduation-is-triggered)
- [Readiness Score Calculation](#readiness-score-calculation)
- [Constitutional Compliance](#constitutional-compliance)
- [Use Cases](#use-cases)
- [Graduation Workflow](#graduation-workflow)
- [Edge Case Testing](#edge-case-testing)
- [Audit Trail Generation](#audit-trail-generation)

---

## Two Types of Graduation ⚡ IMPORTANT

Atom has **two distinct graduation systems** that work together:

### 1. Agent Graduation (This Guide)
**What**: Overall agent maturity level
**Progression**: STUDENT → INTERN → SUPERVISED → AUTONOMOUS
**Based on**: Scoped experience readiness (episodes, intervention rates,
constitutional compliance) **plus** scoped capability qualification of actual
candidate task/output work under the current owner policy
**Scope**: Agent-wide (affects all capabilities)

### 2. Capability Graduation ⚡
**What**: Individual skill/capability maturity
**Progression**: 5 → 20 → 50 new verified successes, subject to reset and revocation rules
**Based on**: Verified successes per capability in the current progression epoch
**Scope**: Per-capability (skills graduate independently)

**Example**:
- An agent can be **INTERN** overall (agent graduation)
- But have **AUTONOMOUS** level for "data_query" capability (capability graduation)
- While still being **STUDENT** for "shell_access" capability

**See**: Capability Graduation Logic for the 5/20/50 rule.

---

## Why Graduation Matters

### 1. Safety

Agents must demonstrate competence before gaining autonomy. Graduation ensures:
- Evidence of performance appropriate to the requested autonomy and domain
- Recorded policy/compliance checks; a score is not regulatory certification
- Proven track record of correct decisions

### 2. Governance Compliance

Regulated industries require audit trails proving:
- Agent performance over time
- Human intervention rates
- Compliance with domain-specific rules

### 3. Trust

Users need confidence that agents:
- Learn from past experiences
- Improve over time
- Don't repeat mistakes

### 4. Multi-Dimensional Learning

Graduation tracking includes:
- **Episodic Memory**: Agent interactions and past experiences
- **Community Skills**: Skill usage diversity and learning velocity
- **Canvas Presentations**: Context-aware decision making
- **User Feedback**: Performance ratings and corrections

---

## Graduation Criteria

### Maturity Levels

| Level | Description | Permissions |
|-------|-------------|-------------|
| **STUDENT** | Learning phase | Read-only, presentations |
| **INTERN** | Basic autonomy | Streaming, form presentations |
| **SUPERVISED** | Advanced autonomy | Form submissions, state changes (with supervision) |
| **AUTONOMOUS** | Highest maturity tier; unrestricted autonomy is the product goal | Current permissions and policies apply; domain exceptions may require oversight |

### Promotion Requirements

| Promotion | Min Episodes | Max Intervention Rate | Min Constitutional Score |
|-----------|--------------|----------------------|--------------------------|
| STUDENT → INTERN | 10 | 50% | 0.70 |
| INTERN → SUPERVISED | 25 | 20% | 0.85 |
| SUPERVISED → AUTONOMOUS | 50 | 0% | 0.95 |

This table is **experience readiness only**. It does not by itself qualify an
agent for an upward transition. The scoped capability qualification described
below is a separate, mandatory input unless the current owner policy explicitly
marks the target tier as not required or names the exact agent in an owner
exception.

### Key Metrics

**Episode Count**: Number of completed episodes at current maturity level

**Intervention Rate**: Percentage of episodes requiring human correction
```
intervention_rate = total_interventions / episode_count
```

**Constitutional Score**: Compliance with domain rules (0.0 to 1.0)
- Validated against Knowledge Graph
- Tracks violations of tax laws, HIPAA, etc.
- Calculated per episode

---

## Scoped capability qualification

Experience readiness answers "has this agent accumulated enough evidence to be
considered for the next tier?" Scoped capability qualification answers a
different question: "has an authorized reviewer inspected this candidate's
actual work for this exact tier and scope, under the current policy, and found
it adequate?"

Historical statistics are not a substitute for that second question. A high
episode count, a clean historical exam or a high readiness score does not
qualify an agent for an unseen task.

### What is reviewed

A qualification review uses an explicit **task/output bundle**:

- the task or context the agent was asked to perform;
- the actual durable output the agent produced (execution result, episode
  segment or artifact);
- the exact agent, tenant, workspace, target tier, source revision and
  evidence references.

History-only episodes are excluded. The supervisor must select the bundle(s)
to review; the UI does not auto-select recent history statistics. The evidence
endpoint is:

```http
GET /api/episodes/graduation/qualification/evidence/{agent_id}?target_maturity=INTERN
```

It returns eligible bundles and the frozen rubric criteria. The reviewer then
requests a review:

```http
POST /api/episodes/graduation/qualification/request
Content-Type: application/json

{
  "agent_id": "agent-123",
  "target_maturity": "INTERN",
  "evidence_refs": [
    {"kind": "agent_episode", "id": "ep-1"},
    {"kind": "agent_execution", "id": "exec-1"}
  ],
  "rubric_version": "heldout-v1"
}
```

The request creates an existing HITL action of type
`agent_qualification_review`. It does **not** promote the agent. The action
appears in the ordinary Approvals queue and is decided with:

```http
POST /api/agents/approvals/{action_id}

{"decision": "approved", "feedback": "Reviewed the selected task and output."}
```

Only an approved review creates a passed qualification receipt. An exact
duplicate request with the same current material reuses the same pending
action; it does not create a needless second review. If the policy revision,
rubric, scope, source or evidence changes, the old pending review is stale and
a fresh review is required. The old review fails closed.

### Receipt binding and states

A receipt is not a generic "exam passed" flag. It is bound to the complete
material that was reviewed:

- review schema and agent identity;
- current tier and target tier;
- tenant and workspace;
- owner-policy revision and digest;
- rubric version and exact rubric criteria;
- source revision and normalized evidence references;
- the authorized reviewer and review action.

The qualification gate reports explicit states:

| State | Meaning | Promotion effect |
|---|---|---|
| `valid` | A current passed receipt matches the complete material | Allowed |
| `unresolved_missing` | No receipt, or required task/output evidence is absent | Blocked |
| `unresolved_failed` | The review or receipt did not pass | Blocked |
| `unresolved_stale` | Policy, rubric, source, tier or receipt material changed | Blocked |
| `unresolved_scope` | Tenant/workspace/agent/reviewer binding is foreign or missing | Blocked |
| `configuration_required` | The owner policy is absent-invalid, unsupported or ambiguous | Blocked |
| `not_required` | The current owner policy explicitly disables this tier | Allowed without a receipt |
| `legacy_unassessed`, `manual_override`, `system_exempt` | An explicit owner-listed agent exception applies | Allowed without claiming qualification |

Missing, failed, stale, foreign or unreadable assessment material defaults to
blocked. It is never treated as allowed, "Ready" or a passing receipt.

The default rubric is a human-review rubric and includes explicit semantic
criteria, including task completion/correctness against the expected or
evidence result, not merely output presence, scope or safety. The evaluator is
`human_review` in v1; there is no model judge and no new score engine.

### Repeat-task model routing

After a qualified promotion, the same agent may serve a repeated, workload-matching assignment
with a model route the recorded evidence still supports, without a new review for every run.

- **Frozen benchmark evidence, not caller claims.** Evidence comes only from offline
  server-side intake against a frozen benchmark set whose dataset digest and scoring
  version are pinned; a changed set or scoring generation is a different benchmark, and
  caller-asserted material is discarded, never scored. Validated observations are
  digest-sealed records under the reserved `benchmark_evidence` key of the run's execution
  metadata, timed by the durable execution `completed_at`; the served identity comes only
  from a campaign-owned sealed transport journal's provider echo, so replay cannot refresh
  a result. Evidence is per-agent, scoped and benchmark-bound — no global leaderboard.
- **Callable route vs provider build.** The evidence identity is the callable route
  `(provider, model)` the transport selected and accepted. A provider-echoed concrete
  build (e.g. a dated suffix on the same model family) is that route's *build*, recorded
  separately — not a different route; a different provider, model family or variant tier
  is a conflicting echo, making the run ineligible. Runtime validation requires the exact
  pinned route and a required provider echo; a bound concrete benchmark build must be
  echoed exactly, a missing or changed echo demotes the effect to supervision, and the
  effect gate rechecks current evidence after restart.
- **Receipt binding is the baseline.** The promotion receipt binds a complete benchmark
  identity (dataset hash, rubric version, canonical workload scope) plus the actually-served
  routes, from validated evidence records only. The runtime baseline is the newest committed
  promotion transition into the current tier plus its receipt. Selection requires the
  assignment's server-derived `workload_scope` to exactly match the binding's scope; a
  candidate needs fresh *passing* observations on the same benchmark (same dataset hash,
  rubric and task scope), and a pinned call is strict: exact route or failure.
- **Supervised fallback is the default.** The resolver fails closed: a missing baseline,
  non-comparable binding, unknown or mismatched workload, no fresh eligible route or an
  unresolvable pin all resolve to `supervised`, and ordinary routing is untouched. Before
  an irreversible effect the route decision is revalidated from durable state and demoted
  to the supervised path when evidence no longer holds.
- **Owner approval still applies.** Routing selects a serving route; it never authorizes
  an effect or bypasses a review. The owner's autonomy gate still decides execute vs
  propose on mutating steps, and no routing outcome removes a required human approval.

## Owner assessment policy

The owner policy is the strict runtime setting
`ATOM_GRADUATION_ASSESSMENT_POLICY` (schema
`atom-graduation-assessment-policy-1`). Its supported shape is:

```json
{
  "schema_version": "atom-graduation-assessment-policy-1",
  "revision": "1",
  "default_required": true,
  "tiers": {"intern": true, "supervised": true, "autonomous": true},
  "exceptions": {
    "legacy": {"allowed": false, "agent_ids": [], "domains": [], "reason": null},
    "manual": {"allowed": false, "agent_ids": [], "domains": [], "reason": null},
    "system": {"allowed": false, "agent_ids": [], "domains": [], "reason": null}
  },
  "evaluator": "human_review",
  "rubric_version": "heldout-v1",
  "rubric_criteria": [
    {"id": "task_context", "label": "Task/context is inspectable and scoped to this agent and tier"},
    {"id": "actual_output", "label": "Actual durable output is present and reviewable"},
    {"id": "task_completion", "label": "Task objective is completed; output is correct against the expected/evidence result"},
    {"id": "scope", "label": "Evidence matches the exact tenant/workspace/policy/source"},
    {"id": "safety", "label": "No unresolved safety or compliance violations"}
  ],
  "source_revision": "agent-evidence-v1"
}
```

Supported controls:

- `default_required: true` and empty exception `domains` lists;
- per-tier gates in `tiers`;
- exceptions that name **exact agent ids** and provide a nonblank reason;
- owner-defined rubric criteria with nonempty, exactly unique `id` values and
  nonblank labels;
- policy revision/digest and CAS checks against the current policy.

Explicitly unsupported selectors are rejected as `configuration_required`
rather than silently ignored:

- `default_required: false` (use `tiers.*` to disable a specific tier);
- any nonempty `exceptions.*.domains` list (name exact `agent_ids` instead);
- an empty `rubric_criteria` list;
- duplicate rubric criterion ids.

Do not advertise domain selectors as working exemptions. The implementation
does not infer a broad or domain exemption from mutable agent category, name or
metadata. An exact owner-listed exception allows an unassessed transition but
does not claim candidate capability qualification.

## Upward writers and the shared gate

Every existing-agent upward writer participates in the same qualification and
CAS path; none may write a higher tier directly:

| Writer | Entry point | Shared behavior |
|---|---|---|
| Public graduation route | `POST /api/episodes/graduation/promote` → `AgentGraduationService.promote_agent_decision` | Readiness + qualification gate + receipt/policy CAS |
| Manual agent promote | `POST /api/agents/{agent_id}/promote` → `agent_decision_write_service.promote_agent` | Manual qualification gate (`manual=True`) + CAS |
| Legacy exam | `GraduationExamService.execute_graduation_exam` | Historical record only; may call `commit_qualified_transition` only after the shared gate allows it |
| Manual graduation grant | `GraduationExamService.promote_agent_manually` | `evaluate_qualification_gate(..., manual=True)` then `commit_qualified_transition` |
| Training completion | `StudentTrainingService.complete_training_session` | `commit_qualified_transition` after readiness |
| Supervision completion | `SupervisionService.complete_supervision` | `commit_qualified_transition`; confidence alone cannot promote |
| Governance confidence change | `AgentGovernanceService` upward path | `commit_qualified_transition`; blocked transitions publish a blocked activity |

`commit_qualified_transition` is the canonical CAS writer for these callers. It
re-checks current authority, exact agent scope, current tier, experience
readiness, qualification state, policy/receipt fingerprints and caller
transaction cleanliness in the same transition. A notification, broadcast,
training or supervision side effect cannot bypass that gate.

Current authority and domain/action policy still apply after promotion. An
AUTONOMOUS label is a maturity state, not unlimited authority.

## Notifications and replay

The public `AgentGraduationService.promote_agent_decision` path awaits one
internal `agent_graduated` notification for the agent's user after its promotion
is durably committed. The notification call is
awaited inside the promotion coroutine; it does not create a second event loop,
thread or background runner.

- A duplicate replay of the same operation returns the original outcome and
  does not create a second notification.
- If the internal notification is unavailable, the promotion remains committed
  and the service logs the notification failure. It does not claim delivery and
  does not roll back the tier change.
- External email is opt-in only; the internal notification row is the default
  record.

---

## How Graduation is Triggered

There are distinct consumers, not one universal automatic promotion trigger:

- **Agent-level promotion:** the authenticated episode API evaluates experience
  readiness, requires the scoped capability qualification (or an explicit
  current owner exception), and applies an authorized next-stage promotion.
  Readiness alone does not bypass the reviewer, qualification gate or current
  scope checks.
- **Training, supervision and governance completions:** these may produce
  upward candidates, but they call the same shared qualification/CAS writer.
  A confidence boost or a completed session is not itself a qualification
  receipt.
- **Capability progression:** verified outcomes update capability maturity;
  fresh-epoch and revocation rules prevent old success counts from immediately
  restoring autonomy after a correction.
- **Skill-path recording:** `GraduationService.check_skill_promotion` can record
  a successful path using its complexity-based streak rule. Its
  `promoted_skills` configuration entry is separate from agent status and
  capability-maturity authority.

Background scheduling depends on the configured runner. A fixed review
interval or universal post-task automatic promotion is not promised here.

---

## Skill Promotion Logic

**Note**: This section describes skill promotion within the agent graduation framework. For per-capability graduation based on usage count (5/20/50 rule), see Capability Graduation Logic.

The separate skill-path recorder uses this **Dynamic Streak Rule**; it does not replace agent readiness or capability graduation:

| Complexity | Required Consecutive Clean Runs |
|------------|--------------------------------|
| **Simple**   | 3                              |
| **Moderate** | 5                              |
| **Complex**  | 8                              |
| **Advanced** | 8                              |

**A "Clean Run" is defined as:**
1.  **Success**: `True` (Task completed objective).
2.  **Human Interventions**: `0` (Zero manual corrections).
3.  **Constitutional Score**: `≥ 0.95` as recorded by that path; this is not proof of full domain or regulatory compliance.

## Readiness Score Calculation

### Maturity adjusted formula and implementation references

The readiness score uses **per-target-level weights**, and each agent is
scored only on the factors its maturity tier can actually evidence. Factors
whose weight is nonzero but which have **no recorded evidence** for the
agent (e.g. constitutional scores for chat-segmented episodes, supervision
when no proposal-linked episodes exist) are **excluded and the remaining
weights renormalized**:

```
readiness = Σ(value_i × weight_i) / Σ(weight_i)   over factors with
                                                  weight > 0 AND recorded evidence
```

**Per-level base weights** (source: `core/episode_service.py::ReadinessWeights`):

| Factor | student → intern | intern → supervised | supervised → autonomous |
|--------|-----------------:|--------------------:|------------------------:|
| Zero Intervention Ratio | 35% | 25% | 30% |
| Average Constitutional Score | 25% | 20% | 25% |
| Average Confidence Score | 20% | 15% | 15% |
| Success Rate | 20% | 25% | 20% |
| Supervision Success Rate | — | 15% | 10% |
| Skill Diversity Score | — | — | — |
| Proposal Quality Score | — | — | — |

**Why the weights differ per maturity (practical basis)**:

- **Students cannot create proposals** (hard block in `ProposalService`) —
  supervision evidence is structurally unreachable at the student tier, so
  it carries no weight there.
- **Interns route every action through a proposal** whose decision episode
  records `human_intervention_count = 1` by design, capping
  zero-intervention near 0.5 — so it carries a reduced weight, and
  supervision (approval rate) is live instead.
- **Skill diversity and proposal quality carry 0% at every tier**: no
  episode writer currently stamps `skill_type="openclaw"` or
  `episode_type="meta_agent_proposal"` metadata. Enabling one in promotion
  scoring is a deliberate weight change in `ReadinessWeights`, not a side
  effect of adding a writer.
- **Supervision success rate** blends approval rate (60%) and
  execution-followed rate (40%) only when follow-through was recorded;
  with no follow-through telemetry it equals the approval rate alone.

**Example Calculation**:

**Scenario**: Chat-trained student seeking promotion to INTERN — 12
episodes, all successful with zero interventions, episode confidence 0.5,
no constitutional scores recorded (chat segmentation does not record one),
no proposals:

```
Applied factors (constitutional excluded — nothing recorded):
  Zero Intervention: 1.00 × 0.35 = 0.350
  Confidence:        0.50 × 0.20 = 0.100
  Success:           1.00 × 0.20 = 0.200
Renormalize over applied weight 0.75:
  readiness = 0.650 / 0.75 = 0.867  ≥ 0.70 threshold → READY
```

Previously the unrecorded constitutional score averaged in as 0.0 and the
formula included structurally-zero factors, so this same agent scored
0.475 and could never cross the threshold — perfect runs included.

### Key Changes from Previous Formula

| Old Formula | Maturity-Adjusted Formula | Change |
|-------------|---------------------------|--------|
| One 6/7-component formula for all tiers | Per-tier weight tables | Each tier scored on evidence it can produce |
| Unrecorded scores averaged in as 0.0 | Unrecorded factors excluded + renormalized | Missing telemetry ≠ zero score |
| Skill diversity 10% (later 7%) + proposal quality 3% | Both 0% (no telemetry writers) | Dead factors no longer cap scores below thresholds |
| Supervision capped at 0.6 (dead follow-through column) | Approval-rate fallback when unrecorded | Supervision credit usable at intern tier |

### Skill Diversity (currently weight 0%)

`skill_diversity_score = min(unique_skills_used / 10, 1.0)` — variety of
skills successfully executed. No writer currently stamps the required
episode metadata, so the factor is disabled (0%) until one does; it
re-enters scoring only by giving it a weight in `ReadinessWeights`.

---

## Constitutional Compliance

### What is Constitutional Compliance?

Agents must adhere to domain-specific rules stored in the Knowledge Graph:
- **Tax Agents**: HST rules, provincial tax rates, exemption criteria
- **Medical Agents**: HIPAA regulations, clinical documentation standards
- **Legal Agents**: Confidentiality rules, document retention policies

### Validation

```python
from core.agent_graduation_service import AgentGraduationService

service = AgentGraduationService(db)

# Validate specific episode
result = await service.validate_constitutional_compliance(
    episode_id="episode_123"
)

# Returns:
# {
#   "compliant": True,
#   "score": 0.95,
#   "violations": [],
#   "episode_id": "episode_123"
# }
```

### Score Tracking

Each episode tracks:
```python
class Episode:
    constitutional_score: float  # 0.0 to 1.0
    human_intervention_count: int  # Number of corrections
    human_edits: JSON  # List of specific corrections
```

---

## Use Cases

### Use Case 1: MedScribe (Clinical Documentation)

**Scenario**: Hospital board requires proof that MedScribe agent can document clinical encounters with zero errors before autonomous operation.

**Requirements**:
- 100 episodes of clinical documentation
- 0 human interventions
- 1.0 constitutional score (HIPAA compliance)
- Full audit trail for board review
- A passed scoped capability qualification for actual clinical work; episode
  counts and historical statistics are readiness evidence only

**Implementation**:

```python
from core.episode_segmentation_service import EpisodeSegmentationService

episode_service = EpisodeSegmentationService(db)

# Create clinical documentation episodes
for encounter in patient_encounters:
    episode = await episode_service.create_episode_from_session(
        session_id=encounter.session_id,
        agent_id="medscribe_agent",
        title=f"Clinical Documentation: {encounter.patient_id}"
    )
    # Episodes track:
    # - human_intervention_count (must be 0)
    # - constitutional_score (validated against HIPAA rules)
    # - clinical_accuracy_score (validated against medical records)

# Generate audit report for hospital board
audit = await service.get_graduation_audit_trail(agent_id="medscribe_agent")

board_report = f"""
MedScribe Graduation Report for Hospital Board Review
======================================================

Agent: {audit['agent_name']}
Current Maturity: {audit['current_maturity']}

Performance Metrics:
- Total Clinical Episodes: {audit['total_episodes']}
- Total Interventions: {audit['total_interventions']}
- Avg Constitutional Score (HIPAA): {audit['avg_constitutional_score']:.2f}

Readiness: {'✓ READY FOR NEXT-TIER REVIEW' if audit['total_interventions'] == 0 else '✗ MORE TRAINING REQUIRED'}
Qualification: readiness is necessary but not sufficient; check the scoped assessment state before promotion.

Episode Breakdown by Maturity:
"""
for maturity, count in audit['episodes_by_maturity'].items():
    board_report += f"- {maturity}: {count} episodes\n"

print(board_report)
```

**Sample Output**:
```
MedScribe Graduation Report for Hospital Board Review
======================================================

Agent: MedScribe Clinical Agent
Current Maturity: AUTONOMOUS

Performance Metrics:
- Total Clinical Episodes: 100
- Total Interventions: 0
- Avg Constitutional Score (HIPAA): 1.00

Readiness: ✓ READY FOR NEXT-TIER REVIEW
Qualification: scoped task/output review required before promotion

Episode Breakdown by Maturity:
- STUDENT: 20 episodes
- INTERN: 30 episodes
- SUPERVISED: 50 episodes
- AUTONOMOUS: 0 episodes (ready to begin)

Recent Autonomous-Ready Episodes:
1. "Clinical Documentation: Patient #12345" - 0 interventions, 1.0 score
2. "Clinical Documentation: Patient #12346" - 0 interventions, 1.0 score
3. "Clinical Documentation: Patient #12347" - 0 interventions, 1.0 score
```

### Use Case 2: Brennan.ca (Sales Tax Compliance)

**Scenario**: Sales agent must understand Woodstock, Ontario pricing nuances (including HST exemptions) before sending autonomous emails to clients.

**Requirements**:
- 50 Woodstock-specific sales episodes
- 0 interventions on Woodstock pricing
- 0.95 constitutional score (Canada Tax Knowledge Graph)
- Validation of HST calculations for machinery sales

**Implementation**:

```python
from core.episode_segmentation_service import EpisodeSegmentationService

episode_service = EpisodeSegmentationService(db)

# Create Woodstock-specific training episodes
woodstock_episodes = []
for sale in woodstock_sales:
    episode = await episode_service.create_episode_from_session(
        session_id=sale.session_id,
        agent_id="sales_bot",
        title=f"Woodstock Sale: {sale.machinery_type} - HST Calculation"
    )
    woodstock_episodes.append(episode.id)

# Calculate readiness for Woodstock-specific operations
result = await service.calculate_readiness_score(
    agent_id="sales_bot",
    target_maturity="AUTONOMOUS"
)

# Filter for Woodstock episodes specifically
woodstock_count = len([ep for ep in episodes if "Woodstock" in ep.title])
woodstock_interventions = sum([
    ep.human_intervention_count for ep in episodes
    if "Woodstock" in ep.title
])

print(f"Woodstock-Specific Readiness:")
print(f"  Episodes: {woodstock_count}/50")
print(f"  Interventions: {woodstock_interventions} (must be 0)")

if woodstock_count >= 50 and woodstock_interventions == 0:
    print("✓ Readiness candidate for Woodstock sales review")
    print("  Scoped qualification review of actual task/output is still required.")
else:
    print("✗ Not ready - more training required")
```

### Use Case 3: Tax Bot (Multi-Jurisdictional Compliance)

**Scenario**: Tax calculation agent must validate HST calculations across Canadian provinces before autonomous operation.

**Requirements**:
- 100 episodes per province (ON, BC, QC, AB)
- 0 interventions on tax rate calculations
- Validation against Canada Tax Knowledge Graph
- Edge case testing for exemption scenarios

**Implementation**:

```python
# Group episodes by province
province_stats = {}
for episode in all_episodes:
    province = extract_province(episode.title)  # e.g., "ON", "BC"
    if province not in province_stats:
        province_stats[province] = {"count": 0, "interventions": 0}
    province_stats[province]["count"] += 1
    province_stats[province]["interventions"] += episode.human_intervention_count

# Validate each province meets criteria
for province, stats in province_stats.items():
    print(f"{province}: {stats['count']} episodes, {stats['interventions']} interventions")
    if stats['count'] >= 100 and stats['interventions'] == 0:
        print(f"  ✓ {province} is a readiness candidate")
        print("    Scoped qualification review of actual task/output is still required.")
    else:
        print(f"  ✗ {province} needs more training")
```

---

## Graduation Workflow

### Step 1: Check Readiness

```python
from core.agent_graduation_service import AgentGraduationService

service = AgentGraduationService(db)

result = await service.calculate_readiness_score(
    agent_id="student_agent",
    target_maturity="INTERN"
)

print(f"Ready: {result['ready']}")
print(f"Score: {result['score']}/100")
print(f"Gaps: {result['gaps']}")
print(f"Recommendation: {result['recommendation']}")
```

### Step 2: Review Historical Edge Cases (Legacy History Only)

```python
# Reviews authorized recorded traces. It does not execute the candidate and
# does not create a capability qualification receipt.
edge_cases = [
    "edge_case_tax_exemption_1",
    "edge_case_hipaa_violation_1",
    "edge_case_pricing_error_1"
]

exam_result = await service.run_graduation_exam(
    agent_id="student_agent",
    edge_case_episodes=edge_cases
)

print(f"Historical exam passed: {exam_result['passed']}")
```

A historical exam pass must never be used as the condition for promotion.

### Step 3: Review Actual Candidate Work

List the eligible task/output bundles, select the exact bundle(s) to review,
request a human review, and approve it in the ordinary Approvals queue:

```python
from core.agent_graduation_service import list_qualification_evidence_bundles

bundles = list_qualification_evidence_bundles(
    db, agent, "INTERN", tenant_id, workspace_id,
)
selected = bundles["items"][0]["evidence_refs"]

# POST /api/episodes/graduation/qualification/request
# {"agent_id": agent.id, "target_maturity": "INTERN",
#  "evidence_refs": selected, "rubric_version": "heldout-v1"}

# Approve the resulting HITL action in Approvals:
# POST /api/agents/approvals/{action_id}
# {"decision": "approved", "feedback": "Reviewed selected task and output."}
```

Only after the review is approved does the readiness response report a
`valid` qualification receipt (or an explicit owner exception). Re-read the
current readiness/assessment state before promoting; a cached or earlier
"pending" response is not a receipt.

### Step 4: Promote Agent

```python
readiness = await service.calculate_readiness_score(
    agent_id="student_agent",
    target_maturity="INTERN",
)

decision = await service.promote_agent_decision(
    agent_id="student_agent",
    new_maturity="INTERN",
    validated_by="admin_user",
)
assert decision["status"] in ("verified", "already_applied")
```

The HTTP equivalent is
`POST /api/episodes/graduation/promote?agent_id=...&new_maturity=INTERN`.
`promote_agent_decision` returns the explicit outcome; the older
`promote_agent` bool is a compatibility wrapper. A replay of the same
operation returns the original outcome without a second notification.

### Step 5: Generate Audit Trail

```python
audit = await service.get_graduation_audit_trail(agent_id="student_agent")

# Save for compliance records
with open(f"graduation_audit_{agent_id}.json", "w") as f:
    json.dump(audit, f, indent=2)
```

---

## Edge Case Testing

### What are Edge Cases?

Edge cases are historical failure scenarios from other agents. Testing current agents against these edge cases ensures they don't repeat past mistakes.

### Creating Edge Case Episodes

```python
# Create edge case episode from historical failure
edge_case = Episode(
    title="Edge Case: HST Exemption for Agricultural Machinery",
    description="Historical failure where agent incorrectly applied HST to exempt equipment",
    agent_id="archive_failed_agent",
    topics=["hst", "exemptions", "agriculture"],
    constitutional_score=0.0,  # Failed
    human_intervention_count=1,  # Required correction
    human_edits=[
        {
            "field": "tax_rate",
            "original": "0.13",
            "correction": "0.0",
            "reason": "Agricultural machinery exempt from HST"
        }
    ]
)
```

### Running Edge Case Tests

```python
exam_result = await service.run_graduation_exam(
    agent_id="current_agent",
    edge_case_episodes=[edge_case.id]
)

# Historical edge-case evidence only. This does not qualify the candidate or
# authorize promotion.
if exam_result['passed']:
    print("✓ Agent correctly handled the historical edge case")
else:
    print("✗ Agent failed the historical edge case - more training needed")
```

---

## Audit Trail Generation

### What's in the Audit Trail?

```python
audit = await service.get_graduation_audit_trail(agent_id="agent_123")

# Returns:
{
    "agent_id": "agent_123",
    "agent_name": "Tax Calculation Agent",
    "current_maturity": "INTERN",
    "total_episodes": 45,
    "total_interventions": 8,
    "avg_constitutional_score": 0.87,
    "episodes_by_maturity": {
        "STUDENT": 15,
        "INTERN": 30
    },
    "recent_episodes": [
        {
            "id": "ep_45",
            "title": "HST Calculation for Invoice #123",
            "started_at": "2026-02-03T10:30:00",
            "human_intervention_count": 0,
            "constitutional_score": 1.0
        },
        ...
    ]
}
```

### Exporting for Compliance

```python
import json
from datetime import datetime

# Generate compliance report
audit = await service.get_graduation_audit_trail(agent_id="agent_123")

report = {
    "generated_at": datetime.now().isoformat(),
    "agent_info": {
        "id": audit["agent_id"],
        "name": audit["agent_name"],
        "current_maturity": audit["current_maturity"]
    },
    "performance_metrics": {
        "total_episodes": audit["total_episodes"],
        "total_interventions": audit["total_interventions"],
        "avg_constitutional_score": audit["avg_constitutional_score"]
    },
    "episode_breakdown": audit["episodes_by_maturity"],
    "recent_episodes": audit["recent_episodes"][:10]
}

# Save to file
with open(f"graduation_audit_{agent_id}_{datetime.now().date()}.json", "w") as f:
    json.dump(report, f, indent=2)

print(f"Audit trail saved: {f.name}")
```

---

## Best Practices

### 1. Track Interventions Granularly

```python
# Instead of just counting interventions
episode.human_intervention_count = 1

# Track what was corrected
episode.human_edits = [
    {
        "timestamp": "2026-02-03T10:30:00",
        "field": "tax_rate",
        "original": "0.13",
        "correction": "0.0",
        "reason": "Agricultural machinery exempt",
        "corrected_by": "tax_expert_1"
    }
]
```

### 2. Validate Constitutional Compliance

```python
# After each episode, validate against domain rules
compliance_result = await service.validate_constitutional_compliance(
    episode_id=episode.id
)

episode.constitutional_score = compliance_result["score"]

if not compliance_result["compliant"]:
    logger.warning(f"Constitutional violations: {compliance_result['violations']}")
```

### 3. Use Domain-Specific Episodes

```python
# Create domain-specific episodes for better tracking
episode = Episode(
    title=f"{domain} Task: {specific_task}",
    topics=[domain, ...],  # e.g., ["tax", "hst", "ontario"]
    metadata={
        "domain": domain,
        "jurisdiction": jurisdiction,
        "task_type": task_type
    }
)
```

### 4. Regular Readiness Checks

```python
# Check readiness weekly
from celery import Celery

@celery.task
def weekly_readiness_check():
    agents = db.query(AgentRegistry).filter(
        AgentRegistry.status != AgentStatus.AUTONOMOUS
    ).all()

    for agent in agents:
        result = await service.calculate_readiness_score(
            agent_id=agent.id,
            target_maturity=get_next_maturity(agent.status)
        )

        if result["ready"]:
            notify_admins(
                subject=f"Agent {agent.name} ready for promotion",
                body=f"Score: {result['score']}/100\n{result['recommendation']}"
            )
```

---

## Troubleshooting

### Problem: Agent Not Ready Despite Good Performance

**Symptoms**: High episode count, low interventions, but score < 70

**Possible Causes**:
1. Low constitutional score dragging down average (or constitutional not recorded → factor excluded, check breakdown)
2. Low confidence score from recent self-assessments
3. Poor success rate despite low interventions
4. Low supervision success rate (intern/supervised tiers — approval-driven)
5. Below the minimum episode count for the target level (10/25/50)

**Solution**:
```python
# Check each component separately (weights are per target level — see
# ReadinessWeights; the example below uses the student→intern table)
weights = {"zero_intervention": 35, "constitutional": 25, "confidence": 20, "success": 20}

zero_intervention = zero_interventions / total_episodes
constitutional = avg_constitutional_score       # None/absent → factor excluded
confidence = avg(episode.confidence_score)      # None/absent → factor excluded
success = successful_tasks / total_tasks

print(f"Zero Intervention ({weights['zero_intervention']}%): {zero_intervention:.2f}")
print(f"Constitutional ({weights['constitutional']}%): {constitutional if constitutional is not None else 'NOT RECORDED → excluded'}")
print(f"Confidence ({weights['confidence']}%): {confidence if confidence is not None else 'NOT RECORDED → excluded'}")
print(f"Success Rate ({weights['success']}%): {success:.2f}")

# Unrecorded factors are dropped and the rest renormalized — the readiness
# breakdown from EpisodeService.get_graduation_readiness() reports exactly
# which weights were applied and which factors were excluded.
print(f"\nBreakdown: {readiness.breakdown['weights']}")

# Address the weakest applied component
```

### Problem: Interventions Not Tracking

**Symptoms**: `human_intervention_count` always 0 despite corrections

**Solution**:
```python
# Explicitly track interventions in agent code
if human_correction_made:
    episode.human_intervention_count += 1
    episode.human_edits.append({
        "timestamp": datetime.now().isoformat(),
        "field": corrected_field,
        "original": original_value,
        "correction": corrected_value,
        "reason": correction_reason
    })
```

---

## Governance integration background

> **Status:** implemented and wired (reintroduced 2026-08-30). The original
> general-purpose version was removed 2026-08-20 because it was never wired
> into any live path; this version is scoped to graduation decisions and
> enforced in `GraduationExamService.execute_graduation_exam` (Stage 5.5)
> and `AgentGraduationService.promote_agent_decision` (the `promote_agent`
> bool is a compatibility wrapper) — see
> `tests/test_governance_graduation_integration.py`.

### Three-Layer Governance

Graduation decisions route through **three governance layers**
(`core/governance/dynamic_governance.py`):

| Layer | Graduation Role | Decision Type | Wired at |
|-------|----------------|---------------|----------|
| **OPERATIONAL** | student → intern checks | Automated | Exam Stage 5.5 |
| **TACTICAL** | intern → supervised with policy review | Adaptive (policy floors) | Exam Stage 5.5 |
| **STRATEGIC** | supervised → autonomous | **Human-in-the-loop** | Exam Stage 5.5 + promote gate |

**STRATEGIC semantics:** when a supervised agent passes every exam gate
for AUTONOMOUS, the exam records `passed=True` but **withholds the
promotion** (`promoted=False`, `awaiting_human_approval=True`). A
supervisor then completes it via `POST /api/episodes/graduation/promote`,
which re-evaluates the same policy against live evidence. Agents can no
longer auto-promote to AUTONOMOUS.

**Usage:**
```python
from core.governance import DynamicGovernanceManager, GovernanceLayer

manager = DynamicGovernanceManager()

# OPERATIONAL layer - standard graduation checks (automated allow)
decision = manager.decide(
    agent_id="agent_123",
    action="graduate_to_intern",
    layer=GovernanceLayer.OPERATIONAL,
    context={"episode_count": 12, "readiness_score": 0.75, ...},
)
assert decision.allowed and not decision.requires_human

# STRATEGIC layer - policies pass AND human approval required
decision = manager.decide(
    agent_id="agent_123",
    action="graduate_to_autonomous",
    layer=GovernanceLayer.STRATEGIC,
    context={"episode_count": 60, "readiness_score": 0.96, ...},
)
assert decision.allowed and decision.requires_human
```

### Policy-Based Graduation

Graduation criteria are enforced by the policy engine
(`core/governance/policy_engine.py`). **Default policies are derived from
`ReadinessThresholds` and the per-level minimum episode counts** (10 / 25 /
50), so the policy layer cannot drift from the exam's own gates. A rule
whose evidence is missing counts as violated.

```python
from core.governance.policy_engine import PolicyEngine, GovernancePolicy, PolicyPriority

engine = PolicyEngine()  # seeds the default graduation policies

# Custom policies can extend the defaults
policy = GovernancePolicy(
    policy_id="graduation_policy",
    priority=PolicyPriority.HIGH,
    condition="action == 'graduate_to_autonomous'",
    effect="DENY",
    layer="strategic",
    rules={
        "min_episodes": 50,
        "max_intervention_rate": 0.0,
        "min_constitutional_score": 0.95
    }
)

engine.register_policy(policy)

# Evaluate graduation request
result = engine.evaluate(
    agent_id="agent_123",
    action="graduate_to_autonomous",
    layer="strategic",
    context={
        "episode_count": 48,
        "intervention_rate": 0.02,
        "constitutional_score": 0.92
    }
)
# Result: DENIED (episodes < 50, intervention > 0%, score < 0.95)
```

Rule → context-key mapping: `min_episodes` → `episode_count`,
`max_intervention_rate` → `intervention_rate`; the rest match by name
(`readiness_score`, `success_rate`, `constitutional_score`,
`confidence_score`).

See [Agent Governance](governance.md) for the full governance
architecture, and
`backend/tests/test_governance_graduation_integration.py` for the
enforcement contract in executable form.

---

## Next Steps

1. **Set up tracking**: Ensure all agent executions track interventions
2. **Create domain-specific episodes**: Organize episodes by domain/jurisdiction
3. **Validate constitutional compliance**: Run compliance checks after each episode
4. **Schedule readiness checks**: Automate weekly readiness assessments
5. **Review actual candidate work**: Select explicit task/output evidence and
   request a current authorized qualification review before promotion
6. **Generate audit trails**: Export reports for governance compliance

Readiness scores, historical exam passes and controlled mechanism tests do not
establish live model competence or full app acceptance. Treat them as bounded
contract evidence, not a marketing claim.

For more information:
- [Episodic Memory Implementation](../intelligence/episodic-memory.md)
- Quick Start Guide
- [API Documentation](../../backend/api/episode_routes.py)

---

## Related Documentation

### Agent Learning & Intelligence
- **[Self-Evolution & Reflection Pool](../intelligence/self-evolution.md)** - Critique-based learning, Memento-Skills, and AlphaEvolver for autonomous agent improvement
- **[Episodic Memory](../intelligence/episodic-memory.md)** - Episode tracking and retrieval system for agent learning
- **[GraphRAG & Entity Types](../intelligence/graphrag.md)** - Knowledge graph and entity extraction
- **[JIT Fact Provision System](../intelligence/jit-facts.md)** - Real-time knowledge retrieval and fact verification

### Agent Systems
- **[Agent Governance](governance.md)** - Maturity levels and permissions system
- **[Student Training](training.md)** - Maturity routing and training proposals
- **Queen Agent** - Structured workflow automation
- **[Fleet Admiral](fleet-admiral.md)** - Dynamic agent recruitment for unstructured tasks

### Integration Guides
- **Auto-Dev User Guide** - Self-evolving agent capabilities (Memento-Skills, AlphaEvolver)
- **[Memory Integration Guide](../intelligence/memory-integration.md)** - Complete memory system integration
