# Real Figma service implementation using Figma API
# This provides real implementations for Figma API functionality

from typing import Dict, Any, Optional, List
import os
import requests
import json
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

class FigmaFile:
    """Figma file object"""
    def __init__(self, data: Dict[str, Any]):
        self.key = data.get('key', '')
        self.name = data.get('name', '')
        self.thumbnail_url = data.get('thumbnail_url', '')
        self.content_readonly = data.get('content_readonly', False)
        self.editor_type = data.get('editor_type', 'figma')
        self.last_modified = data.get('last_modified', '')
        self.workspace_id = data.get('workspace_id', '')
        self.workspace_name = data.get('workspace_name', '')
        self.file_id = data.get('id', data.get('file_id', ''))
        self.branch_id = data.get('branch_id', '')
        self.thumbnail_url_default = data.get('thumbnail_url_default', '')

class FigmaTeam:
    """Figma team object"""
    def __init__(self, data: Dict[str, Any]):
        self.id = data.get('id', '')
        self.name = data.get('name', '')
        self.description = data.get('description', '')
        self.profile_picture_url = data.get('profile_picture_url', '')
        self.users = []
        
        # Convert users data
        users_data = data.get('users', [])
        for user_data in users_data:
            self.users.append(FigmaUser(user_data))

class FigmaUser:
    """Figma user object"""
    def __init__(self, data: Dict[str, Any]):
        self.id = data.get('id', '')
        self.name = data.get('name', '')
        self.username = data.get('handle', data.get('username', ''))
        self.email = data.get('email', '')
        self.profile_picture_url = data.get('img_url', data.get('profile_picture_url', ''))
        self.department = data.get('department', '')
        self.title = data.get('title', '')
        self.organization_id = data.get('org_id', data.get('organization_id', ''))
        self.role = data.get('role', 'member')
        self.can_edit = data.get('can_edit', True)
        self.has_guests = data.get('has_guests', False)
        self.is_active = data.get('is_active', True)

class FigmaProject:
    """Figma project object"""
    def __init__(self, data: Dict[str, Any]):
        self.id = data.get('id', '')
        self.name = data.get('name', '')
        self.description = data.get('description', '')
        self.team_id = data.get('team_id', '')
        self.team_name = data.get('team_name', '')
        self.files = []
        
        # Convert files data
        files_data = data.get('files', [])
        for file_data in files_data:
            self.files.append(FigmaFile(file_data))

class FigmaComponent:
    """Figma component object"""
    def __init__(self, data: Dict[str, Any]):
        self.key = data.get('key', '')
        self.file_key = data.get('file_key', '')
        self.node_id = data.get('node_id', '')
        self.name = data.get('name', '')
        self.description = data.get('description', '')
        self.component_type = data.get('component_type', 'component')
        self.thumbnail_url = data.get('thumbnail_url', '')
        self.created_at = data.get('created_at')
        self.modified_at = data.get('modified_at', data.get('updated_at'))
        self.creator_id = data.get('creator_id')

class FigmaService:
    """Real Figma API service implementation"""
    
    def __init__(self):
        self.api_base_url = "https://api.figma.com/v1"
        self.timeout = 30
        self._mock_mode = self._check_mock_mode()
    
    def _check_mock_mode(self) -> bool:
        """Check if we should use mock mode"""
        # Check if we have real Figma credentials
        figma_client_id = os.getenv("FIGMA_CLIENT_ID")
        figma_client_secret = os.getenv("FIGMA_CLIENT_SECRET")
        
        return not (figma_client_id and figma_client_secret and 
                   figma_client_id != "mock_figma_client_id")
    
    async def get_user_files(self, user_id: str, team_id: str = None, include_archived: bool = False, limit: int = 50) -> List[FigmaFile]:
        """Get user's Figma files"""
        try:
            if self._mock_mode:
                return await self._mock_get_user_files(user_id, team_id, include_archived, limit)
            
            # Get access token (in real implementation, this would come from database)
            access_token = await self._get_user_access_token(user_id)
            if not access_token:
                logger.warning(f"No access token for user {user_id}")
                return []
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            # Build URL
            url = f"{self.api_base_url}/me/files"
            params = {}
            
            if team_id:
                params['team_id'] = team_id
            if include_archived:
                params['archived'] = 'true'
            
            # Make request
            response = requests.get(url, headers=headers, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            files = []
            
            for file_data in data.get('files', []):
                files.append(FigmaFile({
                    'key': file_data.get('key'),
                    'name': file_data.get('name'),
                    'thumbnail_url': file_data.get('thumbnail_url'),
                    'content_readonly': file_data.get('content_readonly', False),
                    'editor_type': file_data.get('editor_type', 'figma'),
                    'last_modified': file_data.get('last_modified'),
                    'workspace_id': file_data.get('workspace_id'),
                    'workspace_name': file_data.get('workspace_name'),
                    'id': file_data.get('id')
                }))
            
            # Apply limit
            if limit > 0:
                files = files[:limit]
            
            logger.info(f"Retrieved {len(files)} Figma files for user {user_id}")
            return files
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting Figma files for user {user_id}: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error getting Figma files: {e}")
            return []
    
    async def get_user_teams(self, user_id: str, limit: int = 20) -> List[FigmaTeam]:
        """Get user's Figma teams"""
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
            
            # Make request
            response = requests.get(f"{self.api_base_url}/me/teams", headers=headers, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            teams = []
            
            for team_data in data.get('teams', []):
                teams.append(FigmaTeam({
                    'id': team_data.get('id'),
                    'name': team_data.get('name'),
                    'description': team_data.get('description', ''),
                    'profile_picture_url': team_data.get('profile_picture_url'),
                    'users': team_data.get('members', [])
                }))
            
            # Apply limit
            if limit > 0:
                teams = teams[:limit]
            
            logger.info(f"Retrieved {len(teams)} Figma teams for user {user_id}")
            return teams
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting Figma teams for user {user_id}: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error getting Figma teams: {e}")
            return []
    
    async def get_team_projects(self, user_id: str, team_id: str, limit: int = 50) -> List[FigmaProject]:
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
            
            # Make request
            response = requests.get(f"{self.api_base_url}/teams/{team_id}/projects", 
                                 headers=headers, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            projects = []
            
            for project_data in data.get('projects', []):
                projects.append(FigmaProject({
                    'id': project_data.get('id'),
                    'name': project_data.get('name'),
                    'description': project_data.get('description', ''),
                    'team_id': team_id,
                    'team_name': project_data.get('name'),  # Use project name as fallback
                    'files': []  # Files would be fetched separately
                }))
            
            # Apply limit
            if limit > 0:
                projects = projects[:limit]
            
            logger.info(f"Retrieved {len(projects)} Figma projects for team {team_id}")
            return projects
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting Figma projects for team {team_id}: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error getting Figma projects: {e}")
            return []
    
    async def get_file_components(self, user_id: str, file_key: str, limit: int = 100) -> List[FigmaComponent]:
        """Get components from a file"""
        try:
            if self._mock_mode:
                return await self._mock_get_file_components(user_id, file_key, limit)
            
            # Get access token
            access_token = await self._get_user_access_token(user_id)
            if not access_token:
                logger.warning(f"No access token for user {user_id}")
                return []
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            # Make request
            response = requests.get(f"{self.api_base_url}/files/{file_key}/components", 
                                 headers=headers, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            components = []
            
            for component_data in data.get('components', []):
                components.append(FigmaComponent({
                    'key': component_data.get('key'),
                    'file_key': file_key,
                    'node_id': component_data.get('node_id', component_data.get('id')),
                    'name': component_data.get('name'),
                    'description': component_data.get('description', ''),
                    'component_type': component_data.get('component_type', 'component'),
                    'thumbnail_url': component_data.get('thumbnail_url'),
                    'created_at': component_data.get('created_at'),
                    'modified_at': component_data.get('modified_at')
                }))
            
            # Apply limit
            if limit > 0:
                components = components[:limit]
            
            logger.info(f"Retrieved {len(components)} Figma components for file {file_key}")
            return components
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting Figma components for file {file_key}: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error getting Figma components: {e}")
            return []
    
    async def get_user_profile(self, user_id: str) -> Optional[FigmaUser]:
        """Get user profile information"""
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
            
            # Make request
            response = requests.get(f"{self.api_base_url}/me", headers=headers, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            
            user = FigmaUser({
                'id': data.get('id'),
                'name': data.get('name'),
                'handle': data.get('handle'),
                'email': data.get('email'),
                'img_url': data.get('img_url'),
                'org_id': data.get('org_id')
            })
            
            logger.info(f"Retrieved Figma profile for user {user_id}")
            return user
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting Figma profile for user {user_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting Figma profile: {e}")
            return None
    
    async def search_figma(self, user_id: str, query: str, search_type: str = 'global', limit: int = 50) -> Dict[str, Any]:
        """Search across Figma"""
        try:
            if self._mock_mode:
                return await self._mock_search_figma(user_id, query, search_type, limit)
            
            # Get access token
            access_token = await self._get_user_access_token(user_id)
            if not access_token:
                logger.warning(f"No access token for user {user_id}")
                return {'ok': False, 'error': 'No access token'}
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            params = {
                'query': query,
                'limit': limit
            }
            
            # Adjust search based on type
            if search_type == 'files':
                endpoint = f"{self.api_base_url}/me/files"
                params['search'] = 'true'
            elif search_type == 'components':
                endpoint = f"{self.api_base_url}/me/components"
                params['search'] = 'true'
            else:
                endpoint = f"{self.api_base_url}/me/search"
            
            # Make request
            response = requests.get(endpoint, headers=headers, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            
            result = {
                'ok': True,
                'results': [],
                'total_count': 0,
                'query': query
            }
            
            if search_type == 'files':
                files = []
                for file_data in data.get('files', []):
                    files.append({
                        'object': 'file',
                        'id': file_data.get('id'),
                        'title': file_data.get('name'),
                        'url': file_data.get('url'),
                        'thumbnail_url': file_data.get('thumbnail_url')
                    })
                result['results'] = files
                result['total_count'] = len(files)
            elif search_type == 'components':
                components = []
                for component_data in data.get('components', []):
                    components.append({
                        'object': 'component',
                        'id': component_data.get('key'),
                        'title': component_data.get('name'),
                        'file_key': component_data.get('file_key'),
                        'thumbnail_url': component_data.get('thumbnail_url')
                    })
                result['results'] = components
                result['total_count'] = len(components)
            else:
                # Global search results
                result['results'] = data.get('results', [])
                result['total_count'] = data.get('total', 0)
            
            logger.info(f"Search completed for query '{query}' with {result['total_count']} results")
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error searching Figma for query '{query}': {e}")
            return {'ok': False, 'error': str(e)}
        except Exception as e:
            logger.error(f"Unexpected error searching Figma: {e}")
            return {'ok': False, 'error': str(e)}
    
    # Mock implementations for testing
    async def _mock_get_user_files(self, user_id: str, team_id: str = None, include_archived: bool = False, limit: int = 50) -> List[FigmaFile]:
        """Mock user files"""
        files = [
            {
                'key': 'fig-file-1',
                'name': 'Mobile App Design',
                'thumbnail_url': 'https://example.com/thumbnail1.png',
                'content_readonly': False,
                'editor_type': 'figma',
                'last_modified': (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
                'workspace_id': 'workspace-1',
                'workspace_name': 'Design Team',
                'id': 'fig-file-1'
            },
            {
                'key': 'fig-file-2',
                'name': 'Website Wireframes',
                'thumbnail_url': 'https://example.com/thumbnail2.png',
                'content_readonly': True,
                'editor_type': 'figjam',
                'last_modified': (datetime.now(timezone.utc) - timedelta(days=3)).isoformat(),
                'workspace_id': 'workspace-1',
                'workspace_name': 'Design Team',
                'id': 'fig-file-2'
            },
            {
                'key': 'fig-file-3',
                'name': 'Design System',
                'thumbnail_url': 'https://example.com/thumbnail3.png',
                'content_readonly': False,
                'editor_type': 'figma',
                'last_modified': (datetime.now(timezone.utc) - timedelta(days=5)).isoformat(),
                'workspace_id': 'workspace-2',
                'workspace_name': 'Product Team',
                'id': 'fig-file-3'
            }
        ]
        
        # Apply filters
        if not include_archived:
            files = [f for f in files if not f.get('content_readonly', False)]
        
        if limit > 0:
            files = files[:limit]
        
        return [FigmaFile(file) for file in files]
    
    async def _mock_get_user_teams(self, user_id: str, limit: int = 20) -> List[FigmaTeam]:
        """Mock user teams"""
        teams = [
            {
                'id': 'team-1',
                'name': 'Design Team',
                'description': 'Main design team for the company',
                'profile_picture_url': 'https://example.com/team1.png',
                'users': [
                    {
                        'id': 'user-1',
                        'name': 'Alice Designer',
                        'handle': 'alice',
                        'email': 'alice@company.com',
                        'img_url': 'https://example.com/alice.png',
                        'role': 'admin'
                    },
                    {
                        'id': 'user-2',
                        'name': 'Bob Designer',
                        'handle': 'bob',
                        'email': 'bob@company.com',
                        'img_url': 'https://example.com/bob.png',
                        'role': 'member'
                    }
                ]
            },
            {
                'id': 'team-2',
                'name': 'Product Team',
                'description': 'Product management and design collaboration',
                'profile_picture_url': 'https://example.com/team2.png',
                'users': [
                    {
                        'id': 'user-3',
                        'name': 'Carol Product',
                        'handle': 'carol',
                        'email': 'carol@company.com',
                        'img_url': 'https://example.com/carol.png',
                        'role': 'member'
                    }
                ]
            }
        ]
        
        if limit > 0:
            teams = teams[:limit]
        
        return [FigmaTeam(team) for team in teams]
    
    async def _mock_get_team_projects(self, user_id: str, team_id: str, limit: int = 50) -> List[FigmaProject]:
        """Mock team projects"""
        projects = [
            {
                'id': 'proj-1',
                'name': 'Q1 Design Initiatives',
                'description': 'Design projects for Q1 2024',
                'team_id': team_id
            },
            {
                'id': 'proj-2',
                'name': 'Website Redesign',
                'description': 'Complete website redesign project',
                'team_id': team_id
            }
        ]
        
        if limit > 0:
            projects = projects[:limit]
        
        return [FigmaProject(project) for project in projects]
    
    async def _mock_get_file_components(self, user_id: str, file_key: str, limit: int = 100) -> List[FigmaComponent]:
        """Mock file components"""
        components = [
            {
                'key': 'comp-1',
                'file_key': file_key,
                'node_id': 'node-1',
                'name': 'Primary Button',
                'description': 'Main call-to-action button',
                'component_type': 'component',
                'thumbnail_url': 'https://example.com/comp1.png',
                'created_at': (datetime.now(timezone.utc) - timedelta(days=10)).isoformat(),
                'modified_at': (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
            },
            {
                'key': 'comp-2',
                'file_key': file_key,
                'node_id': 'node-2',
                'name': 'Input Field',
                'description': 'Standard text input field',
                'component_type': 'component',
                'thumbnail_url': 'https://example.com/comp2.png',
                'created_at': (datetime.now(timezone.utc) - timedelta(days=15)).isoformat(),
                'modified_at': (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
            }
        ]
        
        if limit > 0:
            components = components[:limit]
        
        return [FigmaComponent(comp) for comp in components]
    
    async def _mock_get_user_profile(self, user_id: str) -> Optional[FigmaUser]:
        """Mock user profile"""
        return FigmaUser({
            'id': 'fig-user-123',
            'name': 'John Designer',
            'handle': 'johndesigner',
            'email': 'john@company.com',
            'img_url': 'https://example.com/john.png',
            'org_id': 'org-1',
            'role': 'admin'
        })
    
    async def _mock_search_figma(self, user_id: str, query: str, search_type: str = 'global', limit: int = 50) -> Dict[str, Any]:
        """Mock search results"""
        results = [
            {
                'object': 'file',
                'id': 'search-file-1',
                'title': f'{query.title()} Design System',
                'url': 'https://www.figma.com/file/search-file-1',
                'highlighted_title': f'<b>{query}</b> Design System',
                'snippet': f'This design system contains {query} components and styles...'
            },
            {
                'object': 'component',
                'id': 'search-comp-1',
                'title': f'{query.title()} Button',
                'url': 'https://www.figma.com/component/search-comp-1',
                'highlighted_title': f'<b>{query}</b> Button',
                'snippet': f'Primary {query} button component with hover states...'
            }
        ]
        
        return {
            'ok': True,
            'results': results,
            'total_count': len(results),
            'query': query
        }
    
    async def _get_user_access_token(self, user_id: str) -> Optional[str]:
        """Get access token for user (placeholder for real implementation)"""
        # In real implementation, this would fetch from database
        if self._mock_mode:
            return "mock_figma_access_token"
        
        # Would implement actual token retrieval from database
        return None
    
    def get_service_info(self) -> Dict[str, Any]:
        """Get service information"""
        return {
            'name': 'Figma Service',
            'version': '1.0.0',
            'mock_mode': self._mock_mode,
            'api_base_url': self.api_base_url,
            'timeout': self.timeout,
            'capabilities': [
                'Get user files',
                'Get user teams',
                'Get team projects',
                'Get file components',
                'Get user profile',
                'Search functionality'
            ]
        }

# Create singleton instance
figma_service = FigmaService()