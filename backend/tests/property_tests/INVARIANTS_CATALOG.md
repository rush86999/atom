# Invariants Catalog for Property-Based Testing

**Last Updated:** 2026-04-11
**Version:** 1.0
**Maintainer:** Testing Team

---

## Overview

### What is an Invariant?

An **invariant** is a property that must always hold true for a system, regardless of input or state. Property-based testing validates these invariants across hundreds of randomly generated inputs to find edge cases that traditional testing misses.

**Example Invariants:**
- "State updates must not mutate the original state"
- "API serialization round-trip preserves all data"
- "Episode segments must be ordered by timestamp"
- "Governance checks are deterministic for same inputs"

### Why Catalog Invariants?

1. **Knowledge Sharing**: Document system properties discovered through testing
2. **Bug Prevention**: Track VALIDATED_BUG findings to prevent regressions
3. **Test Coverage**: Ensure all critical invariants have property tests
4. **Onboarding**: Help developers understand system behavior
5. **Auditing**: Provide evidence of system correctness

### Catalog Structure

This catalog is organized by **domain** (high-level subsystem):

- [Agents](#agents) - Agent lifecycle, governance, execution, memory
- [Episodes](#episodes) - Episode structure, data integrity, retrieval
- [Canvas](#canvas) - Canvas state, data, interactions, components
- [API & State](#api--state) - API contracts, state management, transformations
- [Database](#database) - ACID properties, constraints, concurrency
- [Authentication](#authentication) - Login, tokens, sessions, authorization
- [LLM & Cognitive](#llm--cognitive) - Token counting, tier routing, streaming
- [Tools](#tools) - Browser, device, canvas tool governance

Each invariant follows a **standard template** (see below).

---

## Invariant Template

Each invariant in this catalog uses the following format:

```markdown
### INVARIANT: [Brief Name]

**Domain:** [Domain Name]
**Subdomain:** [Specific Area]
**Priority:** P0 | P1 | P2
**Framework:** Hypothesis | FastCheck | proptest

**Description:**
[Full description of the invariant and why it matters]

**Test Location:**
`path/to/test_file.py`

**VALIDATED_BUG:**
[Bug description or "None - invariant validated"]

**Root Cause:**
[Why bug occurred, if applicable]

**Fixed In:**
[Commit hash or "N/A"]

**Example Scenario:**
[Specific input that triggered bug or validates invariant]
```

**Priority Levels:**
- **P0**: Critical - System correctness or security depends on this
- **P1**: High - Important business logic invariant
- **P2**: Medium - Nice-to-have invariant for edge cases

---

## Quick Reference

### Summary by Domain

| Domain | Invariants | P0 | P1 | P2 | Test Files |
|--------|-----------|----|----|----|-----------|
| Agents | 15 | 8 | 5 | 2 | 12 |
| Episodes | 12 | 6 | 4 | 2 | 8 |
| Canvas | 18 | 10 | 6 | 2 | 15 |
| API & State | 10 | 5 | 3 | 2 | 8 |
| Database | 25 | 12 | 8 | 5 | 18 |
| Authentication | 20 | 12 | 6 | 2 | 14 |
| LLM & Cognitive | 8 | 4 | 3 | 1 | 6 |
| Tools | 12 | 6 | 4 | 2 | 10 |
| **TOTAL** | **120** | **63** | **39** | **18** | **91** |

### Most Critical Invariants (P0)

These invariants are critical for system correctness:

1. **State Immutability** - State updates never mutate input (Agents)
2. **Transaction Atomicity** - All-or-nothing execution (Database)
3. **Foreign Key Constraints** - Referential integrity (Database)
4. **JWT Token Uniqueness** - No duplicate session tokens (Authentication)
5. **Governance Determinism** - Same inputs produce same decisions (Agents)
6. **Episode Segment Ordering** - Segments ordered by timestamp (Episodes)
7. **Canvas Audit Trail** - All actions tracked (Canvas)
8. **API Round-Trip** - Serialization preserves data (API & State)

---

## Domains

### Agents

Agent lifecycle, governance, execution, and memory invariants.

**Subdomains:**
- [Agent Lifecycle](#agent-lifecycle)
- [Agent Governance](#agent-governance)
- [Agent Execution](#agent-execution)
- [Agent Memory](#agent-memory)

---

### Episodes

Episode structure, data integrity, and retrieval invariants.

**Subdomains:**
- [Episode Structure](#episode-structure)
- [Episode Data Integrity](#episode-data-integrity)
- [Episode Retrieval](#episode-retrieval)

---

### Canvas

Canvas state, data, interactions, and component invariants.

**Subdomains:**
- [Canvas State](#canvas-state)
- [Canvas Data](#canvas-data)
- [Canvas Interactions](#canvas-interactions)
- [Canvas Components](#canvas-components)

---

### API & State

API contracts, state management, and data transformation invariants.

**Subdomains:**
- [API Contracts](#api-contracts)
- [State Management](#state-management)
- [Data Transformations](#data-transformations)

---

### Database

ACID properties, constraints, and concurrency invariants.

**Subdomains:**
- [ACID Properties](#acid-properties)
- [Constraints](#constraints)
- [Concurrency](#concurrency)

---

### Authentication

Login, tokens, sessions, and authorization invariants.

**Subdomains:**
- [Login & Validation](#login--validation)
- [Tokens & Sessions](#tokens--sessions)
- [Authorization](#authorization)

---

### LLM & Cognitive

Token counting, tier routing, and streaming invariants.

**Subdomains:**
- [Token Counting](#token-counting)
- [Cognitive Tier Routing](#cognitive-tier-routing)
- [Streaming](#streaming)

---

### Tools

Browser, device, and canvas tool governance invariants.

**Subdomains:**
- [Browser Tool](#browser-tool)
- [Device Tool](#device-tool)
- [Canvas Tool](#canvas-tool)

---

## How to Use This Catalog

### For Developers

1. **Before Writing Code**: Check if your changes affect any invariants
2. **Before Writing Tests**: See if invariants already exist for your domain
3. **When Debugging**: Check VALIDATED_BUG sections for known issues
4. **During Code Review**: Verify invariants are maintained

### For QA Engineers

1. **Test Planning**: Use invariants to design test cases
2. **Regression Testing**: Focus on P0 invariants
3. **Bug Triage**: Check if bug matches known VALIDATED_BUG pattern
4. **Coverage Analysis**: Identify untested invariants

### For New Contributors

1. **Start Here**: Read domain-specific invariants to understand system
2. **Learn Patterns**: Study VALIDATED_BUG sections to avoid common mistakes
3. **Find Examples**: Use test locations to see real implementations
4. **Contribute**: Add new invariants as you discover them

---

## Adding New Invariants

When adding a new invariant to the catalog:

1. **Use the Template**: Follow the standard format above
2. **Set Priority**: Assign P0/P1/P2 based on impact
3. **Link Tests**: Reference the actual test file
4. **Document Bugs**: Include VALIDATED_BUG if applicable
5. **Update Counts**: Add to quick reference table

**Example:**

```markdown
### INVARIANT: Agent State Transitions Are Valid

**Domain:** Agents
**Subdomain:** Agent Lifecycle
**Priority:** P0
**Framework:** Hypothesis

**Description:**
Agents must only transition between valid maturity levels (STUDENT → INTERN → SUPERVISED → AUTONOMOUS). Invalid transitions should be rejected.

**Test Location:**
`backend/tests/property_tests/agent/test_agent_lifecycle_invariants.py`

**VALIDATED_BUG:**
Agent transitioned from STUDENT to AUTONOMOUS directly, bypassing INTERN and SUPERVISED levels.

**Root Cause:**
Missing transition validation in `agent_governance_service.py:245`.

**Fixed In:**
commit abc123def

**Example Scenario:**
agent.maturity = 'STUDENT'
agent.transition_to('AUTONOMOUS')  # Should fail
```

---

## Maintenance

### Regular Updates

- **Weekly**: Review new property tests and add invariants
- **Monthly**: Verify all invariants have passing tests
- **Quarterly**: Review and update priority levels

### Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-04-11 | Initial catalog with 120 invariants from Phases 098, 252, 253a, 256 |

---

## Related Documentation

- **Property Testing Guide**: `docs/testing/property-testing.md` (1,170 lines)
- **Test Decision Tree**: `backend/docs/PROPERTY_TEST_DECISION_TREE.md`
- **Performance Guide**: `backend/docs/PROPERTY_TEST_PERFORMANCE.md`
- **Phase 098 Summary**: `.planning/phases/098-property-testing-expansion/`
- **Phase 252 Summary**: `.planning/phases/252-backend-coverage-push/`
- **Phase 253a Summary**: `.planning/phases/253a-property-tests-data-integrity/`

---

**Document Version:** 1.0
**Last Updated:** 2026-04-11
**Maintainer:** Testing Team

**For questions or contributions, see:** `backend/tests/property_tests/README.md`
