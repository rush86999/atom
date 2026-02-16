# Feature Roadmap: OpenClaw Integration

## Overview

Inject the "essence" of OpenClaw (formerly Moltbot) into Atom Agent OS without losing enterprise-grade governance. OpenClaw went viral by being a "companion" (chat-based, local shell access, "cowboy" coding), while Atom is a "manager" (governance, workflows, safety). This initiative brings Atom out of the dashboard and into the user's pocket and terminal.

**Core Philosophy**: Atom users should be able to text their agents from the grocery store, give agents controlled local shell access that earns trust over time, and observe agents "thinking" through a social feed—all while maintaining enterprise-grade governance, audit trails, and safety.

**Last Updated**: February 16, 2026

**Research**: See `.planning/feature-research/OPENCLAW_INTEGRATION_RESEARCH.md` for detailed technical analysis.

## Key Principles

1. **Governance First** - Every new feature maintains Atom's governance architecture (STUDENT → INTERN → SUPERVISED → AUTONOMOUS)
2. **Always Attributable** - All actions (IM commands, shell executions, social posts) are logged to audit trail
3. **Safe by Default** - Personal Edition differs in features (multi-user, SSO), NOT safety (governance, 2FA, audit always on)
4. **Earned Trust** - Agents suggest before executing; autonomy is granted through demonstrated reliability
5. **Observable Operations** - Agent thoughts are visible through social feed, not hidden in logs

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Major feature milestones
- Decimal phases (1.1, 1.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: "Everywhere" Interface (IM Adapters)** - WhatsApp, Telegram adapters that treat the user as a "contact" with governance routing
- [ ] **Phase 2: "God Mode" Local Agent** - Controlled shell/file access outside Docker with maturity-based permissions
- [ ] **Phase 3: "Moltbook" Social Layer** - Agent-to-agent communication feed with observable thoughts and status updates
- [ ] **Phase 4: Simplified Entry Point** - Single-line installer (pip install atom-os) with Personal/Enterprise editions
- [ ] **Phase 5: Community Skills Integration** - Import 5,000+ OpenClaw/ClawHub skills via Markdown+YAML adapters with Docker sandbox security

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. IM Adapters | 4/4 + 2 gap closure | **Gap Closure** | Plans 01-04 complete, verification found 3 gaps |
| 2. God Mode Local Agent | 4/4 | **Complete** | February 16, 2026 |
| 3. Moltbook Social Layer | 3/3 | **Complete** | February 16, 2026 |
| 4. Simplified Installer | 0/3 | **Pending** | - |
| 5. Community Skills Integration | 0/3 | **Pending** | - |

**Overall Progress**: 11/17 plans complete (65%)

---

## Phase Details

### Phase 1: "Everywhere" Interface (IM Adapters)

**Goal**: Users can interact with Atom agents via WhatsApp and Telegram from anywhere, with governance routing maintaining security

**Depends on**: Nothing (first phase)

**Requirements**: IM-01, IM-02, IM-03, IM-04, IM-05, GOV-01, GOV-02

**Success Criteria** (what must be TRUE):
1. User can send "Run the payroll report" via Telegram and receive response
2. User can send "Deploy PR #113" via WhatsApp and Atom requests 2FA approval for critical action
3. Incoming IMs are routed through IMGovernanceService which verifies identity and checks permissions
4. All IM interactions are logged to audit trail (user, message, agent, response, timestamp)
5. Rate limiting prevents spam/abuse (10 requests/minute per user)
6. Webhook signature verification prevents spoofing (X-Hub-Signature for WhatsApp, secret token for Telegram)

**Libraries** (from research):
- **Telegram**: `python-telegram-bot` (official, maintained, 200k+ weekly downloads)
- **WhatsApp**: `PyWa` (WhatsApp Cloud API wrapper, active development)
- **Signal**: Deferred (no official API, all libraries are unofficial bridges)

**Architecture**:
```
User IM (Telegram/WhatsApp)
  ↓ Webhook
IMGovernanceService (identity verification, rate limiting)
  ↓
AgentGovernanceService (maturity check, action complexity scoring)
  ↓
2FA Approval (if complexity ≥3)
  ↓
AgentOrchestrator (execute)
  ↓
IMGatewayService (format response for IM)
  ↓
User receives response
```

**Security Considerations**:
- Webhook signature verification mandatory (prevent spoofing)
- User identity verification via phone number matching
- Maturity-based routing: STUDENT agents receive "training mode" responses for critical actions
- Action complexity scoring: 1-2 (auto-execute), 3-4 (2FA required), 5+ (blocked)

**Plans**: 4 original + 2 gap closure
- [x] 01-im-adapters-01-PLAN.md — IMGovernanceService implementation (sliding window rate limiting, webhook verification, governance checks, audit trail) ✅
- [x] 01-im-adapters-02-PLAN.md — WhatsApp webhook route + Telegram governance integration (missing endpoint added, both use IMGovernanceService) ✅
- [x] 01-im-adapters-03-PLAN.md — IM adapter tests (security testing: webhook spoofing, rate limiting, governance, audit trail) ✅
- [x] 01-im-adapters-04-PLAN.md — Documentation (IM_ADAPTER_SETUP.md, IM_SECURITY_BEST_PRACTICES.md, README.md updates) ✅
- [ ] 01-im-adapters-05-PLAN.md — Gap Closure: Fix security issues (Telegram timing attack, WhatsApp hardcoded token) 🔄
- [ ] 01-im-adapters-06-PLAN.md — Gap Closure: Fix rate limiting documentation (algorithm mismatch) 🔄

**Wave Structure**:
- Wave 1: Plan 01 (IMGovernanceService) - foundational security layer ✅
- Wave 2: Plan 02 (WhatsApp route), Plan 03 (Tests) - parallel execution ✅
- Wave 3: Plan 04 (Documentation) - after implementation complete ✅
- Wave 4 (Gap Closure): Plan 05 (Security fixes), Plan 06 (Documentation updates) - parallel execution 🔄

**Verification Gaps** (from 01-im-adapters-VERIFICATION.md):
- Gap 1: Rate limiting algorithm mismatch (documented as SlowAPI/token bucket, actually sliding window)
- Gap 2: Telegram timing attack vulnerability (uses `==` instead of `hmac.compare_digest`)
- Gap 3: WhatsApp hardcoded verify token (`"YOUR_VERIFY_TOKEN"` instead of env var)

---

### Phase 2: "God Mode" Local Agent

**Goal**: Specialized "Local Device Agent" runs outside Docker container with controlled shell/file access, using maturity model to earn trust

**Depends on**: Phase 1 (governance patterns established)

**Requirements**: SHELL-01, SHELL-02, SHELL-03, SHELL-04, GOV-03, GOV-04

**Success Criteria** (what must be TRUE):
1. Local agent can read/write files on host Desktop (outside Docker container)
2. Local agent can execute terminal commands on host machine with maturity-based permissions
3. Student local agent suggests shell commands but requires user approval
4. Agent earns autonomy: safe directories (/tmp/, ~/Documents/) → AUTONOMOUS, critical (/etc/, root) → STUDENT only
5. All shell executions are logged to audit trail (command, approval, result, timestamp)
6. Command injection protection via strict whitelisting (NEVER shell=True)

**Libraries** (from research):
- **Shell Execution**: `subprocess` (stdlib, shell=False, whitelist-based)
- **File Operations**: `pathlib` (stdlib, cross-platform paths)
- **Command Sanitization**: `plumbum` (safe shell command construction)

**Architecture**:
```
User Request (local terminal or IM)
  ↓
LocalAgentService (runs on host, outside Docker)
  ↓
GovernanceCache (check directory permissions)
  ↓
AgentMaturityCheck (STUDENT → suggest, INTERN → suggest, SUPERVISED → ask, AUTONOMOUS → execute)
  ↓
IF maturity < required:
  PromptUser (show command, ask approval)
  ↓
ELSE:
  ExecuteCommand (subprocess with whitelist)
  ↓
LogToAudit (command, approval, result)
  ↓
ReturnResult
```

**Directory-Based Permissions**:
```
STUDENT (all agents):    /tmp/, ~/Downloads/ (suggest only)
INTERN:                  /tmp/, ~/Downloads/, ~/Documents/ (ask for approval)
SUPERVISED:              ~/Documents/, ~/Desktop/ (ask for approval)
AUTONOMOUS:              /tmp/, ~/Downloads/, ~/Documents/ (auto-execute)
BLOCKED:                 /etc/, /root/, /sys/ (STUDENT only, log attempt)
```

**Shell Command Whitelist**:
```python
ALLOWED_COMMANDS = {
    'ls': ['all', 'safe', 'critical'],
    'cat': ['all', 'safe'],
    'grep': ['all', 'safe'],
    'mkdir': ['autonomous', 'supervised'],  # Can create dirs in safe spaces
    'rm': ['autonomous'],  # Only autonomous can delete
    'cp': ['autonomous', 'supervised'],
    'mv': ['autonomous', 'supervised'],
    'git': ['all'],  # Safe everywhere
    'npm': ['autonomous'],  # Only if fully trusted
    # etc.
}
```

**Security Considerations**:
- **Command Injection**: Use subprocess with shell=False, never trust user input
- **Path Traversal**: Validate all paths with pathlib, reject /etc/, /root/, /sys/
- **Privilege Escalation**: Local agent runs as non-root user, no sudo
- **Docker Escape**: Local agent runs on host, NOT in container (separate deployment)

**Deployment**:
```yaml
# docker-compose.yml (existing)
services:
  atom-backend:
    # Enterprise backend (governance, API, dashboard)

# NEW: Local agent (separate process)
# User runs: python -m atom.local_agent_main
```

**Plans**: 4 plans
- [x] 02-local-agent-01-PLAN.md — LocalAgentService implementation (host process, governance integration) ✅
- [x] 02-local-agent-02-PLAN.md — Directory-based permissions (GovernanceCache extension, path validation) ✅
- [x] 02-local-agent-03-PLAN.md — Shell command whitelist & execution (subprocess, maturity checks) ✅
- [x] 02-local-agent-04-PLAN.md — Testing & security validation (command injection tests, path traversal tests) ✅

---

### Phase 3: "Moltbook" Social Layer

**Goal**: Agent-to-agent communication feed ("Watercooler") where agents post status updates about their operations, making swarm observation engaging

**Depends on**: Phase 2 (local agent operations generate social posts)

**Requirements**: SOCIAL-01, SOCIAL-02, SOCIAL-03, SOCIAL-04

**Success Criteria** (what must be TRUE):
1. Agents post natural language "status updates" when accessing shared context
2. Social feed is visible in dashboard (real-time WebSocket updates)
3. Posts are generated automatically (not manual agent logs): "Just saw PR #123, running tests..."
4. PII is redacted from public posts (user emails, secrets, sensitive data)
5. Users can reply to agent posts (feedback loop to agents)
6. Social posts are logged to audit trail (agent, content, timestamp, related operations)

**Libraries** (from research):
- **Real-time Updates**: Redis pub/sub (already in Atom for WebSocket)
- **Natural Language Generation**: OpenAI GPT-4.1 mini (cheap, fast, $0.15/1M tokens)
- **PII Redaction**: Presidio (Microsoft's privacy library, 99% accuracy)

**Architecture**:
```
Agent Operation (any agent)
  ↓
OperationTracker (existing: AgentOperationTracker)
  ↓
IF operation accesses shared context OR completes significant task:
  SocialPostGenerator (GPT-4.1 mini generates "status update")
  ↓
PIIRedactor (Presidio removes sensitive data)
  ↓
SocialFeedService (Redis pub/sub)
  ↓
WebSocket (push to dashboard)
  ↓
User sees: "Engineering Agent: Just saw PR #123, running tests before I roast @rush"
```

**Social Post Examples**:
```
Engineering Agent: "Just saw a new PR from @rush. The code looks messy; running tests before I roast him."
Sales Agent: "Replied to the engineering agent: Don't be mean, we need this feature for the Q1 demo."
Data Agent: "Finished analyzing Q4 sales data. Revenue up 23% YoY. Posting charts to canvas."
Local Agent: "User approved shell command 'npm install'. Installing packages..."
```

**Triggers for Social Posts**:
1. Agent accesses shared context (Swarm Discovery, Universal Memory)
2. Agent completes significant task (workflow execution, report generation)
3. Agent receives human feedback (thumbs up/down, correction)
4. Agent requests approval (2FA, shell command, file operation)
5. Agent-to-agent communication (one agent calls another's API)

**PII Redaction Rules**:
```python
REDACT_PATTERNS = {
    'email': r'[^@]+@[^@]+\.[^@]+',
    'phone': r'\d{3}-\d{3}-\d{4}',
    'ssn': r'\d{3}-\d{2}-\d{4}',
    'credit_card': r'\d{4}-\d{4}-\d{4}-\d{4}',
    'api_key': r'[A-Za-z0-9]{32,}',  # Long alphanumeric strings
    'secret': r'secret|token|password|key',  # Keyword-based
}
```

**Privacy Controls**:
```python
POST_VISIBILITY = {
    'public': 'All agents and users can see',
    'workspace': 'Only users in same workspace',
    'private': 'Only agent owner (for debugging)',
    'redacted': 'PII removed, safe to share',
}
```

**Integration with Existing Features**:
- **Swarm Discovery**: When agents discover each other, generate "hello" posts
- **Universal Memory**: When agents access episodic memory, generate "learning" posts
- **Canvas Presentations**: When agents present data, generate "sharing" posts
- **Feedback System**: When users give feedback, generate "reflection" posts

**Plans**: 3 plans (Wave 1: 01-02 parallel, Wave 2: 03)
- [x] 03-social-layer-01-PLAN.md — Automatic post generation (AgentOperationTracker hooks, GPT-4.1 mini NLG, rate limiting) ✅
- [x] 03-social-layer-02-PLAN.md — PII redaction with Presidio (NER-based detection, allowlist, audit logging) ✅
- [x] 03-social-layer-03-PLAN.md — Full communication matrix (replies, channels, Redis pub/sub, cursor pagination) ✅

---

### Phase 4: Simplified Entry Point

**Goal**: Single-line installer (pip install atom-os) with "Personal Edition" that hides enterprise features until explicitly enabled

**Depends on**: Phases 1-3 (all features integrated)

**Requirements**: PKG-01, PKG-02, PKG-03, PKG-04, PKG-05

**Success Criteria** (what must be TRUE):
1. User can run `pip install atom-os` and get working Atom installation
2. Personal Edition installs with: Local Agent + Telegram Connector (no multi-user, no SSO, no enterprise dashboard)
3. User can enable enterprise features: `atom enable enterprise --workspace-id=acme-corp`
4. Feature flags control which features are available (PackageFeatureService)
5. Package is published to PyPI (or private package index)
6. Installation documentation covers Personal vs Enterprise editions

**Libraries** (from research):
- **Package Building**: `pyproject.toml` with setuptools (2026 standard)
- **Feature Flags**: Custom `PackageFeatureService` (centralize feature availability)
- **CLI**: `typer` (type-safe CLI, already in Atom for some tools)

**Architecture**:
```toml
# pyproject.toml
[project]
name = "atom-os"
version = "1.0.0"
description = "Atom Agent OS - AI-powered business automation"

[project.optional-dependencies]
enterprise = [
    "atom-os[local,im,social]",
    "sqlalchemy>=2.0",  # Enterprise database
    "redis>=5.0",        # Enterprise cache
    "celery>=5.0",       # Enterprise tasks
]
personal = [
    "atom-os[local,im]",
    "sqlite-unicode",    # Local database only
]
all = ["atom-os[enterprise]"]

[project.scripts]
atom = "atom.cli:main"
```

**Feature Flags**:
```python
# PackageFeatureService.py
FEATURES = {
    'local_agent': {
        'personal': True,
        'enterprise': True,
        'description': 'Local shell/file access',
    },
    'im_telegram': {
        'personal': True,
        'enterprise': True,
        'description': 'Telegram integration',
    },
    'im_whatsapp': {
        'personal': False,  # Business verification required
        'enterprise': True,
        'description': 'WhatsApp integration',
    },
    'social_feed': {
        'personal': True,
        'enterprise': True,
        'description': 'Agent social layer',
    },
    'multi_user': {
        'personal': False,
        'enterprise': True,
        'description': 'Multiple users per workspace',
    },
    'sso': {
        'personal': False,
        'enterprise': True,
        'description': 'SAML/Single Sign-On',
    },
    'enterprise_dashboard': {
        'personal': False,
        'enterprise': True,
        'description': 'Admin dashboard',
    },
}
```

**Installation Flows**:

**Personal Edition** (default):
```bash
pip install atom-os
atom init  # Creates ~/.atom/config.json
atom start local  # Starts local agent
atom connect telegram  # Connects Telegram
```

**Enterprise Edition** (opt-in):
```bash
pip install atom-os[enterprise]
atom init --workspace-id=acme-corp --api-key=xxx
atom start enterprise  # Starts full backend
```

**Package Structure**:
```
atom-os/
├── atom/
│   ├── __init__.py
│   ├── cli.py              # Main CLI entry point
│   ├── local_agent/        # Personal + Enterprise
│   ├── im_adapters/        # Personal + Enterprise
│   ├── social_feed/        # Personal + Enterprise
│   ├── enterprise/         # Enterprise only
│   │   ├── multi_user/
│   │   ├── sso/
│   │   └── dashboard/
│   └── governance/         # Shared (always on)
└── pyproject.toml
```

**Documentation**:
- `INSTALLATION.md` - Personal vs Enterprise, feature matrix
- `PERSONAL_EDITION.md` - Quick start for individual users
- `ENTERPRISE_EDITION.md` - Workspace setup, SSO, multi-user
- `FEATURE_FLAGS.md` - How to enable/disable features

**Distribution**:
- **PyPI** (public): `pip install atom-os`
- **Private Index** (enterprise): `pip install --index-url https://pypi.atom.ai atom-os[enterprise]`

**Plans**: 3 plans
- [ ] 04-simplified-installer-01-PLAN.md — pyproject.toml setup (setuptools, feature flags, package structure)
- [ ] 04-simplified-installer-02-PLAN.md — CLI implementation (typer, init/start/enable commands)
- [ ] 04-simplified-installer-03-PLAN.md — Documentation & PyPI publishing (installation guides, feature matrix)

---

## Open Questions

1. **WhatsApp Business Verification**: Can Personal Edition users use WhatsApp without business verification?
   - **Status**: Blocked by WhatsApp Cloud API requirements
   - **Proposal**: Personal Edition = Telegram only, Enterprise = WhatsApp + Telegram

2. **Signal Long-Term Viability**: No official API - is maintenance burden too high?
   - **Status**: Deferred until official API available
   - **Proposal**: Drop Signal from Phase 1, focus on Telegram + WhatsApp

3. **Local Shell vs Docker**: How to run "God Mode" outside Docker while maintaining governance?
   - **Status**: Architecture defined (separate host process), implementation pending
   - **Proposal**: Local agent runs as systemd service, connects to governance backend via API

4. **Social Feed Privacy**: What to publish vs. keep private? PII redaction strategy?
   - **Status**: Presidio selected, patterns defined
   - **Proposal**: Default = redacted, user controls visibility per post type

5. **Personal/Enterprise Boundary**: Which features go in which edition?
   - **Status**: Feature matrix defined in Phase 4
   - **Proposal**: Governance always on, Enterprise adds multi-user + SSO + dashboard

## Dependencies

**Internal** (Atom features):
- Agent Governance Service (STUDENT → AUTONOMOUS maturity model)
- Governance Cache (<1ms permission checks)
- Agent Orchestrator (request routing and execution)
- Agent Operation Tracker (existing audit trail)
- Redis + WebSocket (existing real-time infrastructure)

**External** (third-party services):
- Telegram Bot API (free, no rate limits)
- WhatsApp Cloud API (free tier, business verification required)
- OpenAI GPT-4.1 mini ($0.15/1M tokens for social post generation)
- Presidio (MIT license, PII redaction)

## Timeline Estimates

| Phase | Plans | Duration | Dependencies |
|-------|-------|----------|--------------|
| Phase 1: IM Adapters | 5 plans | 3-5 days | None |
| Phase 2: Local Agent | 4 plans | 2-3 days | Phase 1 |
| Phase 3: Social Layer | 3 plans | 2-3 days | Phase 2 |
| Phase 4: Installer | 3 plans | 2-3 days | Phases 1-3 |
| **Total** | **15 plans** | **9-14 days** | Sequential phases |

**Parallelization Opportunities**:
- Phase 1.1 (Telegram) and 1.2 (WhatsApp) can run in parallel
- Phase 2.1 (LocalAgentService) and Phase 3.1 (SocialFeedService) can run in parallel
- Phase 4 documentation can start earlier

**Optimistic Timeline**: 7-9 days (parallel execution)
**Realistic Timeline**: 9-14 days (sequential + some parallel)
**Conservative Timeline**: 14-21 days (unforeseen issues, open questions)

## Risk Assessment

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| WhatsApp Business Verification blocks Personal users | High | Medium | Personal = Telegram only, WhatsApp = Enterprise |
| Signal API never materializes | Low | High | Already deferred, no impact |
| Local shell security vulnerability | Critical | Low | Strict whitelist, never shell=True, security review |
| Social post generation cost exceeds budget | Medium | Low | GPT-4.1 mini is cheap ($0.15/1M), cache posts |
| PyPI naming conflict ("atom-os" taken) | Medium | Low | Alternative names: atom-agent-os, atom-ai |
| Governance integration breaks existing features | High | Low | All phases extend governance, never bypass |

## Success Metrics

**Phase 1 (IM Adapters)**:
- 100+ messages sent via Telegram/WhatsApp without security incidents
- <100ms latency from IM send to agent response
- 0% rate limit violations
- 100% of IM interactions logged to audit trail

**Phase 2 (Local Agent)**:
- 50+ shell commands executed with 0 command injection attempts
- Student agents request approval for 100% of critical commands
- Autonomy granted after 10 successful safe commands
- <500ms latency for command execution

**Phase 3 (Social Layer)**:
- 200+ social posts generated with 99% PII redaction accuracy
- Users respond to 20% of agent posts (feedback loop)
- <50ms latency from operation to social post visible
- Social feed increases user engagement by 2x

**Phase 4 (Installer)**:
- `pip install atom-os` succeeds in <30 seconds on fresh machine
- Personal Edition installs with <5 CLI commands
- Enterprise upgrade succeeds with `atom enable enterprise`
- Package passes PyPI security scans (no vulnerabilities)

## Research References

See `.planning/feature-research/OPENCLAW_INTEGRATION_RESEARCH.md` for:
- Library selection rationale (50+ sources cited)
- Security pitfalls and mitigation strategies
- Architecture patterns from established projects
- Official documentation links for all dependencies
- Implementation examples from OpenClaw, LangChain, AutoGPT

---

*This is a living document. As phases are executed, update success criteria, timeline estimates, and risk assessments based on actual data.*
