import os
from flask import Blueprint, request, jsonify
from .github_service import get_user_repositories, create_repository

github_bp = Blueprint('github_bp', __name__)

@github_bp.route('/github/repos', methods=['GET'])
def list_repos():
    """
    List all repositories for the authenticated user.
    """
    user_id = request.headers.get('user-id')
    if not user_id:
        return jsonify({"error": "user-id header is required"}), 400

    try:
        repos = get_user_repositories(user_id)
        return jsonify(repos), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@github_bp.route('/github/repos', methods=['POST'])
def create_repo():
    """
    Create a new repository for the authenticated user.
    """
    user_id = request.headers.get('user-id')
    if not user_id:
        return jsonify({"error": "user-id header is required"}), 400

    data = request.get_json()
    if not data or 'name' not in data:
        return jsonify({"error": "repository name is required"}), 400

    try:
        repo = create_repository(user_id, data['name'], data.get('description', ''))
        return jsonify(repo), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500
