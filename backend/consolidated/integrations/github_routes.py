import logging
from datetime import datetime
from typing import Dict, List, Optional

from flask import Blueprint, jsonify, request

from .github_service import GitHubService

logger = logging.getLogger(__name__)

# Create blueprint for GitHub routes
github_bp = Blueprint("github_routes", __name__)

# Initialize GitHub service
github_service = GitHubService()


# Helper function to extract user_id from request
def get_user_id():
    """Extract user_id from request headers or query parameters"""
    return (
        request.headers.get("X-User-ID")
        or request.args.get("user_id")
        or "default_user"
    )


# Helper function to handle authentication
def require_auth():
    """Check if access token is available"""
    if not hasattr(github_service, "access_token") or not github_service.access_token:
        return jsonify(
            {
                "ok": False,
                "error": "GitHub access token required",
                "message": "Please authenticate with GitHub first",
            }
        ), 401
    return None


@github_bp.route("/api/github/status", methods=["GET"])
def github_status():
    """Get GitHub integration status"""
    try:
        user_id = get_user_id()

        # Check if authenticated
        auth_check = require_auth()
        if auth_check:
            return auth_check

        # Test basic connectivity
        health_check = github_service.health_check()

        return jsonify(
            {
                "ok": True,
                "service": "github",
                "user_id": user_id,
                "status": health_check.get("status", "unknown"),
                "authenticated": True,
                "rate_limit_remaining": health_check.get("rate_limit_remaining"),
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        logger.error(f"GitHub status error: {e}")
        return jsonify(
            {
                "ok": False,
                "service": "github",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }
        ), 500


@github_bp.route("/api/github/auth/set-token", methods=["POST"])
def set_github_token():
    """Set GitHub access token"""
    try:
        data = request.get_json()
        if not data or "access_token" not in data:
            return jsonify({"ok": False, "error": "access_token is required"}), 400

        github_service.set_access_token(data["access_token"])

        return jsonify(
            {
                "ok": True,
                "message": "GitHub access token set successfully",
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        logger.error(f"Set GitHub token error: {e}")
        return jsonify(
            {"ok": False, "error": str(e), "timestamp": datetime.now().isoformat()}
        ), 500


@github_bp.route("/api/github/user/profile", methods=["GET"])
def get_user_profile():
    """Get authenticated user profile"""
    try:
        auth_check = require_auth()
        if auth_check:
            return auth_check

        profile = github_service.get_user_profile()

        if profile:
            return jsonify(
                {
                    "ok": True,
                    "profile": profile,
                    "timestamp": datetime.now().isoformat(),
                }
            )
        else:
            return jsonify(
                {
                    "ok": False,
                    "error": "Failed to fetch user profile",
                    "timestamp": datetime.now().isoformat(),
                }
            ), 500

    except Exception as e:
        logger.error(f"Get user profile error: {e}")
        return jsonify(
            {"ok": False, "error": str(e), "timestamp": datetime.now().isoformat()}
        ), 500


@github_bp.route("/api/github/user/organizations", methods=["GET"])
def get_organizations():
    """Get user's organizations"""
    try:
        auth_check = require_auth()
        if auth_check:
            return auth_check

        organizations = github_service.get_organizations()

        return jsonify(
            {
                "ok": True,
                "organizations": organizations,
                "count": len(organizations),
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        logger.error(f"Get organizations error: {e}")
        return jsonify(
            {"ok": False, "error": str(e), "timestamp": datetime.now().isoformat()}
        ), 500


@github_bp.route("/api/github/repositories", methods=["GET"])
def get_repositories():
    """Get repositories for user or organization"""
    try:
        auth_check = require_auth()
        if auth_check:
            return auth_check

        org = request.args.get("org")
        visibility = request.args.get("visibility", "all")

        repositories = github_service.get_repositories(org=org, visibility=visibility)

        return jsonify(
            {
                "ok": True,
                "repositories": repositories,
                "count": len(repositories),
                "org": org,
                "visibility": visibility,
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        logger.error(f"Get repositories error: {e}")
        return jsonify(
            {"ok": False, "error": str(e), "timestamp": datetime.now().isoformat()}
        ), 500


@github_bp.route("/api/github/repositories/<owner>/<repo>", methods=["GET"])
def get_repository(owner: str, repo: str):
    """Get specific repository details"""
    try:
        auth_check = require_auth()
        if auth_check:
            return auth_check

        repository = github_service.get_repository(owner, repo)

        if repository:
            return jsonify(
                {
                    "ok": True,
                    "repository": repository,
                    "timestamp": datetime.now().isoformat(),
                }
            )
        else:
            return jsonify(
                {
                    "ok": False,
                    "error": f"Repository {owner}/{repo} not found",
                    "timestamp": datetime.now().isoformat(),
                }
            ), 404

    except Exception as e:
        logger.error(f"Get repository error: {e}")
        return jsonify(
            {"ok": False, "error": str(e), "timestamp": datetime.now().isoformat()}
        ), 500


@github_bp.route("/api/github/repositories", methods=["POST"])
def create_repository():
    """Create a new repository"""
    try:
        auth_check = require_auth()
        if auth_check:
            return auth_check

        data = request.get_json()
        if not data or "name" not in data:
            return jsonify({"ok": False, "error": "Repository name is required"}), 400

        repository = github_service.create_repository(
            name=data["name"],
            description=data.get("description", ""),
            private=data.get("private", False),
            auto_init=data.get("auto_init", False),
        )

        if repository:
            return jsonify(
                {
                    "ok": True,
                    "repository": repository,
                    "message": "Repository created successfully",
                    "timestamp": datetime.now().isoformat(),
                }
            )
        else:
            return jsonify(
                {
                    "ok": False,
                    "error": "Failed to create repository",
                    "timestamp": datetime.now().isoformat(),
                }
            ), 500

    except Exception as e:
        logger.error(f"Create repository error: {e}")
        return jsonify(
            {"ok": False, "error": str(e), "timestamp": datetime.now().isoformat()}
        ), 500


@github_bp.route("/api/github/repositories/<owner>/<repo>/issues", methods=["GET"])
def get_issues(owner: str, repo: str):
    """Get issues for a repository"""
    try:
        auth_check = require_auth()
        if auth_check:
            return auth_check

        state = request.args.get("state", "open")
        labels = request.args.get("labels")
        labels_list = labels.split(",") if labels else None

        issues = github_service.get_issues(owner, repo, state=state, labels=labels_list)

        return jsonify(
            {
                "ok": True,
                "issues": issues,
                "count": len(issues),
                "state": state,
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        logger.error(f"Get issues error: {e}")
        return jsonify(
            {"ok": False, "error": str(e), "timestamp": datetime.now().isoformat()}
        ), 500


@github_bp.route("/api/github/repositories/<owner>/<repo>/issues", methods=["POST"])
def create_issue(owner: str, repo: str):
    """Create a new issue"""
    try:
        auth_check = require_auth()
        if auth_check:
            return auth_check

        data = request.get_json()
        if not data or "title" not in data:
            return jsonify({"ok": False, "error": "Issue title is required"}), 400

        issue = github_service.create_issue(
            owner=owner,
            repo=repo,
            title=data["title"],
            body=data.get("body", ""),
            labels=data.get("labels"),
            assignees=data.get("assignees"),
        )

        if issue:
            return jsonify(
                {
                    "ok": True,
                    "issue": issue,
                    "message": "Issue created successfully",
                    "timestamp": datetime.now().isoformat(),
                }
            )
        else:
            return jsonify(
                {
                    "ok": False,
                    "error": "Failed to create issue",
                    "timestamp": datetime.now().isoformat(),
                }
            ), 500

    except Exception as e:
        logger.error(f"Create issue error: {e}")
        return jsonify(
            {"ok": False, "error": str(e), "timestamp": datetime.now().isoformat()}
        ), 500


@github_bp.route("/api/github/repositories/<owner>/<repo>/pulls", methods=["GET"])
def get_pull_requests(owner: str, repo: str):
    """Get pull requests for a repository"""
    try:
        auth_check = require_auth()
        if auth_check:
            return auth_check

        state = request.args.get("state", "open")

        pull_requests = github_service.get_pull_requests(owner, repo, state=state)

        return jsonify(
            {
                "ok": True,
                "pull_requests": pull_requests,
                "count": len(pull_requests),
                "state": state,
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        logger.error(f"Get pull requests error: {e}")
        return jsonify(
            {"ok": False, "error": str(e), "timestamp": datetime.now().isoformat()}
        ), 500


@github_bp.route("/api/github/repositories/<owner>/<repo>/pulls", methods=["POST"])
def create_pull_request(owner: str, repo: str):
    """Create a new pull request"""
    try:
        auth_check = require_auth()
        if auth_check:
            return auth_check

        data = request.get_json()
        required_fields = ["title", "head", "base"]
        for field in required_fields:
            if field not in data:
                return jsonify(
                    {"ok": False, "error": f"Field '{field}' is required"}
                ), 400

        pull_request = github_service.create_pull_request(
            owner=owner,
            repo=repo,
            title=data["title"],
            head=data["head"],
            base=data["base"],
            body=data.get("body", ""),
        )

        if pull_request:
            return jsonify(
                {
                    "ok": True,
                    "pull_request": pull_request,
                    "message": "Pull request created successfully",
                    "timestamp": datetime.now().isoformat(),
                }
            )
        else:
            return jsonify(
                {
                    "ok": False,
                    "error": "Failed to create pull request",
                    "timestamp": datetime.now().isoformat(),
                }
            ), 500

    except Exception as e:
        logger.error(f"Create pull request error: {e}")
        return jsonify(
            {"ok": False, "error": str(e), "timestamp": datetime.now().isoformat()}
        ), 500


@github_bp.route("/api/github/repositories/<owner>/<repo>/workflows", methods=["GET"])
def get_workflow_runs(owner: str, repo: str):
    """Get workflow runs for a repository"""
    try:
        auth_check = require_auth()
        if auth_check:
            return auth_check

        branch = request.args.get("branch")

        workflow_runs = github_service.get_workflow_runs(owner, repo, branch=branch)

        return jsonify(
            {
                "ok": True,
                "workflow_runs": workflow_runs,
                "count": len(workflow_runs),
                "branch": branch,
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        logger.error(f"Get workflow runs error: {e}")
        return jsonify(
            {"ok": False, "error": str(e), "timestamp": datetime.now().isoformat()}
        ), 500


@github_bp.route("/api/github/search/code", methods=["GET"])
def search_code():
    """Search code across repositories"""
    try:
        auth_check = require_auth()
        if auth_check:
            return auth_check

        query = request.args.get("q")
        org = request.args.get("org")

        if not query:
            return jsonify(
                {"ok": False, "error": "Search query parameter 'q' is required"}
            ), 400

        results = github_service.search_code(query=query, org=org)

        return jsonify(
            {
                "ok": True,
                "query": query,
                "org": org,
                "results": results,
                "count": len(results),
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        logger.error(f"Search code error: {e}")
        return jsonify(
            {"ok": False, "error": str(e), "timestamp": datetime.now().isoformat()}
        ), 500


@github_bp.route("/api/github/search/issues", methods=["GET"])
def search_issues():
    """Search issues and pull requests"""
    try:
        auth_check = require_auth()
        if auth_check:
            return auth_check

        query = request.args.get("q")
        org = request.args.get("org")

        if not query:
            return jsonify(
                {"ok": False, "error": "Search query parameter 'q' is required"}
            ), 400

        results = github_service.search_issues(query=query, org=org)

        return jsonify(
            {
                "ok": True,
                "query": query,
                "org": org,
                "results": results,
                "count": len(results),
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        logger.error(f"Search issues error: {e}")
        return jsonify(
            {"ok": False, "error": str(e), "timestamp": datetime.now().isoformat()}
        ), 500


@github_bp.route("/api/github/rate-limit", methods=["GET"])
def get_rate_limit():
    """Get current rate limit status"""
    try:
        auth_check = require_auth()
        if auth_check:
            return auth_check

        rate_limit = github_service.get_rate_limit()

        if rate_limit:
            return jsonify(
                {
                    "ok": True,
                    "rate_limit": rate_limit,
                    "timestamp": datetime.now().isoformat(),
                }
            )
        else:
            return jsonify(
                {
                    "ok": False,
                    "error": "Failed to fetch rate limit",
                    "timestamp": datetime.now().isoformat(),
                }
            ), 500

    except Exception as e:
        logger.error(f"Get rate limit error: {e}")
        return jsonify(
            {"ok": False, "error": str(e), "timestamp": datetime.now().isoformat()}
        ), 500


@github_bp.route("/api/github/health", methods=["GET"])
def health_check():
    """Perform comprehensive health check"""
    try:
        auth_check = require_auth()
        if auth_check:
            return auth_check

        health = github_service.health_check()

        return jsonify(
            {"ok": True, "health": health, "timestamp": datetime.now().isoformat()}
        )

    except Exception as e:
        logger.error(f"Health check error: {e}")
        return jsonify(
            {"ok": False, "error": str(e), "timestamp": datetime.now().isoformat()}
        ), 500
