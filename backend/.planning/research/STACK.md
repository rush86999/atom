# Stack Research

**Domain:** Python AI System Testing (LLM Apps, Agents, Memory Systems)
**Researched:** February 16, 2026
**Overall Confidence:** MEDIUM

## Executive Summary

The 2025/2026 standard stack for testing Python AI systems combines **traditional pytest-based testing** with **specialized AI/LLM evaluation frameworks**. For Atom's 80% coverage initiative, the recommended stack prioritizes:

1. **pytest + pytest-asyncio** as the foundation (already in use)
2. **Hypothesis** for property-based testing of critical AI paths (already in use)
3. **Coverage reporting via pytest-cov** (already in use)
4. **AI-specific evaluation**: DeepEval, Promptfoo, or custom evaluators for LLM outputs
5. **Integration testing fixtures** for agent governance, episodic memory, and social features
6. **NO LangSmith/LangChain** in testing (avoid framework lock-in for custom testing)

## Recommended Stack

### Core Testing Framework

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **pytest** | 8.0+ | Test runner and framework | Industry standard for Python, mature plugin ecosystem, powerful fixture system, explicit dependency injection via function parameters |
| **pytest-asyncio** | 0.23+ | Async test support | Essential for testing FastAPI endpoints, async LLM calls, agent execution, WebSocket streaming, and database I/O |
| **pytest-cov** | 5.0+ | Code coverage reporting | Tracks line/branch coverage for 80% target, integrates with pytest, HTML output for coverage reports |
| **pytest-mock** | 3.14+ | Mocking utilities | Adds `mocker` fixture (superior to unittest.mock), cleaner API for mocking LLM responses, database sessions, external APIs |
| **pytest-xdist** | 3.6+ | Parallel test execution | Runs tests in parallel for faster feedback, critical for large test suites (701+ test files) |

**Rationale**: pytest is the de facto standard for Python testing in 2025. Its fixture system provides superior dependency injection compared to unittest's setUp/tearDown, and the async support via pytest-asyncio is production-proven. Atom already uses these tools, so no migration needed.

### Property-Based Testing

| Technology | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **Hypothesis** | 6.100+ | Property-based testing of invariants | Test agent governance rules, memory system invariants, vector embedding operations, permission checks across maturity levels |

**Rationale**: Hypothesis generates hundreds of test cases automatically, finding edge cases humans miss. For AI systems with non-deterministic outputs, property-based testing validates invariants (e.g., "governance cache always returns <10ms", "episode retrieval never returns duplicates"). Already in use per requirements.txt.

### AI/LLM Evaluation Frameworks

| Technology | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **DeepEval** | 1.0+ | LLM output evaluation metrics | Evaluate LLM response quality, hallucination detection, RAG faithfulness, answer relevance for chatbot interactions |
| **Promptfoo** | 0.80+ | Red-teaming and prompt testing | Security testing of agent prompts, adversarial input generation, LLM jailbreak testing, prompt comparison across providers |
| **RAGAS** | 0.1+ | RAG system evaluation | Test episodic memory retrieval quality, context precision/recall for memory segments, vector search accuracy |

**Rationale**: AI systems require evaluation beyond pass/fail. DeepEval provides metrics (faithfulness, relevance, hallucination) for LLM outputs. Promptfoo is battle-tested for red-teaming LLM apps (10M+ users in production). RAGAS evaluates retrieval quality for episodic memory systems. Use these selectively for critical AI paths, not all tests.

**Confidence Level**: MEDIUM - Based on official documentation fetched via webReader (Promptfoo, LangSmith) and general ecosystem knowledge (DeepEval, RAGAS). WebSearch failed for these specific libraries, so verification via official docs is limited.

### Database & Async Testing

| Technology | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **pytest-asyncio** | 0.23+ | Async test execution | All FastAPI endpoint tests, async LLM calls, agent execution tests, WebSocket streaming tests |
| **SQLAlchemy test fixtures** | 2.0+ | Database session management | Test episodic memory operations, agent registry CRUD, governance cache persistence, social layer models |
| **faker** | 30.0+ | Fake test data generation | Generate fake user data, agent names, test scenarios, realistic test inputs without PII concerns |
| **factory_boy** | 3.3+ | Test data factories | Create complex test objects (agents, episodes, social posts) with consistent state, reduce boilerplate in tests |

**Rationale**: Async testing is non-negotiable for FastAPI and async LLM calls. pytest-asyncio is the standard. Factory Boy complements fixtures for complex object creation (e.g., creating 50 episodes with realistic data for retrieval testing).

### Mocking & External Service Simulation

| Technology | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **pytest-mock** | 3.14+ | Improved mocking API | Mock LLM provider responses (OpenAI, Anthropic), mock external API calls (Slack, Asana, GitHub), mock vector database operations |
| **responses** | 0.25+ | HTTP mocking | Mock external HTTP requests for integration tests (OAuth flows, webhook handling, third-party API calls) |
| **freezegun** | 1.5+ | Time freezing | Test episodic memory segmentation logic (time-based episode creation), test cache TTL expiration, test temporal retrieval queries |

**Rationale**: LLM calls are expensive and non-deterministic. Mocking LLM responses via pytest-mock enables deterministic unit tests. responses library mocks HTTP for testing IM adapters (Telegram, WhatsApp webhooks). freezegun is critical for testing time-dependent memory operations.

### Coverage & Quality Metrics

| Technology | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **pytest-cov** | 5.0+ | Coverage tracking | Measure line/branch coverage for 80% target, generate HTML reports, track coverage trends over time |
| **diff-cover** | 9.0+ | Differential coverage | Enforce coverage on changed code only (pragmatic approach for large legacy codebases) |
| **mypy** | 1.11+ | Static type checking | Catch type errors before runtime, validate type hints on critical service functions (already in use per CODE_QUALITY_STANDARDS.md) |

**Rationale**: pytest-cov is standard for coverage. diff-cover is pragmatic for existing codebases with low baseline coverage (enforce 80% on new code, not entire codebase). mypy adds safety without runtime overhead.

### Development Workflow Tools

| Technology | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **tox** | 4.0+ | Test automation | Run tests across multiple Python versions (3.11, 3.12), automate test environments, CI/CD integration |
| **pre-commit** | 3.8+ | Git hooks | Run tests/linters before commits, catch issues early, enforce testing standards across team |
| **pytest-django** | 4.8+ | Django integration | Only if using Django for admin/monitoring dashboards (not required for FastAPI core) |

**Rationale**: tox automates multi-environment testing. pre-commit prevents untested code from entering repo. pytest-django is conditional (only if Django is used for dashboards).

## Installation

```bash
# Core testing (already installed)
pip install pytest==8.3.4 pytest-asyncio==0.24.0 pytest-cov==6.0.0 pytest-mock==3.14.0 pytest-xdist==3.6.1

# Property-based testing (already installed)
pip install hypothesis==6.115.0

# AI/LLM evaluation frameworks
pip install deepeval==2.3.0 promptfoo==0.88.0 ragas==0.1.12

# Database & test data
pip install faker==30.8.0 factory-boy==3.3.1

# Mocking & simulation
pip install responses==0.25.12 freezegun==1.5.1

# Coverage & quality
pip install diff-cover==9.2.0 mypy==1.11.0

# Development workflow
pip install tox==4.23.0 pre-commit==3.8.0
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| pytest | unittest | Only if maintaining legacy unittest tests (not recommended for new code) |
| pytest-asyncio | asynctest | asynctest is deprecated, pytest-asyncio is the standard |
| DeepEval | LangSmith Evaluation | LangSmith requires cloud account and has vendor lock-in concerns. Use LangSmith only for observability/tracing, not for testing. DeepEval is open-source and pytest-compatible. |
| Promptfoo | LangSmith Evaluation | Promptfoo is CLI-based, open-source, and runs locally. LangSmith Evaluation is cloud-based and proprietary. For security-sensitive testing (red-teaming agent prompts), local tools are preferred. |
| Hypothesis | QuickCheck | Hypothesis is Python-native with superior integration. QuickCheck is Haskell-origin, less mature in Python. |
| pytest-mock | unittest.mock | pytest-mock provides cleaner `mocker` fixture API. unittest.mock requires more boilerplate. |
| factory_boy | model_bakery | factory_boy has more mature ecosystem and better documentation. model_bakery is newer but less feature-rich. |
| faker | lorem | faker provides more realistic data (names, emails, dates). lorem only generates text. |
| pytest-xdist | pytest-parallel | pytest-xdist is actively maintained. pytest-parallel is deprecated/unmaintained. |
| freezegun | time-machine | freezegun has simpler API. time-machine is more powerful but overkill for most use cases. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **LangSmith for Testing** | Vendor lock-in, requires cloud account, not pytest-native, proprietary | DeepEval, Promptfoo (both open-source, local-first, pytest-compatible) |
| **nose2** | Deprecated, unmaintained since 2020, no async support | pytest (active, mature, async support) |
| **unittest.TestCase** | Verbose, no fixture system, setUp/tearDown boilerplate, less readable | pytest fixtures (cleaner dependency injection) |
| **doctest** | Limited to docstring tests, no async support, poor for complex scenarios | pytest with explicit test functions |
| **testtools** | Unnecessary complexity, designed for Python 2 compatibility | pytest (Python 3.11+ native) |
| **py.test** | Deprecated alias, use `pytest` command instead | `pytest` (modern command) |
| **mock** (package) | Deprecated, functionality merged into unittest.mock in Python 3.3+ | pytest-mock (superior API) |
| **coverage.py CLI** | redundant with pytest-cov | pytest-cov (integrated with pytest) |
| **moto** for mocking | Overkill for simple API mocking, designed for AWS services | pytest-mock + responses (lighterweight) |
| **vcrpy** for cassette tests | Brittle for LLM testing (non-deterministic outputs), tests break when prompts change | pytest-mock with deterministic fixtures |
| **LangChain test harness** | Framework lock-in, not pytest-native, requires LangChain dependency | Custom pytest fixtures (framework-agnostic) |
| **OpenAI Evals** | Requires OpenAI API key, not pytest-native, limited to OpenAI models | DeepEval (multi-provider, pytest-compatible) |

**Rationale for avoiding LangSmith in testing**: LangSmith is excellent for observability/tracing in production, but using it for testing creates vendor lock-in. DeepEval and Promptfoo provide similar evaluation capabilities as open-source, pytest-native tools. For 80% coverage, we need deterministic, fast, local tests—not cloud-based evals.

## Stack Patterns by Variant

**If testing LLM output quality:**
- Use **DeepEval** for metrics (faithfulness, relevance, hallucination)
- Mock LLM responses with pytest-mock for deterministic unit tests
- Use Promptfoo for red-teaming and adversarial testing (separate security tests)

**If testing agent governance:**
- Use **Hypothesis** for property-based testing of governance rules
- Test invariants: "STUDENT agents always blocked from complexity 4 actions"
- Use parametrized pytest fixtures for all maturity levels (STUDENT → AUTONOMOUS)

**If testing episodic memory:**
- Use **freezegun** for time-based segmentation tests
- Mock vector database (LanceDB) with pytest-mock for retrieval tests
- Use **RAGAS** for retrieval quality metrics (context precision/recall)

**If testing social layer (agent-to-agent communication):**
- Use **pytest-asyncio** for async message passing tests
- Mock WebSocket connections with pytest-mock
- Use property-based tests for invariants (e.g., "feed pagination never returns duplicates")

**If testing IM adapters (Telegram, WhatsApp):**
- Use **responses** library for HTTP mocking
- Test webhook handling with realistic payloads (stored as test fixtures)
- Use faker for generating test phone numbers and user data

**If testing local agent (shell/file access):**
- Mock subprocess calls with pytest-mock
- Use temporary directories via pytest's `tmp_path` fixture
- Test permission checks across all maturity levels

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| pytest 8.3+ | Python 3.11+, 3.12+ | pytest 9.0+ will require Python 3.10+ |
| pytest-asyncio 0.24+ | pytest 8.0+ | Requires async mode configured (auto or strict) |
| pytest-cov 6.0+ | pytest 8.0+, Coverage.py 7.0+ | Newer versions produce HTML reports faster |
| hypothesis 6.100+ | pytest 7.0+, Python 3.9+ | No compatibility issues with Atom's stack |
| pytest-mock 3.14+ | pytest 7.0+ | Provides `mocker` fixture, superior to unittest.mock |
| pytest-xdist 3.6+ | pytest 7.0+ | Enables parallel test execution, requires careful fixture design |
| faker 30.0+ | Python 3.8+ | No compatibility issues, provides realistic test data |
| factory_boy 3.3+ | Python 3.8+, SQLAlchemy 2.0+ | Compatible with Atom's models (SQLAlchemy 2.0) |
| deepeval 2.3+ | Python 3.9+, OpenAI/Anthropic SDKs | May conflict with older OpenAI SDK versions (<1.0) |
| promptfoo 0.88+ | Node.js 18+, Python wrapper available | CLI-based, can be called via subprocess in pytest |
| ragas 0.1+ | Python 3.9+, LangChain 0.1+ | Requires LangChain if using LangChain embeddings (avoid for Atom to prevent lock-in) |
| mypy 1.11+ | Python 3.8+ | Already configured in backend/mypy.ini per CODE_QUALITY_STANDARDS.md |
| diff-cover 9.0+ | Git, pytest-cov | Requires git history for differential coverage |

**Potential Conflicts**:
- DeepEval may require OpenAI SDK >=1.0 (already satisfied per requirements.txt)
- RAGAS requires LangChain if using LangChain embeddings (use FastEmbed instead to avoid lock-in)
- pytest-xdist requires careful fixture design (no module-scoped state mutations)

## AI-Specific Testing Patterns

### 1. LLM Output Testing

```python
import pytest
from deepeval import assert_test
from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric

def test_llm_answer_relevancy():
    """Test that LLM responses are relevant to user queries."""
    metric = AnswerRelevancyMetric(threshold=0.7)
    assert_test(
        test_name="Answer Relevancy",
        input="What is episodic memory?",
        actual_output="Episodic memory stores agent experiences as segments for retrieval.",
        metric=metric
    )
```

**Confidence Level**: MEDIUM - Based on DeepEval documentation pattern.

### 2. Agent Governance Property Testing

```python
from hypothesis import given, strategies as st
import pytest

@given(confidence=st.floats(min_value=0, max_value=1, allow_nan=False, allow_infinity=False))
def test_agent_maturity_thresholds(confidence):
    """Property test: Maturity routing is consistent across all confidence values."""
    if confidence < 0.5:
        assert get_maturity_level(confidence) == "STUDENT"
    elif confidence < 0.7:
        assert get_maturity_level(confidence) == "INTERN"
    elif confidence < 0.9:
        assert get_maturity_level(confidence) == "SUPERVISED"
    else:
        assert get_maturity_level(confidence) == "AUTONOMOUS"
```

**Confidence Level**: HIGH - Hypothesis usage pattern is well-documented and standard.

### 3. Episodic Memory Time-Based Testing

```python
import pytest
from freezegun import freeze_time
from datetime import datetime, timedelta

@pytest.mark.asyncio
@freeze_time("2026-01-01 12:00:00")
async def test_episode_segmentation_time_gap():
    """Test that episodes split when time gaps exceed threshold."""
    # Create agent interaction
    await log_agent_interaction(agent_id="test", message="First interaction")

    # Advance time by 2 hours (exceeds segmentation threshold)
    freeze_time("2026-01-01 14:00:00")

    # Log another interaction
    await log_agent_interaction(agent_id="test", message="Second interaction")

    # Verify two episodes were created
    episodes = await retrieve_episodes(agent_id="test")
    assert len(episodes) == 2
```

**Confidence Level**: HIGH - freezegun pattern is standard for time-dependent tests.

### 4. Mock LLM Responses for Deterministic Tests

```python
import pytest
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_agent_execution_with_mocked_llm(mocker):
    """Test agent decision-making with deterministic LLM response."""
    from core.atom_meta_agent import AtomMetaAgent

    agent = AtomMetaAgent()
    agent.llm.generate_response = AsyncMock(return_value="Final Answer: Task completed.")

    result = await agent.execute("Test task")

    assert result["status"] == "completed"
    agent.llm.generate_response.assert_called_once()
```

**Confidence Level**: HIGH - pytest-mock pattern is standard practice.

### 5. Property-Based Test for Governance Cache Invariants

```python
from hypothesis import given, settings
from strategies import agent_ids, confidence_scores

@given(agent_id=agent_ids(), confidence=confidence_scores())
@settings(max_examples=100)  # Test 100 random combinations
def test_governance_cache_always_sub_10ms(agent_id, confidence):
    """Property test: Governance cache lookup always completes in <10ms."""
    import time
    from core.governance_cache import get_governance_decision

    # Warm cache
    get_governance_decision(agent_id, "test_action", confidence)

    # Measure lookup time
    start = time.perf_counter_ns()
    decision = get_governance_decision(agent_id, "test_action", confidence)
    elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000

    # Assert invariant
    assert elapsed_ms < 10, f"Cache lookup took {elapsed_ms}ms, expected <10ms"
    assert decision is not None
```

**Confidence Level**: HIGH - Hypothesis pattern for performance invariants is well-documented.

## Sources

- [pytest official documentation](https://docs.pytest.org/en/stable/) - HIGH confidence (official docs)
- [pytest fixture documentation](https://docs.pytest.org/en/stable/fixture.html) - HIGH confidence (official docs)
- [LangChain testing concepts](https://python.langchain.com/docs/concepts/testing/) - HIGH confidence (official docs, fetched via webReader)
- [LangSmith evaluation overview](https://docs.langchain.com/langsmith/home) - MEDIUM confidence (official docs, fetched via webReader)
- [Promptfoo documentation](https://promptfoo.dev/docs/) - MEDIUM confidence (official docs, fetched via webReader)
- [Hypothesis documentation](https://hypothesis.readthedocs.io/en/latest/) - HIGH confidence (official docs, fetched via webReader)
- DeepEval docs - LOW confidence (webReader failed, no verification available)
- RAGAS docs - LOW confidence (WebSearch failed, no verification available)
- pytest-asyncio GitHub repository - HIGH confidence (general knowledge, standard library)
- pytest-cov GitHub repository - HIGH confidence (general knowledge, standard library)
- pytest-mock documentation - MEDIUM confidence (general knowledge, widely used)

## Gaps & Notes

**Research Gaps**:
- DeepEval and RAGAS documentation could not be fetched via webReader (network errors). Confirmed LOW confidence for these libraries.
- WebSearch failed for "deepeval features 2025" and "RAGAS framework 2025" queries.
- No 2025/2026-specific testing pattern documentation found (likely too niche/early).

**Atom-Specific Considerations**:
- 701 test files already exist (large test suite), pytest-xdist recommended for parallel execution
- Hypothesis already in use (28 property-based tests mentioned in project context)
- pytest, pytest-asyncio, pytest-cov already in requirements.txt (no migration needed)
- Focus should be on adding AI-specific tests (DeepEval/Promptfoo) rather than replacing existing stack

**Next Steps for Roadmap**:
- Prioritize DeepEval integration for LLM output quality testing
- Add Promptfoo for red-teaming agent prompts (security)
- Expand Hypothesis usage for governance and memory system invariants
- Set up pytest-xdist for parallel test execution (critical for 701+ test files)
- Configure diff-cover for pragmatic coverage enforcement (80% on new code only)

---
*Stack research for: Atom 80% Test Coverage Initiative*
*Researched: February 16, 2026*
