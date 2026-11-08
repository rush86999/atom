<div align="center">

# Atom — Open-source AI agents with built-in governance

### Put AI to work. Keep control of its actions.

**Automate business tasks with AI agents, reviewable results and controls over what they can do.**

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](LICENSE.md)
[![Python](https://img.shields.io/badge/Python-3.11%E2%80%933.13-blue)](docs/getting_started/quick-start.md)
[![Local workflows](https://img.shields.io/badge/local_workflows-verified-green)](docs/acceptance/VERIFIER_ACCEPTANCE_2026-11-01.md)

[Try locally](#try-atom-locally) · [See the workflows](docs/demo/VERIFIED_WORKFLOWS.md) · [What's verified](#what-you-can-rely-on) · [Report an issue](https://github.com/rush86999/atom/issues)

</div>

![Atom workspace](https://github.com/user-attachments/assets/398de2e3-4ea6-487c-93ae-9600a66598fc)

## Start with a job you already do

Atom is a self-hosted AI agent platform for business automation and AI governance.
Give it files, instructions and rules; inspect the work and control which actions
require human review. For example, give Atom a price list to prepare a quote,
or check an invoice against purchase and receiving records, then produce a document showing
the result. Inspect the source records, calculations and output before using it.

**Open source and self-hosted.** Run your own copy and configure a supported
local or hosted model. The starter sample below needs no model or cloud key.

**Teach your rules. Review the work. Keep the context.**

- **Turn company data into deliverables.** Demonstrated workflows map unfamiliar
  spreadsheet columns, calculate against source records and produce cited
  Word or PowerPoint documents within supported schemas.
- **Make your rules reusable.** Save field mappings, commercial terms and
  contextual lessons. New work adopts accepted corrections; active work keeps
  its accepted teaching snapshot.
- **Handle work that needs an answer.** Supported durable questions, approvals
  and waits survive restarts. Completed operations are retained, and uncertain
  effects need reconciliation before another attempt.
- **Keep decisions reviewable.** Author ordered policies in the canvas editor.
  Supported deterministic rules retain unresolved requirements rather than
  inventing an approval.
- **Bring your own model.** Configure a supported provider or local
  OpenAI-compatible endpoint. Model capability and permissions still matter;
  the starter sample needs no model or cloud key.

Atom's deployment model is **single tenant**: a locally owned workspace with
user, role and workspace boundaries. The workflows below have recorded local
or controlled-provider evidence. General autonomous judgment and universal
business automation remain development goals.

[**Run the local sample →**](#try-atom-locally) ·
[**Explore demonstrated workflows →**](#see-what-an-employee-can-do) ·
[**Check the evidence and limits →**](#what-you-can-rely-on)

## AI governance: control what agents can do

Useful AI needs more than a convincing answer. It needs boundaries around data,
actions and authority. Atom brings AI governance into the execution path through
permissions, policy checks, human approval checkpoints and durable audit records
on supported paths. A model proposal is not permission to act.

- **Human-in-the-loop approvals:** supported governed actions pause for a bound
  review; missing, rejected or mismatched approval cannot authorize the action.
- **Reviewable execution:** supported results retain source and operation
  provenance. Unresolved requirements block completion and dependent reports.
- **Controlled autonomy:** agent graduation toward greater autonomy is an
  explicit project goal; broad autonomous competence is not claimed.

These are engineering controls with recorded acceptance boundaries, not a claim
of regulatory certification or universal protection against AI risks.

## An agent framework beyond a single task

Quotes and invoices make the behavior easy to inspect; they are examples, not
an industry restriction. The broader project covers **multi-agent orchestration,
durable workflows, agent memory, human oversight, BYOK model and cost routing,
MCP tools, and business integrations**. Availability and qualification differ by feature and
release profile; a registered capability does not mean every connected service
or autonomous use case is verified.

Start with the demonstrated workflows below. Consult the evidence and limits
before relying on a broader capability in production.

## Try Atom locally

**Prerequisites:** Git, Make, Python **3.11–3.13** (3.11 recommended), Node.js
**20.9+** and npm. Python 3.14 is not supported by this dependency set.

~~~bash
git clone https://github.com/rush86999/atom.git
cd atom
PYTHON=python3.11 make setup
make dev
~~~

In a second terminal, from the same `atom` directory:

~~~bash
make sample
~~~

Open **http://localhost:3001**. Sign in as `admin@example.com` using the
generated password in `backend/logs/bootstrap_admin_password.txt`. Open
**Assignments** to find the completed sample and download its Word document.

**Your first result:** *Sample Quote Analyst* reads
[`sample-workspace/sample_quote.csv`](sample-workspace/sample_quote.csv),
calculates **232990.00**, and creates a DOCX. Its lessons are editable under
**Agents → Sample Quote Analyst → Training**. The sample uploads local data
and creates local records/artifacts; it sends no email and needs no connected
account or cloud credential.

![Completed sample assignment](docs/demo/evidence/first-use-assignments.png)

If the default ports are busy, use the same pair for startup and the sample:

~~~bash
BACKEND_PORT=8101 FRONTEND_PORT=3101 make dev
# Second terminal:
make sample PORT=8101 FE_PORT=3101
~~~

Then open http://localhost:3101. Stop the development processes with **Ctrl+C**;
restart with `make dev` against the same checkout to keep your local data.
Do not delete the database or generated keys to troubleshoot an existing install.

**Measured first use:** approximately **5 min 15 s** on one fresh-worktree run
with warm package caches, including setup, startup, sample and browser access.
**15 minutes is a cold-install target, not a measured guarantee.** See the
[setup guide](docs/getting_started/quick-start.md) and
[measured first-use record](docs/demo/FIRST_USE_TEST_2026-11-01.md).

## See what an employee can do

| Workflow | What the recorded acceptance demonstrates |
|---|---|
| **Sales quote** | Unfamiliar columns → confirmed mapping → source-grounded total → formatted document; corrected teaching applies to new work. |
| **Grant review** | A second business domain uses the same teaching, calculation, clarification and artifact mechanisms. |
| **Workbook editing** | A tested 24-sheet workbook preserves identifiers and formulas through supported recalculation, export and restart/reopen. |
| **Long-running assignment** | More than two hours waiting, real backend restarts, the same assignment resumes, completed source work is retained and one controlled effect is recorded. |
| **Learn from conversations** | Review a persisted email thread, resolve referenced resources, confirm a lesson and apply it only in its accepted context. |

The [demo guide](docs/demo/VERIFIED_WORKFLOWS.md) distinguishes reproducible
steps from historical runs and lists their exact sources. The two-hour run is
elapsed/recovery evidence on its recorded source; later budget repairs have
their own focused verification.

## What you can rely on

**111 of 123 frozen functional claims (90.2%) were accepted within the documented
local and controlled-provider configurations.** This is a source-bound feature
coverage milestone, not a promise of 90% accuracy or universal reliability.

| Reference | Purpose |
|---|---|
| [`successor-first-use-2026-11-01`](https://github.com/rush86999/atom/tree/successor-first-use-2026-11-01) | Recommended reproducible snapshot with the correctness and first-use fixes. |
| [`accepted-local-2026-11-01-90pct`](https://github.com/rush86999/atom/tree/accepted-local-2026-11-01-90pct) | Immutable historical acceptance reference; its later-discovered budget defect is documented. Prefer the repaired successor for use. |
| [Acceptance and repairs](docs/acceptance/VERIFIER_ACCEPTANCE_2026-11-01.md) | Exact identities, independent checks and scope. |
| [Frozen feature inventory](docs/acceptance/readme_feature_readiness_2026-11-01/CLAIM_INVENTORY.json) | Verified, partial and excluded claims; denominator unchanged. |
| [Successor release notes](docs/acceptance/SUCCESSOR_RELEASE_2026-11-01.md) | Changes from the baseline and first-use measurements. |

To use the fixed snapshot rather than development `main`, run
`git checkout successor-first-use-2026-11-01` **before** `make setup`.

### Recent verified progress

Development `main` also includes newer, separately scoped evidence. These do
not change the frozen 111/123 score or qualify universal employee judgment.

| Capability | Verified boundary |
|---|---|
| **Stored-text document exports** | An ordinary TXT upload, open and reload journey verified downloads as Text, Markdown and JSON with current source-version binding. This exports stored text, not the original binary file; other formats and grounding remain separately qualified. |
| **Information-triggered continuation** | An ordinary source-answer UI episode preserved the same task, wait and source version through a real restart; an authorized answer triggered continuation to one verified task effect and final UI. Model responses were controlled, not a model-quality benchmark. |
| **Goal controls** | Ordinary UI goal set, ranking, reload and clear, with a member read-only/refusal twin. Analytics history used synthetic fixtures. |
| **Backup and restore** | A normal application child-process restart verified restored records and exact document bytes in an isolated local world; this is not whole-app disaster-recovery or crash-durability qualification. |
| **Model-routing feedback** | Scoped business verdicts and shared conditional updates have SQLite and targeted PostgreSQL verification. Grounding support, unresolved decisions and satisfied business outcomes remain distinct. Served multi-model quality is still open. |

See the [current completion and evidence map](docs/engineering/APP_COMPLETION_STATE_2026_11_07.md)
for exact source identities, retained negative results and remaining requirements.

### Long-running coordination: the product goal

A task should be able to request a missing fact from an authorized person or
system, wait durably without repeated prompting, continue independent work,
and resume the same task when the relevant information arrives—even after days
of waiting and application restarts. It may need several request/wait/resume cycles before delivering a
verified result. This is a **general app goal with bounded demonstrations**,
not a claim of universal autonomous coordination or live third-party outreach.

For example, a customer quote may depend on a vendor's availability, price and
lead time. Once authorized information arrives, dependent work should calculate
landed cost and the taught margin or markup, then prepare a quote with supported
lead-time assumptions. Procurement is only an illustration: the same mechanism
must handle dependencies, facts and outputs across domains. It must never invent
missing values, treat an unanswered request as completion, or send/order/spend
without the required authority. See [TASK-WAIT-01 acceptance requirements](docs/acceptance/GOAL_COMPLETION_DELTA_2026_11_06.md#task-wait-01--long-running-tasks-pause-for-information-and-resume-on-its-arrival).

### Clear boundaries

- The demonstrated local topology is **single worker**. Multi-worker execution
  and long soak behavior are not qualified.
- The sample and main acceptance campaigns use local or controlled providers.
  Deterministic taught policy is qualified separately from discretionary model
  judgment; the tested small-model judgment configuration failed qualification.
- **One specifically authorized Outlook send and Microsoft read-only ingestion
  were separately qualified.** That does not qualify every connector, broader
  live sending, autonomous live sending or independent recipient delivery.
- Supported workbook formulas and taught schemas are bounded. Arbitrary Excel
  compatibility, arbitrary schema understanding and UI-taught rounding are not
  promised.
- The broader platform includes workflow, routing, graph, governance and
  integration surfaces. Some need `ATOM_PRODUCT_PROFILE=full`, a configured
  provider or additional infrastructure. Consult the inventory before relying
  on a particular feature.

## Common questions

**Is Atom an AI agent framework or an AI employee app?**

Both: the employee workspace uses the app's shared agent, tool, workflow and
governance mechanisms. “AI employee” describes the business-facing experience;
it is not a separate replacement for the agent framework.

**Can I use it with a local model?**

Yes. Atom supports local inference through configured routes, including Ollama.
A model must meet the workload's capability requirements; local availability
alone does not establish reliable business judgment.

**Can an agent wait for information for days?**

Durable wait/restart/answer workflows are demonstrated at their recorded scopes.
General days-long coordination with external people and systems is an explicit
[acceptance goal](docs/acceptance/GOAL_COMPLETION_DELTA_2026_11_06.md#task-wait-01--long-running-tasks-pause-for-information-and-resume-on-its-arrival).
It is not yet a universal capability claim.

**Does running locally keep all data on my computer?**

Local storage and local inference can support a local workflow. If you configure
a cloud model or connector, the data you send follows that service's terms and
your authorized access. See [security boundaries](docs/security/TRUST_VS_SANDBOX.md).

## Connect your own data and models

After the sample, open **Settings** to configure a provider and the connections
you need. Provider usage and connector access depend on your account and
permissions. Keep credentials out of issues, screenshots and commits.

For local inference, see [Run with Ollama](docs/getting_started/run-with-ollama.md).
For connected Office work, see [Office automation](docs/guides/ATOM_OFFICE_AUTOMATION_GUIDE.md)
and [OAuth setup](docs/guides/OAUTH_QUICK_SETUP_GUIDE.md). Local storage does not
make cloud inference private: data sent to a configured provider follows that
provider's terms.

## Documentation and contributing

- [Documentation hub](docs/README.md) · [Quick start](docs/getting_started/quick-start.md)
- [Verified workflow walkthroughs](docs/demo/VERIFIED_WORKFLOWS.md)
- [Troubleshooting](docs/getting_started/TROUBLESHOOTING.md)
- [Architecture](docs/architecture/README.md) · [Security boundaries](docs/security/TRUST_VS_SANDBOX.md)
- [Brennan business-workflow engineering orders](docs/engineering/brennan/README.md)
- [Contributing](CONTRIBUTING.md) · [Open an issue](https://github.com/rush86999/atom/issues)

For a useful bug report, include the commit/tag, operating system, launch
command, expected result and a minimal sanitized example. Please do not include
passwords, tokens, private documents or your database.

Atom is already public on GitHub under [AGPL v3](LICENSE.md). Hosted deployment
is separate from the verified local setup. If this project helps your work,
**star the repository, try a real workflow and tell us where it gets stuck.**
