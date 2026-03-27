# Crash Artifacts Directory

This directory contains crash artifacts discovered during fuzzing campaigns.

## Purpose

When Atheris discovers a crash (e.g., segmentation fault, unhandled exception), it saves the crashing input and crash log to this directory for analysis.

## Structure

```
crashes/
└── {campaign_id}/
    ├── crash-0001.input  # Crashing input (binary)
    ├── crash-0001.log    # Crash log (stack trace)
    ├── crash-0002.input  # Another crashing input
    ├── crash-0002.log    # Crash log
    └── ...              # More crashes
```

## Crash File Format

Each crash produces two files:

1. **{name}.input**: Binary input that triggered the crash
2. **{name}.log**: Crash log with stack trace and error message

## Analyzing Crashes

### Manual Analysis

```bash
# View crash input (hex dump)
xxd crashes/{campaign_id}/crash-0001.input

# View crash log
cat crashes/{campaign_id}/crash-0001.log
```

### Automated Deduplication

Use CrashDeduplicator to group similar crashes:

```python
from tests.fuzzing.campaigns import CrashDeduplicator
from pathlib import Path

deduplicator = CrashDeduplicator()
crash_dir = Path("backend/tests/fuzzing/campaigns/crashes/{campaign_id}")
crashes_by_signature = deduplicator.deduplicate_crashes(crash_dir)

# Get summary
summary = deduplicator.get_signature_summary(crashes_by_signature)
for item in summary:
    print(f"Signature: {item['signature_hash'][:8]}...")
    print(f"  Count: {item['count']}")
    print(f"  Example: {item['example_crash']}")
```

### Reproducing Crashes

Use crash input to reproduce the crash locally:

```python
# Read crashing input
with open("crashes/{campaign_id}/crash-0001.input", "rb") as f:
    crash_input = f.read()

# Reproduce crash
test_api_endpoint(crash_input)
```

## Bug Filing

Unique crashes (after deduplication) are automatically filed as GitHub issues via BugFilingService:

```python
from tests.fuzzing.campaigns import FuzzingOrchestrator, CrashDeduplicator

orchestrator = FuzzingOrchestrator(github_token="...", github_repository="owner/repo")
deduplicator = CrashDeduplicator()

# Deduplicate crashes
crash_dir = Path("backend/tests/fuzzing/campaigns/crashes/{campaign_id}")
crashes_by_signature = deduplicator.deduplicate_crashes(crash_dir)

# File bugs for unique crashes
bugs = orchestrator.file_bugs_for_crashes("/api/v1/agents", crashes_by_signature)
print(f"Filed {len(bugs)} bugs")
```

## Crash Cleanup

Crash artifacts are excluded from git (see .gitignore). Periodic cleanup is recommended:

```bash
# Remove crash artifacts older than 30 days
find backend/tests/fuzzing/campaigns/crashes -type d -mtime +30 -exec rm -rf {} +
```

## Crash Severity

Crashes are categorized by severity:

- **Critical**: Segmentation faults, memory corruption
- **High**: Unhandled exceptions, assertion failures
- **Medium**: Recoverable errors with data loss
- **Low**: Edge cases with graceful degradation
