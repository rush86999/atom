# Technology Stack: Community Skills Integration

**Domain:** OpenClaw/ClawHub community skills import, Docker sandbox security, LLM security scanning
**Researched:** 2026-02-18
**Overall confidence:** HIGH

## Executive Summary

Community Skills Integration requires **zero new core technologies** - Atom's existing stack already supports all required capabilities. The implementation leverages Docker SDK for sandboxed execution (already in requirements.txt), OpenAI SDK for LLM security scanning (already in requirements.txt), LangChain BaseTool for tool integration (already in requirements.txt), and Python stdlib `ast` module for code parsing.

**One addition needed:** `python-frontmatter` library (not yet in requirements.txt) for robust YAML frontmatter parsing from SKILL.md files. This is the **only** new dependency required.

All other components (SKILL.md parsing, Docker sandbox, security scanning, governance integration) are already implemented and verified in Phase 14 (82 tests, 13/13 success criteria).

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **python-frontmatter** | 1.0+ | Parse YAML frontmatter from SKILL.md files | Specialized library for Jekyll-style frontmatter with `---` delimiters. Handles malformed YAML gracefully, auto-fixes missing fields, extracts metadata + body. De facto standard for markdown-with-metadata parsing. |
| **Docker SDK for Python** | 7.0+ (✅ Already in requirements.txt) | HazardSandbox - isolated execution containers | Official Docker Python SDK. Provides programmatic container lifecycle management, resource limits (memory, CPU), security constraints (network_disabled, read_only), and stream capture. |
| **OpenAI SDK** | 1.0+ (✅ Already in requirements.txt) | GPT-4 security scanning for malicious patterns | Industry-standard LLM API. Used for semantic analysis to detect obfuscated malicious code that static pattern matching misses. Required for 21+ malicious pattern detection. |
| **LangChain** | 0.1+ (✅ Already in requirements.txt) | BaseTool wrapper for community skills | Industry standard for LLM tool orchestration. Provides structured tool interface with automatic schema validation, agent integration, and tool registry compatibility. |
| **Pydantic** | 2.0+ (✅ Already in requirements.txt) | Input validation with `args_schema` | LangChain 0.1+ requires Pydantic 2 for tool validation. Provides automatic JSON Schema generation, type coercion, and validation errors. |
| **SQLAlchemy** | 2.0+ (✅ Already in requirements.txt) | Database models for CommunitySkill, SkillSecurityScan | Store imported skills, security scan results, and execution history. Already in Atom stack with 4 new models added in Phase 14. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **ast** | stdlib | Extract function signatures from Python code | Parse Python skills to find entry points (`def execute()`, `def run()`, `def main()`) and extract docstrings. Zero dependency. |
| **PyYAML** | 6.0+ (✅ Already in requirements.txt) | YAML frontmatter validation | Used by python-frontmatter internally. Provides `yaml.safe_load()` to prevent arbitrary code execution. |
| **hashlib** | stdlib | SHA256 hashing for skill deduplication | Cache security scan results by skill content hash. Avoid re-scanning identical skills. Zero dependency. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| **pytest** (✅ Already in requirements.txt) | Test framework for 82 community skills tests | 6 test files covering parsing, sandbox, security, adapter, episodic integration, CLI skills |
| **pytest-asyncio** (✅ Already in requirements.txt) | Async test support for skill execution | Tests async `_arun()` methods in CommunitySkillTool |
| **hypothesis** (✅ Already in requirements.txt) | Property-based testing for sandbox invariants | Verify resource limits, isolation guarantees, timeout behavior |

## Installation

```bash
# NEW DEPENDENCY - Only addition needed for Community Skills
pip install python-frontmatter

# Already installed in Atom (from requirements.txt)
# docker>=7.0.0
# openai>=1.0.0
# pydantic>=2.0.0
# langchain (via langchain-core)
# sqlalchemy>=2.0.0
# pyyaml>=6.0.0
# pytest>=7.4.0
# pytest-asyncio>=0.21.0
```

**Add to requirements.txt:**
```txt
python-frontmatter>=1.0.0,<2.0.0
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| **python-frontmatter** | Custom regex parsing | Never - Custom regex is fragile for edge cases (nested `---`, malformed YAML, encoding issues). python-frontmatter handles these gracefully. |
| **python-frontmatter** | ruamel.yaml | ruamel.yaml preserves comments and formatting but is heavier (~2x install size). python-frontmatter sufficient for read-only parsing. |
| **Docker SDK** | subprocess + docker-cli | Docker SDK provides programmatic control, error handling, and stream capture vs. parsing CLI output text. subprocess requires manual stdout/stderr handling. |
| **GPT-4 scanning** | Static pattern matching only | Static patterns miss obfuscated threats (base64, string concat, `getattr(getattr(os, "sy"))`). GPT-4 provides semantic analysis. |
| **LangChain BaseTool** | Direct function wrapping | BaseTool provides automatic LLM integration, schema validation, and agent compatibility. Direct wrapping requires manual serialization. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **PyYAML `load()` without `Loader=`** | Arbitrary code execution vulnerability if SKILL.md contains malicious YAML constructors | **`yaml.safe_load()`** (used by python-frontmatter internally) |
| **`exec()` or `eval()` on skill code** | Critical security vulnerability - allows arbitrary code execution outside sandbox | **HazardSandbox** with Docker containers (network_disabled, read_only) |
| **Custom regex for frontmatter** | Fragile edge cases (nested `---`, malformed YAML, encoding issues, tabs vs spaces) | **python-frontmatter** library (handles these automatically) |
| **`--privileged` Docker mode** | Equivalent to no isolation - container can access host devices, escape easily | **Default isolation** + resource limits (mem_limit, cpu_quota, network_disabled) |
| **Hardcoded entry point names** | Python skills don't enforce `def execute()` - authors use `run()`, `main()`, `handler()` | **AST parsing** to detect all function definitions, let user select entry point |
| **Storing skill code as plaintext** | Security risk if database is compromised | **Encryption** or filesystem storage for large skills (Phase 14 uses plaintext with risk acceptance) |

## Stack Patterns by Variant

**If parsing GitHub-hosted SKILL.md files:**
- Use **python-frontmatter** for frontmatter extraction
- Because it handles URL fetch errors, encoding detection, and malformed YAML gracefully

**If importing from local file uploads:**
- Use **python-frontmatter** with `try/except` for each file
- Because it provides detailed error messages for user feedback

**If parsing bulk skill imports (100+ files):**
- Use **SkillParser.parse_batch()** with summary statistics
- Because it logs successes/failures separately, allows import to continue after individual failures

**If skill has Python code blocks:**
- Use **AST parsing** (`ast.parse()`) to extract function signatures
- Because it properly handles Python syntax, nested scopes, and docstrings vs. regex manipulation

**If skill requires execution:**
- Use **HazardSandbox** with Docker SDK
- Because it provides defense-in-depth security (even if malicious code passes scanning)

**If skill type is unclear:**
- Use **auto-detection** (check for ```python blocks, metadata `type: python`)
- Because OpenClaw doesn't enforce skill type conventions, community skills vary

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| python-frontmatter 1.0+ | PyYAML 6.0+, Python 3.8+ | python-frontmatter uses PyYAML internally, requires UTF-8 encoding |
| Docker SDK 7.0+ | Docker Engine 20.10+ | SDK v7 requires Docker Engine API v1.41+ (Docker Desktop 4.0+, Docker CE 20.10+) |
| LangChain 0.1+ | Pydantic 2.0+ | LangChain 0.1.0+ requires Pydantic 2.0+ for BaseTool args_schema |
| OpenAI SDK 1.0+ | Python 3.8+ | SDK v1.0+ is synchronous by default, async client available via `openai.AsyncOpenAI` |

**Known compatibility issues:**
- **LangChain 0.0.x** uses Pydantic 1.x - Migrate to 0.1+ for Pydantic 2 compatibility
- **Docker SDK 6.x** lacks `cpu_quota` parameter - Upgrade to 7.0+ for fine-grained CPU limits
- **PyYAML 5.x** has `load()` security issue - Upgrade to 6.0+ (already in requirements.txt)

## Existing Atom Integration

The following components are **already implemented** in Phase 14 (completed Feb 16, 2026):

### Implemented Services
- `backend/core/skill_parser.py` - SKILL.md parsing with python-frontmatter
- `backend/core/skill_adapter.py` - LangChain BaseTool wrapper
- `backend/core/skill_sandbox.py` - Docker sandbox execution (Docker SDK 7.0+)
- `backend/core/skill_security_scanner.py` - GPT-4 security scanning (OpenAI SDK 1.0+)
- `backend/core/skill_registry_service.py` - Import UI, governance workflow
- `backend/api/skill_routes.py` - 8 REST endpoints for import, list, execute, promote

### Database Models (Added in Phase 14)
- `CommunitySkill` - Skill metadata (name, description, status, skill_type)
- `SkillSecurityScan` - Security scan results (risk_level, findings)
- `SkillExecution` - Execution history (agent_id, result, duration)
- Migration: `20260216_community_skills_model_extensions.py`

### Test Coverage
- 82 tests across 6 test files (all passing)
- Files: `test_skill_parser.py`, `test_skill_adapter.py`, `test_skill_sandbox.py`, `test_skill_security.py`, `test_skill_episodic_integration.py`, `test_atom_cli_skills.py`

### Documentation
- `docs/COMMUNITY_SKILLS.md` - Comprehensive user guide (508 lines)
- `docs/ATOM_VS_OPENCLAW.md` - Feature comparison (297 lines)

## Sources

### Primary (HIGH confidence)

- [python-frontmatter documentation](https://github.com/eyeseast/python-frontmatter) - YAML frontmatter parsing library
- [Docker SDK for Python 7.0](https://docker-py.readthedocs.io/en/stable/) - Container management, resource limits
- [OpenAI API Reference](https://platform.openai.com/docs/api-reference) - GPT-4 security scanning
- [LangChain BaseTool Guide](https://python.langchain.com/docs/modules/agents/tools/how_to/custom_tools) - Tool integration patterns
- [OpenClaw Skills Format Specification](https://github.com/openclaw/clawhub/blob/main/docs/skill-format.md) - SKILL.md file structure
- [Phase 14 Implementation Research](../.planning/phases/14-community-skills-integration/14-RESEARCH.md) - Verified 13/13 success criteria (Feb 16, 2026)

### Secondary (MEDIUM confidence)

- [Pydantic 2.0 Documentation](https://docs.pydantic.dev/latest/) - BaseModel, Field, validation patterns
- [Python ast Module](https://docs.python.org/3/library/ast.html) - AST parsing for function extraction
- [ClawHub Community Skills Repository](https://github.com/openclaw/skills) - 5,000+ community skill examples

### Implementation Verification (HIGH confidence)

- **Code Review:** All core services implemented and tested (82 tests, 100% pass rate)
- **Gap Analysis:** python-frontmatter is only missing dependency (not in requirements.txt)
- **Integration Points:** Governance, episodic memory, graduation framework all integrated (Phase 14 Plans 1-3 complete)
- **Production Readiness:** Health checks, monitoring, deployment runbooks exist (Phase 15)

---

**Stack research complete:** Community Skills Integration requires only **one new dependency** (`python-frontmatter`). All other technologies are already in Atom's stack with verified implementations.

**Researched:** 2026-02-18
**Valid until:** 2026-03-20 (30 days - verify OpenClaw skill format changes)
