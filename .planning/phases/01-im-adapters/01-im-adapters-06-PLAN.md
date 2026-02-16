---
phase: 01-im-adapters
plan: 06
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/core/im_governance_service.py
  - backend/docs/IM_ADAPTER_SETUP.md
  - backend/docs/IM_SECURITY_BEST_PRACTICES.md
  - .planning/phases/01-im-adapters/01-im-adapters-01-PLAN.md
autonomous: true
gap_closure: true
user_setup: []

must_haves:
  truths:
    - "Documentation accurately describes the rate limiting algorithm (sliding window, not token bucket)"
    - "Rate limiting implementation matches documented behavior"
    - "Users can configure rate limits via environment variables"
    - "No false claims about SlowAPI usage in code or documentation"
  artifacts:
    - path: "backend/core/im_governance_service.py"
      provides: "Rate limiting with accurate docstring"
      contains: "sliding window"
    - path: "backend/docs/IM_ADAPTER_SETUP.md"
      provides: "Accurate rate limiting documentation"
      contains: "sliding window"
    - path: "backend/docs/IM_SECURITY_BEST_PRACTICES.md"
      provides: "Rate limiting implementation details"
      contains: "sliding window"
  key_links:
    - from: "backend/core/im_governance_service.py"
      to: "_check_rate_limit docstring"
      via: "accurate algorithm description"
      pattern: "sliding window|fixed window"
    - from: "backend/docs/IM_ADAPTER_SETUP.md"
      to: "rate limiting section"
      via: "documentation accuracy"
      pattern: "sliding window"
---

<objective>
Address Gap 1: Rate limiting algorithm mismatch between specification and implementation.

**Gap:** Plan 01 specified "SlowAPI with token bucket algorithm" but implementation uses custom sliding window. The rate limiting works correctly (10 req/min enforced) but documentation is misleading.

**Approach:** Update documentation to match implementation rather than replacing working code. The custom sliding window is:
- Functional (correctly enforces 10 req/min)
- Simple (no external dependency)
- Well-tested (property tests pass)

Purpose: Close documentation gap without disrupting working rate limiting implementation
Output: Accurate documentation describing the actual sliding window algorithm
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/01-im-adapters/01-im-adapters-VERIFICATION.md
@.planning/phases/01-im-adapters/01-im-adapters-CONTEXT.md
@.planning/phases/01-im-adapters/01-im-adapters-01-PLAN.md

# Files to update
@backend/core/im_governance_service.py
@backend/docs/IM_ADAPTER_SETUP.md
@backend/docs/IM_SECURITY_BEST_PRACTICES.md
@backend/tests/property_tests/im_governance_invariants.py
</context>

<tasks>

<task type="auto">
  <name>Fix rate limiting docstring in im_governance_service.py</name>
  <files>backend/core/im_governance_service.py</files>
  <action>
Update the inaccurate docstring on _check_rate_limit method (line 359-389):

**Current docstring (INCORRECT):**
```python
def _check_rate_limit(self, key: str) -> bool:
    """
    Check if request is within rate limit using token bucket algorithm.
    """
```

**Fixed docstring (ACCURATE):**
```python
def _check_rate_limit(self, key: str) -> bool:
    """
    Check if request is within rate limit using sliding window algorithm.

    Algorithm:
    - Maintains a list of request timestamps for each key
    - Removes timestamps older than the rate limit window (60 seconds)
    - Allows request if fewer than rate_limit_requests (10) in window
    - Adds current timestamp and allows request

    Rate limit: 10 requests per minute per key (platform:sender_id)
    Window: 60 seconds sliding window
    Burst behavior: All 10 requests can arrive instantly (not true token bucket)

    Note: This is a fixed window with timestamp cleanup, not a true token bucket.
    For production with multiple workers, consider Redis-based rate limiting.
    """
```

**Also update class docstring** if it mentions "token bucket":

Search for any references to "token bucket" or "SlowAPI" in the file and replace with accurate description:
- "token bucket" -> "sliding window"
- "SlowAPI" -> remove (not used)
- "allows bursts" -> keep (accurate - all 10 can come instantly)

**Why documentation fix vs code replacement:**
1. Implementation is correct and tested (property tests pass)
2. No performance issue with current approach (<1ms per check)
3. Avoids adding external dependency (SlowAPI) for working code
4. User decision from CONTEXT.md: governance hardening focus, not rebuilding
  </action>
  <verify>
```bash
# Verify accurate docstring
grep -A 15 "def _check_rate_limit" backend/core/im_governance_service.py | grep -i "sliding window"

# Verify no inaccurate claims remain
! grep -i "token bucket" backend/core/im_governance_service.py
! grep -i "slowapi" backend/core/im_governance_service.py
```
  </verify>
  <done>
im_governance_service.py has accurate rate limiting documentation:
- _check_rate_limit docstring describes sliding window algorithm
- No mention of "token bucket" (inaccurate)
- No mention of "SlowAPI" (not used)
- Burst behavior documented (all 10 requests can arrive instantly)
- Production note added about Redis for multi-worker deployments
  </done>
</task>

<task type="auto">
  <name>Update IM_ADAPTER_SETUP.md rate limiting section</name>
  <files>backend/docs/IM_ADAPTER_SETUP.md</files>
  <action>
Update the rate limiting section to accurately describe the sliding window implementation:

**Find the rate limiting section** and update:

**Before (if it mentions token bucket):**
```
## Rate Limiting

Rate limiting uses the SlowAPI library with a token bucket algorithm...
```

**After (accurate description):**
```markdown
## Rate Limiting

IMGovernanceService implements rate limiting using a **sliding window algorithm**:

- **Limit**: 10 requests per minute per user (platform:sender_id key)
- **Window**: 60 second sliding window
- **Burst behavior**: All 10 requests can arrive instantly (not throttled)
- **Enforcement**: 11th request returns HTTP 429 with Retry-After header

### Algorithm Details

```
1. Extract sender_id from webhook payload
2. Check rate limit store for {platform}:{sender_id}
3. Remove timestamps older than 60 seconds
4. If >= 10 timestamps remain → return 429
5. Otherwise, add current timestamp and allow request
```

### Configuration

Environment variables for rate limiting (optional, defaults shown):

| Variable | Default | Description |
|----------|---------|-------------|
| `IM_RATE_LIMIT_REQUESTS` | 10 | Max requests per window |
| `IM_RATE_LIMIT_WINDOW_SECONDS` | 60 | Time window in seconds |

### Production Considerations

The current implementation uses in-memory storage. For multi-worker deployments:
- Consider Redis for distributed rate limiting
- Use a single rate limit worker if continuing in-memory approach
- Each worker maintains its own rate limit store (requests = workers * 10)
```

**Add to rate limiting troubleshooting section:**
```markdown
### Rate Limiting Issues

**Problem:** Requests not being rate limited in multi-worker deployment
**Cause:** Each worker maintains its own in-memory rate limit store
**Solution:** Use Redis-based rate limiting or single rate limit worker
```
  </action>
  <verify>
```bash
# Verify accurate algorithm description
grep -i "sliding window" backend/docs/IM_ADAPTER_SETUP.md

# Verify no inaccurate claims
! grep -i "token bucket" backend/docs/IM_ADAPTER_SETUP.md
! grep -i "SlowAPI" backend/docs/IM_ADAPTER_SETUP.md
```
  </verify>
  <done>
IM_ADAPTER_SETUP.md accurately documents rate limiting:
- Describes sliding window algorithm (not token bucket)
- Documents burst behavior correctly
- Includes configuration environment variables
- Notes production considerations for multi-worker deployments
- Troubleshooting section added for rate limiting issues
  </done>
</task>

<task type="auto">
  <name>Update IM_SECURITY_BEST_PRACTICES.md and original plan reference</name>
  <files>backend/docs/IM_SECURITY_BEST_PRACTICES.md, .planning/phases/01-im-adapters/01-im-adapters-01-PLAN.md</files>
  <action>
**1. Update IM_SECURITY_BEST_PRACTICES.md:**

Add or update the rate limiting section:

```markdown
## Rate Limiting Implementation

IMGovernanceService uses a **sliding window** rate limiting algorithm:

### Algorithm

For each unique key `{platform}:{sender_id}`:
1. Maintain list of request timestamps
2. Remove timestamps older than window (60s)
3. Reject if >= 10 requests in window
4. Otherwise, add current timestamp and allow

### Characteristics

- **Burst-tolerant**: All 10 requests can arrive simultaneously
- **Memory-efficient**: Old timestamps automatically cleaned up
- **Single-worker**: In-memory store doesn't share across workers
- **Latency**: <1ms per check (in-memory lookup)

### Production Notes

For multi-worker deployments (gunicorn -w 4):
- Each worker has its own rate limit store
- Effective limit = workers * 10 requests/minute
- Solution: Use Redis-backed rate limiting for distributed deployments
```

**2. Add note to 01-im-adapters-01-PLAN.md:**

Add a gap closure note at the end of the PLAN.md file:

```markdown
---

## Gap Closure Note (Plan 06)

Original plan specified SlowAPI with token bucket algorithm. Implementation used
custom sliding window which works correctly but created documentation mismatch.

Resolution (Plan 06): Update documentation to match implementation rather than
replacing working code. Sliding window is:
- Functional: Correctly enforces 10 req/min
- Simple: No external dependency
- Well-tested: Property tests verify invariants

See 01-im-adapters-06-PLAN.md for details.
```

**3. Add environment variable support** (optional enhancement):

In im_governance_service.py __init__, add:

```python
# Rate limiting configuration (with env var overrides)
self.rate_limit_requests = int(os.getenv("IM_RATE_LIMIT_REQUESTS", "10"))
self.rate_limit_window = int(os.getenv("IM_RATE_LIMIT_WINDOW_SECONDS", "60"))
```

This makes rate limiting configurable without code changes.
  </action>
  <verify>
```bash
# Verify docs updated
grep -i "sliding window" backend/docs/IM_SECURITY_BEST_PRACTICES.md

# Verify plan note added
grep -A 10 "Gap Closure Note" .planning/phases/01-im-adapters/01-im-adapters-01-PLAN.md

# Verify env var support (if added)
grep "IM_RATE_LIMIT" backend/core/im_governance_service.py
```
  </verify>
  <done>
Documentation and configuration updated:
- IM_SECURITY_BEST_PRACTICES.md describes sliding window accurately
- 01-im-adapters-01-PLAN.md has gap closure note explaining the mismatch
- Environment variables IM_RATE_LIMIT_REQUESTS and IM_RATE_LIMIT_WINDOW_SECONDS supported
- No inaccurate references to token bucket or SlowAPI remain
- Production notes for multi-worker deployments included
  </done>
</task>

</tasks>

<verification>
After completion, verify:
1. im_governance_service.py docstring describes sliding window accurately
2. No "token bucket" or "SlowAPI" references in code or docs
3. IM_ADAPTER_SETUP.md has accurate rate limiting section
4. IM_SECURITY_BEST_PRACTICES.md describes sliding window implementation
5. 01-im-adapters-01-PLAN.md has gap closure note
6. Environment variables for rate limiting documented
7. Property tests still pass (im_governance_invariants.py)
</verification>

<success_criteria>
- Gap 1 CLOSED: Documentation matches implementation (sliding window)
- All inaccurate claims removed (token bucket, SlowAPI)
- Rate limiting behavior correctly documented (burst behavior, window size)
- Production guidance added (multi-worker considerations)
- Environment variable configuration documented
- No functional changes to working rate limiting code
</success_criteria>

<output>
After completion, create `.planning/phases/01-im-adapters/01-im-adapters-06-SUMMARY.md` with:
- Documentation updates made
- Algorithm correctly described as sliding window
- Inaccurate claims removed
- Configuration options documented
- Gap 1 closure confirmation
