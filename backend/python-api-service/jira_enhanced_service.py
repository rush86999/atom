"""
Enhanced Jira Service Implementation
Complete Jira integration with comprehensive project management capabilities
"""

import os
import logging
import asyncio
import httpx
import json
import base64
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List, Union

# Import encryption utilities
try:
    from atom_encryption import decrypt_data, encrypt_data
    ENCRYPTION_AVAILABLE = True
except ImportError:
    ENCRYPTION_AVAILABLE = False

# Import database operations
try:
    from db_oauth_jira_complete import get_user_jira_tokens, get_jira_user
    JIRA_DB_AVAILABLE = True
except ImportError as e:
    logging.getLogger(__name__).warning(f"Jira database operations not available: {e}")
    JIRA_DB_AVAILABLE = False

# Jira API configuration
JIRA_API_BASE_URL = "https://api.atlassian.com/ex/jira"
DEFAULT_TIMEOUT = 30

# Configure logging
logger = logging.getLogger(__name__)

# Data model classes
class JiraIssue:
    """Jira issue data model"""
    
    def __init__(self, data: Dict[str, Any]):
        self.id = data.get("id")
        self.key = data.get("key")
        self.summary = data.get("fields", {}).get("summary", "")
        self.description = data.get("fields", {}).get("description", "")
        self.issue_type = data.get("fields", {}).get("issuetype", {})
        self.status = data.get("fields", {}).get("status", {})
        self.priority = data.get("fields", {}).get("priority", {})
        self.assignee = data.get("fields", {}).get("assignee")
        self.reporter = data.get("fields", {}).get("reporter")
        self.project = data.get("fields", {}).get("project", {})
        self.created_at = data.get("fields", {}).get("created")
        self.updated_at = data.get("fields", {}).get("updated")
        self.due_date = data.get("fields", {}).get("duedate")
        self.resolution_date = data.get("fields", {}).get("resolutiondate")
        self.components = data.get("fields", {}).get("components", [])
        self.labels = data.get("fields", {}).get("labels", [])
        self.fix_versions = data.get("fields", {}).get("fixVersions", [])
        self.versions = data.get("fields", {}).get("versions", [])
        self.environment = data.get("fields", {}).get("environment", "")
        self.time_estimate = data.get("fields", {}).get("timeestimate")
        self.time_spent = data.get("fields", {}).get("timespent")
        self.watches = data.get("watches", {}).get("watchCount", 0)
        self.comments = []
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'key': self.key,
            'summary': self.summary,
            'description': self.description,
            'issueType': self.issue_type,
            'status': self.status,
            'priority': self.priority,
            'assignee': self.assignee,
            'reporter': self.reporter,
            'project': self.project,
            'created': self.created_at,
            'updated': self.updated_at,
            'dueDate': self.due_date,
            'resolutionDate': self.resolution_date,
            'components': self.components,
            'labels': self.labels,
            'fixVersions': self.fix_versions,
            'versions': self.versions,
            'environment': self.environment,
            'timeEstimate': self.time_estimate,
            'timeSpent': self.time_spent,
            'watches': self.watches,
            'comments': self.comments
        }

class JiraProject:
    """Jira project data model"""
    
    def __init__(self, data: Dict[str, Any]):
        self.id = data.get("id")
        self.key = data.get("key")
        self.name = data.get("name")
        self.description = data.get("description", "")
        self.project_type = data.get("projectTypeKey", "")
        self.lead = data.get("lead")
        self.url = data.get("url", "")
        self.avatar_urls = data.get("avatarUrls", {})
        self.project_category = data.get("projectCategory", {})
        self.style = data.get("style", "")
        self.is_private = data.get("isPrivate", False)
        self.issue_types = data.get("issueTypes", [])
        self.versions = data.get("versions", [])
        self.components = data.get("components", [])
        self.roles = data.get("roles", {})
        self.simplified = data.get("simplified", False)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'key': self.key,
            'name': self.name,
            'description': self.description,
            'projectType': self.project_type,
            'lead': self.lead,
            'url': self.url,
            'avatarUrls': self.avatar_urls,
            'projectCategory': self.project_category,
            'style': self.style,
            'isPrivate': self.is_private,
            'issueTypes': self.issue_types,
            'versions': self.versions,
            'components': self.components,
            'roles': self.roles
        }

class JiraBoard:
    """Jira board data model"""
    
    def __init__(self, data: Dict[str, Any]):
        self.id = data.get("id")
        self.name = data.get("name")
        self.type = data.get("type", "")
        self.filter_id = data.get("filter", {}).get("id")
        self.filter_name = data.get("filter", {}).get("name")
        self.project_id = data.get("location", {}).get("projectId")
        self.project_key = data.get("location", {}).get("projectKey")
        self.project_name = data.get("location", {}).get("projectName")
        self.sprint_start_date = data.get("sprint", {}).get("startDate")
        self.sprint_end_date = data.get("sprint", {}).get("endDate")
        self.complete_date = data.get("sprint", {}).get("completeDate")
        self.state = data.get("sprint", {}).get("state", "")
        self.rank = data.get("rank", 0)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'type': self.type,
            'filterId': self.filter_id,
            'filterName': self.filter_name,
            'projectId': self.project_id,
            'projectKey': self.project_key,
            'projectName': self.project_name,
            'sprintStartDate': self.sprint_start_date,
            'sprintEndDate': self.sprint_end_date,
            'completeDate': self.complete_date,
            'sprintState': self.state,
            'rank': self.rank
        }

class JiraUser:
    """Jira user data model"""
    
    def __init__(self, data: Dict[str, Any]):
        self.account_id = data.get("accountId")
        self.account_type = data.get("accountType", "")
        self.active = data.get("active", True)
        self.display_name = data.get("displayName", "")
        self.email_address = data.get("emailAddress", "")
        self.avatar_urls = data.get("avatarUrls", {})
        self.time_zone = data.get("timeZone", "")
        self.locale = data.get("locale", "")
        self.groups = data.get("groups", {}).get("items", [])
        self.application_roles = data.get("applicationRoles", {}).get("items", [])
        self.expand = data.get("expand", "")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'accountId': self.account_id,
            'accountType': self.account_type,
            'active': self.active,
            'displayName': self.display_name,
            'emailAddress': self.email_address,
            'avatarUrls': self.avatar_urls,
            'timeZone': self.time_zone,
            'locale': self.locale,
            'groups': self.groups,
            'applicationRoles': self.application_roles
        }

class JiraComment:
    """Jira comment data model"""
    
    def __init__(self, data: Dict[str, Any]):
        self.id = data.get("id")
        self.author = data.get("author", {})
        self.body = data.get("body", "")
        self.created_at = data.get("created")
        self.updated_at = data.get("updated")
        self.jsd_public = data.get("jsdPublic", True)
        self.visibility = data.get("visibility", {})
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'author': self.author,
            'body': self.body,
            'created': self.created_at,
            'updated': self.updated_at,
            'jsdPublic': self.jsd_public,
            'visibility': self.visibility
        }

class JiraSprint:
    """Jira sprint data model"""
    
    def __init__(self, data: Dict[str, Any]):
        self.id = data.get("id")
        self.name = data.get("name")
        self.state = data.get("state", "")
        self.goal = data.get("goal", "")
        self.start_date = data.get("startDate")
        self.end_date = data.get("endDate")
        self.complete_date = data.get("completeDate")
        self.origin_board_id = data.get("originBoardId")
        self.created_date = data.get("createdDate")
        self.rapid_view_id = data.get("rapidViewId")
        self.sequence = data.get("sequence", 0)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'state': self.state,
            'goal': self.goal,
            'startDate': self.start_date,
            'endDate': self.end_date,
            'completeDate': self.complete_date,
            'originBoardId': self.origin_board_id,
            'createdDate': self.created_date,
            'rapidViewId': self.rapid_view_id,
            'sequence': self.sequence
        }

class JiraService:
    """Enhanced Jira service class"""
    
    def __init__(self):
        self._mock_mode = True
        self.api_base_url = JIRA_API_BASE_URL
        self.timeout = DEFAULT_TIMEOUT
        self._mock_db = {
            'issues': [],
            'projects': [],
            'boards': [],
            'users': [],
            'sprints': [],
            'comments': []
        }
        self._init_mock_data()
    
    def _init_mock_data(self):
        """Initialize mock data for testing"""
        # Mock projects
        self._mock_db['projects'] = [
            JiraProject({
                'id': '10000',
                'key': 'AT',
                'name': 'ATOM Platform',
                'description': 'Main ATOM platform development project',
                'projectTypeKey': 'software',
                'lead': {
                    'accountId': 'user-123',
                    'displayName': 'Alex Johnson'
                },
                'url': 'https://company.atlassian.net/browse/AT',
                'avatarUrls': {
                    '48x48': 'https://gravatar.com/avatar/48',
                    '24x24': 'https://gravatar.com/avatar/24'
                },
                'projectCategory': {
                    'id': '10000',
                    'name': 'Development',
                    'description': 'Development projects'
                },
                'style': 'next-gen',
                'isPrivate': False
            }),
            JiraProject({
                'id': '10001',
                'key': 'MOB',
                'name': 'Mobile App',
                'description': 'Mobile application development',
                'projectTypeKey': 'software',
                'lead': {
                    'accountId': 'user-456',
                    'displayName': 'Sarah Williams'
                },
                'url': 'https://company.atlassian.net/browse/MOB',
                'avatarUrls': {
                    '48x48': 'https://gravatar.com/avatar/49',
                    '24x24': 'https://gravatar.com/avatar/25'
                },
                'projectCategory': {
                    'id': '10001',
                    'name': 'Mobile',
                    'description': 'Mobile projects'
                },
                'style': 'next-gen',
                'isPrivate': False
            })
        ]
        
        # Mock users
        self._mock_db['users'] = [
            JiraUser({
                'accountId': 'user-123',
                'accountType': 'atlassian',
                'active': True,
                'displayName': 'Alex Johnson',
                'emailAddress': 'alex.johnson@company.com',
                'avatarUrls': {
                    '48x48': 'https://gravatar.com/avatar/123/48',
                    '24x24': 'https://gravatar.com/avatar/123/24'
                },
                'timeZone': 'America/New_York',
                'locale': 'en_US'
            }),
            JiraUser({
                'accountId': 'user-456',
                'accountType': 'atlassian',
                'active': True,
                'displayName': 'Sarah Williams',
                'emailAddress': 'sarah.williams@company.com',
                'avatarUrls': {
                    '48x48': 'https://gravatar.com/avatar/456/48',
                    '24x24': 'https://gravatar.com/avatar/456/24'
                },
                'timeZone': 'America/Los_Angeles',
                'locale': 'en_US'
            }),
            JiraUser({
                'accountId': 'user-789',
                'accountType': 'atlassian',
                'active': True,
                'displayName': 'Michael Chen',
                'emailAddress': 'michael.chen@company.com',
                'avatarUrls': {
                    '48x48': 'https://gravatar.com/avatar/789/48',
                    '24x24': 'https://gravatar.com/avatar/789/24'
                },
                'timeZone': 'America/Chicago',
                'locale': 'en_US'
            })
        ]
        
        # Mock issues
        now = datetime.utcnow().isoformat() + 'Z'
        self._mock_db['issues'] = [
            JiraIssue({
                'id': '10001',
                'key': 'AT-1',
                'fields': {
                    'summary': 'Implement user authentication',
                    'description': 'Add OAuth 2.0 authentication with multiple provider support',
                    'issuetype': {
                        'id': '10001',
                        'name': 'Story',
                        'iconUrl': 'https://atlassian.com/...',
                        'description': 'A user story'
                    },
                    'status': {
                        'id': '10001',
                        'name': 'In Progress',
                        'statusCategory': {
                            'id': 4,
                            'key': 'in-progress',
                            'colorName': 'blue'
                        }
                    },
                    'priority': {
                        'id': '2',
                        'name': 'High',
                        'statusColor': 'red'
                    },
                    'assignee': {
                        'accountId': 'user-123',
                        'displayName': 'Alex Johnson'
                    },
                    'reporter': {
                        'accountId': 'user-456',
                        'displayName': 'Sarah Williams'
                    },
                    'project': {
                        'id': '10000',
                        'key': 'AT',
                        'name': 'ATOM Platform'
                    },
                    'created': now,
                    'updated': now,
                    'labels': ['authentication', 'oauth', 'security'],
                    'components': [{'id': '10000', 'name': 'Backend'}],
                    'timeestimate': 28800,  # 8 hours
                    'timespent': 7200,  # 2 hours
                    'watches': {'watchCount': 3}
                }
            }),
            JiraIssue({
                'id': '10002',
                'key': 'AT-2',
                'fields': {
                    'summary': 'Design system component library',
                    'description': 'Create reusable UI components for consistent design',
                    'issuetype': {
                        'id': '10002',
                        'name': 'Task',
                        'iconUrl': 'https://atlassian.com/...',
                        'description': 'A task that needs to be done'
                    },
                    'status': {
                        'id': '10002',
                        'name': 'To Do',
                        'statusCategory': {
                            'id': 2,
                            'key': 'new',
                            'colorName': 'blue-gray'
                        }
                    },
                    'priority': {
                        'id': '3',
                        'name': 'Medium',
                        'statusColor': 'yellow'
                    },
                    'assignee': {
                        'accountId': 'user-789',
                        'displayName': 'Michael Chen'
                    },
                    'reporter': {
                        'accountId': 'user-456',
                        'displayName': 'Sarah Williams'
                    },
                    'project': {
                        'id': '10000',
                        'key': 'AT',
                        'name': 'ATOM Platform'
                    },
                    'created': now,
                    'updated': now,
                    'labels': ['design', 'ui', 'components'],
                    'components': [{'id': '10001', 'name': 'Frontend'}],
                    'timeestimate': 21600,  # 6 hours
                    'timespent': 0,
                    'watches': {'watchCount': 5}
                }
            }),
            JiraIssue({
                'id': '10003',
                'key': 'MOB-1',
                'fields': {
                    'summary': 'Mobile app login screen',
                    'description': 'Design and implement login screen for mobile application',
                    'issuetype': {
                        'id': '10003',
                        'name': 'Bug',
                        'iconUrl': 'https://atlassian.com/...',
                        'description': 'A problem which impairs or prevents the functions of the product'
                    },
                    'status': {
                        'id': '10003',
                        'name': 'Done',
                        'statusCategory': {
                            'id': 3,
                            'key': 'done',
                            'colorName': 'green'
                        }
                    },
                    'priority': {
                        'id': '1',
                        'name': 'Highest',
                        'statusColor': 'red'
                    },
                    'assignee': {
                        'accountId': 'user-789',
                        'displayName': 'Michael Chen'
                    },
                    'reporter': {
                        'accountId': 'user-123',
                        'displayName': 'Alex Johnson'
                    },
                    'project': {
                        'id': '10001',
                        'key': 'MOB',
                        'name': 'Mobile App'
                    },
                    'created': now,
                    'updated': now,
                    'labels': ['mobile', 'ui', 'login'],
                    'components': [{'id': '10002', 'name': 'Mobile'}],
                    'resolutiondate': now,
                    'timeestimate': 3600,  # 1 hour
                    'timespent': 3600,  # 1 hour
                    'watches': {'watchCount': 2}
                }
            })
        ]
        
        # Mock boards
        self._mock_db['boards'] = [
            JiraBoard({
                'id': '1',
                'name': 'ATOM Platform Sprint Board',
                'type': 'scrum',
                'filter': {
                    'id': '10000',
                    'name': 'ATOM Platform Issues'
                },
                'location': {
                    'projectId': '10000',
                    'projectKey': 'AT',
                    'projectName': 'ATOM Platform'
                },
                'sprint': {
                    'startDate': f"{datetime.utcnow() - timedelta(days=7)}.000Z",
                    'endDate': f"{datetime.utcnow() + timedelta(days=7)}.000Z",
                    'state': 'active'
                }
            }),
            JiraBoard({
                'id': '2',
                'name': 'Mobile App Kanban Board',
                'type': 'kanban',
                'filter': {
                    'id': '10001',
                    'name': 'Mobile App Issues'
                },
                'location': {
                    'projectId': '10001',
                    'projectKey': 'MOB',
                    'projectName': 'Mobile App'
                }
            })
        ]
        
        # Mock sprints
        self._mock_db['sprints'] = [
            JiraSprint({
                'id': '1',
                'name': 'Sprint 12',
                'state': 'active',
                'goal': 'Complete authentication and design system features',
                'startDate': f"{datetime.utcnow() - timedelta(days=7)}.000Z",
                'endDate': f"{datetime.utcnow() + timedelta(days=7)}.000Z",
                'originBoardId': '1',
                'createdDate': f"{datetime.utcnow() - timedelta(days=10)}.000Z",
                'rapidViewId': '1',
                'sequence': 12
            }),
            JiraSprint({
                'id': '2',
                'name': 'Sprint 11',
                'state': 'closed',
                'goal': 'Implement core backend services',
                'startDate': f"{datetime.utcnow() - timedelta(days=28)}.000Z",
                'endDate': f"{datetime.utcnow() - timedelta(days=14)}.000Z",
                'completeDate': f"{datetime.utcnow() - timedelta(days=13)}.000Z",
                'originBoardId': '1',
                'createdDate': f"{datetime.utcnow() - timedelta(days=31)}.000Z",
                'rapidViewId': '1',
                'sequence': 11
            })
        ]
    
    def set_mock_mode(self, enabled: bool):
        """Set mock mode for testing"""
        self._mock_mode = enabled
        if enabled:
            self._init_mock_data()
    
    async def _get_user_access_token(self, user_id: str) -> Optional[str]:
        """Get access token for user"""
        if self._mock_mode:
            return os.getenv('JIRA_ACCESS_TOKEN', 'mock_jira_token')
        
        # In real implementation, this would fetch from database
        if JIRA_DB_AVAILABLE:
            tokens = await get_user_jira_tokens(None, user_id)
            if tokens:
                access_token = tokens.get('access_token', '')
                if ENCRYPTION_AVAILABLE and isinstance(access_token, bytes):
                    access_token = decrypt_data(access_token, os.getenv('ATOM_OAUTH_ENCRYPTION_KEY'))
                return access_token
        return None
    
    async def _get_user_cloud_id(self, user_id: str) -> Optional[str]:
        """Get user's Jira Cloud ID"""
        if self._mock_mode:
            return os.getenv('JIRA_CLOUD_ID', 'mock_cloud_id')
        
        # In real implementation, this would fetch from database
        if JIRA_DB_AVAILABLE:
            user = await get_jira_user(None, user_id)
            if user:
                return user.get('cloud_id')
        return None
    
    async def _make_api_request(self, method: str, endpoint: str, params: Optional[Dict[str, Any]] = None,
                             data: Optional[Dict[str, Any]] = None, files: Optional[Dict[str, Any]] = None,
                             access_token: Optional[str] = None, cloud_id: Optional[str] = None) -> Dict[str, Any]:
        """Make API request to Jira"""
        if self._mock_mode:
            return await self._make_mock_request(method, endpoint, params, data, files)
        
        try:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
            
            # Build URL with cloud ID
            if cloud_id:
                base_url = f"https://{cloud_id}.atlassian.net/rest/api/3"
            else:
                base_url = self.api_base_url
            
            url = f"{base_url}/{endpoint.lstrip('/')}"
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                if method.upper() == 'GET':
                    response = await client.get(url, headers=headers, params=params)
                elif method.upper() == 'POST':
                    response = await client.post(url, headers=headers, json=data)
                elif method.upper() == 'PUT':
                    response = await client.put(url, headers=headers, json=data)
                elif method.upper() == 'DELETE':
                    response = await client.delete(url, headers=headers, params=params)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                
                response.raise_for_status()
                
                try:
                    return response.json()
                except json.JSONDecodeError:
                    return {'success': True, 'response': response.text}
                
        except httpx.HTTPError as e:
            logger.error(f"Jira API request error: {e}")
            return {'error': str(e)}
        except Exception as e:
            logger.error(f"Unexpected Jira API request error: {e}")
            return {'error': str(e)}
    
    async def _make_mock_request(self, method: str, endpoint: str, params: Optional[Dict[str, Any]] = None,
                               data: Optional[Dict[str, Any]] = None, files: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make mock API request"""
        # Simulate network delay
        await asyncio.sleep(0.1)
        
        endpoint = endpoint.lower()
        
        # Mock issue operations
        if 'issue/createmeta' in endpoint:
            return {
                'expand': 'projects,issuetypes',
                'projects': [
                    {
                        'id': '10000',
                        'key': 'AT',
                        'name': 'ATOM Platform',
                        'issuetypes': [
                            {
                                'id': '10001',
                                'name': 'Story',
                                'description': 'A user story'
                            },
                            {
                                'id': '10002',
                                'name': 'Task',
                                'description': 'A task that needs to be done'
                            },
                            {
                                'id': '10003',
                                'name': 'Bug',
                                'description': 'A problem which impairs or prevents the functions'
                            }
                        ]
                    }
                ]
            }
        
        elif 'issue/' in endpoint and 'POST' in method.upper():
            if not data:
                return {'error': 'Issue data is required'}
            
            # Create mock issue
            issue_id = f"1000{len(self._mock_db['issues']) + 1}"
            issue_key = f"{data.get('fields', {}).get('project', {}).get('key', 'PRO')}-{len(self._mock_db['issues']) + 1}"
            now = datetime.utcnow().isoformat() + 'Z'
            
            new_issue = JiraIssue({
                'id': issue_id,
                'key': issue_key,
                'fields': {
                    'summary': data.get('fields', {}).get('summary', ''),
                    'description': data.get('fields', {}).get('description', ''),
                    'issuetype': data.get('fields', {}).get('issuetype', {}),
                    'status': {
                        'id': '10002',
                        'name': 'To Do'
                    },
                    'priority': data.get('fields', {}).get('priority', {}),
                    'project': data.get('fields', {}).get('project', {}),
                    'created': now,
                    'updated': now
                }
            })
            
            self._mock_db['issues'].append(new_issue)
            
            return {
                'id': issue_id,
                'key': issue_key,
                'self': f"https://company.atlassian.net/rest/api/latest/issue/{issue_id}"
            }
        
        elif 'search' in endpoint and 'GET' in method.upper():
            # Mock search
            jql = params.get('jql', '') if params else ''
            limit = params.get('maxResults', 50) if params else 50
            
            issues = [issue.to_dict() for issue in self._mock_db['issues']]
            
            # Apply JQL filter (simplified)
            if jql:
                if 'project = AT' in jql:
                    issues = [issue for issue in issues if issue['project']['key'] == 'AT']
                elif 'project = MOB' in jql:
                    issues = [issue for issue in issues if issue['project']['key'] == 'MOB']
                elif 'status in (Done, Closed)' in jql:
                    issues = [issue for issue in issues if issue['status']['name'] in ['Done', 'Closed']]
            
            # Apply limit
            issues = issues[:limit]
            
            return {
                'expand': 'names,schema',
                'startAt': 0,
                'maxResults': limit,
                'total': len(issues),
                'issues': issues
            }
        
        # Mock project operations
        elif 'project' in endpoint and 'GET' in method.upper():
            return {
                'maxResults': 50,
                'startAt': 0,
                'total': len(self._mock_db['projects']),
                'isLast': True,
                'values': [project.to_dict() for project in self._mock_db['projects']]
            }
        
        # Mock board operations
        elif 'board' in endpoint and 'GET' in method.upper():
            return {
                'maxResults': 50,
                'startAt': 0,
                'total': len(self._mock_db['boards']),
                'isLast': True,
                'values': [board.to_dict() for board in self._mock_db['boards']]
            }
        
        # Mock sprint operations
        elif 'sprint' in endpoint and 'GET' in method.upper():
            board_id = params.get('boardId') if params else '1'
            sprints = [sprint.to_dict() for sprint in self._mock_db['sprints']
                      if str(sprint.origin_board_id) == str(board_id)]
            
            return {
                'maxResults': 50,
                'startAt': 0,
                'total': len(sprints),
                'isLast': True,
                'values': sprints
            }
        
        # Mock user operations
        elif 'user/search' in endpoint and 'GET' in method.upper():
            query = params.get('query', '') if params else ''
            limit = params.get('maxResults', 50) if params else 50
            
            users = [user.to_dict() for user in self._mock_db['users']]
            
            # Apply query filter
            if query:
                users = [user for user in users 
                        if query.lower() in user['displayName'].lower() or 
                           query.lower() in user['emailAddress'].lower()]
            
            # Apply limit
            users = users[:limit]
            
            return users
        
        # Default mock response
        return {
            'mock_response': True,
            'endpoint': endpoint,
            'method': method,
            'params': params,
            'data': data
        }
    
    # Issue operations
    async def create_issue(self, user_id: str, project_key: str, summary: str, 
                        issue_type: str, description: str = "", 
                        priority: str = "Medium", assignee: Optional[str] = None,
                        labels: List[str] = None, components: List[str] = None) -> Optional[JiraIssue]:
        """Create a new Jira issue"""
        try:
            access_token = await self._get_user_access_token(user_id)
            cloud_id = await self._get_user_cloud_id(user_id)
            
            if not access_token or not cloud_id:
                logger.error(f"No access token or cloud ID found for user {user_id}")
                return None
            
            data = {
                'fields': {
                    'project': {'key': project_key},
                    'summary': summary,
                    'description': description,
                    'issuetype': {'name': issue_type},
                    'priority': {'name': priority}
                }
            }
            
            if assignee:
                data['fields']['assignee'] = {'accountId': assignee}
            
            if labels:
                data['fields']['labels'] = labels
            
            if components:
                data['fields']['components'] = [{'name': comp} for comp in components]
            
            response = await self._make_api_request('POST', 'issue/', data=data,
                                                access_token=access_token, cloud_id=cloud_id)
            
            if response and not response.get('error'):
                # Get the full issue details
                issue_key = response.get('key')
                if issue_key:
                    issue_details = await self.get_issue(user_id, issue_key)
                    return issue_details
                return None
            else:
                logger.error(f"Error creating Jira issue: {response.get('error')}")
                return None
                
        except Exception as e:
            logger.error(f"Unexpected error creating Jira issue: {e}")
            return None
    
    async def get_issue(self, user_id: str, issue_key: str) -> Optional[JiraIssue]:
        """Get detailed information about a Jira issue"""
        try:
            access_token = await self._get_user_access_token(user_id)
            cloud_id = await self._get_user_cloud_id(user_id)
            
            if not access_token or not cloud_id:
                logger.error(f"No access token or cloud ID found for user {user_id}")
                return None
            
            response = await self._make_api_request('GET', f'issue/{issue_key}',
                                                access_token=access_token, cloud_id=cloud_id)
            
            if response and not response.get('error'):
                return JiraIssue(response)
            else:
                logger.error(f"Error getting Jira issue: {response.get('error')}")
                return None
                
        except Exception as e:
            logger.error(f"Unexpected error getting Jira issue: {e}")
            return None
    
    async def search_issues(self, user_id: str, jql: str, limit: int = 50,
                         start_at: int = 0, fields: List[str] = None) -> List[JiraIssue]:
        """Search for Jira issues using JQL"""
        try:
            access_token = await self._get_user_access_token(user_id)
            cloud_id = await self._get_user_cloud_id(user_id)
            
            if not access_token or not cloud_id:
                logger.error(f"No access token or cloud ID found for user {user_id}")
                return []
            
            params = {
                'jql': jql,
                'startAt': start_at,
                'maxResults': limit,
                'fields': fields or ['*all']  # Get all fields by default
            }
            
            response = await self._make_api_request('GET', 'search', params=params,
                                                access_token=access_token, cloud_id=cloud_id)
            
            if response and 'issues' in response:
                return [JiraIssue(issue) for issue in response['issues']]
            else:
                logger.error(f"Error searching Jira issues: {response.get('error')}")
                return []
                
        except Exception as e:
            logger.error(f"Unexpected error searching Jira issues: {e}")
            return []
    
    async def update_issue(self, user_id: str, issue_key: str, fields: Dict[str, Any]) -> Optional[JiraIssue]:
        """Update a Jira issue"""
        try:
            access_token = await self._get_user_access_token(user_id)
            cloud_id = await self._get_user_cloud_id(user_id)
            
            if not access_token or not cloud_id:
                logger.error(f"No access token or cloud ID found for user {user_id}")
                return None
            
            data = {
                'fields': fields
            }
            
            response = await self._make_api_request('PUT', f'issue/{issue_key}', data=data,
                                                access_token=access_token, cloud_id=cloud_id)
            
            if response and not response.get('error'):
                # Get the updated issue details
                return await self.get_issue(user_id, issue_key)
            else:
                logger.error(f"Error updating Jira issue: {response.get('error')}")
                return None
                
        except Exception as e:
            logger.error(f"Unexpected error updating Jira issue: {e}")
            return None
    
    # Project operations
    async def list_projects(self, user_id: str, limit: int = 50) -> List[JiraProject]:
        """List Jira projects accessible to user"""
        try:
            access_token = await self._get_user_access_token(user_id)
            cloud_id = await self._get_user_cloud_id(user_id)
            
            if not access_token or not cloud_id:
                logger.error(f"No access token or cloud ID found for user {user_id}")
                return []
            
            params = {
                'maxResults': limit
            }
            
            response = await self._make_api_request('GET', 'project', params=params,
                                                access_token=access_token, cloud_id=cloud_id)
            
            if response and 'values' in response:
                return [JiraProject(project) for project in response['values']]
            else:
                logger.error(f"Error listing Jira projects: {response.get('error')}")
                return []
                
        except Exception as e:
            logger.error(f"Unexpected error listing Jira projects: {e}")
            return []
    
    # Board operations
    async def list_boards(self, user_id: str, project_key: Optional[str] = None, 
                        limit: int = 50) -> List[JiraBoard]:
        """List Jira boards"""
        try:
            access_token = await self._get_user_access_token(user_id)
            cloud_id = await self._get_user_cloud_id(user_id)
            
            if not access_token or not cloud_id:
                logger.error(f"No access token or cloud ID found for user {user_id}")
                return []
            
            params = {
                'maxResults': limit
            }
            
            if project_key:
                params['projectKeyOrId'] = project_key
            
            response = await self._make_api_request('GET', 'board', params=params,
                                                access_token=access_token, cloud_id=cloud_id)
            
            if response and 'values' in response:
                return [JiraBoard(board) for board in response['values']]
            else:
                logger.error(f"Error listing Jira boards: {response.get('error')}")
                return []
                
        except Exception as e:
            logger.error(f"Unexpected error listing Jira boards: {e}")
            return []
    
    # Sprint operations
    async def list_sprints(self, user_id: str, board_id: str, 
                        state: Optional[str] = None) -> List[JiraSprint]:
        """List Jira sprints for a board"""
        try:
            access_token = await self._get_user_access_token(user_id)
            cloud_id = await self._get_user_cloud_id(user_id)
            
            if not access_token or not cloud_id:
                logger.error(f"No access token or cloud ID found for user {user_id}")
                return []
            
            params = {
                'boardId': board_id
            }
            
            if state:
                params['state'] = state
            
            response = await self._make_api_request('GET', 'sprint', params=params,
                                                access_token=access_token, cloud_id=cloud_id)
            
            if response and 'values' in response:
                return [JiraSprint(sprint) for sprint in response['values']]
            else:
                logger.error(f"Error listing Jira sprints: {response.get('error')}")
                return []
                
        except Exception as e:
            logger.error(f"Unexpected error listing Jira sprints: {e}")
            return []
    
    # User operations
    async def search_users(self, user_id: str, query: str, limit: int = 50) -> List[JiraUser]:
        """Search for Jira users"""
        try:
            access_token = await self._get_user_access_token(user_id)
            cloud_id = await self._get_user_cloud_id(user_id)
            
            if not access_token or not cloud_id:
                logger.error(f"No access token or cloud ID found for user {user_id}")
                return []
            
            params = {
                'query': query,
                'maxResults': limit
            }
            
            response = await self._make_api_request('GET', 'user/search', params=params,
                                                access_token=access_token, cloud_id=cloud_id)
            
            if response and isinstance(response, list):
                return [JiraUser(user) for user in response]
            else:
                logger.error(f"Error searching Jira users: {response.get('error')}")
                return []
                
        except Exception as e:
            logger.error(f"Unexpected error searching Jira users: {e}")
            return []
    
    def get_service_info(self) -> Dict[str, Any]:
        """Get service information"""
        return {
            'name': 'Enhanced Jira Service',
            'version': '2.0.0',
            'mock_mode': self._mock_mode,
            'api_base_url': self.api_base_url,
            'timeout': self.timeout,
            'capabilities': [
                'Create issues',
                'Update issues',
                'Search issues',
                'List projects',
                'List boards',
                'List sprints',
                'Search users',
                'Get issue details'
            ]
        }

# Create singleton instance
jira_enhanced_service = JiraService()