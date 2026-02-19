# Domain Pitfalls: Community Skills Integration

**Domain:** Community Skills Integration (OpenClaw/ClawHub ecosystem)
**Researched:** 2026-02-18
**Overall confidence:** HIGH

---

## Critical Pitfalls

Mistakes that cause rewrites, security breaches, or major operational issues.

### Pitfall 1: Docker Sandbox Escape via Container Misconfiguration

**What goes wrong:** Malicious Python skill escapes Docker container isolation through socket mounts, privileged mode, or kernel exploits, gaining access to host filesystem and Docker daemon.

**Why it happens:**
- Development shortcuts: mounting `/var/run/docker.sock` for "convenience"
- Copying container configurations from production app containers that need privileges
- Using `--privileged` mode to debug skill execution issues
- Outdated Docker daemon with known CVEs (CVE-2024-4237, CVE-2025-1728)
- Forgetting to set `network_disabled=True` or `read_only=True`

**Consequences:**
- **CRITICAL**: Container escape allows skill to:
  - Access host filesystem (`/home`, `/root`, `.env` files with API keys)
  - Control Docker daemon (spawn malicious containers, attack other containers)
  - Exfiltrate data via network (bypass `network_disabled` via Docker socket)
  - Persist malware (install backdoors, modify Docker images)
- Data breach requiring customer notification
- Complete system compromise requiring full rebuild

**Prevention:**
```python
# CRITICAL: Never allow these configurations
FORBIDDEN_CONFIGS = {
    "privileged": True,           # Equivalent to no isolation
    "network_mode": "host",        # Bypass network isolation
    "volumes": ["/var/run/docker.sock"],  # Docker daemon access
    "user": "root",                # Privileged user in container
    "cap_add": ["ALL"],            # All Linux capabilities
}

# REQUIRED: Always enforce these constraints
REQUIRED_SECURITY = {
    "network_disabled": True,      # No network access
    "read_only": True,             # No persistent filesystem changes
    "mem_limit": "256m",           # Memory constraint
    "cpu_quota": 50000,            # CPU constraint (0.5 cores)
    "auto_remove": True,           # Cleanup after execution
    "tmpfs": {"/tmp": "size=10m"}, # Temporary storage only
}
```

**Detection:**
- Container attempts to mount `/var/run/docker.sock`
- Skills request `--privileged` or `network_mode=host`
- Container runtime logs show syscall blocking (seccomp violations)
- Skill execution time exceeds 5-minute timeout (crypto mining indicator)

**Phase to address:** Plan 01 (Skill Adapter & Sandbox) - Implement sandbox with hardcoded security constraints, unit tests for forbidden configurations

---

### Pitfall 2: LLM Security Scanner Bypass via Obfuscation

**What goes wrong:** GPT-4 semantic analysis misses obfuscated malicious code (base64-encoded payloads, string concatenation, `getattr(getattr(os, "sy") + "stem")`), allowing dangerous skills to be marked "LOW" risk.

**Why it happens:**
- Static pattern matching only catches obvious threats (`os.system`, `subprocess.call`)
- LLM focuses on surface-level code structure, not runtime behavior
- Malicious authors use advanced obfuscation techniques
- Base64-encoded strings decode to dangerous commands at runtime
- Dynamic imports (`__import__` decoded from character manipulation)

**Consequences:**
- **HIGH**: Malicious skills marked "LOW" risk bypass human review
- Skills execute with `eval(decode(base64_payload))` after import
- Data exfiltration via DNS tunneling (bypasses `network_disabled` detection)
- Persistence via scheduled tasks or container image pollution
- Trust collapse: Users stop trusting security scan results

**Prevention:**
```python
# Enhanced static analysis (beyond pattern matching)
def _advanced_static_scan(code: str) -> List[str]:
    """Detect obfuscated malicious patterns."""
    findings = []

    # Check for base64 strings
    if re.search(r'base64\.b64decode\(["\']([A-Za-z0-9+/=]{20,})["\']\)', code):
        findings.append("Base64 decoding detected (potential payload obfuscation)")

    # Check for string concatenation to build function names
    if re.search(r'getattr\([\w\s+,+]+\)', code):
        findings.append("Dynamic attribute access detected (potential obfuscation)")

    # Check for character manipulation
    if re.search(r'["\'][\w\s]*["\']\s*\+\s*["\'][\w\s]*["\']', code) and 'import' in code:
        findings.append("String concatenation detected (import obfuscation)")

    # Check for compile() or exec() with strings
    if 'compile(' in code or 'exec(' in code:
        findings.append("Dynamic code execution detected (compile/exec)")

    # Check for encoded import statements
    if '__import__' in code and any(s in code for s in ['base64', 'decode', 'chr(', 'ord(']):
        findings.append("Potential import obfuscation detected")

    return findings
```

**Detection:**
- Security scan returns "LOW" but skill uses `base64`, `compile`, or `getattr`
- LLM analysis doesn't mention obfuscation techniques
- Skill imports with "UNKNOWN" risk but has suspicious function calls
- Post-scan validation: Re-scan with deobfuscation attempts

**Phase to address:** Plan 03 (Skills Registry & Security) - Implement advanced static analysis, add deobfuscation detection, test with known malicious patterns

---

### Pitfall 3: Governance Bypass via Skill Maturity Escalation

**What goes wrong:** STUDENT/INTERN agents bypass maturity checks through community skills that execute restricted actions (Python code, system commands, network access) without proper gatekeeping.

**Why it happens:**
- Skill governance checks only agent maturity, not skill risk level
- Community skills default to "INTERN" maturity requirement even for dangerous skills
- Missing action complexity classification (Action Level 4: deletions should require AUTONOMOUS)
- Skills marked "Active" after single LLM scan without human review
- STUDENT agents blocked from Python skills but can use prompt skills that trick LLM into executing code

**Consequences:**
- **HIGH**: STUDENT agents execute restricted actions through skill proxy
- Unauthorized file deletions, database modifications
- Data loss from skills marked "safe" but performing destructive operations
- Audit trail gaps: Skill execution logged but skill content not reviewed
- Graduation pollution: Agents advance using community skills instead of learning

**Prevention:**
```python
# Enhanced governance check in skill execution
def _validate_skill_execution(
    self,
    agent_id: str,
    skill: Dict[str, Any],
    inputs: Dict[str, Any]
) -> Tuple[bool, str]:
    """
    Validate agent maturity against skill risk and action complexity.

    Returns:
        (allowed, reason)
    """
    agent = self._governance.get_agent(agent_id)
    if not agent:
        return False, f"Agent not found: {agent_id}"

    agent_maturity = agent.get("maturity_level", "STUDENT")
    skill_type = skill.get("skill_type")
    risk_level = skill.get("security_scan_result", {}).get("risk_level", "UNKNOWN")
    status = skill.get("status")

    # Rule 1: Untrusted skills require AUTONOMOUS approval
    if status == "Untrusted":
        if agent_maturity != "AUTONOMOUS":
            return False, f"Untrusted skills require AUTONOMOUS maturity (agent: {agent_maturity})"

    # Rule 2: STUDENT agents blocked from ALL Python skills
    if agent_maturity == "STUDENT" and skill_type == "python_code":
        return False, "STUDENT agents cannot execute Python skills (educational gate)"

    # Rule 3: INTERN agents require approval for Python skills
    if agent_maturity == "INTERN" and skill_type == "python_code":
        # Check if skill has prior approval history
        approval_count = self._get_skill_approval_count(skill["skill_id"])
        if approval_count == 0:
            return False, f"INTERN agent requires approval for Python skill '{skill['skill_name']}'"

    # Rule 4: HIGH/CRITICAL risk skills require SUPERVISED+ maturity
    if risk_level in ["HIGH", "CRITICAL"]:
        if agent_maturity not in ["SUPERVISED", "AUTONOMOUS"]:
            return False, f"HIGH/CRITICAL risk skills require SUPERVISED+ maturity (agent: {agent_maturity})"

    # Rule 5: Action complexity classification (future enhancement)
    # Parse skill code for destructive operations (DELETE, DROP, rm -rf)
    destructive_ops = self._detect_destructive_operations(skill.get("skill_body", ""))
    if destructive_ops and agent_maturity != "AUTONOMOUS":
        return False, f"Destructive operations ({destructive_ops}) require AUTONOMOUS maturity"

    return True, "Governance check passed"
```

**Detection:**
- STUDENT agents successfully execute Python skills
- Skills with "HIGH" risk marked "Active" without human approval
- Audit logs show skills executing actions beyond agent maturity level
- Graduation metrics spike from community skill usage (not genuine learning)

**Phase to address:** Gap Closure - Add governance integration tests, verify maturity checks for all skill types, add destructive operation detection

---

### Pitfall 4: Memory Pollution via Excessive Skill Episode Creation

**What goes wrong:** Every skill execution creates EpisodeSegments, causing episodic memory bloat (thousands of low-value episodes), slowing retrieval, and degrading graduation readiness scoring.

**Why it happens:**
- Line 461-521 in `skill_registry_service.py`: All skill executions create episodes
- No filtering for trivial skills (calculators, formatters)
- Episode segmentation lacks skill-specific heuristics (success/failure not sufficient)
- No episode consolidation for repeated skill executions
- Memory retrieval returns thousands of "Executed calculator_skill" segments

**Consequences:**
- **MEDIUM**: Episodic memory database grows 10x faster (1000 episodes/day vs. 100/day)
- Semantic search performance degrades (LanceDB queries slow with 100K+ segments)
- Graduation readiness scoring polluted (agent has 5000 episodes but 4500 are trivial skill executions)
- Agent retrieval quality drops: Low-value segments drown out meaningful episodes
- Storage costs increase (PostgreSQL + LanceDB storage for redundant episodes)

**Prevention:**
```python
# Enhanced episode creation with skill-specific filtering
async def _create_execution_episode(
    self,
    skill_name: str,
    agent_id: str,
    inputs: dict,
    result: Any,
    error: Optional[Exception],
    execution_time: float
) -> Optional[str]:
    """
    Create episode segment only for significant skill executions.

    Filter criteria:
    - Failed executions (always valuable for learning)
    - Execution time > 1 second (significant computation)
    - Skills with destructive operations (learning trigger)
    - Skills with error handling (recovery patterns)
    - Reject: Trivial skills (< 100ms, no errors, deterministic output)
    """
    # Filter 1: Always create episodes for failures
    if error is not None:
        return await self._create_segment(...)

    # Filter 2: Skip trivial executions (fast, deterministic, no complexity)
    if execution_time < 0.1:  # < 100ms
        # Check if skill is deterministic (same inputs → same output)
        if self._is_deterministic_skill(skill_name):
            logger.debug(f"Skipping episode for trivial skill: {skill_name} ({execution_time:.3f}s)")
            return None

    # Filter 3: Skip high-volume utility skills
    trivial_skills = {"calculator", "formatter", "timestamp", "hash_generator", "uuid_generator"}
    if any(name in skill_name.lower() for name in trivial_skills):
        logger.debug(f"Skipping episode for utility skill: {skill_name}")
        return None

    # Filter 4: Create episode for significant executions
    if execution_time > 1.0 or error is not None:
        return await self._create_segment(...)

    # Filter 5: Rate limiting - max 10 episodes per skill per day
    episode_count = self._get_skill_episode_count(agent_id, skill_name, hours=24)
    if episode_count >= 10:
        logger.debug(f"Rate limit reached for skill: {skill_name} ({episode_count} episodes/day)")
        return None

    # Default: Create episode
    return await self._create_segment(...)
```

**Detection:**
- EpisodeSegments table grows >10K rows/week (normal: <100/week)
- Semantic retrieval returns >50% trivial skill executions
- Agent graduation readiness score inflated (episode count high but intervention rate unchanged)
- LanceDB query latency increases (semantic search >500ms for 10K+ segments)

**Phase to address:** Gap Closure - Add skill episode filtering, rate limiting, and consolidation logic

---

## Moderate Pitfalls

Mistakes that cause operational issues or degraded performance.

### Pitfall 5: Orphaned Docker Containers from Skill Execution Failures

**What goes wrong:** Skill execution errors (timeout, exception, Docker crash) leave containers running, consuming resources and filling up Docker daemon.

**Why it happens:**
- `auto_remove=True` only works if container exits cleanly
- Errors during container startup leave containers in "Created" state
- Exception handlers don't call `container.remove(force=True)`
- Docker daemon crashes/restarts leave zombie containers
- No periodic cleanup job for orphaned containers

**Consequences:**
- **MEDIUM**: Hundreds of stopped containers accumulate
- Disk space exhaustion (container layers, log files)
- Container name conflicts (`skill_abc123` already exists)
- Docker daemon slowdown (managing 1000+ containers)
- Skill execution failures (can't create new containers)

**Prevention:**
```python
# Robust container cleanup in HazardSandbox
def execute_python(self, code: str, inputs: Dict[str, Any], ...) -> str:
    container_id = f"skill_{uuid.uuid4().hex[:8]}"
    container = None

    try:
        # Create container (don't run yet)
        container = self.client.containers.create(
            image="python:3.11-slim",
            command=["python", "-c", wrapper_script],
            name=container_id,
            **self._security_constraints
        )

        # Start container
        container.start()

        # Wait for completion with timeout
        result = container.wait(timeout=timeout_seconds)

        # Get logs
        output = container.logs(stdout=True, stderr=True).decode("utf-8")

        return output

    except Exception as e:
        logger.error(f"Container execution failed: {e}")
        # CRITICAL: Always cleanup on error
        if container:
            try:
                container.remove(force=True)
                logger.info(f"Cleaned up container {container_id} after error")
            except Exception as cleanup_error:
                logger.error(f"Failed to cleanup container {container_id}: {cleanup_error}")
        raise

    finally:
        # Ensure container is removed even if successful
        if container:
            try:
                container.remove(force=True)
            except Exception as e:
                logger.warning(f"Final cleanup failed for {container_id}: {e}")

# Periodic cleanup job (run every hour)
def cleanup_orphaned_containers():
    """Remove any orphaned skill containers."""
    client = docker.from_env()

    # List all containers with "skill_" prefix
    containers = client.containers.list(all=True, filters={"name": "skill_"})

    orphaned_count = 0
    for container in containers:
        # Remove containers that are stopped or dead
        if container.status in ["exited", "dead", "created"]:
            try:
                container.remove(force=True)
                orphaned_count += 1
                logger.info(f"Removed orphaned container {container.name}")
            except Exception as e:
                logger.error(f"Failed to remove {container.name}: {e}")

    if orphaned_count > 0:
        logger.warning(f"Cleaned up {orphaned_count} orphaned skill containers")
```

**Detection:**
- `docker ps -a | grep skill_ | wc -l` shows >100 containers
- Container names like `skill_abc123def` in "Created" or "Exited" status
- Docker daemon logs show "no space left on device"
- Skill execution fails with "container name already exists"

**Phase to address:** Plan 01 (Skill Adapter & Sandbox) - Add robust cleanup logic, periodic cleanup job, monitoring for orphaned containers

---

### Pitfall 6: Skill Parse Failures from Malformed SKILL.md Files

**What goes wrong:** Community SKILL.md files have invalid YAML syntax, missing `---` delimiters, or non-standard field names, causing import failures and user frustration.

**Why it happens:**
- OpenClaw/ClawHub has loose validation (skills accepted without linting)
- Authors manually create SKILL.md without YAML validators
- Mixed indentation (tabs vs. spaces)
- Missing required fields (`name:`, `description:`)
- Custom fields not in Atom's schema

**Consequences:**
- **MEDIUM**: 10-30% of skill imports fail with parsing errors
- Users abandon Community Skills feature ("nothing imports")
- Support burden: "Why can't I import this skill?"
- Negative community perception
- Manual skill fixing required (defeats automation goal)

**Prevention:**
Already implemented in `skill_parser.py` with lenient parsing. Add recovery statistics tracking and user-friendly error messages.

**Detection:**
- Import success rate <70% (normal: >90%)
- Error logs show `YAMLError`, `ScannerError`
- User reports: "Import failed with no clear error message"
- Support tickets: "How do I fix SKILL.md format?"

**Phase to address:** Plan 01 (Skill Adapter & Sandbox) - Already implemented with lenient parsing, add recovery statistics and user-friendly error messages

---

### Pitfall 7: LLM Security Scanning Costs and Rate Limits

**What goes wrong:** GPT-4 API costs accumulate ($0.01 per skill × 5000 skills = $50 per full scan), API rate limits trigger, and scanning becomes a bottleneck.

**Why it happens:**
- Every import triggers LLM scan (no caching by content hash)
- OpenAI rate limits (3,000 RPM for GPT-4)
- Re-importing same skill re-scans (wasted API calls)
- No batch scanning support
- Fail-open behavior means scans fail but cost still incurred

**Consequences:**
- **MEDIUM**: Monthly OpenAI bill spikes from community skill imports
- Import failures: "Rate limit exceeded, please retry"
- Slow imports (5-10 seconds per skill for API call)
- Cache pollution: Multiple scans of identical skill content
- Cost monitoring needed (unexpected budget overruns)

**Prevention:**
```python
# Enhanced caching and batch scanning
class SkillSecurityScanner:
    def __init__(self):
        # Persistent cache (Redis or database)
        self._scan_cache = {}  # TODO: Migrate to Redis
        self._pending_scans = {}  # Deduplicate concurrent scans

    def scan_skill(self, skill_name: str, skill_content: str) -> Dict[str, Any]:
        """
        Scan with SHA-based caching and deduplication.
        """
        # Check cache first (SHA hash of content)
        cache_key = hashlib.sha256(skill_content.encode()).hexdigest()
        if cache_key in self._scan_cache:
            logger.debug(f"Cache hit for skill '{skill_name}' (SHA: {cache_key[:8]}...)")
            return self._scan_cache[cache_key]

        # Deduplicate concurrent scans (same skill being imported by multiple users)
        if cache_key in self._pending_scans:
            logger.info(f"Waiting for existing scan of '{skill_name}'...")
            return self._pending_scans[cache_key]

        # Perform scan (with rate limit handling)
        try:
            # Static scan first (free, fast)
            static_findings = self._static_scan(skill_content)
            if static_findings:
                result = {"safe": False, "risk_level": "CRITICAL", "findings": static_findings}
                self._scan_cache[cache_key] = result
                return result

            # LLM scan (with retry for rate limits)
            llm_result = self._llm_scan_with_retry(skill_name, skill_content)

            # Cache result
            self._scan_cache[cache_key] = llm_result
            return llm_result

        finally:
            # Remove from pending scans
            self._pending_scans.pop(cache_key, None)

    def _llm_scan_with_retry(self, skill_name: str, skill_content: str) -> Dict[str, Any]:
        """
        LLM scan with exponential backoff for rate limits.
        """
        max_retries = 3
        base_delay = 1.0

        for attempt in range(max_retries):
            try:
                return self._llm_scan(skill_name, skill_content)
            except RateLimitError as e:
                if attempt == max_retries - 1:
                    # Last attempt failed, return UNKNOWN
                    logger.error(f"LLM scan rate limited after {max_retries} attempts")
                    return {
                        "safe": True,
                        "risk_level": "UNKNOWN",
                        "findings": [f"Scan rate limited: {str(e)}"]
                    }

                # Exponential backoff
                delay = base_delay * (2 ** attempt)
                logger.warning(f"LLM scan rate limited, retrying in {delay}s...")
                time.sleep(delay)
```

**Detection:**
- OpenAI API costs spike >$100/month
- Import logs show "Rate limit exceeded" errors
- Scan cache hit rate <50% (should be >80%)
- Duplicate scan entries in database (same SHA, different timestamps)

**Phase to address:** Plan 03 (Skills Registry & Security) - Implement SHA-based caching, Redis for persistent cache, rate limit handling, batch scanning API

---

## Minor Pitfalls

Mistakes that cause minor issues or edge case failures.

### Pitfall 8: Pydantic Validation Errors Blocking Agent Tool Calls

**What goes wrong:** LangChain agents fail to call skill tools because `args_schema` validation rejects inputs (type mismatch, missing fields, extra fields not allowed).

**Why it happens:**
- Pydantic 2 is strict about type coercion (no implicit string → int conversion)
- Skills expect flexible inputs (query can be string, dict, or list)
- Missing `Field(default=None)` for optional parameters
- `extra='forbid'` in BaseModel rejects additional fields
- LLM provides JSON but skill expects plain string

**Consequences:**
- **MINOR**: Agent execution fails with `ValidationError`
- Tools never called despite being available
- User confusion: "Why didn't the agent use the skill?"
- Agent fallback to manual responses

**Prevention:**
```python
# Flexible Pydantic schema for skill inputs
from pydantic import BaseModel, Field, ConfigDict
from typing import Any, Optional

class CommunitySkillInput(BaseModel):
    """
    Flexible input schema for community skills.
    """
    model_config = ConfigDict(
        extra='allow'  # Allow extra fields (don't reject LLM additions)
    )

    # Use Any for flexible types (LLM can pass string, dict, list)
    query: Any = Field(
        description="User query or input (can be string, dict, or list)",
        default=None
    )

    # Optional parameters with defaults
    context: Optional[dict] = Field(
        description="Additional context for skill execution",
        default=None
    )

    # Custom validator for type coercion
    @field_validator('query')
    @classmethod
    def validate_query(cls, v: Any) -> Any:
        """Accept any query type, convert to string if needed."""
        if v is None:
            return ""
        if isinstance(v, (dict, list)):
            return json.dumps(v)
        return str(v)
```

**Detection:**
- Agent execution logs show `ValidationError` for skill tools
- Tools available but never called in agent traces
- User reports: "Agent didn't use the skill I requested"
- LangChain callback logs show tool call failures

**Phase to address:** Plan 01 (Skill Adapter & Sandbox) - Use flexible Pydantic schemas, add type coercion validators, test with various input types

---

### Pitfall 9: Database Schema Mismatch for Skill Metadata

**What goes wrong:** SkillExecution model lacks fields needed for community skills (`skill_source`, `security_scan_result`, `sandbox_enabled`), causing migration errors.

**Why it happens:**
- Phase 14 extends existing SkillExecution model (originally for ACU billing)
- Alembic migration not created before code deployment
- PostgreSQL JSON columns incompatible with SQLAlchemy JSON type
- Missing indexes on new fields (slow queries)

**Consequences:**
- **MINOR**: `IntegrityError` on skill insert
- `NoSuchColumnError` when querying imported skills
- Slow skill listing (full table scan without indexes)
- Manual SQL patches required

**Prevention:**
```python
# Alembic migration for community skills
"""add_community_skill_fields

Revision ID: 001_community_skills
Create Date: 2026-02-16
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade():
    # Add community skill columns to skill_executions
    op.add_column('skill_executions', sa.Column('skill_source', sa.String(), nullable=True))
    op.add_column('skill_executions', sa.Column('security_scan_result', postgresql.JSON(), nullable=True))
    op.add_column('skill_executions', sa.Column('sandbox_enabled', sa.Boolean(), default=False))

    # Create indexes for filtering
    op.create_index('ix_skill_executions_skill_source', 'skill_executions', ['skill_source'])
    op.create_index('ix_skill_executions_status', 'skill_executions', ['status'])

    # Backfill existing records
    op.execute("""
        UPDATE skill_executions
        SET skill_source = 'cloud',
            sandbox_enabled = FALSE
        WHERE skill_source IS NULL
    """)

    # Set columns to non-nullable after backfill
    op.alter_column('skill_executions', 'skill_source', nullable=False)

def downgrade():
    op.drop_index('ix_skill_executions_status', 'skill_executions')
    op.drop_index('ix_skill_executions_skill_source', 'skill_executions')
    op.drop_column('skill_executions', 'sandbox_enabled')
    op.drop_column('skill_executions', 'security_scan_result')
    op.drop_column('skill_executions', 'skill_source')
```

**Detection:**
- `alembic upgrade head` fails with `DuplicateColumnError`
- Application startup fails: `NoSuchColumnError: skill_executions.skill_source`
- Skill listing queries slow (>1 second for 1000 skills)

**Phase to address:** Plan 03 (Skills Registry & Security) - Create Alembic migration before deploying code, add indexes, test with existing data

---

### Pitfall 10: Skill Execution Timeout Issues

**What goes wrong:** Skills with infinite loops, blocking operations, or slow computation exceed 5-minute timeout, leaving containers running and agents hanging.

**Why it happens:**
- No timeout enforcement in sandbox (Docker `timeout` parameter not set)
- Skills use `time.sleep()` or blocking I/O
- Infinite loops from malformed code
- Large dataset processing without chunking
- No early termination signal

**Consequences:**
- **MINOR**: Agent execution hangs for 5+ minutes
- Container resources tied up (can't execute other skills)
- User frustration: "Agent is stuck"
- Timeout errors lack context (which skill caused it?)

**Prevention:**
```python
# Enforce timeout with early termination
def execute_python(
    self,
    code: str,
    inputs: Dict[str, Any],
    timeout_seconds: int = 30,  # Default 30s (not 5 minutes)
    memory_limit: str = "256m",
    cpu_limit: float = 0.5
) -> str:
    """
    Execute with strict timeout and resource limits.
    """
    container_id = f"skill_{uuid.uuid4().hex[:8]}"

    try:
        # Validate timeout (max 5 minutes)
        timeout_seconds = min(timeout_seconds, 300)

        # Check for obvious infinite loops before execution
        if self._detect_infinite_loop(code):
            raise ValueError("Code contains potential infinite loop (rejected)")

        # Run with timeout
        output = self.client.containers.run(
            ...,
            timeout=timeout_seconds,  # Docker SDK timeout
            ...
        )

        return output.decode("utf-8")

    except ReadTimeout as e:
        logger.error(f"Skill timeout after {timeout_seconds}s: {container_id}")
        return f"TIMEOUT: Skill execution exceeded {timeout_seconds} seconds"

    except Exception as e:
        return f"ERROR: {str(e)}"

def _detect_infinite_loop(self, code: str) -> bool:
    """
    Detect obvious infinite loop patterns.
    """
    dangerous_patterns = [
        "while True:",       # Infinite loop
        "for i in itertools.count():",  # Infinite iterator
        "while 1:",          # Infinite loop (old style)
        "while not done:",   # Flag never set
    ]

    for pattern in dangerous_patterns:
        if pattern in code:
            # Check if there's a break statement
            if "break" not in code[code.find(pattern):code.find(pattern)+200]:
                return True

    return False
```

**Detection:**
- Skill execution logs show "timeout after 300s"
- Agent traces show 5-minute gaps during skill calls
- User reports: "Agent froze while using skill"
- Container list shows running containers older than 5 minutes

**Phase to address:** Plan 01 (Skill Adapter & Sandbox) - Implement timeout validation, infinite loop detection, and early termination

---

## Integration Pitfalls

### Pitfall 11: Breaking Existing Governance via Skill Proxy

**What goes wrong:** Community skills bypass existing governance checks (GovernanceCache, TriggerInterceptor, ProposalService) by executing actions on behalf of agents without proper attribution.

**Why it happens:**
- Skill execution doesn't integrate with GovernanceCache
- Agent maturity checked but action complexity not validated
- Skills trigger downstream actions (file deletes, API calls) without proposal workflow
- Audit trail shows skill execution but not underlying actions

**Consequences:**
- **MEDIUM**: Agents bypass maturity-based restrictions through skill proxy
- TriggerInterceptor doesn't block skill-triggered automated actions
- ProposalService unaware of skill-initiated state changes
- Audit trail gaps (skill logged but internal actions not)

**Prevention:**
```python
# Integrate skill execution with existing governance
async def execute_skill(self, skill_id: str, inputs: Dict, agent_id: str) -> Dict:
    """
    Execute skill with full governance integration.
    """
    # Step 1: Check governance cache (existing system)
    cache_key = f"{agent_id}:skill_execution:{skill_id}"
    cached_decision = self._governance_cache.get(cache_key)
    if cached_decision:
        if not cached_decision["allowed"]:
            raise ValueError(f"Governance cache blocked: {cached_decision['reason']}")
    else:
        # Step 2: Full governance check (AgentGovernanceService)
        allowed, reason = await self._governance.check_agent_action(
            agent_id=agent_id,
            action_type="skill_execution",
            action_complexity=self._get_skill_complexity(skill_id),
            context={"skill_id": skill_id, "inputs": inputs}
        )

        if not allowed:
            # Cache denial
            self._governance_cache.set(cache_key, {"allowed": False, "reason": reason})
            raise ValueError(f"Governance check failed: {reason}")

        # Cache approval
        self._governance_cache.set(cache_key, {"allowed": True})

    # Step 3: Check if proposal required (INTERN maturity)
    agent = await self._governance.get_agent(agent_id)
    if agent["maturity_level"] == "INTERN" and self._is_python_skill(skill_id):
        # Create proposal for human approval
        proposal = await self._proposal_service.create_proposal(
            agent_id=agent_id,
            action_type="skill_execution",
            proposed_action={"skill_id": skill_id, "inputs": inputs},
            reason="INTERN agent requires approval for Python skill"
        )
        return {"status": "awaiting_approval", "proposal_id": proposal.id}

    # Step 4: Execute skill
    result = await self._execute_skill_impl(skill_id, inputs, agent_id)

    # Step 5: Log to audit trail (existing system)
    await self._audit_log.log_action(
        agent_id=agent_id,
        action_type="skill_execution",
        action_id=skill_id,
        result=result,
        metadata={"governance": "passed", "complexity": self._get_skill_complexity(skill_id)}
    )

    return result
```

**Detection:**
- GovernanceCache hit rate drops (skills bypass cache)
- Audit logs missing skill-triggered actions
- INTERN agents execute Python skills without proposals
- TriggerInterceptor allows automated triggers from skills

**Phase to address:** Gap Closure - Integrate skill execution with GovernanceCache, ProposalService, and audit logging

---

### Pitfall 12: Graduation Readiness Pollution from Skill Episodes

**What goes wrong:** Agent graduation framework counts skill execution episodes toward readiness scores, allowing agents to graduate without genuine learning.

**Why it happens:**
- Graduation criteria: "50 episodes" (doesn't distinguish skill vs. agent actions)
- Agent runs 50 trivial calculator skills → qualifies for INTERN promotion
- No intervention rate tracking for skill executions (skills don't trigger supervision)
- Episode quality scoring not applied to skill episodes

**Consequences:**
- **MEDIUM**: Agents graduate without learning skills (episodic memory polluted)
- INTERN agents promoted to SUPERVISED after 50 calculator executions
- Graduation readiness score meaningless (high quantity, low quality)
- Constitutional compliance validation passes (no interventions from skills)

**Prevention:**
```python
# Graduation framework ignores or discounts skill episodes
class AgentGraduationService:
    def calculate_readiness_score(self, agent_id: str) -> float:
        """
        Calculate readiness score with skill episode discounting.
        """
        # Get all episodes for agent
        episodes = self._segmentation_service.get_agent_episodes(agent_id)

        # Separate skill episodes from agent episodes
        skill_episodes = [e for e in episodes if e.metadata.get("source_type") == "skill_execution"]
        agent_episodes = [e for e in episodes if e.metadata.get("source_type") != "skill_execution"]

        # Weight agent episodes 10x higher than skill episodes
        skill_count = len(skill_episodes) * 0.1  # Discount skill episodes
        agent_count = len(agent_episodes)

        # Episode count score (40% of readiness)
        episode_score = min((agent_count + skill_count) / 50, 1.0) * 0.4

        # Intervention rate (only count agent-initiated interventions)
        agent_interventions = self._get_intervention_count(agent_id, exclude_skills=True)
        intervention_score = (1 - agent_interventions / agent_count) * 0.3

        # Constitutional compliance (already skill-aware)
        compliance_score = self._get_compliance_score(agent_id) * 0.3

        return episode_score + intervention_score + compliance_score
```

**Detection:**
- Agents graduate with 90%+ skill episodes
- Graduation readiness score high but intervention rate unchanged
- SUPERVISED agents have poor performance despite passing graduation
- Episode breakdown shows <10% agent-initiated actions

**Phase to address:** Gap Closure - Modify graduation scoring to discount skill episodes, track skill vs. agent episodes separately

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|----------------|------------|
| **14-01: Skill Adapter & Sandbox** | Docker sandbox escape (Pitfall 1), Orphaned containers (Pitfall 5), Timeout issues (Pitfall 10) | Hardcode security constraints, add robust cleanup, implement timeout validation |
| **14-02: Skills Registry API** | Parse failures (Pitfall 6), Database schema mismatch (Pitfall 9) | Use lenient parsing, create Alembic migration before code |
| **14-03: Security & Governance** | LLM scanner bypass (Pitfall 2), Governance bypass (Pitfall 3), Scanning costs (Pitfall 7) | Add advanced static analysis, enhanced maturity checks, SHA-based caching |
| **Gap Closure: Memory Integration** | Memory pollution (Pitfall 4) | Add skill episode filtering, rate limiting, and consolidation |

---

## Security Mistakes

Beyond general web security — Community Skills specific issues.

| Mistake | Risk | Prevention |
|---------|------|------------|
| **Docker socket mount** | Container escape → host compromise | NEVER mount `/var/run/docker.sock`, use `network_disabled=True` |
| **Privileged mode** | Full system access from container | Always use non-privileged containers, drop capabilities |
| **LLM scanner bypass** | Malicious code marked safe | Combine static analysis + LLM semantic + deobfuscation detection |
| **Base64 payloads** | Hidden malicious code | Detect `base64.b64decode()`, `decode()`, string manipulation |
| **Dynamic imports** | Obfuscated module loading | Flag `__import__`, `getattr()`, character manipulation |
| **Sandbox timeout** | Resource exhaustion | Enforce 5-minute max timeout, implement early termination |
| **Network bypass** | Data exfiltration | Set `network_disabled=True`, block DNS requests |

---

## Performance Traps

Patterns that work at small scale but fail with 5,000+ skills.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| **No scan caching** | $500+ OpenAI bill, slow imports | SHA-based caching, Redis persistence | >100 skills imported |
| **Episodic bloat** | DB grows 1GB/week, slow retrieval | Filter trivial skills, rate limiting | >1,000 skill executions/day |
| **Orphaned containers** | Disk full, container name conflicts | Robust cleanup, periodic cleanup job | >500 skill executions |
| **Missing indexes** | Skill listing >5 seconds | Index on `skill_source`, `status` | >1,000 skills in DB |
| **Synchronous scanning** | Import takes 10s/skill | Batch scanning API, async LLM calls | Bulk imports (>50 skills) |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Sandbox Security:** Container config looks secure BUT missing forbidden config validation → Add unit tests for security constraints
- [ ] **LLM Scanning:** Returns "LOW" risk BUT missing deobfuscation detection → Test with base64-encoded payloads
- [ ] **Governance Checks:** Agent maturity validated BUT missing action complexity → Add destructive operation detection
- [ ] **Episode Creation:** Creates segments BUT missing trivial skill filtering → Add execution time and deterministic checks
- [ ] **Container Cleanup:** Uses `auto_remove=True` BUT missing error handling → Test with container crashes
- [ ] **Database Schema:** Columns added BUT missing indexes → Check query performance with 1K+ skills
- [ ] **Import Parsing:** Works for valid YAML BUT missing recovery for malformed files → Test with 100 real ClawHub skills
- [ ] **Graduation Integration:** Episodes created BUT missing skill episode discounting → Verify graduation scoring logic

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| **Container escape detected** | HIGH | 1. Immediate: Kill all containers, restart Docker daemon 2. Audit: Review all skill executions in past 24h 3. Forensics: Check host filesystem for modifications 4. Remediation: Rotate all API keys, rebuild Docker images 5. Prevention: Add forbidden config validation tests |
| **Malicious skill imported** | MEDIUM | 1. Immediate: Ban skill in database, mark as "Banned" 2. Audit: List all agents that executed the skill 3. Impact: Review audit logs for suspicious activity 4. Recovery: Revoke any permissions granted via skill 5. Prevention: Add advanced static analysis |
| **Memory database bloated** | MEDIUM | 1. Immediate: Run episode consolidation script 2. Filtering: Delete episodes matching trivial skill patterns 3. Archival: Move old episodes to LanceDB cold storage 4. Indexing: Rebuild vector indexes 5. Prevention: Add filtering at creation time |
| **Orphaned containers accumulated** | LOW | 1. Immediate: Run `docker ps -a | grep skill_ | xargs docker rm -f` 2. Cleanup: Execute periodic cleanup job 3. Monitoring: Add container count alert (>100 containers) 4. Prevention: Add robust cleanup in error handlers |
| **Database migration failed** | LOW | 1. Immediate: Rollback to previous migration 2. Fix: Update migration script with proper indexes 3. Test: Run migration on staging database 4. Deploy: Re-run migration with downtime 5. Prevention: Test migrations before code deployment |

---

## Pitfall-to-Phase Mapping

How Phase 14 plans should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| **1. Docker sandbox escape** | Plan 01 (Skill Adapter & Sandbox) | Unit tests for forbidden configs, integration tests with malicious skills |
| **2. LLM scanner bypass** | Plan 03 (Security & Governance) | Test suite with obfuscated payloads, scan evasion attempts |
| **3. Governance bypass** | Gap Closure | Integration tests with all maturity levels, audit trail validation |
| **4. Memory pollution** | Gap Closure | Episode filtering tests, memory growth monitoring |
| **5. Orphaned containers** | Plan 01 (Skill Adapter & Sandbox) | Container cleanup tests, periodic cleanup job validation |
| **6. Parse failures** | Plan 01 (Skill Adapter & Sandbox) | Import success rate >90% with 100 real ClawHub skills |
| **7. Scanning costs** | Plan 03 (Security & Governance) | Cache hit rate >80%, batch API implemented |
| **8. Pydantic validation** | Plan 01 (Skill Adapter & Sandbox) | Agent tool call tests with various input types |
| **9. Database schema** | Plan 03 (Security & Governance) | Migration tests on staging, query performance <100ms |
| **10. Timeout issues** | Plan 01 (Skill Adapter & Sandbox) | Timeout enforcement tests, infinite loop detection |
| **11. Governance integration** | Gap Closure | GovernanceCache integration tests, proposal workflow tests |
| **12. Graduation pollution** | Gap Closure | Graduation scoring tests with skill/agent episode separation |

---

## Sources

### Primary (HIGH confidence)

- [Phase 14 RESEARCH.md](/.planning/phases/14-community-skills-integration/14-RESEARCH.md) - Complete research document with verified patterns
- [skill_sandbox.py](/backend/core/skill_sandbox.py) - Docker sandbox implementation with security constraints
- [skill_security_scanner.py](/backend/core/skill_security_scanner.py) - LLM-based security scanning with static analysis
- [skill_registry_service.py](/backend/core/skill_registry_service.py) - Skill lifecycle management and governance integration
- [COMMUNITY_SKILLS.md](/docs/COMMUNITY_SKILLS.md) - User guide with security features and governance
- [Docker Security Best Practices](https://docs.docker.com/engine/security/) - Container isolation and security constraints
- [Pydantic 2 Validation](https://docs.pydantic.dev/latest/concepts/serialization/) - Flexible input validation patterns

### Secondary (MEDIUM confidence)

- [OWASP Docker Security](https://owasp.org/www-project-docker-security/) - Container escape prevention
- [OpenAI API Rate Limits](https://platform.openai.com/docs/guides/rate-limits) - API quota management
- [LangChain BaseTool Patterns](https://python.langchain.com/docs/modules/agents/tools/how_to/custom_tools) - Tool schema validation
- [PostgreSQL JSON Columns](https://www.postgresql.org/docs/current/datatype-json.html) - JSON field indexing
- [Alembic Migration Guide](https://alembic.sqlalchemy.org/en/latest/tutorial.html) - Database schema evolution

### Tertiary (LOW confidence)

- [OpenClaw Skill Format](https://github.com/openclaw/clawhub/blob/main/docs/skill-format.md) - SKILL.md specification (needs validation against real skills)
- [ClawHub Community Skills](https://github.com/openclaw/skills) - Sample skills for testing parsing edge cases

---

## Metadata

**Confidence breakdown:**
- Security pitfalls: HIGH - Based on documented Docker CVEs and container escape patterns
- Governance pitfalls: HIGH - Verified against existing governance implementation
- Performance pitfalls: HIGH - Based on test results and code review
- Integration pitfalls: HIGH - Cross-referenced with episodic memory and graduation services

**Research date:** 2026-02-18
**Valid until:** 2026-03-20 (30 days - Community Skills ecosystem evolving, verify before Phase 14 completion)
