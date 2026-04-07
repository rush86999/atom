# Documentation Reorganization Plan

**Created:** April 7, 2026
**Status:** Draft - Pending Review

## Current State

- **141 markdown files** in `docs/` root (too many)
- **18 subdirectories** already exist (good foundation)
- Multiple redundant/overlapping documents
- Legacy implementation docs mixed with current docs
- Missing documentation for recent features

## Reorganization Strategy

### Phase 1: File Categorization

Move files from `docs/` root to appropriate subdirectories:

#### 1. **Agent System** → `docs/agents/`
- `AGENT_GOVERNANCE.md` → `agents/governance.md`
- `AGENT_GOVERNANCE_LEARNING_INTEGRATION.md` → `agents/governance-learning.md`
- `AGENT_GRADUATION_GUIDE.md` → `agents/graduation.md`
- `AGENT_GUIDANCE_IMPLEMENTATION.md` → `agents/guidance-system.md`
- `AGENT_MARKETPLACE.md` → `agents/marketplace.md`
- `AGENTS.md` → `agents/overview.md`
- `STUDENT_AGENT_TRAINING_IMPLEMENTATION.md` → `agents/training.md`

#### 2. **AI & Intelligence** → `docs/intelligence/`
- `AI_DEBUG_QUICK_START.md` → `intelligence/debug-quickstart.md`
- `AI_DEBUG_SYSTEM.md` → `intelligence/debug-system.md`
- `EPISODIC_MEMORY_IMPLEMENTATION.md` → `intelligence/episodic-memory.md`
- `WORLD_MODEL_IMPLEMENTATION.md` → `intelligence/world-model.md`
- `GRAPHRAG_AND_ENTITY_TYPES.md` → `intelligence/graphrag.md`
- `ai-world-model.md` → `intelligence/world-model-guide.md`

#### 3. **Canvas & Presentations** → `docs/canvas/`
- `CANVAS_AGENT_LEARNING_INTEGRATION.md` → `canvas/agent-learning.md`
- `CANVAS_AI_ACCESSIBILITY.md` → `canvas/ai-accessibility.md`
- `CANVAS_FEEDBACK_EPISODIC_MEMORY.md` → `canvas/feedback-memory.md`
- `CANVAS_QUICK_REFERENCE.md` → `canvas/quick-reference.md`
- `CANVAS_RECORDING_IMPLEMENTATION.md` → `canvas/recording.md`
- `CANVAS_STATE_API.md` → `canvas/state-api.md`
- `LLM_CANVAS_SUMMARIES.md` → `canvas/llm-summaries.md`

#### 4. **Integration & Automation** → `docs/integrations/`
- `ADVANCED_SKILL_EXECUTION.md` → `integrations/advanced-skills.md`
- `ATOM_OPENCLAW_FEATURES.md` → `integrations/openclaw-features.md`
- `BROWSER_AUTOMATION.md` → `integrations/browser-automation.md`
- `BROWSER_QUICK_START.md` → `integrations/browser-quickstart.md`
- `COMMUNITY_SKILLS.md` → `integrations/community-skills.md`
- `DEVICE_CAPABILITIES.md` → `integrations/device-capabilities.md`
- `INTEGRATIONS.md` → `integrations/overview.md`
- `ATOM_CLI_SKILLS_GUIDE.md` → `integrations/cli-skills.md`

#### 5. **Marketplace** → `docs/marketplace/`
- `MARKETPLACE_CONNECTION_GUIDE.md` → `marketplace/connection.md`
- `MARKETPLACE_UPDATE_SUMMARY.md` → `marketplace/update-summary.md`
- `MARKETPLACE_ANALYTICS.md` → `marketplace/analytics.md`
- `SKILL_MARKETPLACE_GUIDE.md` → `marketplace/skills.md`

#### 6. **Testing & Quality** → `docs/testing/`
- `TESTING_INDEX.md` → `testing/index.md`
- `TESTING_ONBOARDING.md` → `testing/onboarding.md`
- `TESTING_IMPLEMENTATION_PROGRESS.md` → `testing/progress.md`
- `E2E_TESTING_GUIDE.md` → `testing/e2e.md`
- `MOBILE_TESTING_GUIDE.md` → `testing/mobile.md`
- `PROPERTY_TESTING_PATTERNS.md` → `testing/property-testing.md`
- `CROSS_PLATFORM_COVERAGE.md` → `testing/cross-platform.md`
- `CROSS_PLATFORM_PROPERTY_TESTING.md` → `testing/cross-platform-property.md`
- `DESKTOP_COVERAGE.md` → `testing/desktop.md`
- `DESKTOP_TESTING_GUIDE.md` → `testing/desktop-guide.md`

#### 7. **Deployment & Operations** → `docs/operations/`
- `DEPLOYMENT.md` → `operations/deployment.md`
- `DEPLOYMENT_GUIDE.md` → `operations/deployment-guide.md`
- `PERSONAL_EDITION.md` → `operations/personal-edition.md`
- `MONITORING_GUIDE.md` → `operations/monitoring.md`
- `PERFORMANCE_TUNING.md` → `operations/performance.md`
- `PRODUCTION_READINESS.md` → `operations/production-readiness.md`
- `ROLLBACK_PROCEDURE.md` → `operations/rollback.md`

#### 8. **Platform & Architecture** → `docs/platform/`
- `ARCHITECTURE.md` → `platform/architecture.md`
- `TECHNICAL_OVERVIEW.md` → `platform/technical-overview.md`
- `DATABASE_ARCHITECTURE.md` → `platform/database.md`
- `SINGLE_TENANT.md` → `platform/single-tenant.md`
- `PLATFORM.md` → `platform/overview.md`

#### 9. **API Reference** → `docs/api/`
- `API.md` → `api/overview.md`
- `API_DOCUMENTATION_INDEX.md` → `api/index.md`
- `API_TYPE_GENERATION.md` → `api/type-generation.md`
- `FRONTEND_TO_BACKEND_API.md` → `api/frontend-backend.md`

#### 10. **Development** → `docs/development/`
- `DEVELOPMENT.md` → `development/overview.md`
- `DEVELOPMENT_SETUP.md` → `development/setup.md`
- `CODE_QUALITY_GUIDE.md` → `development/code-quality.md`
- `BUILD.md` → `development/build.md`

#### 11. **Security** → `docs/security/`
- `PACKAGE_SECURITY.md` → `security/packages.md`
- `PYTHON_PACKAGES_DEPLOYMENT.md` → `security/python-packages.md`
- `NPM_PACKAGE_SUPPORT.md` → `security/npm-packages.md`

#### 12. **Features & Use Cases** → `docs/features/`
- `ATOM_VS_OPENCLAW.md` → `features/atom-vs-openclaw.md`
- `USE_CASES.md` → `features/use-cases.md`
- `FEATURE_MATRIX.md` → `features/matrix.md`

### Phase 2: Consolidation & Deduplication

#### Consolidate Redundant Docs:

1. **Agent Governance** (3 files → 1)
   - `AGENT_GOVERNANCE.md`
   - `AGENT_GOVERNANCE_LEARNING_INTEGRATION.md`
   - Merge into `agents/governance.md` with sections

2. **Canvas Documentation** (6 files → 3)
   - `CANVAS_QUICK_REFERENCE.md` + `CANVAS_STATE_API.md` → `canvas/reference.md`
   - Keep separate: `canvas/implementation.md`, `canvas/ai-features.md`

3. **Testing Documentation** (10 files → 5)
   - Merge coverage docs into `testing/coverage.md`
   - Merge property testing into `testing/property-testing.md`
   - Keep guides separate

4. **Deployment** (3 files → 2)
   - Merge `DEPLOYMENT.md` + `DEPLOYMENT_GUIDE.md` → `operations/deployment.md`
   - Keep `operations/personal-edition.md` separate

### Phase 3: Archive Legacy Docs

Move to `docs/archive/legacy/`:

- `ATOM_SAAS_SYNC_DEPLOYMENT.md` (SaaS-specific)
- `CITATION_SYSTEM_GUIDE.md` (superseded by world-model docs)
- `DEEPLINK_IMPLEMENTATION.md` (implementation detail, not user-facing)
- `MEMORY_INTEGRATION_GUIDE.md` (superseded)
- `MENUBAR_*` files (platform-specific, move to `archive/menubar/`)
- `MOBILE_*` implementation files (move to `archive/mobile/`)
- `NATIVE_SETUP.md` (outdated)
- `PHASE_*` files (implementation history)
- `PROPERTY_TESTING_PATTERNS.md` (if duplicated in testing/)
- `PYTHON_PACKAGES.md` → consolidate with `security/python-packages.md`
- All `*_IMPLEMENTATION.md` files (unless actively referenced)

### Phase 4: Add Missing Documentation

#### Recent Features (from git history):

1. **WhatsApp Multi-Tenant OAuth** → `integrations/whatsapp-oauth.md`
2. **Marketplace Sync & Analytics** → `marketplace/sync-analytics.md`
3. **Meta-Agent Routing** → `agents/meta-agent.md`
4. **Fleet Admiral** → `agents/fleet-admiral.md`
5. **Intent Classifier** → `intelligence/intent-classifier.md`
6. **Single-Tenant Architecture** → `platform/single-tenant.md` (exists, verify)

#### Missing User Guides:

1. **Troubleshooting Guide** → `guides/troubleshooting.md`
2. **FAQ** → `guides/faq.md`
3. **Migration Guide** (for updates) → `guides/migration.md`
4. **Configuration Reference** → `reference/configuration.md`

### Phase 5: Update Cross-References

1. Update all markdown links to new paths
2. Update `README.md` documentation section
3. Update `docs/README.md` index
4. Update `docs/INDEX.md` if it exists
5. Update `CLAUDE.md` documentation references

## Proposed Final Structure

```
docs/
├── README.md                          # Main documentation hub
├── USER_GUIDE_INDEX.md               # User documentation index
├── INDEX.md                          # Complete documentation index
│
├── agents/                           # Agent System
│   ├── overview.md
│   ├── governance.md
│   ├── graduation.md
│   ├── training.md
│   ├── guidance-system.md
│   ├── meta-agent.md
│   ├── fleet-admiral.md
│   └── marketplace.md
│
├── intelligence/                     # AI & Memory
│   ├── episodic-memory.md
│   ├── world-model.md
│   ├── graphrag.md
│   ├── intent-classifier.md
│   ├── debug-system.md
│   └── cognitive-tiers.md
│
├── canvas/                           # Canvas & Presentations
│   ├── overview.md
│   ├── implementation.md
│   ├── ai-features.md
│   ├── state-api.md
│   └── reference.md
│
├── integrations/                     # Integrations
│   ├── overview.md
│   ├── browser-automation.md
│   ├── community-skills.md
│   ├── cli-skills.md
│   ├── device-capabilities.md
│   └── whatsapp-oauth.md
│
├── marketplace/                      # Marketplace
│   ├── connection.md
│   ├── skills.md
│   ├── analytics.md
│   └── sync.md
│
├── testing/                          # Testing & Quality
│   ├── index.md
│   ├── onboarding.md
│   ├── e2e.md
│   ├── mobile.md
│   ├── desktop.md
│   ├── property-testing.md
│   └── coverage.md
│
├── operations/                       # Operations & Deployment
│   ├── deployment.md
│   ├── personal-edition.md
│   ├── monitoring.md
│   ├── performance.md
│   └── production-readiness.md
│
├── platform/                         # Platform Architecture
│   ├── architecture.md
│   ├── technical-overview.md
│   ├── database.md
│   └── single-tenant.md
│
├── api/                              # API Reference
│   ├── overview.md
│   ├── index.md
│   ├── type-generation.md
│   └── frontend-backend.md
│
├── development/                      # Development
│   ├── overview.md
│   ├── setup.md
│   ├── code-quality.md
│   └── build.md
│
├── security/                         # Security
│   ├── packages.md
│   ├── python-packages.md
│   └── npm-packages.md
│
├── features/                         # Features & Comparisons
│   ├── atom-vs-openclaw.md
│   ├── use-cases.md
│   └── matrix.md
│
├── guides/                           # User Guides
│   ├── QUICKSTART.md
│   ├── USER_GUIDE.md
│   ├── troubleshooting.md
│   ├── faq.md
│   └── migration.md
│
├── reference/                        # Reference Materials
│   ├── configuration.md
│   ├── environment-vars.md
│   └── cli-commands.md
│
└── archive/                          # Archived Documentation
    ├── legacy/
    ├── menubar/
    ├── mobile/
    └── phases/
```

## Implementation Checklist

### Phase 1: Categorization (Move files)
- [ ] Create new directory structure
- [ ] Move Agent System docs
- [ ] Move Intelligence docs
- [ ] Move Canvas docs
- [ ] Move Integration docs
- [ ] Move Marketplace docs
- [ ] Move Testing docs
- [ ] Move Operations docs
- [ ] Move Platform docs
- [ ] Move API docs
- [ ] Move Development docs
- [ ] Move Security docs
- [ ] Move Features docs

### Phase 2: Consolidation
- [ ] Consolidate Agent Governance docs (3→1)
- [ ] Consolidate Canvas docs (6→3)
- [ ] Consolidate Testing docs (10→5)
- [ ] Consolidate Deployment docs (3→2)
- [ ] Review and merge other redundant docs

### Phase 3: Archive
- [ ] Move legacy implementation docs
- [ ] Move SaaS-specific docs
- [ ] Move platform-specific docs
- [ ] Move phase completion docs
- [ ] Update archive index

### Phase 4: Add Missing Docs
- [ ] Add WhatsApp OAuth guide
- [ ] Add Marketplace Sync guide
- [ ] Add Meta-Agent documentation
- [ ] Add Fleet Admiral guide
- [ ] Add Intent Classifier docs
- [ ] Add Troubleshooting guide
- [ ] Add FAQ
- [ ] Add Migration guide
- [ ] Add Configuration reference

### Phase 5: Update References
- [ ] Update README.md links
- [ ] Update docs/README.md links
- [ ] Update docs/INDEX.md links
- [ ] Update CLAUDE.md references
- [ ] Verify all internal links work

## Success Metrics

- **Root docs folder**: 141 files → ~20 files (hubs and indexes)
- **Clear navigation**: User can find any doc in <3 clicks
- **No redundancy**: Each topic documented once
- **Complete coverage**: All recent features documented
- **Working links**: All internal links verified

## Notes

- Preserve all file history using `git mv`
- Create redirect pages for commonly-accessed moved docs
- Update all documentation indexes after moves
- Run link checker to verify no broken links
- Archive rather than delete to preserve history
