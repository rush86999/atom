"""
Enhanced GitHub Integration Demo Script

This script demonstrates the comprehensive GitHub integration capabilities
including repository management, issue tracking, pull request automation,
and workflow management.

Usage:
    python demo_github_integration.py
"""

from datetime import datetime
import json
import logging
import os
import sys
from typing import Dict, List, Optional

# Add parent directory to path to import the service
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from github_service import GitHubService

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class GitHubIntegrationDemo:
    """Demonstration class for GitHub integration features"""

    def __init__(self):
        self.service = GitHubService()
        self.demo_results = []

    def set_access_token(self, token: str):
        """Set GitHub access token for authenticated operations"""
        self.service.set_access_token(token)
        logger.info("GitHub access token set")

    def demo_basic_operations(self) -> Dict:
        """Demonstrate basic GitHub operations"""
        logger.info("🚀 Starting Basic GitHub Operations Demo")

        results = {}

        try:
            # 1. Get user profile
            logger.info("1. Getting user profile...")
            profile = self.service.get_user_profile()
            if profile:
                results["user_profile"] = {
                    "login": profile.get("login"),
                    "name": profile.get("name"),
                    "email": profile.get("email"),
                    "public_repos": profile.get("public_repos"),
                }
                logger.info(f"   User: {profile.get('login')} ({profile.get('name')})")

            # 2. Get organizations
            logger.info("2. Getting organizations...")
            orgs = self.service.get_organizations()
            results["organizations"] = [
                {"login": org.get("login"), "name": org.get("name")}
                for org in orgs[:3]  # Show first 3 orgs
            ]
            logger.info(f"   Found {len(orgs)} organizations")

            # 3. Get repositories
            logger.info("3. Getting repositories...")
            repos = self.service.get_repositories()
            results["repositories"] = [
                {
                    "name": repo.get("name"),
                    "full_name": repo.get("full_name"),
                    "private": repo.get("private"),
                    "html_url": repo.get("html_url"),
                }
                for repo in repos[:5]  # Show first 5 repos
            ]
            logger.info(f"   Found {len(repos)} repositories")

            # 4. Get rate limit
            logger.info("4. Checking rate limits...")
            rate_limit = self.service.get_rate_limit()
            if rate_limit:
                core = rate_limit.get("resources", {}).get("core", {})
                results["rate_limit"] = {
                    "remaining": core.get("remaining"),
                    "limit": core.get("limit"),
                    "reset_time": datetime.fromtimestamp(
                        core.get("reset", 0)
                    ).isoformat(),
                }
                logger.info(
                    f"   Rate limit: {core.get('remaining')}/{core.get('limit')}"
                )

            # 5. Health check
            logger.info("5. Performing health check...")
            health = self.service.health_check()
            results["health"] = health
            logger.info(f"   Health status: {health.get('status')}")

            logger.info("✅ Basic operations demo completed successfully")

        except Exception as e:
            logger.error(f"❌ Basic operations demo failed: {e}")
            results["error"] = str(e)

        return results

    def demo_repository_management(self, owner: str, repo: str) -> Dict:
        """Demonstrate repository management operations"""
        logger.info(f"📁 Starting Repository Management Demo for {owner}/{repo}")

        results = {}

        try:
            # 1. Get repository details
            logger.info("1. Getting repository details...")
            repository = self.service.get_repository(owner, repo)
            if repository:
                results["repository"] = {
                    "name": repository.get("name"),
                    "full_name": repository.get("full_name"),
                    "description": repository.get("description"),
                    "stars": repository.get("stargazers_count"),
                    "forks": repository.get("forks_count"),
                    "open_issues": repository.get("open_issues_count"),
                }
                logger.info(f"   Repository: {repository.get('full_name')}")

            # 2. Get branches
            logger.info("2. Getting branches...")
            branches = self.service.get_branches(owner, repo)
            results["branches"] = [
                branch.get("name")
                for branch in branches[:5]  # Show first 5 branches
            ]
            logger.info(f"   Found {len(branches)} branches")

            # 3. Get issues
            logger.info("3. Getting issues...")
            issues = self.service.get_issues(owner, repo, state="open")
            results["issues"] = [
                {
                    "number": issue.get("number"),
                    "title": issue.get("title"),
                    "state": issue.get("state"),
                    "labels": [label.get("name") for label in issue.get("labels", [])],
                }
                for issue in issues[:3]  # Show first 3 issues
            ]
            logger.info(f"   Found {len(issues)} open issues")

            # 4. Get pull requests
            logger.info("4. Getting pull requests...")
            pull_requests = self.service.get_pull_requests(owner, repo, state="open")
            results["pull_requests"] = [
                {
                    "number": pr.get("number"),
                    "title": pr.get("title"),
                    "state": pr.get("state"),
                    "user": pr.get("user", {}).get("login"),
                }
                for pr in pull_requests[:3]  # Show first 3 PRs
            ]
            logger.info(f"   Found {len(pull_requests)} open pull requests")

            # 5. Get workflow runs
            logger.info("5. Getting workflow runs...")
            workflow_runs = self.service.get_workflow_runs(owner, repo)
            results["workflow_runs"] = [
                {
                    "id": run.get("id"),
                    "name": run.get("name"),
                    "status": run.get("status"),
                    "conclusion": run.get("conclusion"),
                }
                for run in workflow_runs[:3]  # Show first 3 workflow runs
            ]
            logger.info(f"   Found {len(workflow_runs)} workflow runs")

            logger.info("✅ Repository management demo completed successfully")

        except Exception as e:
            logger.error(f"❌ Repository management demo failed: {e}")
            results["error"] = str(e)

        return results

    def demo_search_operations(self) -> Dict:
        """Demonstrate search operations"""
        logger.info("🔍 Starting Search Operations Demo")

        results = {}

        try:
            # 1. Search code
            logger.info("1. Searching code...")
            code_results = self.service.search_code("def main()", org="github")
            results["code_search"] = [
                {
                    "name": item.get("name"),
                    "path": item.get("path"),
                    "repository": item.get("repository", {}).get("full_name"),
                }
                for item in code_results[:3]  # Show first 3 results
            ]
            logger.info(f"   Found {len(code_results)} code search results")

            # 2. Search issues
            logger.info("2. Searching issues...")
            issue_results = self.service.search_issues("bug label:bug", org="github")
            results["issue_search"] = [
                {
                    "number": item.get("number"),
                    "title": item.get("title"),
                    "state": item.get("state"),
                    "repository": item.get("repository", {}).get("full_name"),
                }
                for item in issue_results[:3]  # Show first 3 results
            ]
            logger.info(f"   Found {len(issue_results)} issue search results")

            logger.info("✅ Search operations demo completed successfully")

        except Exception as e:
            logger.error(f"❌ Search operations demo failed: {e}")
            results["error"] = str(e)

        return results

    def demo_advanced_operations(self, owner: str, repo: str) -> Dict:
        """Demonstrate advanced operations (read-only for safety)"""
        logger.info("⚡ Starting Advanced Operations Demo")

        results = {}

        try:
            # Note: These are read-only operations for safety in demo

            # 1. Get teams (if organization)
            logger.info("1. Getting teams...")
            teams = self.service.get_teams(owner)
            results["teams"] = [
                {
                    "name": team.get("name"),
                    "slug": team.get("slug"),
                    "description": team.get("description"),
                }
                for team in teams[:3]  # Show first 3 teams
            ]
            logger.info(f"   Found {len(teams)} teams")

            # 2. Get projects
            logger.info("2. Getting projects...")
            projects = self.service.get_projects(owner, repo)
            results["projects"] = [
                {
                    "name": project.get("name"),
                    "body": project.get("body"),
                    "state": project.get("state"),
                }
                for project in projects[:3]  # Show first 3 projects
            ]
            logger.info(f"   Found {len(projects)} projects")

            # 3. Get commits
            logger.info("3. Getting recent commits...")
            commits = self.service.get_commits(owner, repo, branch="main")
            results["commits"] = [
                {
                    "sha": commit.get("sha")[:7],
                    "message": commit.get("commit", {}).get("message"),
                    "author": commit.get("commit", {}).get("author", {}).get("name"),
                    "date": commit.get("commit", {}).get("author", {}).get("date"),
                }
                for commit in commits[:3]  # Show first 3 commits
            ]
            logger.info(f"   Found {len(commits)} commits")

            logger.info("✅ Advanced operations demo completed successfully")

        except Exception as e:
            logger.error(f"❌ Advanced operations demo failed: {e}")
            results["error"] = str(e)

        return results

    def run_complete_demo(
        self, access_token: Optional[str] = None, demo_repo: str = "octocat/Hello-World"
    ) -> Dict:
        """Run complete demonstration of GitHub integration features"""
        logger.info("🎬 Starting Complete GitHub Integration Demo")
        logger.info("=" * 60)

        demo_results = {
            "demo_timestamp": datetime.now().isoformat(),
            "demo_repository": demo_repo,
            "sections": {},
        }

        # Set access token if provided
        if access_token:
            self.set_access_token(access_token)

        # Extract owner and repo from demo_repo
        owner, repo = demo_repo.split("/")

        try:
            # Run all demo sections
            demo_results["sections"]["basic_operations"] = self.demo_basic_operations()
            demo_results["sections"]["repository_management"] = (
                self.demo_repository_management(owner, repo)
            )
            demo_results["sections"]["search_operations"] = (
                self.demo_search_operations()
            )
            demo_results["sections"]["advanced_operations"] = (
                self.demo_advanced_operations(owner, repo)
            )

            # Calculate overall success
            successful_sections = sum(
                1
                for section in demo_results["sections"].values()
                if "error" not in section
            )
            total_sections = len(demo_results["sections"])

            demo_results["summary"] = {
                "total_sections": total_sections,
                "successful_sections": successful_sections,
                "success_rate": f"{(successful_sections / total_sections) * 100:.1f}%",
                "overall_status": "SUCCESS"
                if successful_sections == total_sections
                else "PARTIAL",
            }

            logger.info("=" * 60)
            logger.info("🎉 GitHub Integration Demo Completed!")
            logger.info(f"   Status: {demo_results['summary']['overall_status']}")
            logger.info(f"   Success Rate: {demo_results['summary']['success_rate']}")

        except Exception as e:
            logger.error(f"❌ Complete demo failed: {e}")
            demo_results["error"] = str(e)
            demo_results["summary"] = {"overall_status": "FAILED"}

        # Save results to file
        output_file = "github_integration_demo_results.json"
        with open(output_file, "w") as f:
            json.dump(demo_results, f, indent=2)

        logger.info(f"📄 Demo results saved to: {output_file}")

        return demo_results


def main():
    """Main function to run the GitHub integration demo"""
    print("GitHub Integration Demo")
    print("=" * 50)

    # Check for access token
    access_token = os.getenv("GITHUB_ACCESS_TOKEN")
    if not access_token:
        print("⚠️  No GITHUB_ACCESS_TOKEN environment variable found.")
        print("   Some operations will be limited to public data only.")
        print("   Set GITHUB_ACCESS_TOKEN for full functionality.")
        print()

    # Demo repository (public repo for testing)
    demo_repo = "octocat/Hello-World"  # GitHub's example repository

    print(f"📁 Using demo repository: {demo_repo}")
    print()

    # Run the demo
    demo = GitHubIntegrationDemo()
    results = demo.run_complete_demo(access_token=access_token, demo_repo=demo_repo)

    # Print summary
    print("\n" + "=" * 50)
    print("DEMO SUMMARY")
    print("=" * 50)

    summary = results.get("summary", {})
    print(f"Overall Status: {summary.get('overall_status', 'UNKNOWN')}")
    print(
        f"Successful Sections: {summary.get('successful_sections', 0)}/{summary.get('total_sections', 0)}"
    )
    print(f"Success Rate: {summary.get('success_rate', '0%')}")

    if "error" in results:
        print(f"\n❌ Demo Error: {results['error']}")
        return 1

    print("\n✅ Demo completed successfully!")
    print(
        "📄 Check the generated 'github_integration_demo_results.json' for detailed results."
    )

    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
