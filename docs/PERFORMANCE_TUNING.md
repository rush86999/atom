# Performance Tuning Guide

This guide explains how to optimize the performance of Atom's advanced skill execution features, including package installation, skill loading, marketplace search, and workflow execution.

---

## Table of Contents

1. [Performance Targets](#performance-targets)
2. [Package Installation](#package-installation)
3. [Skill Loading](#skill-loading)
4. [Marketplace Performance](#marketplace-performance)
5. [Workflow Performance](#workflow-performance)
6. [Benchmarking](#benchmarking)
7. [Production Configuration](#production-configuration)
8. [Monitoring](#monitoring)
9. [Troubleshooting](#troubleshooting)
10. [Optimization Checklist](#optimization-checklist)

---

## Performance Targets

### Operation Targets

| Operation | Target | Typical | How to Measure |
|-----------|--------|---------|----------------|
| **Package Installation** | < 5 seconds | 3-5s | Small packages (requests, lodash) |
| **Skill Loading** | < 1 second | 0.5-1s | Dynamic import from file |
| **Hot-Reload** | < 1 second | 0.3-0.8s | File change to reload |
| **Marketplace Search** | < 100ms | 20-50ms | With pagination |
| **Workflow Validation** | < 50ms | 10-30ms | DAG validation |
| **Dependency Resolution** | < 500ms | 100-300ms | Conflict detection |

### Regression Thresholds

Performance regressions detected when operation exceeds 1.5x baseline:

```python
REGRESSION_THRESHOLD = 1.5  # 50% slower triggers alert
```

**Example**:
- Baseline: Package installation = 4 seconds
- Regression threshold: 4 * 1.5 = 6 seconds
- Alert triggered if: Installation takes > 6 seconds

### Performance Budgets

Allocate time budgets for workflow operations:

```python
PERFORMANCE_BUDGETS = {
    "package_install": 5.0,      # 5 seconds
    "skill_load": 1.0,           # 1 second
    "hot_reload": 1.0,           # 1 second
    "marketplace_search": 0.1,   # 100ms
    "workflow_validation": 0.05  # 50ms
}
```

---

## Package Installation

### Optimize Installation Time

#### Use Small Packages

Prefer minimal dependencies to reduce installation time:

```python
# GOOD: Small, focused package
packages = ["requests==2.28.0"]  # ~5MB

# AVOID: Large packages with many transitive dependencies
packages = ["tensorflow==2.12.0"]  # ~500MB (use only if needed)
```

**Package Size Impact**:
- Small (<10MB): 1-3 seconds installation
- Medium (10-50MB): 3-10 seconds installation
- Large (>50MB): 10-60 seconds installation

#### Enable Image Caching

Auto-installer caches images by default:

```python
from core.auto_installer_service import AutoInstallerService

installer = AutoInstallerService(db)

# Check cache hit
result = await installer.install_dependencies(
    skill_id="my-skill",
    packages=["pandas==2.0.0"],
    package_type="python",
    agent_id="my-agent"
)

if result.get("cached"):
    print("Used cached image - no rebuild needed")
    # Installation: <1 second (cached)
else:
    print("Building new image")
    # Installation: 3-5 seconds (new build)
```

**Cache Benefits**:
- First installation: 3-5 seconds
- Cached installation: <1 second
- 5-10x speedup for repeat installations

#### Batch Installations

Install multiple skills at once:

```python
# BAD: Sequential installations (slow)
for skill_id in ["skill1", "skill2", "skill3"]:
    await installer.install_dependencies(
        skill_id=skill_id,
        packages=["pandas==2.0.0"],
        package_type="python",
        agent_id="my-agent"
    )
# Total time: 3 * 5s = 15 seconds

# GOOD: Batch installation (fast)
result = await installer.batch_install(
    installations=[
        {"skill_id": "skill1", "packages": ["pandas==2.0.0"], "package_type": "python"},
        {"skill_id": "skill2", "packages": ["numpy>=1.24.0"], "package_type": "python"},
        {"skill_id": "skill3", "packages": ["requests==2.28.0"], "package_type": "python"}
    ],
    agent_id="my-agent"
)
# Total time: 5-7 seconds (parallel builds)
```

**Performance Gains**:
- Sequential: 3 skills * 5s = 15 seconds
- Batch: 5-7 seconds (2-3x faster)

### Troubleshooting Slow Installation

#### Problem: Installation takes > 5 seconds

**Diagnosis**:
```bash
# Check package size
pip show pandas

# Check download speed
time pip download pandas==2.0.0

# Check Docker build time
docker build -t test-build .
```

**Solutions**:

1. **Check package size**:
   ```bash
   # Large packages take longer
   pip show --files pandas | wc -l  # File count
   du -sh ~/.cache/pip  # Cache size
   ```

2. **Verify network speed**:
   ```bash
   # Slow network slows downloads
   speedtest-cli
   ping pypi.org
   ```

3. **Reduce number of dependencies**:
   ```python
   # Before: 10 packages (slow)
   packages = ["pandas", "numpy", "scipy", "matplotlib", "seaborn", ...]

   # After: 3 packages (fast)
   packages = ["pandas", "numpy", "requests"]
   ```

4. **Use local package mirror**:
   ```bash
   # Configure pip to use mirror
   pip config set global.index-url https://mirror.example.com/pypi/simple/
   ```

#### Problem: Docker build hangs

**Diagnosis**:
```bash
# Check Docker daemon
docker ps
docker info

# Check build logs
docker logs <container_id>
```

**Solutions**:

1. **Check Docker daemon**:
   ```bash
   # Restart Docker if hung
   sudo systemctl restart docker  # Linux
   # macOS: Restart Docker Desktop
   ```

2. **Increase Docker resources**:
   ```bash
   # Docker Desktop: Settings > Resources
   # Increase CPU and memory allocation
   ```

3. **Use --no-cache** for debugging:
   ```bash
   # Disable cache to debug slow layers
   docker build --no-cache -t test-build .
   ```

---

## Skill Loading

### Optimize Load Time

#### Preload Frequently Used Skills

Load skills on startup for faster access:

```python
from core.skill_dynamic_loader import get_global_loader

loader = get_global_loader()

# Preload common skills on startup
COMMON_SKILLS = [
    ("http_get", "/path/to/http_get.py"),
    ("json_parse", "/path/to/json_parse.py"),
    ("database_insert", "/path/to/database_insert.py")
]

for skill_name, skill_path in COMMON_SKILLS:
    loader.load_skill(skill_name, skill_path)
    print(f"Preloaded: {skill_name}")

# Now skills are ready for instant use
module = loader.get_skill("http_get")  # <1ms (cached)
```

**Performance Impact**:
- First load: 500-1000ms
- Preloaded access: <1ms (1000x faster)

#### Enable File Monitoring (Development)

Watchdog-based hot-reload for development:

```python
from core.skill_dynamic_loader import SkillDynamicLoader

# Development: Enable monitoring
loader = SkillDynamicLoader(
    skills_dir="/path/to/skills",
    enable_monitoring=True  # Watch for file changes
)

# File changes trigger automatic reload
# Detected change in http_get.py, reloading...
```

**Performance**:
- File detection: <100ms (watchdog)
- Reload time: 300-800ms
- No server restart required

#### Disable Monitoring (Production)

Disable monitoring for performance:

```python
# Production: Disable monitoring for performance
loader = SkillDynamicLoader(
    skills_dir="/path/to/skills",
    enable_monitoring=False  # Disabled in production
)

# Skills still loadable, just no auto-reload
module = loader.load_skill("http_get", "/path/to/http_get.py")
```

**Production Best Practices**:
- Disable file monitoring (reduces CPU usage)
- Use preloaded skills (faster access)
- Restart service to update skills (safer than hot-reload)

### Module Cache Management

The loader automatically clears `sys.modules` on reload:

```python
# GOOD: Uses proper cache clearing
loader.reload_skill("my_skill")  # Clears sys.modules first

# BAD: Manual reload without cache clearing
import importlib
importlib.reload(sys.modules["my_skill"])  # Stale code!
```

**Cache Clearing Flow**:
```python
def reload_skill(self, skill_name: str):
    """Hot-reload skill without service restart."""
    # Step 1: Clear module cache (prevents stale code)
    if skill_name in sys.modules:
        del sys.modules[skill_name]

    # Step 2: Reload from file path
    skill_path = self.loaded_skills[skill_name]['path']
    return self.load_skill(skill_path, skill_name)
```

**Why Clear Cache?**
- Python caches imported modules in `sys.modules`
- Reloading without clear causes old code to execute
- Stale imports cause bugs and inconsistencies

### Troubleshooting Slow Loading

#### Problem: Skill loading takes > 1 second

**Diagnosis**:
```bash
# Check file size
ls -lh /path/to/skill.py

# Check import dependencies
python -c "import importtime; import skill"

# Check disk I/O
iostat -x 1
```

**Solutions**:

1. **Check file size**:
   ```bash
   # Large files take longer to load
   wc -l /path/to/skill.py  # Line count
   ```

2. **Reduce import dependencies**:
   ```python
   # BAD: Many imports (slow)
   import pandas
   import numpy
   import scipy
   import matplotlib
   import seaborn

   # GOOD: Lazy imports (fast)
   def execute():
       import pandas  # Import only when needed
       return pandas.DataFrame()
   ```

3. **Use bytecode caching**:
   ```bash
   # Python automatically caches .pyc files
   # Ensure __pycache__ directory is writable
   ls -la __pycache__/
   ```

#### Problem: Hot-reload not working

**Diagnosis**:
```bash
# Check watchdog installation
pip show watchdog

# Check file permissions
ls -la /path/to/skills/

# Test file monitoring
python -m watchdog.observers
```

**Solutions**:

1. **Install watchdog**:
   ```bash
   pip install watchdog
   ```

2. **Check file permissions**:
   ```bash
   # Ensure read access to skill directory
   chmod +r /path/to/skills/*.py
   ```

3. **Verify monitoring enabled**:
   ```python
   # Check enable_monitoring flag
   loader = SkillDynamicLoader(
       skills_dir="/path/to/skills",
       enable_monitoring=True  # Must be True
   )
   ```

---

## Marketplace Performance

### Optimize Search

#### Use Specific Queries

```bash
# GOOD: Specific category (fast)
/marketplace/skills?category=data
# Time: ~20ms (indexed query)

# SLOWER: Full-text search
/marketplace/skills?query=data
# Time: ~50ms (text search)
```

**Query Performance**:
- Category filter: ~20ms (indexed)
- Type filter: ~20ms (indexed)
- Full-text search: ~50ms (text matching)
- Combined filters: ~40ms (index + text)

#### Pagination

```bash
# GOOD: Reasonable page size
/marketplace/skills?page=1&page_size=20
# Time: ~20ms (single query)

# AVOID: Too large page size
/marketplace/skills?page=1&page_size=1000
# Time: ~100ms (large result set)
```

**Page Size Guidelines**:
- Default: 20 items (recommended)
- Maximum: 100 items (API limit)
- Optimal: 20-50 items (balance performance vs. UX)

#### Caching

Application-level caching for popular queries:

```python
import asyncio
from datetime import datetime, timedelta

cache = {}

async def get_cached_skills(query: str):
    """Get skills from cache or database."""
    cache_key = f"skills:{query}"

    # Check cache
    if cache_key in cache:
        cached_data, timestamp = cache[cache_key]
        age = datetime.now() - timestamp

        if age < timedelta(minutes=5):
            print("Cache hit")
            return cached_data

    # Cache miss - fetch from database
    print("Cache miss")
    result = await fetch_skills_from_db(query)

    # Store in cache
    cache[cache_key] = (result, datetime.now())

    return result
```

**Cache Strategy**:
- TTL: 5 minutes
- Cache key: `skills:{query}:{category}:{page}`
- Invalidate: On skill import/update

### Troubleshooting Slow Queries

#### Problem: Marketplace search > 100ms

**Diagnosis**:
```bash
# Check query plan
EXPLAIN ANALYZE SELECT * FROM skill_executions WHERE ...

# Check database indexes
\di skill_executions

# Check database connection
psql -c "SELECT version();"
```

**Solutions**:

1. **Add database indexes**:
   ```sql
   -- Index on skill_id
   CREATE INDEX idx_skill_id ON skill_executions(skill_id);

   -- Index on category
   CREATE INDEX idx_category ON skill_executions((input_params->>'skill_metadata'->>'category'));

   -- Index on status
   CREATE INDEX idx_status ON skill_executions(status);
   ```

2. **Enable query result caching**:
   ```python
   # Cache query results for 5-15 minutes
   cache_ttl = 300  # 5 minutes
   ```

3. **Reduce page_size**:
   ```bash
   # Use smaller page sizes
   /marketplace/skills?page=1&page_size=10  # Instead of 100
   ```

4. **Use specific filters**:
   ```bash
   # Instead of full-text search
   /marketplace/skills?query=data

   # Use category filter
   /marketplace/skills?category=data
   ```

---

## Workflow Performance

### Optimize DAG Structure

#### Minimize Depth

```python
# GOOD: Shallow workflow (parallelizable)
steps = [
    SkillStep("a", "task", {}, []),
    SkillStep("b", "task", {}, []),
    SkillStep("c", "merge", {}, ["a", "b"])
]
# Execution time: 2 * task_time (parallel)

# BAD: Deep chain (sequential)
steps = [
    SkillStep(f"step{i}", "task", {}, [f"step{i-1}"] if i > 0 else [])
    for i in range(10)
]
# Execution time: 10 * task_time (sequential)
```

**Performance Impact**:
- Shallow: Parallel execution = faster
- Deep: Sequential execution = slower

#### Parallel Branches

```python
# GOOD: Independent steps execute in parallel
steps = [
    SkillStep("start", "data_fetch", {}, []),
    SkillStep("branch1", "process_a", {}, ["start"]),
    SkillStep("branch2", "process_b", {}, ["start"]),
    SkillStep("branch3", "process_c", {}, ["start"])
]
# Execution time: 2 * task_time

# BAD: Sequential dependencies
steps = [
    SkillStep("branch1", "process_a", {}, []),
    SkillStep("branch2", "process_b", {}, ["branch1"]),
    SkillStep("branch3", "process_c", {}, ["branch2"])
]
# Execution time: 3 * task_time
```

**Speedup**:
- Parallel: 1.5-2x faster (for independent steps)

### Reduce Skill Execution Time

#### Optimize Individual Skills

```python
# GOOD: Efficient algorithm
def process_data(data):
    return [x * 2 for x in data]  # O(n)

# BAD: Inefficient algorithm
def process_data(data):
    result = []
    for i, x in enumerate(data):
        result.append(data[i] * 2)  # O(n) but slower
    return result
```

**Optimization Tips**:
- Use built-in functions (map, filter, list comprehensions)
- Minimize I/O operations
- Cache external API calls
- Use appropriate data structures

#### Set Appropriate Timeouts

```python
steps = [
    SkillStep("quick", "fast_task", {}, [], timeout_seconds=10),
    SkillStep("slow", "heavy_task", {}, [], timeout_seconds=300)
]
```

**Timeout Guidelines**:
- Quick operations: 10-30 seconds
- Heavy computation: 300-600 seconds (5-10 minutes)
- External API calls: 30-60 seconds

### Workflow Caching

Cache workflow results for repeated executions:

```python
from functools import lru_cache
import hashlib

def get_workflow_hash(steps):
    """Generate hash for workflow caching."""
    steps_json = json.dumps([s.__dict__ for s in steps], sort_keys=True)
    return hashlib.sha256(steps_json.encode()).hexdigest()

@lru_cache(maxsize=100)
def execute_cached_workflow(workflow_hash, agent_id):
    """Execute workflow with caching."""
    return await execute_workflow(steps, agent_id)
```

**Cache Benefits**:
- Repeated workflows: Instant results
- Idempotent workflows: Safe to cache
- TTL: 1-60 minutes (configurable)

---

## Benchmarking

### Run Benchmarks

```bash
# Run all performance benchmarks
pytest backend/tests/test_performance_benchmarks.py --benchmark-only

# Run specific benchmark group
pytest backend/tests/test_performance_benchmarks.py --benchmark-only -k "package-install"

# Generate benchmark report
pytest backend/tests/test_performance_benchmarks.py --benchmark-only --benchmark-json=benchmark.json

# Compare against baseline
pytest backend/tests/test_performance_benchmarks.py --benchmark-only --benchmark-compare
```

### Benchmark Results

Example output:

```
--------------------------------------------------------------------------------------------------
Name (time in ms)                          Min       Max      Mean    StdDev    Median     Rounds
--------------------------------------------------------------------------------------------------
test_package_install_small               3200.5   4500.2   3800.1    450.3    3750.2         10
test_package_install_cached                 50.2     80.1     65.3     12.4      62.1         10
test_skill_load_first                     850.3   1200.5    950.2    150.4    920.3         10
test_skill_load_cached                      0.8      1.2      1.0      0.2       0.9         10
test_marketplace_search                   25.3     45.2     32.1      8.5      30.2         10
test_workflow_validation                  15.2     35.4     22.3      7.2      20.1         10
test_dependency_resolution               150.3    280.5    190.2     45.3    180.2         10
--------------------------------------------------------------------------------------------------
```

### Compare Against Baselines

```python
from core.performance_monitor import get_monitor

monitor = get_monitor()

# Check for regression
result = monitor.check_regression(
    operation="package_install",
    current_duration=6.0  # 6 seconds
)

if result["regression"]:
    print(f"REGRESSION: {result['percent_change']:.1f}% slower than baseline")
    print(f"Baseline: {result['baseline']:.2f}s")
    print(f"Current: {result['current']:.2f}s")
else:
    print("Performance OK")
```

**Regression Detection**:
- Threshold: 1.5x baseline (50% slower)
- Alert: Triggers when threshold exceeded
- Action: Investigate performance degradation

---

## Production Configuration

### Environment Variables

```bash
# .env.production

# Disable hot-reload in production
SKILL_HOT_RELOAD_ENABLED=false

# Increase timeout for heavy workflows
WORKFLOW_TIMEOUT_SECONDS=600

# Limit concurrent installations
MAX_CONCURRENT_INSTALLATIONS=3

# Enable image caching
DOCKER_IMAGE_CACHE_ENABLED=true

# Marketplace cache TTL (seconds)
MARKETPLACE_CACHE_TTL=300

# Workflow cache TTL (seconds)
WORKFLOW_CACHE_TTL=60
```

### Resource Limits

```python
# Set Docker resource limits for skill execution
installer.install_packages(
    skill_id="my-skill",
    requirements=["pandas==2.0.0"],
    memory_limit="512m",  # Limit memory
    cpu_limit=1.0         # Limit CPU (1 core)
)
```

**Resource Guidelines**:
- Small skills: 256m memory, 0.5 CPU
- Medium skills: 512m memory, 1.0 CPU
- Large skills: 1024m memory, 2.0 CPU

### Connection Pooling

```python
# Database connection pool
from sqlalchemy.pool import QueuePool

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=20,        # Max connections
    max_overflow=10,     # Extra connections
    pool_timeout=30,     # Wait time for connection
    pool_recycle=3600    # Recycle connections after 1 hour
)
```

---

## Monitoring

### Track Performance Metrics

```python
from core.performance_monitor import measure_performance

with measure_performance("my_operation") as timer:
    # Do work
    result = expensive_operation()

if timer.duration > PERFORMANCE_TARGETS["my_operation"]:
    logger.warning(f"Operation slow: {timer.duration:.2f}s")
```

### Review Performance Reports

```python
monitor = get_monitor()
summary = monitor.get_summary()

for op, stats in summary["operations"].items():
    print(f"{op}:")
    print(f"  Avg: {stats['avg']:.3f}s")
    print(f"  Min: {stats['min']:.3f}s")
    print(f"  Max: {stats['max']:.3f}s")
    print(f"  P50: {stats['p50']:.3f}s")
    print(f"  P95: {stats['p95']:.3f}s")
    print(f"  P99: {stats['p99']:.3f}s")
```

**Output**:
```
package_install:
  Avg: 4.250s
  Min: 3.200s
  Max: 5.100s
  P50: 4.100s
  P95: 5.000s
  P99: 5.080s

skill_load:
  Avg: 0.650s
  Min: 0.500s
  Max: 1.200s
  P50: 0.600s
  P95: 1.100s
  P99: 1.180s
```

### Alert on Performance Degradation

```python
def check_performance_alerts():
    """Check for performance regressions."""
    monitor = get_monitor()
    summary = monitor.get_summary()

    alerts = []

    for op, stats in summary["operations"].items():
        # Check if P99 exceeds 1.5x baseline
        baseline = PERFORMANCE_TARGETS.get(op, 1.0)
        p99 = stats['p99']

        if p99 > baseline * 1.5:
            alerts.append({
                "operation": op,
                "severity": "HIGH",
                "message": f"P99 ({p99:.2f}s) exceeds 1.5x baseline ({baseline:.2f}s)"
            })

    return alerts
```

---

## Troubleshooting

### Performance Degradation

**Problem**: Operations getting slower over time

**Diagnosis**:
```bash
# Check memory usage
docker stats

# Check database query performance
psql -c "SELECT * FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10;"

# Check disk I/O
iostat -x 1

# Check CPU usage
top
```

**Solutions**:

1. **Check for memory leaks**:
   ```bash
   # Restart service if memory usage increases
   systemctl restart atom-api
   ```

2. **Clear module cache**:
   ```python
   from core.skill_dynamic_loader import get_global_loader
   loader = get_global_loader()
   loader.clear_cache()
   ```

3. **Review Docker image storage**:
   ```bash
   # Cleanup old images
   docker system prune -a
   ```

4. **Check database query performance**:
   ```sql
   -- Add indexes if needed
   CREATE INDEX CONCURRENTLY idx_performance ON skill_executions(skill_id);

   -- Vacuum database
   VACUUM ANALYZE skill_executions;
   ```

### High Memory Usage

**Problem**: Memory usage increases with skill loading

**Diagnosis**:
```bash
# Check memory usage
docker stats

# Check Python memory
python -c "import psutil; print(psutil.virtual_memory())"

# Check for memory leaks
python -m memory_profiler script.py
```

**Solutions**:

1. **Unload unused skills**:
   ```python
   loader.unload_skill("unused_skill")
   ```

2. **Reduce module cache size**:
   ```python
   loader = SkillDynamicLoader(
       cache_size=100  # Limit cache to 100 skills
   )
   ```

3. **Use process isolation**:
   ```bash
   # Run skills in separate processes
   uvicorn main:app --workers 4
   ```

4. **Monitor with memory profiler**:
   ```bash
   pip install memory_profiler
   python -m memory_profiler script.py
   ```

### Slow Marketplace Queries

**Problem**: Marketplace search > 100ms

**Diagnosis**:
```bash
# Check query plan
EXPLAIN ANALYZE SELECT * FROM skill_executions WHERE skill_id LIKE '%data%';

# Check database indexes
psql -c "\di skill_executions"

# Check database connections
psql -c "SELECT count(*) FROM pg_stat_activity;"
```

**Solutions**:

1. **Add database indexes**:
   ```sql
   CREATE INDEX idx_skill_name ON skill_executions(skill_id);
   CREATE INDEX idx_category ON skill_executions((input_params->>'skill_metadata'->>'category'));
   ```

2. **Enable query result caching**:
   ```python
   # Cache results for 5-15 minutes
   cache_ttl = 300
   ```

3. **Reduce page_size**:
   ```bash
   /marketplace/skills?page=1&page_size=10  # Instead of 100
   ```

4. **Use specific filters**:
   ```bash
   /marketplace/skills?category=data  # Instead of ?query=data
   ```

---

## Optimization Checklist

### Pre-Deployment

- [ ] Run performance benchmarks
- [ ] Check for regressions against baseline
- [ ] Verify all targets met (<5s install, <1s load, <100ms search)
- [ ] Test with production data volume
- [ ] Validate caching strategy
- [ ] Review database query plans
- [ ] Check resource limits (CPU, memory)

### Production Monitoring

- [ ] Enable performance metrics collection
- [ ] Set up performance alerts (1.5x baseline)
- [ ] Monitor P95/P99 latencies
- [ ] Track error rates
- [ ] Review performance reports weekly
- [ ] Investigate regressions within 24 hours

### Optimization Opportunities

- [ ] Enable image caching for packages
- [ ] Preload frequently used skills
- [ ] Use batch installations
- [ ] Implement query result caching
- [ ] Add database indexes
- [ ] Optimize DAG structure (minimize depth)
- [ ] Use parallel execution for independent steps
- [ ] Set appropriate timeouts
- [ ] Implement workflow result caching

---

## Summary

Performance optimization requires:

- ✅ **Baseline Metrics**: Establish performance targets
- ✅ **Benchmarking**: Regular performance testing
- ✅ **Monitoring**: Track metrics over time
- ✅ **Alerting**: Detect regressions early
- ✅ **Optimization**: Continuous improvement

**Quick Wins**:
1. Enable image caching (5-10x faster repeat installations)
2. Preload common skills (1000x faster access)
3. Use batch installations (2-3x faster)
4. Add database indexes (2-5x faster queries)
5. Minimize workflow depth (1.5-2x faster execution)

**Next Steps**:
1. Run performance benchmarks
2. Establish baselines
3. Set up monitoring and alerting
4. Optimize based on findings
5. Review and iterate regularly

---

**See Also**:
- [Advanced Skill Execution](./ADVANCED_SKILL_EXECUTION.md) - Phase 60 overview
- [Skill Composition Patterns](./SKILL_COMPOSITION_PATTERNS.md) - Workflow optimization
- [Supply Chain Security](./SUPPLY_CHAIN_SECURITY.md) - Security testing (Plan 60-06)

**Last Updated**: February 19, 2026
