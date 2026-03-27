"""
FuzzingOrchestrator Service for Campaign Management

This module provides centralized campaign lifecycle management for all
API fuzzing tests, including start, stop, monitor, and automated bug filing.

Features:
- Campaign lifecycle management (start, stop, monitor)
- Crash deduplication using error signature hashing
- Automated GitHub issue filing via BugFilingService
- Campaign statistics tracking (executions, crashes, coverage)
- Corpus management for re-seeding campaigns
"""

import os
import sys
import signal
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class FuzzingOrchestrator:
    """
    Service for managing fuzzing campaigns.

    Orchestrates the complete lifecycle of fuzzing campaigns including
    starting campaigns, monitoring statistics, stopping campaigns,
    deduplicating crashes, and filing bugs for unique crashes.

    Example:
        orchestrator = FuzzingOrchestrator(github_token="...", github_repository="owner/repo")
        result = orchestrator.start_campaign("/api/v1/agents", "tests/fuzzing/test_auth_api.py")
        # ... wait for campaign to complete
        stats = orchestrator.monitor_campaign(result["campaign_id"])
        orchestrator.stop_campaign(result["campaign_id"])
    """

    def __init__(self, github_token: str, github_repository: str):
        """
        Initialize FuzzingOrchestrator.

        Args:
            github_token: GitHub Personal Access Token for bug filing
            github_repository: Repository in format "owner/repo"
        """
        self.github_token = github_token
        self.github_repository = github_repository

        # Create base directories
        self.backend_dir = Path(__file__).parent.parent.parent.parent
        self.fuzzing_dir = self.backend_dir / "tests" / "fuzzing" / "campaigns"
        self.corpus_dir = self.fuzzing_dir / "corpus"
        self.crash_dir = self.fuzzing_dir / "crashes"

        # Create directories if they don't exist
        self.corpus_dir.mkdir(parents=True, exist_ok=True)
        self.crash_dir.mkdir(parents=True, exist_ok=True)

        # Track running campaigns: {campaign_id: subprocess.Popen}
        self.running_campaigns: Dict[str, subprocess.Popen] = {}

    def start_campaign(
        self,
        target_endpoint: str,
        test_file: str,
        duration_seconds: int = 3600,
        iterations: int = 10000
    ) -> Dict:
        """
        Start a fuzzing campaign for a target endpoint.

        Args:
            target_endpoint: API endpoint to fuzz (e.g., "/api/v1/agents")
            test_file: Path to test file relative to backend directory
            duration_seconds: Campaign duration in seconds (default: 3600)
            iterations: Number of fuzzing iterations (default: 10000)

        Returns:
            Dict with campaign_id, status, pid, target_endpoint, duration_seconds, iterations
        """
        # Generate campaign_id
        timestamp = datetime.utcnow().isoformat().replace(":", "-").replace(".", "-")
        safe_endpoint = target_endpoint.replace("/", "-").strip("-")
        campaign_id = f"{safe_endpoint}_{timestamp}"

        # Create campaign crash directory
        campaign_crash_dir = self.crash_dir / campaign_id
        campaign_crash_dir.mkdir(parents=True, exist_ok=True)

        # Set environment variables for campaign
        env = os.environ.copy()
        env["FUZZ_CAMPAIGN_ID"] = campaign_id
        env["FUZZ_CRASH_DIR"] = str(campaign_crash_dir)
        env["FUZZ_ITERATIONS"] = str(iterations)

        # Build pytest command
        test_file_path = self.backend_dir / test_file
        cmd = [
            sys.executable,
            "-m",
            "pytest",
            str(test_file_path),
            "-v",
            "-m",
            "fuzzing"
        ]

        # Start subprocess
        try:
            process = subprocess.Popen(
                cmd,
                cwd=self.backend_dir,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            # Track running campaign
            self.running_campaigns[campaign_id] = process

            return {
                "campaign_id": campaign_id,
                "status": "running",
                "pid": process.pid,
                "target_endpoint": target_endpoint,
                "duration_seconds": duration_seconds,
                "iterations": iterations,
                "crash_dir": str(campaign_crash_dir)
            }

        except Exception as e:
            return {
                "campaign_id": campaign_id,
                "status": "failed",
                "error": str(e)
            }

    def stop_campaign(self, campaign_id: str) -> Dict:
        """
        Stop a running fuzzing campaign.

        Args:
            campaign_id: Campaign ID to stop

        Returns:
            Dict with campaign_id and status
        """
        if campaign_id not in self.running_campaigns:
            return {
                "campaign_id": campaign_id,
                "status": "not_found",
                "error": f"Campaign {campaign_id} not found in running campaigns"
            }

        process = self.running_campaigns[campaign_id]

        try:
            # Send SIGTERM for graceful shutdown
            process.send_signal(signal.SIGTERM)

            # Wait up to 10 seconds for graceful shutdown
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                # Force kill if not shutdown gracefully
                process.send_signal(signal.SIGKILL)
                process.wait()

            # Remove from running campaigns
            del self.running_campaigns[campaign_id]

            return {
                "campaign_id": campaign_id,
                "status": "stopped"
            }

        except Exception as e:
            return {
                "campaign_id": campaign_id,
                "status": "error",
                "error": str(e)
            }

    def monitor_campaign(self, campaign_id: str) -> Dict:
        """
        Monitor campaign statistics.

        Args:
            campaign_id: Campaign ID to monitor

        Returns:
            Dict with campaign_id, status, executions, crashes, duration_seconds
        """
        # Get campaign crash directory
        campaign_crash_dir = self.crash_dir / campaign_id

        if not campaign_crash_dir.exists():
            return {
                "campaign_id": campaign_id,
                "status": "not_found",
                "error": f"Campaign crash directory not found: {campaign_crash_dir}"
            }

        # Count crashes (number of *.input files)
        crash_inputs = list(campaign_crash_dir.glob("*.input"))
        crash_count = len(crash_inputs)

        # Count executions (estimate from crash logs or default to iterations)
        executions = 0
        for crash_log in campaign_crash_dir.glob("*.log"):
            try:
                with open(crash_log, "r") as f:
                    content = f.read()
                    # Try to extract execution count from log
                    if "executions" in content.lower():
                        for line in content.split("\n"):
                            if "executions" in line.lower():
                                # Extract number from line like "Executions: 1234"
                                parts = line.split(":")
                                if len(parts) == 2:
                                    try:
                                        executions = max(executions, int(parts[1].strip()))
                                        break
                                    except ValueError:
                                        pass
            except Exception:
                pass

        # If no executions found in logs, estimate from crash count
        if executions == 0:
            executions = crash_count * 100  # Rough estimate

        # Check if campaign is still running
        is_running = campaign_id in self.running_campaigns
        if is_running:
            # Check if process is still alive
            process = self.running_campaigns[campaign_id]
            if process.poll() is not None:
                # Process has terminated
                status = "completed"
                del self.running_campaigns[campaign_id]
            else:
                status = "running"
        else:
            status = "completed"

        return {
            "campaign_id": campaign_id,
            "status": status,
            "executions": executions,
            "crashes": crash_count,
            "crash_dir": str(campaign_crash_dir)
        }

    def file_bugs_for_crashes(
        self,
        target_endpoint: str,
        crashes_by_signature: Dict[str, List[Path]]
    ) -> List[Dict]:
        """
        File bugs for unique crashes via BugFilingService.

        Args:
            target_endpoint: API endpoint that was fuzzed
            crashes_by_signature: Dict mapping signature_hash to list of crash files

        Returns:
            List of bug filing results
        """
        # Import BugFilingService from Phase 236
        from tests.bug_discovery.bug_filing_service import BugFilingService

        bug_service = BugFilingService(self.github_token, self.github_repository)
        filed_bugs = []

        for signature_hash, crash_files in crashes_by_signature.items():
            if not crash_files:
                continue

            # Get first crash file as representative
            crash_file = crash_files[0]
            crash_log_file = crash_file.with_suffix(".log")

            try:
                # Read crash input (binary)
                with open(crash_file, "rb") as f:
                    crash_input = f.read()

                # Read crash log
                crash_log = ""
                if crash_log_file.exists():
                    with open(crash_log_file, "r") as f:
                        crash_log = f.read()

                # Prepare metadata
                test_name = f"fuzzing_{target_endpoint.replace('/', '_')}"
                error_message = f"Crash in {target_endpoint}: {crash_log[:200] if crash_log else 'Unknown error'}"

                metadata = {
                    "test_type": "fuzzing",
                    "target_endpoint": target_endpoint,
                    "crash_input": crash_input.hex()[:1000],  # First 1000 chars of hex
                    "crash_log": crash_log[:500],  # First 500 chars
                    "signature_hash": signature_hash,
                    "related_crashes": len(crash_files),
                    "platform": "api"
                }

                # File bug
                bug_result = bug_service.file_bug(
                    test_name=test_name,
                    error_message=error_message,
                    metadata=metadata
                )

                filed_bugs.append(bug_result)

            except Exception as e:
                # Log warning but continue processing other crashes
                print(f"Warning: Failed to file bug for crash {crash_file}: {e}")
                filed_bugs.append({
                    "status": "error",
                    "crash_file": str(crash_file),
                    "error": str(e)
                })

        return filed_bugs

    def run_campaign_with_bug_filing(
        self,
        target_endpoint: str,
        test_file: str,
        duration_seconds: int = 3600
    ) -> Dict:
        """
        Run complete campaign lifecycle with automated bug filing.

        Args:
            target_endpoint: API endpoint to fuzz
            test_file: Path to test file
            duration_seconds: Campaign duration in seconds

        Returns:
            Dict with campaign_id, executions, crashes, bugs_filed
        """
        # Import CrashDeduplicator
        from tests.fuzzing.campaigns.crash_deduplicator import CrashDeduplicator

        # Start campaign
        start_result = self.start_campaign(target_endpoint, test_file, duration_seconds)
        campaign_id = start_result["campaign_id"]

        if start_result["status"] != "running":
            return {
                "campaign_id": campaign_id,
                "status": "failed",
                "error": start_result.get("error", "Unknown error")
            }

        # Wait for campaign duration
        try:
            time.sleep(duration_seconds)
        except KeyboardInterrupt:
            print(f"\nCampaign {campaign_id} interrupted by user")
            self.stop_campaign(campaign_id)
            return {
                "campaign_id": campaign_id,
                "status": "interrupted"
            }

        # Stop campaign
        stop_result = self.stop_campaign(campaign_id)
        if stop_result["status"] != "stopped":
            return {
                "campaign_id": campaign_id,
                "status": "error",
                "error": stop_result.get("error", "Unknown error")
            }

        # Monitor campaign statistics
        stats = self.monitor_campaign(campaign_id)

        # Deduplicate crashes
        campaign_crash_dir = self.crash_dir / campaign_id
        deduplicator = CrashDeduplicator()
        crashes_by_signature = deduplicator.deduplicate_crashes(campaign_crash_dir)

        # File bugs for unique crashes
        filed_bugs = self.file_bugs_for_crashes(target_endpoint, crashes_by_signature)

        return {
            "campaign_id": campaign_id,
            "executions": stats["executions"],
            "crashes": stats["crashes"],
            "unique_crashes": len(crashes_by_signature),
            "bugs_filed": len([b for b in filed_bugs if b.get("status") == "created"]),
            "bug_results": filed_bugs,
            "status": "completed"
        }


# Convenience functions for campaign management
def start_campaign(
    target_endpoint: str,
    test_file: str,
    duration_seconds: int = 3600,
    iterations: int = 10000,
    github_token: Optional[str] = None,
    github_repository: Optional[str] = None
) -> Dict:
    """
    Start a fuzzing campaign.

    Args:
        target_endpoint: API endpoint to fuzz
        test_file: Path to test file
        duration_seconds: Campaign duration in seconds
        iterations: Number of fuzzing iterations
        github_token: GitHub token for bug filing (optional)
        github_repository: GitHub repository (optional)

    Returns:
        Campaign start result
    """
    github_token = github_token or os.getenv("GITHUB_TOKEN")
    github_repository = github_repository or os.getenv("GITHUB_REPOSITORY")

    if not github_token or not github_repository:
        raise ValueError("GITHUB_TOKEN and GITHUB_REPOSITORY must be set")

    orchestrator = FuzzingOrchestrator(github_token, github_repository)
    return orchestrator.start_campaign(target_endpoint, test_file, duration_seconds, iterations)


def stop_campaign(campaign_id: str, github_token: Optional[str] = None, github_repository: Optional[str] = None) -> Dict:
    """
    Stop a running fuzzing campaign.

    Args:
        campaign_id: Campaign ID to stop
        github_token: GitHub token for bug filing (optional)
        github_repository: GitHub repository (optional)

    Returns:
        Campaign stop result
    """
    github_token = github_token or os.getenv("GITHUB_TOKEN")
    github_repository = github_repository or os.getenv("GITHUB_REPOSITORY")

    if not github_token or not github_repository:
        raise ValueError("GITHUB_TOKEN and GITHUB_REPOSITORY must be set")

    orchestrator = FuzzingOrchestrator(github_token, github_repository)
    return orchestrator.stop_campaign(campaign_id)


def monitor_campaign(campaign_id: str, github_token: Optional[str] = None, github_repository: Optional[str] = None) -> Dict:
    """
    Monitor a fuzzing campaign.

    Args:
        campaign_id: Campaign ID to monitor
        github_token: GitHub token for bug filing (optional)
        github_repository: GitHub repository (optional)

    Returns:
        Campaign statistics
    """
    github_token = github_token or os.getenv("GITHUB_TOKEN")
    github_repository = github_repository or os.getenv("GITHUB_REPOSITORY")

    if not github_token or not github_repository:
        raise ValueError("GITHUB_TOKEN and GITHUB_REPOSITORY must be set")

    orchestrator = FuzzingOrchestrator(github_token, github_repository)
    return orchestrator.monitor_campaign(campaign_id)


def file_bugs_for_crashes(
    target_endpoint: str,
    crashes_by_signature: Dict[str, List[Path]],
    github_token: Optional[str] = None,
    github_repository: Optional[str] = None
) -> List[Dict]:
    """
    File bugs for unique crashes.

    Args:
        target_endpoint: API endpoint that was fuzzed
        crashes_by_signature: Dict mapping signature_hash to list of crash files
        github_token: GitHub token for bug filing (optional)
        github_repository: GitHub repository (optional)

    Returns:
        List of bug filing results
    """
    github_token = github_token or os.getenv("GITHUB_TOKEN")
    github_repository = github_repository or os.getenv("GITHUB_REPOSITORY")

    if not github_token or not github_repository:
        raise ValueError("GITHUB_TOKEN and GITHUB_REPOSITORY must be set")

    orchestrator = FuzzingOrchestrator(github_token, github_repository)
    return orchestrator.file_bugs_for_crashes(target_endpoint, crashes_by_signature)
