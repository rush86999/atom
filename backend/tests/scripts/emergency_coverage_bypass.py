#!/usr/bin/env python3
"""
Emergency Coverage Bypass Tracking Script

Purpose: Track and alert on emergency bypass usage to prevent abuse while allowing
critical PRs (security fixes, hotfixes) to bypass coverage gates with approval.

Usage:
    export EMERGENCY_COVERAGE_BYPASS=true
    export GITHUB_PR_URL="https://github.com/rushiparikh/atom/pull/1234"
    export BYPASS_REASON="Security fix: Critical authentication vulnerability"
    export GITHUB_APPROVERS="alice,bob"
    python emergency_coverage_bypass.py

Features:
- Logs bypass usage to JSON file with timestamp, reason, PR URL, approvers
- Checks bypass frequency (>3 bypasses in 30 days triggers warning)
- Sends alert notifications (Slack webhook placeholder)
- Provides audit trail for monthly review process

Output:
- Console: Bypass status and alert messages
- File: backend/tests/coverage_reports/metrics/bypass_log.json
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any


# Path configuration
BYPASS_LOG_PATH = Path(__file__).parent.parent / "coverage_reports" / "metrics" / "bypass_log.json"

# Bypass frequency threshold (triggers investigation if exceeded)
BYPASS_FREQUENCY_THRESHOLD = 3
BYPASS_FREQUENCY_WINDOW_DAYS = 30


def track_bypass_usage(
    reason: str,
    pr_url: str,
    approvers: List[str],
    phase: str,
    environment: str
) -> Dict[str, Any]:
    """
    Track emergency bypass usage for audit trail.

    Args:
        reason: Bypass reason (e.g., "Security fix: Critical auth vulnerability")
        pr_url: Pull request URL (e.g., "https://github.com/rushiparikh/atom/pull/1234")
        approvers: List of approver usernames (e.g., ["alice", "bob"])
        phase: Current coverage phase (e.g., "phase_1", "phase_2", "phase_3")
        environment: Environment (e.g., "production", "staging", "unknown")

    Returns:
        Dict containing bypass entry with timestamp, metadata
    """
    # Create bypass entry
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "reason": reason,
        "pr_url": pr_url,
        "approvers": approvers,
        "phase": phase,
        "environment": environment
    }

    # Load existing log
    if BYPASS_LOG_PATH.exists():
        try:
            with open(BYPASS_LOG_PATH, 'r') as f:
                log = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"⚠️  Warning: Failed to load bypass log: {e}")
            log = {"bypasses": []}
    else:
        log = {"bypasses": []}

    # Add entry
    log["bypasses"].append(entry)

    # Save log
    BYPASS_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(BYPASS_LOG_PATH, 'w') as f:
            json.dump(log, f, indent=2)
    except IOError as e:
        print(f"⚠️  Warning: Failed to save bypass log: {e}")

    return entry


def check_bypass_frequency() -> bool:
    """
    Check if bypass usage exceeds threshold (>3 per month).

    Returns:
        True if bypass frequency exceeds threshold (investigation needed)
        False if bypass usage within acceptable range
    """
    if not BYPASS_LOG_PATH.exists():
        return False

    try:
        with open(BYPASS_LOG_PATH, 'r') as f:
            log = json.load(f)
    except (json.JSONDecodeError, IOError):
        return False

    # Count bypasses in last 30 days
    cutoff_timestamp = datetime.now(timezone.utc).timestamp() - (BYPASS_FREQUENCY_WINDOW_DAYS * 24 * 60 * 60)

    recent_bypasses = []
    for bypass in log.get("bypasses", []):
        try:
            bypass_time = datetime.fromisoformat(bypass["timestamp"].replace('Z', '+00:00')).timestamp()
            if bypass_time > cutoff_timestamp:
                recent_bypasses.append(bypass)
        except (ValueError, KeyError):
            # Skip invalid entries
            continue

    if len(recent_bypasses) > BYPASS_FREQUENCY_THRESHOLD:
        print(f"⚠️  WARNING: More than {BYPASS_FREQUENCY_THRESHOLD} emergency bypasses in last {BYPASS_FREQUENCY_WINDOW_DAYS} days")
        print(f"   Recent bypasses: {len(recent_bypasses)}")
        print(f"   Consider: Investigating root causes, adjusting thresholds")
        print(f"   Recent bypass reasons:")
        for bypass in recent_bypasses[-5:]:  # Show last 5
            reason = bypass.get("reason", "No reason provided")[:60]
            date = bypass.get("timestamp", "")[:10]
            print(f"   - {date}: {reason}")
        return True

    return False


def send_bypass_alert(entry: Dict):
    """
    Send alert notification for bypass usage.

    Current implementation: Console output (placeholder for Slack webhook)

    Future: Integrate with Slack webhook for team notification

    Args:
        entry: Bypass entry dict with timestamp, reason, pr_url, approvers, phase
    """
    print("🚨 EMERGENCY COVERAGE BYPASS ACTIVATED")
    print(f"   Reason: {entry['reason']}")
    print(f"   PR: {entry['pr_url']}")
    print(f"   Approvers: {', '.join(entry['approvers'])}")
    print(f"   Phase: {entry['phase']}")
    print(f"   Environment: {entry['environment']}")
    print(f"   Timestamp: {entry['timestamp']}")
    print()

    # Future: Integrate with Slack webhook
    # webhook_url = os.getenv("SLACK_COVERAGE_WEBHOOK")
    # if webhook_url:
    #     try:
    #         import requests
    #         message = {
    #             "text": f"🚨 Coverage bypass: {entry['pr_url']}",
    #             "attachments": [{
    #                 "color": "warning",
    #                 "fields": [
    #                     {"title": "Reason", "value": entry['reason']},
    #                     {"title": "Approvers", "value": ', '.join(entry['approvers'])},
    #                     {"title": "Phase", "value": entry['phase']}
    #                 ]
    #             }]
    #         }
    #         requests.post(webhook_url, json=message)
    #     except Exception as e:
    #         print(f"⚠️  Warning: Failed to send Slack alert: {e}")


def print_bypass_summary():
    """Print summary of all bypasses in log."""
    if not BYPASS_LOG_PATH.exists():
        return

    try:
        with open(BYPASS_LOG_PATH, 'r') as f:
            log = json.load(f)
    except (json.JSONDecodeError, IOError):
        return

    total_bypasses = len(log.get("bypasses", []))
    if total_bypasses == 0:
        return

    print(f"📊 Bypass Summary: {total_bypasses} total bypasses logged")
    print()

    # Show recent bypasses (last 5)
    recent = log.get("bypasses", [])[-5:]
    for i, bypass in enumerate(reversed(recent), 1):
        reason = bypass.get("reason", "No reason")[:50]
        pr = bypass.get("pr_url", "Unknown PR")
        print(f"   {i}. {reason}")
        print(f"      {pr}")
    print()


def main():
    """Main bypass tracking logic."""
    bypass_active = os.getenv("EMERGENCY_COVERAGE_BYPASS", "false").lower() == "true"

    if not bypass_active:
        print("✅ Coverage gate active (no bypass)")
        print()
        print_bypass_summary()
        return 0

    print("⚠️  COVERAGE GATE BYPASSED (emergency mode)")
    print()

    # Get bypass metadata from environment
    pr_url = os.getenv("GITHUB_PR_URL", "unknown")
    reason = os.getenv("BYPASS_REASON", "not provided")
    approvers_str = os.getenv("GITHUB_APPROVERS", "")
    approvers = [a.strip() for a in approvers_str.split(",") if a.strip()] if approvers_str else ["unknown"]
    phase = os.getenv("COVERAGE_PHASE", "phase_1")
    environment = os.getenv("ENVIRONMENT", "unknown")

    # Track usage
    entry = track_bypass_usage(reason, pr_url, approvers, phase, environment)

    # Send alert
    send_bypass_alert(entry)

    # Check frequency
    check_bypass_frequency()

    print()
    print("📝 Bypass logged to:", BYPASS_LOG_PATH)
    print("⚠️  Remember to remove EMERGENCY_COVERAGE_BYPASS after PR merges")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
