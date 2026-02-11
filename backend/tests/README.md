# Atom Test Suite

Comprehensive test suite for the Atom AI-powered business automation platform.

Quick Start
-----------

Run all tests:

```bash
cd backend
pytest tests/ -v
```

Run with coverage:

```bash
pytest tests/ --cov=core --cov=api --cov=tools --cov-report=html
open tests/coverage_reports/html/index.html
```

Run in parallel:

```bash
pytest tests/ -n auto
```

Test Organization
------------------

```
tests/
├── conftest.py                    # Root fixtures
├── factories/                     # Test data factories
│   ├── __init__.py               # BaseFactory
│   ├── agent_factory.py          # AgentRegistry
│   ├── user_factory.py           # User
│   ├── episode_factory.py        # Episode/EpisodeSegment
│   ├── execution_factory.py      # AgentExecution
│   └── canvas_factory.py         # CanvasAudit
├── property_tests/               # Hypothesis property tests
├── integration/                  # Integration tests
├── unit/                         # Isolated unit tests
└── coverage_reports/             # Coverage reports
```

Using Test Factories
--------------------

Factories provide dynamic, isolated test data:

```python
from tests.factories import AgentFactory, UserFactory

# Create an agent with dynamic data
agent = AgentFactory.create(
    status="STUDENT",
    confidence=0.4
)
# agent.id is a unique UUID (not hardcoded)

# Create a user
user = UserFactory.create(
    role="member",
    status="active"
)
# user.email is unique (Faker-generated)
```

Markers
-------

Tests are categorized by markers:

```bash
pytest -m unit              # Unit tests only
pytest -m integration       # Integration tests only
pytest -m "not slow"        # Exclude slow tests
pytest -m P0               # Critical priority tests
```

CI/CD Integration
-----------------

GitHub Actions runs tests automatically:

1. **Push to main/develop**: Full test suite with coverage
2. **Pull Request**: Full test suite with coverage enforcement
3. **Coverage Threshold**: 80% minimum (configurable)

Coverage reports are uploaded as artifacts and retained for 30 days.

Local Development
-----------------

For fast feedback during development:

```bash
# Run only modified tests
pytest tests/ -v --lf  # "last failed" - rerun failed tests

# Run with pdb on failure
pytest tests/ -v --pdb

# Stop on first failure
pytest tests/ -v -x

# Run specific file
pytest tests/property_tests/database/test_database_invariants.py -v
```

Coverage Targets
----------------

| Domain | Target | Priority |
|--------|--------|----------|
| Governance | 80% | P0 |
| Security | 80% | P0 |
| Episodes | 80% | P1 |
| Core backend | 80% | P1 |

See [TESTING_GUIDE.md](./TESTING_GUIDE.md) for comprehensive testing documentation.
