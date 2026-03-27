"""
Fuzzing Campaign Management Package

This package provides centralized campaign lifecycle management for all
API fuzzing tests, including campaign orchestration, crash deduplication,
and automated bug filing.

Components:
- FuzzingOrchestrator: Campaign lifecycle management (start, stop, monitor)
- CrashDeduplicator: Crash deduplication using error signature hashing

Campaign Lifecycle:
1. Start campaign with start_campaign(target_endpoint, test_file)
2. Monitor progress with monitor_campaign(campaign_id)
3. Stop campaign with stop_campaign(campaign_id)
4. Deduplicate crashes with CrashDeduplicator.deduplicate_crashes(crash_dir)
5. File bugs with file_bugs_for_crashes(target_endpoint, crashes_by_signature)

Example:
    from tests.fuzzing.campaigns import FuzzingOrchestrator, CrashDeduplicator

    orchestrator = FuzzingOrchestrator(github_token="...", github_repository="owner/repo")
    result = orchestrator.start_campaign("/api/v1/agents", "tests/fuzzing/test_auth_api.py")

    # Wait for campaign to complete
    import time
    time.sleep(3600)

    stats = orchestrator.monitor_campaign(result["campaign_id"])
    orchestrator.stop_campaign(result["campaign_id"])

    # Deduplicate and file bugs
    deduplicator = CrashDeduplicator()
    crashes_by_signature = deduplicator.deduplicate_crashes(stats["crash_dir"])
    bugs = orchestrator.file_bugs_for_crashes("/api/v1/agents", crashes_by_signature)
"""

from tests.fuzzing.campaigns.fuzzing_orchestrator import (
    FuzzingOrchestrator,
    start_campaign,
    stop_campaign,
    monitor_campaign,
    file_bugs_for_crashes
)

from tests.fuzzing.campaigns.crash_deduplicator import (
    CrashDeduplicator,
    deduplicate_crashes
)

__all__ = [
    # FuzzingOrchestrator
    "FuzzingOrchestrator",
    "start_campaign",
    "stop_campaign",
    "monitor_campaign",
    "file_bugs_for_crashes",

    # CrashDeduplicator
    "CrashDeduplicator",
    "deduplicate_crashes",
]
