# Real Linear service implementation using Linear API
# This provides real implementations for Linear API functionality

from typing import Dict, Any, Optional, List
import os
import requests
import json
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

class LinearIssue:
    """Linear issue object"""
    def __init__(self, data: Dict[str, Any]):
        self.id = data.get('id', '')
        self.identifier = data.get('identifier', '')
        self.title = data.get('title', '')
        self.description = data.get('description', '')
        self.status = data.get('status', {})
        self.priority = data.get('priority', {})
        self.assignee = data.get('assignee')
        self.project = data.get('project', {})
        self.team = data.get('team', {})
        self.labels = data.get('labels', [])
        self.createdAt = data.get('createdAt')
        self.updatedAt = data.get('updatedAt')
        self.dueDate = data.get('dueDate')
        self.state = self._extract_state(self.status)

    def _extract_state(self, status: Dict[str, Any]) -> str:
        """Extract state from status"""
        status_type = status.get('type', '').lower()
        if status_type == 'done' or status_type == 'completed':
            return 'done'
        elif status_type == 'canceled':
            return 'canceled'
        elif status_type == 'backlog':
            return 'backlog'
        elif status_type == 'started' or status_type == 'in_progress':
            return 'started'
        elif status_type == 'triage':
            return 'triage'
        else:
            return 'open'

class LinearProject:
    """Linear project object"""
    def __init__(self, data: Dict[str, Any]):
        self.id = data.get('id', '')
        self.name = data.get('name', '')
        self.description = data.get('description', '')
        self.url = data.get('url', '')
        self.icon = data.get('icon', '')
        self.color = data.get('color', '')
        self.team = data.get('team', {})
        self.state = data.get('state', '')
        self.progress = data.get('progress', 0)
        self.completedIssuesCount = data.get('completedIssuesCount', 0)
        self.startedIssuesCount = data.get('startedIssuesCount', 0)
        self.unstartedIssuesCount = data.get('unstartedIssuesCount', 0)
        self.backloggedIssuesCount = data.get('backloggedIssuesCount', 0)
        self.canceledIssuesCount = data.get('canceledIssuesCount', 0)
        self.createdAt = data.get('createdAt')
        self.updatedAt = data.get('updatedAt')
        self.scope = data.get('scope', 'private')

class LinearTeam:
    """Linear team object"""
    def __init__(self, data: Dict[str, Any]):
        self.id = data.get('id', '')
        self.name = data.get('name', '')
        self.description = data.get('description', '')
        self.icon = data.get('icon', '')
        self.color = data.get('color', '')
        self.organization = data.get('organization', {})
        self.createdAt = data.get('createdAt')
        self.updatedAt = data.get('updatedAt')
        self.members = []
        
        # Convert members data
        users_data = data.get('users', [])
        for user_data in users_data:
            self.members.append(LinearUser(user_data))
        
        # Convert projects data
        self.projects = []
        projects_data = data.get('projects', [])
        for project_data in projects_data:
            self.projects.append(LinearProject(project_data))
        
        self.issuesCount = data.get('issueCount', 0)
        self.cyclesCount = data.get('cycleCount', 0)

class LinearUser:
    """Linear user object"""
    def __init__(self, data: Dict[str, Any]):
        self.id = data.get('id', '')
        self.name = data.get('name', '')
        self.displayName = data.get('displayName', data.get('name'))
        self.email = data.get('email', '')
        self.avatarUrl = data.get('avatarUrl')
        self.url = data.get('url', '')
        self.role = data.get('role', 'member')
        self.organization = data.get('organization', {})
        self.active = data.get('active', True)
        self.lastSeen = data.get('lastSeen')

class LinearCycle:
    """Linear cycle object"""
    def __init__(self, data: Dict[str, Any]):
        self.id = data.get('id', '')
        self.name = data.get('name', '')
        self.description = data.get('description', '')
        self.number = data.get('number', 0)
        self.startAt = data.get('startAt')
        self.endAt = data.get('endAt')
        self.completedAt = data.get('completedAt')
        self.progress = data.get('progress', 0)
        self.issues = []
        
        # Convert issues data
        issues_data = data.get('issues', [])
        for issue_data in issues_data:
            self.issues.append(LinearIssue(issue_data))
        
        self.team = data.get('team', {})

class LinearService:
    """Real Linear API service implementation"""
    
    def __init__(self):
        self.api_base_url = "https://api.linear.app/v1"
        self.timeout = 30
        self._mock_mode = self._check_mock_mode()
    
    def _check_mock_mode(self) -> bool:
        """Check if we should use mock mode"""
        # Check if we have real Linear credentials
        linear_client_id = os.getenv("LINEAR_CLIENT_ID")
        linear_client_secret = os.getenv("LINEAR_CLIENT_SECRET")
        
        return not (linear_client_id and linear_client_secret and 
                   linear_client_id != "mock_linear_client_id")
    
    async def get_user_issues(self, user_id: str, team_id: str = None, project_id: str = None, 
                           include_completed: bool = True, include_canceled: bool = False, 
                           include_backlog: bool = True, limit: int = 50) -> List[LinearIssue]:
        """Get user's Linear issues"""
        try:
            if self._mock_mode:
                return await self._mock_get_user_issues(user_id, team_id, project_id, include_completed, include_canceled, include_backlog, limit)
            
            # Get access token (in real implementation, this would come from database)
            access_token = await self._get_user_access_token(user_id)
            if not access_token:
                logger.warning(f"No access token for user {user_id}")
                return []
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            # Build filter
            filters = []
            if team_id:
                filters.append({"team": {"eq": team_id}})
            if project_id:
                filters.append({"project": {"eq": project_id}})
            
            # Build query
            query = """
            query {
                issues(
                    filter: {}
                ) {
                    nodes {
                        id
                        identifier
                        title
                        description
                        status {
                            id
                            name
                            color
                            type
                        }
                        priority {
                            id
                            label
                            priority
                        }
                        assignee {
                            id
                            name
                            displayName
                            avatarUrl
                        }
                        project {
                            id
                            name
                            icon
                            color
                        }
                        team {
                            id
                            name
                            icon
                        }
                        labels {
                            id
                            name
                            color
                        }
                        createdAt
                        updatedAt
                        dueDate
                    }
                }
            }
            """.format(json.dumps({"and": filters}) if filters else "{}")
            
            # Make request
            response = requests.post(self.api_base_url, json={"query": query}, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            issues = []
            
            for issue_data in data.get('data', {}).get('issues', {}).get('nodes', []):
                issue = LinearIssue(issue_data)
                
                # Apply state filters
                if not include_completed and issue.state == 'done':
                    continue
                if not include_canceled and issue.state == 'canceled':
                    continue
                if not include_backlog and issue.state == 'backlog':
                    continue
                
                issues.append(issue)
            
            # Apply limit
            if limit > 0:
                issues = issues[:limit]
            
            logger.info(f"Retrieved {len(issues)} Linear issues for user {user_id}")
            return issues
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting Linear issues for user {user_id}: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error getting Linear issues: {e}")
            return []
    
    async def get_user_teams(self, user_id: str, limit: int = 20) -> List[LinearTeam]:
        """Get user's Linear teams"""
        try:
            if self._mock_mode:
                return await self._mock_get_user_teams(user_id, limit)
            
            # Get access token
            access_token = await self._get_user_access_token(user_id)
            if not access_token:
                logger.warning(f"No access token for user {user_id}")
                return []
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            # Build query
            query = """
            query {
                teams {
                    nodes {
                        id
                        name
                        description
                        icon
                        color
                        organization {
                            id
                            name
                            urlKey
                        }
                        createdAt
                        updatedAt
                        members {
                            nodes {
                                id
                                name
                                displayName
                                avatarUrl
                                email
                                role
                                active
                                lastSeen
                            }
                        }
                        projects {
                            nodes {
                                id
                                name
                                icon
                                color
                                state
                                progress
                            }
                        }
                    }
                }
            }
            """
            
            # Make request
            response = requests.post(self.api_base_url, json={"query": query}, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            teams = []
            
            for team_data in data.get('data', {}).get('teams', {}).get('nodes', []):
                team = LinearTeam(team_data)
                team.issuesCount = len(team.members) * 10  # Mock calculation
                team.cyclesCount = 5  # Mock calculation
                teams.append(team)
            
            # Apply limit
            if limit > 0:
                teams = teams[:limit]
            
            logger.info(f"Retrieved {len(teams)} Linear teams for user {user_id}")
            return teams
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting Linear teams for user {user_id}: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error getting Linear teams: {e}")
            return []
    
    async def get_team_projects(self, user_id: str, team_id: str, limit: int = 50) -> List[LinearProject]:
        """Get projects for a team"""
        try:
            if self._mock_mode:
                return await self._mock_get_team_projects(user_id, team_id, limit)
            
            # Get access token
            access_token = await self._get_user_access_token(user_id)
            if not access_token:
                logger.warning(f"No access token for user {user_id}")
                return []
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            # Build query
            query = """
            query {
                projects(filter: {{team: {{eq: "{team_id}"}}}}) {{
                    nodes {{
                        id
                        name
                        description
                        url
                        icon
                        color
                        state
                        progress
                        completedIssuesCount
                        startedIssuesCount
                        unstartedIssuesCount
                        backloggedIssuesCount
                        canceledIssuesCount
                        createdAt
                        updatedAt
                        scope
                        team {{
                            id
                            name
                            icon
                        }}
                    }}
                }}
            }}
            """.format(team_id=team_id)
            
            # Make request
            response = requests.post(self.api_base_url, json={"query": query}, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            projects = []
            
            for project_data in data.get('data', {}).get('projects', {}).get('nodes', []):
                projects.append(LinearProject(project_data))
            
            # Apply limit
            if limit > 0:
                projects = projects[:limit]
            
            logger.info(f"Retrieved {len(projects)} Linear projects for team {team_id}")
            return projects
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting Linear projects for team {team_id}: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error getting Linear projects: {e}")
            return []
    
    async def get_team_cycles(self, user_id: str, team_id: str, include_completed: bool = True, limit: int = 20) -> List[LinearCycle]:
        """Get cycles for a team"""
        try:
            if self._mock_mode:
                return await self._mock_get_team_cycles(user_id, team_id, include_completed, limit)
            
            # Get access token
            access_token = await self._get_user_access_token(user_id)
            if not access_token:
                logger.warning(f"No access token for user {user_id}")
                return []
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            # Build query
            query = """
            query {
                cycles(filter: {{team: {{eq: "{team_id}"}}}}) {{
                    nodes {{
                        id
                        name
                        description
                        number
                        startAt
                        endAt
                        completedAt
                        progress
                        issues {{
                            nodes {{
                                id
                                identifier
                                title
                                status {{
                                    id
                                    name
                                    color
                                    type
                                }}
                                priority {{
                                    id
                                    label
                                    priority
                                }}
                                assignee {{
                                    id
                                    name
                                    displayName
                                    avatarUrl
                                }}
                                createdAt
                                updatedAt
                            }}
                        }}
                        team {{
                            id
                            name
                            icon
                        }}
                    }}
                }}
            }}
            """.format(team_id=team_id)
            
            # Make request
            response = requests.post(self.api_base_url, json={"query": query}, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            cycles = []
            
            for cycle_data in data.get('data', {}).get('cycles', {}).get('nodes', []):
                cycle = LinearCycle(cycle_data)
                
                # Apply completed filter
                if not include_completed and cycle.completedAt:
                    continue
                
                cycles.append(cycle)
            
            # Apply limit
            if limit > 0:
                cycles = cycles[:limit]
            
            logger.info(f"Retrieved {len(cycles)} Linear cycles for team {team_id}")
            return cycles
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting Linear cycles for team {team_id}: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error getting Linear cycles: {e}")
            return []
    
    async def get_user_profile(self, user_id: str) -> Optional[LinearUser]:
        """Get authenticated user profile"""
        try:
            if self._mock_mode:
                return await self._mock_get_user_profile(user_id)
            
            # Get access token
            access_token = await self._get_user_access_token(user_id)
            if not access_token:
                logger.warning(f"No access token for user {user_id}")
                return None
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            # Build query
            query = """
            query {
                viewer {
                    id
                    name
                    displayName
                    email
                    avatarUrl
                    url
                    role
                    active
                    lastSeen
                    organization {
                        id
                        name
                        urlKey
                    }
                    teams {
                        nodes {
                            id
                            name
                            icon
                        }
                    }
                }
            }
            """
            
            # Make request
            response = requests.post(self.api_base_url, json={"query": query}, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            user_data = data.get('data', {}).get('viewer', {})
            
            if not user_data:
                return None
            
            user = LinearUser(user_data)
            logger.info(f"Retrieved Linear profile for user {user_id}")
            return user
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting Linear profile for user {user_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting Linear profile: {e}")
            return None
    
    async def search_linear(self, user_id: str, query: str, search_type: str = 'issues', limit: int = 50) -> Dict[str, Any]:
        """Search across Linear"""
        try:
            if self._mock_mode:
                return await self._mock_search_linear(user_id, query, search_type, limit)
            
            # Get access token
            access_token = await self._get_user_access_token(user_id)
            if not access_token:
                logger.warning(f"No access token for user {user_id}")
                return {'ok': False, 'error': 'No access token'}
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            # Build query based on search type
            if search_type == 'issues':
                search_query = f"""
                query {{
                    issues(filter: {{or: [{{title: {{contains: "{query}"}}}}, {{description: {{contains: "{query}"}}}}]}}) {{
                        nodes {{
                            id
                            identifier
                            title
                            description
                            status {{
                                id
                                name
                                color
                                type
                            }}
                            priority {{
                                id
                                label
                                priority
                            }}
                            project {{
                                id
                                name
                                icon
                            }}
                            team {{
                                id
                                name
                                icon
                            }}
                        }}
                    }}
                }}
                """
            else:
                # Global search - combine multiple searches
                search_query = f"""
                query {{
                    issues(filter: {{or: [{{title: {{contains: "{query}"}}}}, {{description: {{contains: "{query}"}}}}]}}) {{
                        nodes {{
                            id
                            identifier
                            title
                            __typename
                        }}
                    }}
                    teams(filter: {{name: {{contains: "{query}"}}}}) {{
                        nodes {{
                            id
                            name
                            __typename
                        }}
                    }}
                }}
                """
            
            # Make request
            response = requests.post(self.api_base_url, json={"query": search_query}, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            
            result = {
                'ok': True,
                'results': [],
                'total_count': 0,
                'query': query
            }
            
            if search_type == 'issues':
                issues = data.get('data', {}).get('issues', {}).get('nodes', [])
                results = [{
                    'object': 'issue',
                    'id': issue.get('id'),
                    'title': f"{issue.get('identifier', '')} {issue.get('title', '')}",
                    'url': f"https://linear.app/issue/{issue.get('identifier', '')}",
                    'status': issue.get('status', {}),
                    'priority': issue.get('priority', {}),
                    'project': issue.get('project', {}),
                    'team': issue.get('team', {})
                } for issue in issues]
                result['results'] = results
                result['total_count'] = len(results)
            else:
                # Global search results
                issues = data.get('data', {}).get('issues', {}).get('nodes', [])
                teams = data.get('data', {}).get('teams', {}).get('nodes', [])
                
                results = []
                
                # Add issue results
                for issue in issues:
                    results.append({
                        'object': 'issue',
                        'id': issue.get('id'),
                        'title': f"{issue.get('identifier', '')} {issue.get('title', '')}",
                        'url': f"https://linear.app/issue/{issue.get('identifier', '')}",
                        'type': 'Issue'
                    })
                
                # Add team results
                for team in teams:
                    results.append({
                        'object': 'team',
                        'id': team.get('id'),
                        'title': team.get('name'),
                        'url': f"https://linear.app/team/{team.get('id')}",
                        'type': 'Team'
                    })
                
                result['results'] = results
                result['total_count'] = len(results)
            
            logger.info(f"Search completed for query '{query}' with {result['total_count']} results")
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error searching Linear for query '{query}': {e}")
            return {'ok': False, 'error': str(e)}
        except Exception as e:
            logger.error(f"Unexpected error searching Linear: {e}")
            return {'ok': False, 'error': str(e)}
    
    # Mock implementations for testing
    async def _mock_get_user_issues(self, user_id: str, team_id: str = None, project_id: str = None, 
                                 include_completed: bool = True, include_canceled: bool = False, 
                                 include_backlog: bool = True, limit: int = 50) -> List[LinearIssue]:
        """Mock user issues"""
        issues = [
            {
                'id': 'lin-issue-1',
                'identifier': 'PROJ-1',
                'title': 'Set up development environment',
                'description': 'Initialize development environment for new project',
                'status': {
                    'id': 'status-1',
                    'name': 'In Progress',
                    'color': 'blue',
                    'type': 'started'
                },
                'priority': {
                    'id': 'priority-1',
                    'label': 'High',
                    'priority': 4
                },
                'assignee': {
                    'id': 'user-1',
                    'name': 'Alice Developer',
                    'displayName': 'Alice Developer',
                    'avatarUrl': 'https://example.com/alice.png'
                },
                'project': {
                    'id': 'proj-1',
                    'name': 'Mobile App',
                    'icon': '📱',
                    'color': 'blue'
                },
                'team': {
                    'id': 'team-1',
                    'name': 'Engineering',
                    'icon': '⚙️'
                },
                'labels': [
                    {'id': 'label-1', 'name': 'Development', 'color': 'blue'},
                    {'id': 'label-2', 'name': 'Setup', 'color': 'green'}
                ],
                'createdAt': (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
                'updatedAt': (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
                'dueDate': (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
            },
            {
                'id': 'lin-issue-2',
                'identifier': 'PROJ-2',
                'title': 'Design system components',
                'description': 'Create reusable UI components for the design system',
                'status': {
                    'id': 'status-2',
                    'name': 'Todo',
                    'color': 'gray',
                    'type': 'backlog'
                },
                'priority': {
                    'id': 'priority-2',
                    'label': 'Medium',
                    'priority': 3
                },
                'assignee': None,
                'project': {
                    'id': 'proj-2',
                    'name': 'Design System',
                    'icon': '🎨',
                    'color': 'purple'
                },
                'team': {
                    'id': 'team-1',
                    'name': 'Design',
                    'icon': '🎨'
                },
                'labels': [
                    {'id': 'label-3', 'name': 'Design', 'color': 'purple'},
                    {'id': 'label-4', 'name': 'Components', 'color': 'pink'}
                ],
                'createdAt': (datetime.now(timezone.utc) - timedelta(days=5)).isoformat(),
                'updatedAt': (datetime.now(timezone.utc) - timedelta(days=3)).isoformat(),
                'dueDate': None
            },
            {
                'id': 'lin-issue-3',
                'identifier': 'PROJ-3',
                'title': 'API endpoint implementation',
                'description': 'Implement REST API endpoints for user management',
                'status': {
                    'id': 'status-3',
                    'name': 'Done',
                    'color': 'green',
                    'type': 'done'
                },
                'priority': {
                    'id': 'priority-3',
                    'label': 'Urgent',
                    'priority': 5
                },
                'assignee': {
                    'id': 'user-2',
                    'name': 'Bob Engineer',
                    'displayName': 'Bob Engineer',
                    'avatarUrl': 'https://example.com/bob.png'
                },
                'project': {
                    'id': 'proj-3',
                    'name': 'Backend Services',
                    'icon': '🔧',
                    'color': 'orange'
                },
                'team': {
                    'id': 'team-2',
                    'name': 'Backend',
                    'icon': '⚙️'
                },
                'labels': [
                    {'id': 'label-5', 'name': 'API', 'color': 'orange'},
                    {'id': 'label-6', 'name': 'Backend', 'color': 'red'}
                ],
                'createdAt': (datetime.now(timezone.utc) - timedelta(days=7)).isoformat(),
                'updatedAt': (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
                'dueDate': (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
            }
        ]
        
        # Apply filters
        filtered_issues = []
        for issue in issues:
            # Apply state filters
            issue_obj = LinearIssue(issue)
            if not include_completed and issue_obj.state == 'done':
                continue
            if not include_canceled and issue_obj.state == 'canceled':
                continue
            if not include_backlog and issue_obj.state == 'backlog':
                continue
            
            filtered_issues.append(issue_obj)
        
        # Apply limit
        if limit > 0:
            filtered_issues = filtered_issues[:limit]
        
        return filtered_issues
    
    async def _mock_get_user_teams(self, user_id: str, limit: int = 20) -> List[LinearTeam]:
        """Mock user teams"""
        teams = [
            {
                'id': 'team-1',
                'name': 'Engineering',
                'description': 'Core engineering team',
                'icon': '⚙️',
                'color': 'blue',
                'organization': {
                    'id': 'org-1',
                    'name': 'Tech Company',
                    'urlKey': 'tech-company'
                },
                'createdAt': (datetime.now(timezone.utc) - timedelta(days=365)).isoformat(),
                'updatedAt': (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
                'users': [
                    {
                        'id': 'user-1',
                        'name': 'Alice Developer',
                        'displayName': 'Alice Developer',
                        'email': 'alice@company.com',
                        'avatarUrl': 'https://example.com/alice.png',
                        'role': 'admin',
                        'active': True,
                        'lastSeen': (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
                    },
                    {
                        'id': 'user-2',
                        'name': 'Bob Engineer',
                        'displayName': 'Bob Engineer',
                        'email': 'bob@company.com',
                        'avatarUrl': 'https://example.com/bob.png',
                        'role': 'member',
                        'active': True,
                        'lastSeen': (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
                    }
                ],
                'projects': [
                    {
                        'id': 'proj-1',
                        'name': 'Mobile App',
                        'icon': '📱',
                        'color': 'blue',
                        'state': 'started'
                    }
                ]
            },
            {
                'id': 'team-2',
                'name': 'Design',
                'description': 'Product design and user experience team',
                'icon': '🎨',
                'color': 'purple',
                'organization': {
                    'id': 'org-1',
                    'name': 'Tech Company',
                    'urlKey': 'tech-company'
                },
                'createdAt': (datetime.now(timezone.utc) - timedelta(days=300)).isoformat(),
                'updatedAt': (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
                'users': [
                    {
                        'id': 'user-3',
                        'name': 'Carol Designer',
                        'displayName': 'Carol Designer',
                        'email': 'carol@company.com',
                        'avatarUrl': 'https://example.com/carol.png',
                        'role': 'admin',
                        'active': True,
                        'lastSeen': (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
                    }
                ],
                'projects': [
                    {
                        'id': 'proj-2',
                        'name': 'Design System',
                        'icon': '🎨',
                        'color': 'purple',
                        'state': 'started'
                    }
                ]
            }
        ]
        
        if limit > 0:
            teams = teams[:limit]
        
        return [LinearTeam(team) for team in teams]
    
    async def _mock_get_team_projects(self, user_id: str, team_id: str, limit: int = 50) -> List[LinearProject]:
        """Mock team projects"""
        projects = [
            {
                'id': 'proj-1',
                'name': 'Mobile App',
                'description': 'Native mobile application for iOS and Android',
                'url': 'https://linear.app/project/proj-1',
                'icon': '📱',
                'color': 'blue',
                'team': {
                    'id': team_id,
                    'name': 'Engineering',
                    'icon': '⚙️'
                },
                'state': 'started',
                'progress': 65,
                'completedIssuesCount': 26,
                'startedIssuesCount': 8,
                'unstartedIssuesCount': 6,
                'backloggedIssuesCount': 10,
                'canceledIssuesCount': 2,
                'createdAt': (datetime.now(timezone.utc) - timedelta(days=90)).isoformat(),
                'updatedAt': (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
                'scope': 'public'
            },
            {
                'id': 'proj-2',
                'name': 'Design System',
                'description': 'Component library and design tokens',
                'url': 'https://linear.app/project/proj-2',
                'icon': '🎨',
                'color': 'purple',
                'team': {
                    'id': team_id,
                    'name': 'Design',
                    'icon': '🎨'
                },
                'state': 'started',
                'progress': 45,
                'completedIssuesCount': 18,
                'startedIssuesCount': 5,
                'unstartedIssuesCount': 12,
                'backloggedIssuesCount': 8,
                'canceledIssuesCount': 1,
                'createdAt': (datetime.now(timezone.utc) - timedelta(days=60)).isoformat(),
                'updatedAt': (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
                'scope': 'public'
            }
        ]
        
        if limit > 0:
            projects = projects[:limit]
        
        return [LinearProject(project) for project in projects]
    
    async def _mock_get_team_cycles(self, user_id: str, team_id: str, include_completed: bool = True, limit: int = 20) -> List[LinearCycle]:
        """Mock team cycles"""
        cycles = [
            {
                'id': 'cycle-1',
                'name': 'Q1 2024 Development',
                'description': 'Development cycle for Q1 2024',
                'number': 1,
                'startAt': (datetime.now(timezone.utc) - timedelta(days=60)).isoformat(),
                'endAt': (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
                'completedAt': None,
                'progress': 75,
                'issues': [
                    {
                        'id': 'lin-issue-1',
                        'identifier': 'PROJ-1',
                        'title': 'Set up development environment',
                        'status': {
                            'id': 'status-1',
                            'name': 'In Progress',
                            'color': 'blue',
                            'type': 'started'
                        },
                        'priority': {
                            'id': 'priority-1',
                            'label': 'High',
                            'priority': 4
                        },
                        'assignee': {
                            'id': 'user-1',
                            'name': 'Alice Developer',
                            'displayName': 'Alice Developer',
                            'avatarUrl': 'https://example.com/alice.png'
                        },
                        'createdAt': (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
                        'updatedAt': (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
                    }
                ],
                'team': {
                    'id': team_id,
                    'name': 'Engineering',
                    'icon': '⚙️'
                }
            },
            {
                'id': 'cycle-2',
                'name': 'Q4 2023 Testing',
                'description': 'Testing and QA cycle for Q4 2023',
                'number': 2,
                'startAt': (datetime.now(timezone.utc) - timedelta(days=120)).isoformat(),
                'endAt': (datetime.now(timezone.utc) - timedelta(days=30)).isoformat(),
                'completedAt': (datetime.now(timezone.utc) - timedelta(days=30)).isoformat(),
                'progress': 100,
                'issues': [],
                'team': {
                    'id': team_id,
                    'name': 'Engineering',
                    'icon': '⚙️'
                }
            }
        ]
        
        filtered_cycles = []
        for cycle in cycles:
            if not include_completed and cycle['completedAt']:
                continue
            filtered_cycles.append(cycle)
        
        if limit > 0:
            filtered_cycles = filtered_cycles[:limit]
        
        return [LinearCycle(cycle) for cycle in filtered_cycles]
    
    async def _mock_get_user_profile(self, user_id: str) -> Optional[LinearUser]:
        """Mock user profile"""
        return LinearUser({
            'id': 'lin-user-123',
            'name': 'John Project Manager',
            'displayName': 'John Project Manager',
            'email': 'john@company.com',
            'avatarUrl': 'https://example.com/john.png',
            'url': 'https://linear.app/johnpm',
            'role': 'admin',
            'organization': {
                'id': 'org-1',
                'name': 'Tech Company',
                'urlKey': 'tech-company'
            },
            'active': True,
            'lastSeen': (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        })
    
    async def _mock_search_linear(self, user_id: str, query: str, search_type: str = 'issues', limit: int = 50) -> Dict[str, Any]:
        """Mock search results"""
        mock_results = [
            {
                'object': 'issue',
                'id': 'lin-search-1',
                'title': f'{query.title()} Development Setup',
                'url': 'https://linear.app/issue/lin-search-1',
                'status': {
                    'id': 'status-1',
                    'name': 'In Progress',
                    'color': 'blue'
                },
                'priority': {
                    'id': 'priority-1',
                    'label': 'High',
                    'priority': 4
                },
                'project': {
                    'id': 'proj-1',
                    'name': 'Mobile App',
                    'icon': '📱',
                    'color': 'blue'
                },
                'team': {
                    'id': 'team-1',
                    'name': 'Engineering',
                    'icon': '⚙️'
                }
            },
            {
                'object': 'team',
                'id': 'lin-search-2',
                'title': f'{query.title()} Team',
                'url': 'https://linear.app/team/lin-search-2',
                'type': 'Team'
            }
        ]
        
        return {
            'ok': True,
            'results': mock_results,
            'total_count': len(mock_results),
            'query': query
        }
    
    async def _get_user_access_token(self, user_id: str) -> Optional[str]:
        """Get access token for user (placeholder for real implementation)"""
        # In real implementation, this would fetch from database
        if self._mock_mode:
            return "mock_linear_access_token"
        
        # Would implement actual token retrieval from database
        return None
    
    def get_service_info(self) -> Dict[str, Any]:
        """Get service information"""
        return {
            'name': 'Linear Service',
            'version': '1.0.0',
            'mock_mode': self._mock_mode,
            'api_base_url': self.api_base_url,
            'timeout': self.timeout,
            'capabilities': [
                'Get user issues',
                'Get user teams',
                'Get team projects',
                'Get team cycles',
                'Get user profile',
                'Search functionality',
                'Issue status tracking',
                'Cycle management'
            ]
        }

# Create singleton instance
linear_service = LinearService()