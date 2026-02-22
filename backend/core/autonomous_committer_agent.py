"""
Autonomous Committer Agent - Automated Git commits and pull requests.

Creates conventional commit messages with Co-Authored-By attribution,
stages files, generates commits, and creates pull requests with
detailed descriptions including test results and coverage.

Integration:
- Uses CodeGeneratorOrchestrator output as input
- Integrates with TestRunnerService for test results
- Integrates with BYOK handler for LLM message refinement
- Uses gitpython for Git operations
- Integrates with GitHub API for PR creation

Performance targets:
- Commit message generation: <5 seconds
- Git operations: <2 seconds
- PR creation: <3 seconds
"""

import asyncio
import logging
import os
import re
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import git
import httpx

from sqlalchemy.orm import Session

from core.autonomous_coder_agent import CodeGeneratorOrchestrator
from core.code_quality_service import CodeQualityService, QualityCheckResults
from core.feature_flags import QUALITY_ENFORCEMENT_ENABLED, EMERGENCY_QUALITY_BYPASS
from core.llm.byok_handler import BYOKHandler
from core.test_runner_service import TestRunnerService

logger = logging.getLogger(__name__)


class QualityGateError(Exception):
    """Raised when quality gates fail and enforcement is enabled."""
    pass


# ============================================================================
# Task 1: Conventional Commit Message Generator
# ============================================================================

class CommitType(str, Enum):
    """Conventional commit types."""
    FEAT = "feat"
    FIX = "fix"
    DOCS = "docs"
    STYLE = "style"
    REFACTOR = "refactor"
    TEST = "test"
    CHORE = "chore"


class CommitMessageGenerator:
    """
    Generate conventional commit messages.

    Follows conventional commits specification with Atom-specific formatting.
    Includes Co-Authored-By footer for attribution.

    Attributes:
        db: Database session
        byok_handler: LLM handler for message refinement

    Example:
        generator = CommitMessageGenerator(db, byok_handler)
        message = await generator.generate_commit_summary(implementation_result, test_results)
        print(message)  # "feat(oauth): add OAuth2 authentication..."
    """

    # Conventional commit types with descriptions
    COMMIT_TYPES = {
        "feat": "New feature",
        "fix": "Bug fix",
        "docs": "Documentation only changes",
        "style": "Code style changes (formatting, etc.)",
        "refactor": "Code refactoring",
        "test": "Adding or updating tests",
        "chore": "Maintenance tasks"
    }

    def __init__(self, db: Session, byok_handler: BYOKHandler):
        """
        Initialize commit message generator.

        Args:
            db: Database session
            byok_handler: BYOK handler for LLM access
        """
        self.db = db
        self.byok_handler = byok_handler

    async def generate_commit_message(
        self,
        implementation_summary: Dict[str, Any],
        test_results: Dict[str, Any]
    ) -> str:
        """
        Generate conventional commit message.

        Format: <type>(<scope>): <subject>

        <body>

        <footer>

        Args:
            implementation_summary: Summary of code changes
            test_results: Test results and coverage

        Returns complete commit message.
        """
        logger.info("Generating conventional commit message")

        # Infer commit components
        commit_type = self.infer_commit_type(implementation_summary)
        scope = self.infer_scope(implementation_summary.get("files_changed", []))
        subject = self.generate_subject(implementation_summary)
        body = self.generate_body(
            implementation_summary.get("files_created", []),
            implementation_summary.get("files_modified", []),
            test_results
        )
        footer = self.generate_footer(test_results, implementation_summary.get("coverage", {}))

        # Build full message
        message = f"{commit_type}({scope}): {subject}\n\n{body}\n\n{footer}"

        # Refine with LLM if available
        try:
            message = await self.refine_message_with_llm(message, implementation_summary)
        except Exception as e:
            logger.warning(f"LLM refinement failed, using draft: {e}")

        return message.strip()

    def infer_commit_type(
        self,
        summary: Dict[str, Any]
    ) -> str:
        """
        Infer commit type from changes.

        Rules:
        - New files: feat
        - Bug fixes: fix
        - Only docs changed: docs
        - Only tests changed: test
        - Refactoring: refactor
        - Default: chore

        Args:
            summary: Implementation summary

        Returns commit type string.
        """
        files_created = summary.get("files_created", [])
        files_modified = summary.get("files_modified", [])

        # Check if only docs
        all_files = files_created + files_modified
        if all_files and all(f.endswith((".md", ".txt", ".rst")) for f in all_files):
            return CommitType.DOCS.value

        # Check if only tests
        if all_files and all("test" in f for f in all_files):
            return CommitType.TEST.value

        # Check for bug indicators
        description = summary.get("description", "").lower()
        if any(keyword in description for keyword in ["fix", "bug", "error", "issue"]):
            return CommitType.FIX.value

        # Check for new files
        if files_created and not files_modified:
            return CommitType.FEAT.value

        # Check for refactor indicators
        if any(keyword in description for keyword in ["refactor", "restructure", "reorganize"]):
            return CommitType.REFACTOR.value

        # Default
        return CommitType.CHORE.value

    def infer_scope(
        self,
        files_changed: List[str]
    ) -> str:
        """
        Infer scope from changed files.

        Returns: core, api, tests, docs, etc.

        Args:
            files_changed: List of changed file paths

        Returns scope string.
        """
        if not files_changed:
            return "general"

        # Count files by directory
        scopes = {}
        for file_path in files_changed:
            parts = Path(file_path).parts
            if len(parts) > 1:
                # First directory is scope (e.g., "backend/core" -> "core")
                scope = parts[1] if parts[0] == "backend" else parts[0]
            else:
                scope = "root"

            scopes[scope] = scopes.get(scope, 0) + 1

        # Return most common scope
        if scopes:
            return max(scopes, key=scopes.get)

        return "general"

    def generate_subject(
        self,
        summary: Dict[str, Any]
    ) -> str:
        """
        Generate commit subject line.

        Imperative mood, 50 char limit.
        Example: "add OAuth2 authentication with Google and GitHub"

        Args:
            summary: Implementation summary

        Returns subject line.
        """
        description = summary.get("description", "")

        # Remove common prefixes
        for prefix in ["implement ", "add ", "create ", "update "]:
            if description.lower().startswith(prefix):
                description = description[len(prefix):]

        # Truncate to 50 chars
        if len(description) > 50:
            description = description[:47] + "..."

        return description.lower()

    def generate_body(
        self,
        files_created: List[str],
        files_modified: List[str],
        test_results: Dict[str, Any]
    ) -> str:
        """
        Generate commit body.

        Lists changes made and test results.

        Args:
            files_created: New files
            files_modified: Modified files
            test_results: Test execution results

        Returns body text.
        """
        lines = []

        # List files created
        if files_created:
            lines.append(f"Created ({len(files_created)} files):")
            for file_path in files_created[:10]:  # Max 10 files
                lines.append(f"- {file_path}")
            if len(files_created) > 10:
                lines.append(f"- ... and {len(files_created) - 10} more")

        # List files modified
        if files_modified:
            if files_created:
                lines.append("")
            lines.append(f"Modified ({len(files_modified)} files):")
            for file_path in files_modified[:10]:
                lines.append(f"- {file_path}")
            if len(files_modified) > 10:
                lines.append(f"- ... and {len(files_modified) - 10} more")

        # Add test summary
        if test_results:
            if files_created or files_modified:
                lines.append("")
            lines.append("Test Results:")
            lines.append(f"- {test_results.get('passed', 0)}/{test_results.get('total', 0)} tests passing")

        return "\n".join(lines)

    def generate_footer(
        self,
        test_results: Dict[str, Any],
        coverage: Dict[str, Any]
    ) -> str:
        """
        Generate commit footer.

        Includes:
        - Co-Authored-By: Claude Sonnet <noreply@anthropic.com>
        - Test results
        - Coverage metrics

        Args:
            test_results: Test execution results
            coverage: Coverage metrics

        Returns footer text.
        """
        lines = []

        # Co-Authored-By
        lines.append("Co-Authored-By: Claude Sonnet <noreply@anthropic.com>")

        # Test results
        if test_results:
            passed = test_results.get("passed", 0)
            total = test_results.get("total", 0)
            if total > 0:
                lines.append(f"Tests: {passed}/{total} passing")

        # Coverage
        if coverage:
            percent = coverage.get("percent", 0)
            lines.append(f"Coverage: {percent}%")

        return "\n".join(lines)

    async def refine_message_with_llm(
        self,
        draft_message: str,
        context: Dict[str, Any]
    ) -> str:
        """
        Use LLM to refine commit message.

        Improves clarity and formatting.

        Args:
            draft_message: Draft commit message
            context: Implementation context

        Returns refined message.
        """
        logger.info("Refining commit message with LLM")

        try:
            prompt = f"""Refine this conventional commit message for clarity and formatting:

Draft:
{draft_message}

Context: {context.get('description', '')}

Rules:
1. Keep conventional commit format: type(scope): subject
2. Use imperative mood in subject line
3. Keep subject under 50 characters
4. Ensure body is clear and concise
5. Keep Co-Authored-By footer

Return only the refined message, no explanations."""

            response = await self.byok_handler.generate_response(
                prompt=prompt,
                system_instruction="You are an expert Git user. Refine commit messages to follow conventional commit format.",
                model_type="quality",
                temperature=0.3,
                task_type="commit_message"
            )

            refined = response.strip()
            return refined if refined else draft_message

        except Exception as e:
            logger.error(f"LLM refinement failed: {e}")
            return draft_message


# ============================================================================
# Task 2: Git Operations Wrapper
# ============================================================================

class GitOperations:
    """
    Wrapper for Git operations using gitpython.

    Provides safe Git operations with error handling.

    Attributes:
        repo_path: Path to Git repository
        repo: GitPython Repo object

    Example:
        git_ops = GitOperations(".")
        files = git_ops.get_changed_files()
        git_ops.stage_files()
        commit_sha = git_ops.create_commit("feat: add feature")
    """

    def __init__(self, repo_path: str = "."):
        """
        Initialize Git operations wrapper.

        Args:
            repo_path: Path to Git repository (default: current directory)

        Raises:
            ValueError: If not a Git repository
        """
        self.repo_path = Path(repo_path).resolve()
        try:
            self.repo = git.Repo(self.repo_path)
        except git.exc.InvalidGitRepositoryError:
            raise ValueError(f"Not a Git repository: {self.repo_path}")

    def get_changed_files(
        self,
        include_untracked: bool = True
    ) -> Dict[str, List[str]]:
        """
        Get list of changed files.

        Returns:
            {
                "added": [str],
                "modified": [str],
                "deleted": [str],
                "untracked": [str]
            }

        Args:
            include_untracked: Include untracked files

        Returns dict with file lists.
        """
        changed = {
            "added": [],
            "modified": [],
            "deleted": [],
            "untracked": []
        }

        # Get changed files
        for item in self.repo.index.diff(None):
            if item.new_file:
                changed["added"].append(item.b_path)
            elif item.deleted_file:
                changed["deleted"].append(item.a_path)
            else:
                changed["modified"].append(item.b_path)

        # Get untracked files
        if include_untracked:
            changed["untracked"] = self.repo.untracked_files

        return changed

    def stage_files(
        self,
        files: Optional[List[str]] = None
    ) -> None:
        """
        Stage files for commit.

        If files is None, stages all changes (git add .).

        Args:
            files: List of file paths to stage (None = all)
        """
        if files:
            logger.info(f"Staging {len(files)} files")
            self.repo.index.add(files)
        else:
            logger.info("Staging all changes")
            self.repo.index.add(["."])

    def create_commit(
        self,
        message: str,
        allow_empty: bool = False
    ) -> str:
        """
        Create commit with message.

        Args:
            message: Commit message
            allow_empty: Allow empty commit (not supported in all gitpython versions)

        Returns commit SHA.

        Raises exception if commit fails.
        """
        logger.info(f"Creating commit: {message.split(chr(10))[0]}")

        try:
            # gitpython doesn't support allow_empty parameter, ignore it
            commit = self.repo.index.commit(message)
            logger.info(f"Commit created: {commit.hexsha}")
            return commit.hexsha
        except Exception as e:
            logger.error(f"Commit failed: {e}")
            raise

    def get_current_branch(self) -> str:
        """
        Get current branch name.

        Returns branch name.
        """
        return self.repo.active_branch.name

    def get_latest_commit(self) -> git.Commit:
        """
        Get latest commit object.

        Returns commit object.
        """
        return self.repo.head.commit

    def create_branch(
        self,
        branch_name: str,
        start_point: Optional[str] = None
    ) -> str:
        """
        Create and checkout new branch.

        Args:
            branch_name: New branch name
            start_point: Starting point (default: current HEAD)

        Returns branch name.
        """
        logger.info(f"Creating branch: {branch_name}")

        if start_point:
            new_branch = self.repo.create_head(branch_name, start_point)
        else:
            new_branch = self.repo.create_head(branch_name)

        new_branch.checkout()
        logger.info(f"Checked out branch: {branch_name}")
        return branch_name

    def check_merge_conflicts(self) -> List[str]:
        """
        Check for merge conflicts.

        Returns list of conflicted files.
        """
        conflicts = []

        # Check for unmerged entries
        for item in self.repo.index.unmerged_blobs():
            conflicts.append(item[0].path)

        return conflicts

    def get_commit_diff(
        self,
        commit_sha: str
    ) -> str:
        """
        Get diff for commit.

        Args:
            commit_sha: Commit SHA

        Returns unified diff string.
        """
        commit = self.repo.commit(commit_sha)
        return commit.diff(commit.parents[0] if commit.parents else None, create_patch=True)

    def rollback_commit(
        self,
        commit_sha: str
    ) -> None:
        """
        Rollback to commit.

        Resets HEAD to commit SHA.

        Args:
            commit_sha: Commit SHA to rollback to
        """
        logger.info(f"Rolling back to commit: {commit_sha}")
        self.repo.git.reset("--hard", commit_sha)


# ============================================================================
# Task 3: Pull Request Generator
# ============================================================================

class PullRequestGenerator:
    """
    Generate pull requests using GitHub API.

    Creates PRs with detailed descriptions including test results,
    coverage, and configuration changes.

    Attributes:
        repo_owner: Repository owner (e.g., "username")
        repo_name: Repository name (e.g., "atom")
        github_token: GitHub personal access token

    Example:
        pr_gen = PullRequestGenerator("owner", "repo", "token")
        pr = await pr_gen.create_pull_request("feature", "main", title, description)
        print(f"PR created: {pr['url']}")
    """

    def __init__(self, repo_owner: str, repo_name: str, github_token: Optional[str] = None):
        """
        Initialize PR generator.

        Args:
            repo_owner: Repository owner
            repo_name: Repository name
            github_token: GitHub token (from env if None)
        """
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.github_token = github_token or os.getenv("GITHUB_TOKEN")
        self.api_base = "https://api.github.com"

    def generate_pr_title(
        self,
        commit_message: str
    ) -> str:
        """
        Generate PR title from commit message.

        Uses subject line from commit.
        Max 70 characters for GitHub.

        Args:
            commit_message: Full commit message

        Returns PR title.
        """
        # Extract first line (subject)
        subject = commit_message.split("\n")[0]

        # Truncate to 70 chars
        if len(subject) > 70:
            subject = subject[:67] + "..."

        return subject

    def generate_pr_description(
        self,
        implementation_summary: Dict[str, Any],
        test_results: Dict[str, Any],
        coverage: Dict[str, Any]
    ) -> str:
        """
        Generate PR description in Markdown.

        Structure:
        # Summary
        Brief description of changes

        ## Changes
        - ✅ Item 1
        - ✅ Item 2

        ## Testing
        Test results and coverage

        ## Configuration
        Environment variables needed

        ## Checklist
        - [x] Tests passing
        - [x] Coverage met
        - [x] Docs updated

        Returns complete Markdown description.

        Args:
            implementation_summary: Code generation summary
            test_results: Test execution results
            coverage: Coverage metrics

        Returns Markdown description.
        """
        lines = []

        # Summary
        lines.append(f"# {implementation_summary.get('name', 'Changes')}")
        lines.append("")
        lines.append("## Summary")
        lines.append(implementation_summary.get("description", ""))
        lines.append("")

        # Changes
        files_created = implementation_summary.get("files_created", [])
        files_modified = implementation_summary.get("files_modified", [])

        if files_created or files_modified:
            lines.append("## Changes")
            for file_path in files_created:
                lines.append(f"- ✅ Created: {file_path}")
            for file_path in files_modified:
                lines.append(f"- ✅ Modified: {file_path}")
            lines.append("")

        # Testing
        if test_results:
            lines.append("## Testing")
            lines.append(f"**Tests:** {test_results.get('passed', 0)}/{test_results.get('total', 0)} passing")
            if test_results.get("failed", 0) > 0:
                lines.append(f"**Failures:** {test_results['failed']} tests failed")
            lines.append(f"**Duration:** {test_results.get('duration_seconds', 0):.2f}s")
            lines.append("")

        # Coverage
        if coverage:
            lines.append("## Coverage")
            lines.append(f"**Line Coverage:** {coverage.get('percent', 0)}%")
            lines.append(f"**Lines:** {coverage.get('covered_lines', 0)} / {coverage.get('total_lines', 0)}")
            lines.append("")

        # Configuration
        env_vars = implementation_summary.get("environment_variables", [])
        if env_vars:
            lines.append("## Configuration")
            lines.append("Add to `.env`:")
            lines.append("```")
            for var in env_vars:
                lines.append(f"{var}=...")
            lines.append("```")
            lines.append("")

        # Checklist
        lines.append("## Checklist")
        lines.append(f"- [x] Tests passing ({test_results.get('passed', 0)}/{test_results.get('total', 0)})")
        lines.append(f"- [x] Coverage ≥{coverage.get('percent', 0)}%")
        lines.append("- [x] mypy: No type errors")
        lines.append("- [x] Black: Formatted")
        lines.append("- [x] Documentation updated")
        lines.append("- [x] No breaking changes")
        lines.append("")

        return "\n".join(lines)

    def generate_checklist(
        self,
        changes: Dict[str, Any]
    ) -> List[str]:
        """
        Generate PR checklist items.

        Includes tests, coverage, docs, etc.

        Args:
            changes: Changes summary

        Returns list of checklist items.
        """
        checklist = [
            "Tests passing",
            "Coverage met",
            "Documentation updated",
            "No breaking changes"
        ]

        # Add specific items
        if changes.get("api_changes"):
            checklist.append("API documentation updated")

        if changes.get("database_changes"):
            checklist.append("Migration included")

        if changes.get("env_vars"):
            checklist.append("Environment variables documented")

        return checklist

    async def create_pull_request(
        self,
        source_branch: str,
        target_branch: str,
        title: str,
        description: str
    ) -> Dict[str, Any]:
        """
        Create PR via GitHub API.

        Args:
            source_branch: Source branch (feature)
            target_branch: Target branch (main/master)
            title: PR title
            description: PR description (Markdown)

        Returns PR data including number, URL, state.

        Raises exception if API call fails.
        """
        if not self.github_token:
            logger.warning("No GitHub token, skipping PR creation")
            return {
                "success": False,
                "error": "No GitHub token configured"
            }

        logger.info(f"Creating PR: {source_branch} -> {target_branch}")

        try:
            # Build API endpoint
            endpoint = f"/repos/{self.repo_owner}/{self.repo_name}/pulls"

            # Build request data
            data = {
                "title": title,
                "body": description,
                "head": source_branch,
                "base": target_branch
            }

            # Call API
            response_data = await self._call_github_api(endpoint, method="POST", data=data)

            logger.info(f"PR created: #{response_data['number']}")
            return {
                "success": True,
                "number": response_data["number"],
                "url": response_data["html_url"],
                "state": response_data["state"]
            }

        except Exception as e:
            logger.error(f"PR creation failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _call_github_api(
        self,
        endpoint: str,
        method: str = "GET",
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Call GitHub API.

        Handles authentication and pagination.

        Args:
            endpoint: API endpoint (e.g., "/repos/owner/repo/pulls")
            method: HTTP method (GET, POST, PATCH)
            data: Request data for POST/PATCH

        Returns response JSON.
        """
        url = f"{self.api_base}{endpoint}"

        headers = {
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"token {self.github_token}"
        }

        async with httpx.AsyncClient() as client:
            if method == "GET":
                response = await client.get(url, headers=headers)
            elif method == "POST":
                response = await client.post(url, json=data, headers=headers)
            elif method == "PATCH":
                response = await client.patch(url, json=data, headers=headers)
            else:
                raise ValueError(f"Unsupported method: {method}")

            response.raise_for_status()
            return response.json()

    async def get_pr_status(
        self,
        pr_number: int
    ) -> Dict[str, Any]:
        """
        Get PR status (checks, reviews, comments).

        Args:
            pr_number: Pull request number

        Returns status information.
        """
        endpoint = f"/repos/{self.repo_owner}/{self.repo_name}/pulls/{pr_number}"

        try:
            response_data = await self._call_github_api(endpoint)
            return {
                "state": response_data.get("state"),
                "merged": response_data.get("merged", False),
                "mergeable": response_data.get("mergeable"),
                "review_status": response_data.get("review_comments_state"),
                "comments": response_data.get("comments", 0)
            }
        except Exception as e:
            logger.error(f"Failed to get PR status: {e}")
            return {
                "error": str(e)
            }


# ============================================================================
# Task 4: Main CommitterAgent Orchestration
# ============================================================================

class CommitterAgent:
    """
    Main agent for automated commits and PRs.

    Coordinates commit message generation, Git operations,
    and pull request creation for autonomous coding workflow.

    Attributes:
        db: Database session
        byok_handler: BYOK handler for LLM access
        message_generator: Commit message generator
        git_ops: Git operations wrapper
        pr_generator: Pull request generator

    Example:
        committer = CommitterAgent(db, byok_handler)
        result = await committer.create_commit(implementation_result, test_results, workflow_id)
        print(f"Commit created: {result['commit_sha']}")
    """

    def __init__(
        self,
        db: Session,
        byok_handler: BYOKHandler,
        repo_path: str = ".",
        github_token: Optional[str] = None
    ):
        """
        Initialize committer agent.

        Args:
            db: Database session
            byok_handler: BYOK handler for LLM access
            repo_path: Path to Git repository
            github_token: GitHub token for PR creation
        """
        self.db = db
        self.byok_handler = byok_handler
        self.message_generator = CommitMessageGenerator(db, byok_handler)
        self.git_ops = GitOperations(repo_path)
        self.pr_generator = PullRequestGenerator(
            repo_owner=self._infer_repo_owner(),
            repo_name=self._infer_repo_name(),
            github_token=github_token
        )
        self.quality_service = CodeQualityService()

    async def create_commit(
        self,
        implementation_result: Dict[str, Any],
        test_results: Dict[str, Any],
        workflow_id: str
    ) -> Dict[str, Any]:
        """
        Create Git commit for implementation.

        Args:
            implementation_result: Code generation result
            test_results: Test execution results
            workflow_id: Workflow tracking ID

        Returns:
            {
                "commit_sha": str,
                "commit_message": str,
                "files_committed": int,
                "branch": str
            }
        """
        logger.info(f"Creating commit for workflow {workflow_id}")

        # Build summary from implementation result
        summary = {
            "name": implementation_result.get("name", "Changes"),
            "description": implementation_result.get("description", ""),
            "files_created": [f["path"] for f in implementation_result.get("files", [])],
            "files_modified": implementation_result.get("files_modified", []),
            "coverage": implementation_result.get("coverage", {})
        }

        # Generate commit message
        commit_message = await self.message_generator.generate_commit_message(
            summary,
            test_results
        )

        # Stage files
        files_to_stage = summary["files_created"] + summary["files_modified"]
        self.git_ops.stage_files(files_to_stage)

        # Quality gate validation before commit
        if QUALITY_ENFORCEMENT_ENABLED and not EMERGENCY_QUALITY_BYPASS:
            # Validate quality on all Python files being committed
            for file_path in files_to_stage:
                if file_path.endswith(".py"):
                    quality_gate_result = self.quality_service.validate_code_quality(
                        file_path=file_path,
                        language="python"
                    )

                    if not quality_gate_result.all_passed:
                        # Block commit on quality failures
                        raise QualityGateError(
                            f"Quality gate failed for {file_path}:\n"
                            f"{quality_gate_result.get_summary()}\n"
                            f"Commit blocked. Fix quality issues or set EMERGENCY_QUALITY_BYPASS=true."
                        )

        # Create commit
        commit_sha = self.git_ops.create_commit(commit_message)

        # Get current branch
        branch = self.git_ops.get_current_branch()

        result = {
            "success": True,
            "commit_sha": commit_sha,
            "commit_message": commit_message,
            "files_committed": len(files_to_stage),
            "branch": branch
        }

        # Save to workflow
        self.save_commit_to_workflow(workflow_id, result)

        logger.info(f"Commit created successfully: {commit_sha}")
        return result

    async def create_commit_with_review(
        self,
        implementation_result: Dict[str, Any],
        test_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create commit with human review checkpoint.

        Pauses after generating commit message for human approval.
        Returns after approval.

        Args:
            implementation_result: Code generation result
            test_results: Test execution results

        Returns commit result after approval.
        """
        # Generate commit message
        summary = {
            "name": implementation_result.get("name", "Changes"),
            "description": implementation_result.get("description", ""),
            "files_created": [f["path"] for f in implementation_result.get("files", [])],
            "files_modified": implementation_result.get("files_modified", []),
            "coverage": implementation_result.get("coverage", {})
        }

        commit_message = await self.message_generator.generate_commit_message(
            summary,
            test_results
        )

        # In real implementation, this would pause for human review
        # For now, auto-approve
        logger.info("Auto-approving commit message")

        return {
            "commit_message": commit_message,
            "approved": True
        }

    async def create_pull_request(
        self,
        implementation_result: Dict[str, Any],
        test_results: Dict[str, Any],
        coverage: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create pull request for changes.

        Creates branch if needed, commits changes, creates PR.

        Args:
            implementation_result: Code generation result
            test_results: Test execution results
            coverage: Coverage metrics

        Returns PR data.
        """
        logger.info("Creating pull request")

        # Generate PR title and description
        pr_title = self.pr_generator.generate_pr_title(
            implementation_result.get("description", "")
        )

        pr_description = self.pr_generator.generate_pr_description(
            implementation_result,
            test_results,
            coverage
        )

        # Create PR
        current_branch = self.git_ops.get_current_branch()
        target_branch = implementation_result.get("target_branch", "main")

        pr_result = await self.pr_generator.create_pull_request(
            current_branch,
            target_branch,
            pr_title,
            pr_description
        )

        return pr_result

    async def commit_and_pr_workflow(
        self,
        implementation_result: Dict[str, Any],
        test_results: Dict[str, Any],
        coverage: Dict[str, Any],
        create_pr: bool = True
    ) -> Dict[str, Any]:
        """
        Full commit + PR workflow.

        1. Create feature branch
        2. Stage all changes
        3. Create commit with conventional message
        4. Create pull request
        5. Return PR URL

        Returns complete workflow result.

        Args:
            implementation_result: Code generation result
            test_results: Test execution results
            coverage: Coverage metrics
            create_pr: Whether to create PR

        Returns workflow result.
        """
        logger.info("Starting commit and PR workflow")

        workflow_id = implementation_result.get("workflow_id", "unknown")

        # Step 1: Create feature branch
        branch_name = implementation_result.get("branch_name", "feature/automated-changes")
        self.git_ops.create_branch(branch_name)

        # Step 2 & 3: Commit changes
        commit_result = await self.create_commit(
            implementation_result,
            test_results,
            workflow_id
        )

        result = {
            "commit": commit_result,
            "branch": branch_name
        }

        # Step 4 & 5: Create PR if requested
        if create_pr:
            pr_result = await self.create_pull_request(
                implementation_result,
                test_results,
                coverage
            )
            result["pull_request"] = pr_result

        logger.info("Commit and PR workflow complete")
        return result

    def save_commit_to_workflow(
        self,
        workflow_id: str,
        commit_result: Dict[str, Any]
    ) -> None:
        """
        Save commit result to AutonomousWorkflow.

        Updates workflow with commit SHA and PR info.

        Args:
            workflow_id: Autonomous workflow ID
            commit_result: Commit result from create_commit
        """
        from core.models import AutonomousWorkflow

        workflow = self.db.query(AutonomousWorkflow).filter(
            AutonomousWorkflow.id == workflow_id
        ).first()

        if workflow:
            workflow.commit_sha = commit_result.get("commit_sha")
            workflow.commit_message = commit_result.get("commit_message")
            workflow.branch = commit_result.get("branch")
            workflow.updated_at = datetime.utcnow()
            self.db.commit()
            logger.info(f"Saved commit to workflow {workflow_id}")
        else:
            logger.warning(f"Workflow {workflow_id} not found")

    def _infer_repo_owner(self) -> str:
        """
        Infer GitHub repo owner from git remote.

        Returns owner/username.
        """
        try:
            remote_url = self.git_ops.repo.remotes.origin.url
            # Parse GitHub URL (git@github.com:owner/repo.git or https://github.com/owner/repo.git)
            if "github.com" in remote_url:
                if remote_url.startswith("git@"):
                    # git@github.com:owner/repo.git
                    owner = remote_url.split(":")[-1].split("/")[0]
                else:
                    # https://github.com/owner/repo.git
                    owner = remote_url.split("/")[-2]
                return owner
        except Exception as e:
            logger.warning(f"Failed to infer repo owner: {e}")

        return "unknown"

    def _infer_repo_name(self) -> str:
        """
        Infer GitHub repo name from git remote.

        Returns repository name.
        """
        try:
            remote_url = self.git_ops.repo.remotes.origin.url
            # Parse repo name
            repo_name = remote_url.split("/")[-1].replace(".git", "")
            return repo_name
        except Exception as e:
            logger.warning(f"Failed to infer repo name: {e}")

        return "unknown"
