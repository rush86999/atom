#!/usr/bin/env python3
"""
🚀 Jira Integration Routes
Provides REST API endpoints for Jira integration
"""

import logging
import httpx
from flask import Blueprint, jsonify, request
from datetime import datetime

jira_bp = Blueprint('jira', __name__)
logger = logging.getLogger(__name__)

@jira_bp.route('/health', methods=['GET'])
def health_check():
    """Health check for Jira integration"""
    try:
        return jsonify({
            'status': 'healthy',
            'integration': 'jira',
            'timestamp': datetime.utcnow().isoformat(),
            'version': '1.0.0'
        })
    except Exception as e:
        logger.error(f"Jira health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'integration': 'jira'
        }), 500

@jira_bp.route('/projects', methods=['GET'])
def get_projects():
    """Get Jira projects"""
    try:
        # Mock implementation - in production, this would use Jira API
        return jsonify({
            'projects': [
                {'key': 'PROJ', 'name': 'Main Project', 'type': 'software'},
                {'key': 'ADMIN', 'name': 'Admin Tasks', 'type': 'service_desk'},
                {'key': 'MARKET', 'name': 'Marketing', 'type': 'business'}
            ],
            'total': 3
        })
    except Exception as e:
        logger.error(f"Failed to get projects: {e}")
        return jsonify({'error': str(e)}), 500

@jira_bp.route('/issues', methods=['GET'])
def get_issues():
    """Get Jira issues"""
    try:
        project = request.args.get('project')
        if not project:
            return jsonify({'error': 'Project parameter required'}), 400
            
        # Mock implementation
        return jsonify({
            'issues': [
                {'key': f'{project}-1', 'summary': 'Integration enhancement', 'status': 'Open'},
                {'key': f'{project}-2', 'summary': 'Bug fix needed', 'status': 'In Progress'},
                {'key': f'{project}-3', 'summary': 'Feature request', 'status': 'Done'}
            ],
            'project': project,
            'total': 3
        })
    except Exception as e:
        logger.error(f"Failed to get issues: {e}")
        return jsonify({'error': str(e)}), 500

@jira_bp.route('/create', methods=['POST'])
def create_issue():
    """Create a new Jira issue"""
    try:
        data = request.get_json()
        project_key = data.get('project_key')
        summary = data.get('summary')
        description = data.get('description', '')
        issue_type = data.get('issue_type', 'Task')
        
        if not project_key or not summary:
            return jsonify({'error': 'Project key and summary required'}), 400
            
        # Mock implementation
        issue_key = f'{project_key}-NEW'
        return jsonify({
            'issue': {
                'key': issue_key,
                'summary': summary,
                'description': description,
                'type': issue_type,
                'status': 'Open',
                'created_at': datetime.utcnow().isoformat()
            },
            'message': 'Issue created successfully'
        })
    except Exception as e:
        logger.error(f"Failed to create issue: {e}")
        return jsonify({'error': str(e)}), 500

@jira_bp.route('/update/<issue_key>', methods=['PUT'])
def update_issue(issue_key):
    """Update Jira issue"""
    try:
        data = request.get_json()
        summary = data.get('summary')
        description = data.get('description')
        status = data.get('status')
        
        # Mock implementation
        return jsonify({
            'issue': {
                'key': issue_key,
                'summary': summary,
                'description': description,
                'status': status,
                'updated_at': datetime.utcnow().isoformat()
            },
            'message': 'Issue updated successfully'
        })
    except Exception as e:
        logger.error(f"Failed to update issue: {e}")
        return jsonify({'error': str(e)}), 500

@jira_bp.route('/delete/<issue_key>', methods=['DELETE'])
def delete_issue(issue_key):
    """Delete Jira issue"""
    try:
        # Mock implementation
        return jsonify({
            'issue': issue_key,
            'deleted_at': datetime.utcnow().isoformat(),
            'message': 'Issue deleted successfully'
        })
    except Exception as e:
        logger.error(f"Failed to delete issue: {e}")
        return jsonify({'error': str(e)}), 500