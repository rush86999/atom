# Atom Documentation

Welcome to the Atom documentation hub. This guide helps you find relevant information quickly.

---

## 📚 **Category Index**

Browse documentation by category:

- **[🤖 Agent System](AGENTS.md)** - Governance, graduation, and orchestration
- **[🧠 Intelligence & Memory](INTELLIGENCE.md)** - AI capabilities, knowledge management
- **[🔌 Integration & Automation](INTEGRATION.md)** - Platform integrations and automation
- **[🚀 Platform & Deployment](PLATFORM.md)** - Deployment, monitoring, operations

---

## 🚀 Quick Start

**New to Atom?** Start here:
- [Installation Guide](INSTALLATION.md) - Get Atom running in 5 minutes
- [Quick Start Guide](QUICK_START.md) - Your first workflow
- [User Guide](USER_GUIDE.md) - Core concepts and features

---

## 📖 Core Documentation

### Platform Architecture
- [Architecture Overview](ARCHITECTURE.md) - System design and components
- [Technical Overview](TECHNICAL_OVERVIEW.md) - Deep technical dive
- [Database Architecture](DATABASE_ARCHITECTURE.md) - Data models and schema
- [API Documentation](API.md) - REST API reference

### Agent System 🤖
- **[Agent System Index](AGENTS.md)** - Complete agent documentation
- [Agent Governance](AGENT_GOVERNANCE.md) - Maturity levels and permissions
- [Agent Graduation Guide](AGENT_GRADUATION_GUIDE.md) - Learning and promotion
- [Student Agent Training](STUDENT_AGENT_TRAINING_IMPLEMENTATION.md) - Training workflow

### ✨ **NEW** Unstructured Complex Tasks
- [Unstructured Complex Tasks](UNSTRUCTURED_COMPLEX_TASKS.md) - Intent classification & routing
- [Fleet Admiral](FLEET_ADMIRAL.md) - Multi-agent orchestration
- [Domain Creation](UNSTRUCTURED_COMPLEX_TASKS.md#domain-creation-system) - Specialist templates

### Intelligence & Memory 🧠
- **[Intelligence Index](INTELLIGENCE.md)** - Complete intelligence documentation
- [Episodic Memory](EPISODIC_MEMORY_IMPLEMENTATION.md) - Agent learning system
- [World Model & Business Facts](ai-world-model.md) - Knowledge management
- [GraphRAG & Entity Types](GRAPHRAG_AND_ENTITY_TYPES.md) - Graph-based intelligence

### Canvas & Presentations
- [Canvas AI Accessibility](CANVAS_AI_ACCESSIBILITY.md) - AI-readable canvas state
- [LLM Canvas Summaries](LLM_CANVAS_SUMMARIES.md) - Enhanced memory integration
- [Canvas Quick Reference](CANVAS_QUICK_REFERENCE.md) - Quick reference guide
- [Canvas State API](CANVAS_STATE_API.md) - State API documentation

### Integration & Automation 🔌
- **[Integration Index](INTEGRATION.md)** - Complete integration documentation
- [Integrations](INTEGRATIONS.md) - 46+ platform integrations
- [Advanced Skill Execution](ADVANCED_SKILL_EXECUTION.md) - Community skills
- [Browser Automation](BROWSER_AUTOMATION.md) - Web scraping and automation

### Platform & Deployment 🚀
- **[Platform Index](PLATFORM.md)** - Complete platform documentation
- [Production Readiness](PRODUCTION_READINESS.md) - Deployment checklist
- [Monitoring Guide](MONITORING_GUIDE.md) - Health checks and metrics
- [Performance Tuning](PERFORMANCE_TUNING.md) - Optimization strategies

---

## 🏗️ Development Guides

### Getting Started
- [Development Setup](DEVELOPMENT_SETUP.md) - Local development environment
- [Development Guide](DEVELOPMENT.md) - Coding standards and workflows
- [Code Quality Guide](CODE_QUALITY_GUIDE.md) - Testing and style guidelines

### Testing
- [Testing Index](TESTING_INDEX.md) - Test organization
- [E2E Testing Guide](E2E_TESTING_GUIDE.md) - End-to-end tests
- [Property Testing Patterns](PROPERTY_TESTING_PATTERNS.md) - Property-based testing
- [Test Results Report](TEST_RESULTS_REPORT.md) - Coverage and metrics

### Deployment
- [Deployment Guide](DEPLOYMENT_GUIDE.md) - Production deployment
- [Personal Edition](PERSONAL_EDITION.md) - Local Docker setup
- [Rollback Procedure](ROLLBACK_PROCEDURE.md) - Emergency rollback

---

## 📱 Platform-Specific

### Desktop
- [MenuBar App Guide](MENUBAR_GUIDE.md) - macOS menu bar application
- [Native Setup](NATIVE_SETUP.md) - Native desktop builds

### Mobile
- [Mobile Quick Start](MOBILE_QUICK_START.md) - React Native app
- [Mobile Testing Guide](MOBILE_TESTING_GUIDE.md) - Mobile-specific testing

---

## 📖 Additional Resources

### Reference Materials
- [Feature Matrix](FEATURE_MATRIX.md) - Capability comparison
- [Features List](ATOM_OPENCLAW_FEATURES.md) - Complete feature list
- [Use Cases](USE_CASES.md) - Real-world examples
- [User Personas](USER_PERSONAS_AND_JOURNEYS.md) - Target users

### Implementation History
- [Implementation History](IMPLEMENTATION_HISTORY.md) - Phase-by-phase history
- [All Phases Complete](archive/ALL_PHASES_COMPLETE.md) - Completion summary (archived)

### Troubleshooting
- [Error Handling Guidelines](ERROR_HANDLING_GUIDELINES.md) - Common errors and solutions

---

## 🗄️ Archived Documentation

Legacy documentation has been moved to [`docs/archive/`](archive/). These files are kept for historical reference but may contain outdated information.

**Archived Topics**:
- Phase-specific completion reports
- Temporary implementation notes
- Deprecated features
- Historical bug reports

---

## 🔍 Finding Information

### By Role

**Developers**:
- [Development Guide](DEVELOPMENT.md)
- [API Documentation](API.md)
- [Testing Index](TESTING_INDEX.md)

**System Administrators**:
- [Deployment Guide](DEPLOYMENT_GUIDE.md)
- [Monitoring Guide](MONITORING_GUIDE.md)
- [Performance Tuning](PERFORMANCE_TUNING.md)

**Product Managers**:
- [Feature Matrix](FEATURE_MATRIX.md)
- [Use Cases](USE_CASES.md)
- [User Personas](USER_PERSONAS_AND_JOURNEYS.md)

**End Users**:
- [Quick Start](QUICK_START.md)
- [User Guide](USER_GUIDE.md)

### By Task

**Setting up Atom**:
1. [Installation](INSTALLATION.md)
2. [Development Setup](DEVELOPMENT_SETUP.md)
3. [Personal Edition](PERSONAL_EDITION.md)

**Building Agents**:
1. [Agent Governance](AGENT_GOVERNANCE.md)
2. [Agent Graduation](AGENT_GRADUATION_GUIDE.md)
3. [Unstructured Complex Tasks](UNSTRUCTURED_COMPLEX_TASKS.md)

**Integrating Systems**:
1. [Integrations](INTEGRATIONS.md)
2. [API Documentation](API.md)
3. [OAuth Setup](OAUTH_SETUP_GUIDE.md)

**Deploying to Production**:
1. [Production Readiness](PRODUCTION_READINESS.md)
2. [Deployment Guide](DEPLOYMENT_GUIDE.md)
3. [Monitoring Guide](MONITORING_GUIDE.md)

---

## 📝 Documentation Standards

### Writing Style
- **Concise**: Get to the point quickly
- **Actionable**: Provide examples and commands
- **Structured**: Use consistent formatting and headings
- **Up-to-date**: Update docs when code changes

### Template
```markdown
# Title

> **Last Updated**: YYYY-MM-DD
> **Status**: ✅ Production Ready | 🚧 In Progress | ⚠️ Deprecated

## Overview
Brief description of what this document covers.

## Key Concepts
- Concept 1
- Concept 2

## Usage
\`\`\`python
# Code examples
\`\`\`

## See Also
- [Related Doc 1](path/to/doc1.md)
- [Related Doc 2](path/to/doc2.md)
```

---

## 🤝 Contributing

When adding new features:
1. Update relevant documentation
2. Add code comments for complex logic
3. Update [CLAUDE.md](../CLAUDE.md) with key changes
4. Archive outdated docs

When fixing bugs:
1. Document the fix in [BUGS_FIXED_SUMMARY.md](archive/BUGS_FIXED_SUMMARY.md)
2. Update relevant troubleshooting sections

---

## 🔗 Quick Links

- **Main Project**: [GitHub Repository](https://github.com/rush869ark99/atom)
- **Issues**: [GitHub Issues](https://github.com/rush869ark99/atom/issues)
- **Discussions**: [GitHub Discussions](https://github.com/rush869ark99/atom/discussions)

---

**Need Help?**
- Check the [Troubleshooting](ERROR_HANDLING_GUIDELINES.md) guide
- Review [FAQ](QUICKSTART.md#faq)
- Search [GitHub Issues](https://github.com/rush869ark99/atom/issues)

---

*Last Updated: April 5, 2026*
