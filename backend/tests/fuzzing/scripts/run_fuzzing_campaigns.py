#!/usr/bin/env python3
"""
Fuzzing Campaign Orchestration Script

This script orchestrates fuzzing campaigns for multiple API endpoints,
including campaign lifecycle management, crash deduplication, and automated
bug filing via FuzzingOrchestrator.

Usage:
    python run_fuzzing_campaigns.py --duration 3600
    python run_fuzzing_campaigns.py --duration 60 --campaign "POST /api/auth/login"

Environment Variables:
    GITHUB_TOKEN: GitHub Personal Access Token (automatic in CI/CD)
    GITHUB_REPOSITORY: Repository in format "owner/repo"
    FUZZ_CAMPAIGN_DURATION: Campaign duration in seconds (default: 3600)
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from tests.fuzzing.campaigns.fuzzing_orchestrator import FuzzingOrchestrator
from tests.fuzzing.campaigns.crash_deduplicator import CrashDeduplicator


def run_campaign(
    target_endpoint,
    test_file,
    duration_seconds=3600,
    github_token=None,
    github_repository=None
):
    """
    Run a single fuzzing campaign with lifecycle management.

    Args:
        target_endpoint: API endpoint to fuzz (e.g., "POST /api/auth/login")
        test_file: Path to test file (e.g., "tests/fuzzing/test_auth_api_fuzzing.py::test_login_endpoint_fuzzing")
        duration_seconds: Campaign duration in seconds (default: 3600)
        github_token: GitHub token for bug filing
        github_repository: GitHub repository in format "owner/repo"

    Returns:
        Dict with campaign_id, status, executions, crashes, bugs_filed
    """
    print(f"\n{'='*60}")
    print(f"Starting Campaign: {target_endpoint}")
    print(f"{'='*60}")
    print(f"Test file: {test_file}")
    print(f"Duration: {duration_seconds}s")
    print(f"Started at: {datetime.utcnow().isoformat()}Z")

    # Initialize orchestrator
    orchestrator = FuzzingOrchestrator(github_token, github_repository)

    # Start campaign
    start_result = orchestrator.start_campaign(target_endpoint, test_file, duration_seconds)
    campaign_id = start_result["campaign_id"]

    if start_result["status"] != "running":
        print(f"✗ Failed to start campaign: {start_result.get('error', 'Unknown error')}")
        return {
            "target_endpoint": target_endpoint,
            "status": "failed",
            "error": start_result.get("error", "Unknown error")
        }

    print(f"✓ Campaign started: {campaign_id}")
    print(f"PID: {start_result['pid']}")

    # Monitor campaign every 60 seconds
    elapsed = 0
    monitor_interval = 60  # seconds
    while elapsed < duration_seconds:
        time.sleep(min(monitor_interval, duration_seconds - elapsed))
        elapsed += min(monitor_interval, duration_seconds - elapsed)

        stats = orchestrator.monitor_campaign(campaign_id)
        print(f"  [{elapsed}s] Executions: {stats['executions']}, Crashes: {stats['crashes']}, Status: {stats['status']}")

        # Stop early if campaign failed
        if stats["status"] == "failed":
            print(f"✗ Campaign failed: {stats.get('error', 'Unknown error')}")
            orchestrator.stop_campaign(campaign_id)
            return {
                "target_endpoint": target_endpoint,
                "campaign_id": campaign_id,
                "status": "failed",
                "error": stats.get("error", "Unknown error")
            }

    # Stop campaign
    print(f"\nStopping campaign...")
    stop_result = orchestrator.stop_campaign(campaign_id)

    if stop_result["status"] != "stopped":
        print(f"✗ Failed to stop campaign: {stop_result.get('error', 'Unknown error')}")
        return {
            "target_endpoint": target_endpoint,
            "campaign_id": campaign_id,
            "status": "error",
            "error": stop_result.get("error", "Unknown error")
        }

    print(f"✓ Campaign stopped")

    # Get final statistics
    stats = orchestrator.monitor_campaign(campaign_id)
    print(f"\nCampaign Statistics:")
    print(f"  Executions: {stats['executions']}")
    print(f"  Crashes: {stats['crashes']}")

    # Deduplicate crashes
    campaign_crash_dir = Path(start_result["crash_dir"])
    if campaign_crash_dir.exists() and stats["crashes"] > 0:
        print(f"\nDeduplicating crashes...")
        deduplicator = CrashDeduplicator()
        crashes_by_signature = deduplicator.deduplicate_crashes(campaign_crash_dir)
        unique_crashes = len(crashes_by_signature)
        print(f"  Total crashes: {stats['crashes']}")
        print(f"  Unique crashes: {unique_crashes}")

        # File bugs for unique crashes
        if unique_crashes > 0:
            print(f"\nFiling bugs for {unique_crashes} unique crashes...")
            filed_bugs = orchestrator.file_bugs_for_crashes(target_endpoint, crashes_by_signature)
            bugs_filed = len([b for b in filed_bugs if b.get("status") == "created"])

            print(f"  Bugs filed: {bugs_filed}")

            # Print bug filing results
            for bug_result in filed_bugs:
                if bug_result.get("status") == "created":
                    print(f"    ✓ {bug_result.get('issue_url', 'N/A')}")
                elif bug_result.get("status") == "duplicate":
                    print(f"    ⊘ Duplicate: {bug_result.get('issue_url', 'N/A')}")
                elif bug_result.get("status") == "error":
                    print(f"    ✗ Error: {bug_result.get('error', 'Unknown error')}")

            return {
                "target_endpoint": target_endpoint,
                "campaign_id": campaign_id,
                "status": "completed",
                "executions": stats["executions"],
                "crashes": stats["crashes"],
                "unique_crashes": unique_crashes,
                "bugs_filed": bugs_filed,
                "bug_results": filed_bugs
            }
        else:
            return {
                "target_endpoint": target_endpoint,
                "campaign_id": campaign_id,
                "status": "completed",
                "executions": stats["executions"],
                "crashes": stats["crashes"],
                "unique_crashes": 0,
                "bugs_filed": 0
            }
    else:
        return {
            "target_endpoint": target_endpoint,
            "campaign_id": campaign_id,
            "status": "completed",
            "executions": stats["executions"],
            "crashes": 0,
            "unique_crashes": 0,
            "bugs_filed": 0
        }


def run_all_campaigns(duration_seconds=3600, github_token=None, github_repository=None):
    """
    Run all fuzzing campaigns.

    Args:
        duration_seconds: Campaign duration in seconds (default: 3600)
        github_token: GitHub token for bug filing
        github_repository: GitHub repository in format "owner/repo"

    Returns:
        Dict with overall summary (total_executions, total_crashes, bugs_filed, campaign_results)
    """
    # Define campaign configs
    campaign_configs = [
        {
            "target": "POST /api/auth/login",
            "test_file": "tests/fuzzing/test_auth_api_fuzzing.py::test_login_endpoint_fuzzing"
        },
        {
            "target": "POST /api/agents/{id}/run",
            "test_file": "tests/fuzzing/test_agent_api_fuzzing.py::test_agent_run_fuzzing"
        },
        {
            "target": "POST /api/canvas/present",
            "test_file": "tests/fuzzing/test_canvas_presentation_fuzzing.py::test_canvas_present_fuzzing"
        },
        {
            "target": "POST /api/workflows",
            "test_file": "tests/fuzzing/test_workflow_api_fuzzing.py::test_workflow_create_fuzzing"
        },
        {
            "target": "POST /api/skills/import",
            "test_file": "tests/fuzzing/test_skill_installation_fuzzing.py::test_skill_import_fuzzing"
        }
    ]

    print(f"\n{'='*60}")
    print(f"Running All Fuzzing Campaigns")
    print(f"{'='*60}")
    print(f"Total campaigns: {len(campaign_configs)}")
    print(f"Duration per campaign: {duration_seconds}s")
    print(f"Estimated total time: {len(campaign_configs) * duration_seconds}s (~{len(campaign_configs) * duration_seconds // 60} min)")
    print(f"Started at: {datetime.utcnow().isoformat()}Z")

    # Track overall results
    campaign_results = []
    total_executions = 0
    total_crashes = 0
    total_bugs_filed = 0

    # Run each campaign
    for i, config in enumerate(campaign_configs, 1):
        print(f"\n\nCampaign {i}/{len(campaign_configs)}")

        try:
            result = run_campaign(
                config["target"],
                config["test_file"],
                duration_seconds,
                github_token,
                github_repository
            )
            campaign_results.append(result)

            # Aggregate statistics
            if result["status"] == "completed":
                total_executions += result.get("executions", 0)
                total_crashes += result.get("crashes", 0)
                total_bugs_filed += result.get("bugs_filed", 0)
            else:
                print(f"✗ Campaign failed: {result.get('error', 'Unknown error')}")

        except Exception as e:
            print(f"✗ Campaign error: {e}")
            campaign_results.append({
                "target_endpoint": config["target"],
                "status": "error",
                "error": str(e)
            })

    # Print overall summary
    print(f"\n\n{'='*60}")
    print(f"Overall Summary")
    print(f"{'='*60}")
    print(f"Total campaigns: {len(campaign_configs)}")
    print(f"Successful campaigns: {len([r for r in campaign_results if r['status'] == 'completed'])}")
    print(f"Failed campaigns: {len([r for r in campaign_results if r['status'] != 'completed'])}")
    print(f"Total executions: {total_executions}")
    print(f"Total crashes: {total_crashes}")
    print(f"Bugs filed: {total_bugs_filed}")
    print(f"Completed at: {datetime.utcnow().isoformat()}Z")

    return {
        "total_campaigns": len(campaign_configs),
        "successful_campaigns": len([r for r in campaign_results if r["status"] == "completed"]),
        "failed_campaigns": len([r for r in campaign_results if r["status"] != "completed"]),
        "total_executions": total_executions,
        "total_crashes": total_crashes,
        "bugs_filed": total_bugs_filed,
        "campaign_results": campaign_results
    }


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Orchestrate fuzzing campaigns for API endpoints",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all campaigns for 1 hour (3600 seconds)
  python run_fuzzing_campaigns.py --duration 3600

  # Run single campaign for 60 seconds
  python run_fuzzing_campaigns.py --duration 60 --campaign "POST /api/auth/login"

  # Run with environment variable override
  FUZZ_CAMPAIGN_DURATION=7200 python run_fuzzing_campaigns.py
        """
    )

    parser.add_argument(
        "--duration",
        type=int,
        default=None,
        help="Campaign duration in seconds (default: FUZZ_CAMPAIGN_DURATION env var or 3600)"
    )

    parser.add_argument(
        "--campaign",
        type=str,
        default=None,
        help="Run specific campaign by target endpoint (e.g., 'POST /api/auth/login')"
    )

    args = parser.parse_args()

    # Get environment variables
    github_token = os.getenv("GITHUB_TOKEN")
    github_repository = os.getenv("GITHUB_REPOSITORY")

    if not github_token:
        print("Error: GITHUB_TOKEN environment variable not set")
        sys.exit(2)

    if not github_repository:
        print("Error: GITHUB_REPOSITORY environment variable not set")
        sys.exit(2)

    # Get duration from env var or args or default
    duration = args.duration or int(os.getenv("FUZZ_CAMPAIGN_DURATION", "3600"))

    print(f"Fuzzing Campaign Configuration:")
    print(f"  GitHub Repository: {github_repository}")
    print(f"  Duration: {duration}s")
    print(f"  Campaign: {args.campaign or 'All campaigns'}")

    # Run campaigns
    try:
        if args.campaign:
            # Run single campaign
            result = run_campaign(args.campaign, None, duration, github_token, github_repository)

            # Print JSON summary for CI parsing
            print(json.dumps(result, indent=2))

            # Exit code: 0 if success, 1 if crashes found, 2 if errors
            if result["status"] == "completed":
                if result.get("crashes", 0) > 0:
                    sys.exit(1)  # Crashes found
                else:
                    sys.exit(0)  # Success, no crashes
            else:
                sys.exit(2)  # Error

        else:
            # Run all campaigns
            summary = run_all_campaigns(duration, github_token, github_repository)

            # Print JSON summary for CI parsing
            print(json.dumps(summary, indent=2))

            # Exit code: 0 if success, 1 if crashes found, 2 if errors
            if summary.get("total_crashes", 0) > 0:
                sys.exit(1)  # Crashes found
            elif summary.get("failed_campaigns", 0) > 0:
                sys.exit(2)  # Errors
            else:
                sys.exit(0)  # Success

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(2)
    except Exception as e:
        print(f"\n\nError: {e}")
        sys.exit(2)


if __name__ == "__main__":
    main()
